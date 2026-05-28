"""
DAG: ingest_cvm_informe_diario

Baixa o Informe Diário de Fundos de Investimento (CVM) do mês anterior,
valida schema, salva como Parquet particionado.

Fonte: https://dados.cvm.gov.br/dataset/fi-doc-inf_diario
Schema (CVM):
    CNPJ_FUNDO, DT_COMPTC, VL_TOTAL, VL_QUOTA, VL_PATRIM_LIQ,
    CAPTC_DIA, RESG_DIA, NR_COTST

Particionamento: data/raw/cvm/inf_diario/YYYY-MM/inf_diario.parquet
"""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from airflow.decorators import dag, task

LOGGER = logging.getLogger(__name__)

CVM_BASE_URL = (
    "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/"
    "inf_diario_fi_{yyyymm}.zip"
)

# Caminho dentro do container Airflow (montado via docker-compose)
RAW_BASE = Path("/opt/airflow/data/raw/cvm/inf_diario")

EXPECTED_COLUMNS = {
    "TP_FUNDO",
    "CNPJ_FUNDO",
    "DT_COMPTC",
    "VL_TOTAL",
    "VL_QUOTA",
    "VL_PATRIM_LIQ",
    "CAPTC_DIA",
    "RESG_DIA",
    "NR_COTST",
}


@dag(
    dag_id="ingest_cvm_informe_diario",
    description="Ingere Informe Diario de Fundos CVM (Parquet particionado por YYYY-MM)",
    schedule="0 6 5 * *",  # dia 5 de cada mes as 06:00 (CVM publica entre dia 1-4)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "nicolas",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["cvm", "ingest", "raw"],
    doc_md=__doc__,
)
def ingest_cvm_informe_diario():
    @task
    def resolver_periodo(logical_date: datetime | None = None) -> str:
        """
        Retorna YYYYMM do mes anterior ao logical_date.
        CVM publica o informe de mes M no inicio do mes M+1.
        """
        ref = logical_date or datetime.now(UTC)
        primeiro_dia_mes_atual = ref.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        yyyymm = ultimo_dia_mes_anterior.strftime("%Y%m")
        LOGGER.info("Periodo resolvido: %s (referencia=%s)", yyyymm, ref.date())
        return yyyymm

    @task
    def baixar_zip(yyyymm: str) -> bytes:
        """Download do ZIP CVM. Levanta excecao em 404 ou >5xx (Airflow re-tenta)."""
        url = CVM_BASE_URL.format(yyyymm=yyyymm)
        LOGGER.info("Baixando %s", url)
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        size_mb = len(resp.content) / (1024 * 1024)
        LOGGER.info("Download OK: %.2f MB", size_mb)
        return resp.content

    @task
    def extrair_e_validar(zip_bytes: bytes, yyyymm: str) -> dict:
        """Extrai CSV do ZIP, valida schema, retorna metadata."""
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            nomes = [n for n in zf.namelist() if n.endswith(".csv")]
            if not nomes:
                raise ValueError(f"Nenhum CSV encontrado no ZIP {yyyymm}")
            nome_csv = nomes[0]
            LOGGER.info("CSV extraido: %s", nome_csv)
            with zf.open(nome_csv) as f:
                df = pd.read_csv(
                    f,
                    sep=";",
                    encoding="latin-1",
                    dtype={"CNPJ_FUNDO": str},
                )

        # Validacao de schema (raise se faltar coluna obrigatoria)
        cols_faltantes = EXPECTED_COLUMNS - set(df.columns)
        if cols_faltantes:
            raise ValueError(
                f"Schema CVM mudou — colunas faltantes em {yyyymm}: {cols_faltantes}"
            )

        # Type coercion seguro
        df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"], errors="coerce")
        for col in ["VL_TOTAL", "VL_QUOTA", "VL_PATRIM_LIQ", "CAPTC_DIA", "RESG_DIA"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Materializa em /tmp pra proxima task ler (Airflow XCom limita tamanho)
        tmp_path = Path("/tmp") / f"cvm_{yyyymm}.parquet"
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, tmp_path, compression="snappy")

        return {
            "yyyymm": yyyymm,
            "linhas": len(df),
            "fundos_unicos": df["CNPJ_FUNDO"].nunique(),
            "tmp_path": str(tmp_path),
            "tamanho_bytes": tmp_path.stat().st_size,
        }

    @task
    def salvar_particionado(metadata: dict) -> dict:
        """Move parquet temporario pra particao YYYY-MM no data lake."""
        yyyymm = metadata["yyyymm"]
        # Particao com hifen pra ficar legivel (2026-04 ao inves de 202604)
        particao = f"{yyyymm[:4]}-{yyyymm[4:]}"
        destino_dir = RAW_BASE / particao
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / "inf_diario.parquet"

        # Idempotencia: sobrescreve (download determinístico, mesmo periodo = mesmo dado)
        Path(metadata["tmp_path"]).rename(destino)

        LOGGER.info(
            "Persistido: %s (%d linhas, %d fundos, %.2f MB)",
            destino,
            metadata["linhas"],
            metadata["fundos_unicos"],
            metadata["tamanho_bytes"] / (1024 * 1024),
        )

        return {
            **metadata,
            "destino": str(destino),
            "particao": particao,
        }

    # Pipeline
    yyyymm = resolver_periodo()
    zip_bytes = baixar_zip(yyyymm)
    metadata = extrair_e_validar(zip_bytes, yyyymm)
    salvar_particionado(metadata)


ingest_cvm_informe_diario()
