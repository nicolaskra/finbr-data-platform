"""
DAG: ingest_cvm_informe_diario_spark

Versao PySpark da DAG ingest_cvm_informe_diario (paralela / didatica).

Por que duas versoes (pandas + Spark)?
-------------------------------------
Sinal senior: escolher tool pelo tamanho do dataset, nao por dogma.

| Dataset                     | Ferramenta correta                |
|-----------------------------|-----------------------------------|
| < 1 GB (CVM mensal: 14 MB)  | pandas + pyarrow (eficiente)     |
| 1 GB - 100 GB               | DuckDB / Polars / pandas chunked |
| > 100 GB / distribuido      | Spark / PySpark / Dask           |

O CVM hoje cabe em pandas — Spark seria overkill (cold start + JVM > 30s
para processar 14 MB). Mas a logica esta aqui pra:
  1. Demonstrar fluencia PySpark
  2. Servir de base para futuras fontes maiores (B3 cotacoes diarias historicas, etc.)
  3. Documentar a decisao de NAO usar Spark hoje no `docs/decisions/005-pandas-vs-pyspark.md`

Schema, particionamento e idempotencia identicos a versao pandas.
"""
from __future__ import annotations

import io
import logging
import shutil
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from airflow.decorators import dag, task

LOGGER = logging.getLogger(__name__)

CVM_BASE_URL = (
    "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/"
    "inf_diario_fi_{yyyymm}.zip"
)

RAW_BASE = Path("/opt/airflow/data/raw/cvm/inf_diario")

EXPECTED_COLUMNS = {
    "TP_FUNDO_CLASSE",
    "CNPJ_FUNDO_CLASSE",
    "ID_SUBCLASSE",
    "DT_COMPTC",
    "VL_TOTAL",
    "VL_QUOTA",
    "VL_PATRIM_LIQ",
    "CAPTC_DIA",
    "RESG_DIA",
    "NR_COTST",
}


@dag(
    dag_id="ingest_cvm_informe_diario_spark",
    description="(PySpark) Ingere Informe Diario CVM — versao distribuida didatica",
    schedule=None,  # Manual apenas — pandas eh a versao oficial pra esse dataset
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "nicolas",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["cvm", "ingest", "raw", "pyspark", "didatico"],
    doc_md=__doc__,
)
def ingest_cvm_informe_diario_spark():
    @task
    def resolver_periodo(logical_date: datetime | None = None) -> str:
        ref = logical_date or datetime.now(UTC)
        primeiro_dia_mes_atual = ref.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        yyyymm = ultimo_dia_mes_anterior.strftime("%Y%m")
        LOGGER.info("Periodo resolvido: %s (referencia=%s)", yyyymm, ref.date())
        return yyyymm

    @task
    def baixar_zip(yyyymm: str) -> str:
        """Baixa ZIP CVM e salva em /tmp (PySpark le do path, nao do byte stream)."""
        url = CVM_BASE_URL.format(yyyymm=yyyymm)
        LOGGER.info("Baixando %s", url)
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()

        # Extrai CSV do ZIP para path acessivel pelo Spark
        tmp_csv = Path("/tmp") / f"inf_diario_fi_{yyyymm}.csv"
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            nome_csv = next(n for n in zf.namelist() if n.endswith(".csv"))
            with zf.open(nome_csv) as src, open(tmp_csv, "wb") as dst:
                shutil.copyfileobj(src, dst)

        size_mb = tmp_csv.stat().st_size / (1024 * 1024)
        LOGGER.info("CSV extraido: %s (%.2f MB)", tmp_csv, size_mb)
        return str(tmp_csv)

    @task
    def processar_com_spark(csv_path: str, yyyymm: str) -> dict:
        """Processa CSV com PySpark: validacao schema + cast + escreve parquet particionado."""
        # Import dentro da task pra nao quebrar parse da DAG se PySpark nao instalado
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
        from pyspark.sql.types import (
            DoubleType,
            IntegerType,
            StringType,
            StructField,
            StructType,
        )

        # Schema explicito (fail-fast se CVM mudar)
        schema = StructType(
            [
                StructField("TP_FUNDO_CLASSE", StringType(), True),
                StructField("CNPJ_FUNDO_CLASSE", StringType(), True),
                StructField("ID_SUBCLASSE", StringType(), True),
                StructField("DT_COMPTC", StringType(), True),  # cast pra date depois
                StructField("VL_TOTAL", DoubleType(), True),
                StructField("VL_QUOTA", DoubleType(), True),
                StructField("VL_PATRIM_LIQ", DoubleType(), True),
                StructField("CAPTC_DIA", DoubleType(), True),
                StructField("RESG_DIA", DoubleType(), True),
                StructField("NR_COTST", IntegerType(), True),
            ]
        )

        spark = (
            SparkSession.builder.appName(f"finbr-ingest-cvm-{yyyymm}")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.default.parallelism", "4")
            .getOrCreate()
        )

        try:
            # Le CSV com schema explicito (sem inference — fail-fast)
            df = (
                spark.read.option("delimiter", ";")
                .option("header", "true")
                .option("encoding", "ISO-8859-1")  # Spark nao reconhece 'latin-1' (alias)
                .schema(schema)
                .csv(csv_path)
            )

            # Validacao de schema: se mudou, lanca erro
            cols_lidas = set(df.columns)
            faltantes = EXPECTED_COLUMNS - cols_lidas
            if faltantes:
                raise ValueError(
                    f"Schema CVM mudou — colunas faltantes em {yyyymm}: {faltantes}"
                )

            # Cast DT_COMPTC pra date
            df = df.withColumn("DT_COMPTC", F.to_date("DT_COMPTC"))

            # Stats antes de escrever
            linhas = df.count()
            fundos_unicos = df.select("CNPJ_FUNDO_CLASSE").distinct().count()

            # Escreve parquet (coalesce(1) pra 1 arquivo so — dataset pequeno)
            particao = f"{yyyymm[:4]}-{yyyymm[4:]}"
            destino_dir = RAW_BASE / particao
            destino_dir.mkdir(parents=True, exist_ok=True)

            # Spark escreve em diretorio; renomeamos pro mesmo schema da versao pandas
            spark_out = destino_dir / "_spark_tmp"
            df.coalesce(1).write.mode("overwrite").parquet(str(spark_out))

            # Move o unico .parquet pra inf_diario.parquet (compat com versao pandas)
            parquet_file = next(spark_out.glob("part-*.parquet"))
            destino = destino_dir / "inf_diario.parquet"
            shutil.move(str(parquet_file), str(destino))
            shutil.rmtree(spark_out)

            tamanho_bytes = destino.stat().st_size
            LOGGER.info(
                "PySpark persistiu: %s (%d linhas, %d fundos, %.2f MB)",
                destino,
                linhas,
                fundos_unicos,
                tamanho_bytes / (1024 * 1024),
            )

            return {
                "yyyymm": yyyymm,
                "particao": particao,
                "destino": str(destino),
                "linhas": linhas,
                "fundos_unicos": fundos_unicos,
                "tamanho_bytes": tamanho_bytes,
                "engine": "pyspark",
            }
        finally:
            spark.stop()
            # Limpa CSV tmp
            Path(csv_path).unlink(missing_ok=True)

    # Pipeline
    yyyymm = resolver_periodo()
    csv_path = baixar_zip(yyyymm)
    processar_com_spark(csv_path, yyyymm)


ingest_cvm_informe_diario_spark()
