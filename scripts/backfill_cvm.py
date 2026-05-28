"""
Backfill CVM informe diario para multiplos meses.

Replica a logica das tasks da DAG `ingest_cvm_informe_diario` mas roda
fora do Airflow, em loop, para popular `data/raw/cvm/inf_diario/YYYY-MM/`
com varios meses de historico de uma vez.

Uso:
    python scripts/backfill_cvm.py 2025-05 2026-04   # range inclusivo
    python scripts/backfill_cvm.py 2026-03           # mes unico

Apos rodar, executar `dbt build --target local --profiles-dir .` no
diretorio `dbt/` para reconstruir as marts em cima dos novos parquets.
"""

from __future__ import annotations

import io
import logging
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

LOGGER = logging.getLogger("backfill_cvm")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CVM_BASE_URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{yyyymm}.zip"
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_BASE = REPO_ROOT / "data" / "raw" / "cvm" / "inf_diario"

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


def _iter_months(start: str, end: str | None) -> list[str]:
    """Gera lista de YYYY-MM entre start e end (inclusivos)."""
    s = date.fromisoformat(f"{start}-01")
    e = date.fromisoformat(f"{end}-01") if end else s
    if e < s:
        raise ValueError(f"end ({end}) anterior ao start ({start})")
    out = []
    cur = s
    while cur <= e:
        out.append(cur.strftime("%Y-%m"))
        # avanca um mes
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return out


def ingerir_mes(yyyy_mm: str, skip_if_exists: bool = True) -> dict:
    """Baixa, valida e persiste o informe de UM mes. Idempotente."""
    yyyymm = yyyy_mm.replace("-", "")
    destino_dir = RAW_BASE / yyyy_mm
    destino = destino_dir / "inf_diario.parquet"

    if skip_if_exists and destino.exists():
        size_mb = destino.stat().st_size / (1024 * 1024)
        LOGGER.info("SKIP %s (ja existe, %.2f MB)", yyyy_mm, size_mb)
        return {"yyyy_mm": yyyy_mm, "skipped": True, "destino": str(destino)}

    url = CVM_BASE_URL.format(yyyymm=yyyymm)
    LOGGER.info("Baixando %s", url)
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    size_mb = len(resp.content) / (1024 * 1024)
    LOGGER.info("  Download OK: %.2f MB", size_mb)

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        nomes = [n for n in zf.namelist() if n.endswith(".csv")]
        if not nomes:
            raise ValueError(f"Nenhum CSV no ZIP {yyyy_mm}")
        with zf.open(nomes[0]) as f:
            df = pd.read_csv(
                f,
                sep=";",
                encoding="latin-1",
                dtype={"CNPJ_FUNDO_CLASSE": str, "ID_SUBCLASSE": str},
            )

    cols_faltantes = EXPECTED_COLUMNS - set(df.columns)
    if cols_faltantes:
        raise ValueError(f"Schema mudou em {yyyy_mm}: faltam {cols_faltantes}")

    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"], errors="coerce")
    for col in ["VL_TOTAL", "VL_QUOTA", "VL_PATRIM_LIQ", "CAPTC_DIA", "RESG_DIA"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    destino_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = destino_dir / "inf_diario.parquet.tmp"
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, tmp_path, compression="snappy")
    shutil.move(str(tmp_path), str(destino))

    LOGGER.info(
        "  Persistido %s: %d linhas, %d classes, %.2f MB",
        destino,
        len(df),
        df["CNPJ_FUNDO_CLASSE"].nunique(),
        destino.stat().st_size / (1024 * 1024),
    )

    return {
        "yyyy_mm": yyyy_mm,
        "linhas": len(df),
        "classes": int(df["CNPJ_FUNDO_CLASSE"].nunique()),
        "destino": str(destino),
        "skipped": False,
    }


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Uso: python scripts/backfill_cvm.py YYYY-MM [YYYY-MM]")
        return 1

    start = sys.argv[1]
    end = sys.argv[2] if len(sys.argv) == 3 else None
    meses = _iter_months(start, end)

    LOGGER.info("Backfill de %d meses: %s -> %s", len(meses), meses[0], meses[-1])
    total_linhas = 0
    falhas = []
    for m in meses:
        try:
            r = ingerir_mes(m)
            if not r["skipped"]:
                total_linhas += r["linhas"]
        except Exception as exc:
            LOGGER.error("FALHA em %s: %s", m, exc)
            falhas.append((m, str(exc)))

    LOGGER.info("---")
    LOGGER.info("Concluido: %d linhas novas em %d meses", total_linhas, len(meses))
    if falhas:
        LOGGER.warning("Falhas: %s", falhas)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
