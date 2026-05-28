"""
Tests para airflow/dags/ingest_cvm_informe_diario.py

Cobre:
- DAG estruturalmente valida (sem ciclos, todas tasks presentes)
- Resolver periodo retorna YYYYMM correto
- Validacao de schema falha se coluna obrigatoria faltar
- Fluxo end-to-end com ZIP mockado

Rodar:
    pytest tests/dags/test_ingest_cvm_informe_diario.py -v
"""
from __future__ import annotations

import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Adiciona airflow/dags ao path pra importar a DAG diretamente
DAGS_PATH = Path(__file__).resolve().parents[2] / "airflow" / "dags"
sys.path.insert(0, str(DAGS_PATH))


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

CVM_COLUMNS_OK = [
    "TP_FUNDO",
    "CNPJ_FUNDO",
    "DT_COMPTC",
    "VL_TOTAL",
    "VL_QUOTA",
    "VL_PATRIM_LIQ",
    "CAPTC_DIA",
    "RESG_DIA",
    "NR_COTST",
]


@pytest.fixture
def csv_cvm_valido() -> bytes:
    """CSV no formato CVM, valido."""
    df = pd.DataFrame(
        {
            "TP_FUNDO": ["FI", "FI", "FI"],
            "CNPJ_FUNDO": ["00.000.001/0001-01", "00.000.002/0001-02", "00.000.003/0001-03"],
            "DT_COMPTC": ["2026-04-01", "2026-04-01", "2026-04-02"],
            "VL_TOTAL": [1000.50, 2000.75, 3000.00],
            "VL_QUOTA": [1.1, 1.2, 1.3],
            "VL_PATRIM_LIQ": [950.0, 1900.0, 2900.0],
            "CAPTC_DIA": [10.0, 20.0, 30.0],
            "RESG_DIA": [5.0, 15.0, 25.0],
            "NR_COTST": [100, 200, 300],
        }
    )
    return df.to_csv(sep=";", index=False, encoding="latin-1").encode("latin-1")


@pytest.fixture
def zip_cvm_valido(csv_cvm_valido: bytes) -> bytes:
    """ZIP contendo CSV CVM valido."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inf_diario_fi_202604.csv", csv_cvm_valido)
    return buffer.getvalue()


@pytest.fixture
def zip_cvm_schema_quebrado() -> bytes:
    """ZIP com CSV faltando colunas obrigatorias (simula mudanca de schema CVM)."""
    df = pd.DataFrame({"CNPJ_FUNDO": ["01"], "DT_COMPTC": ["2026-04-01"]})
    csv = df.to_csv(sep=";", index=False, encoding="latin-1").encode("latin-1")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inf_diario_fi_202604.csv", csv)
    return buffer.getvalue()


# ----------------------------------------------------------------------
# Tests: estrutura da DAG
# ----------------------------------------------------------------------


def test_dag_carrega_sem_erros():
    """DAG importa sem ImportError, SyntaxError ou dependencia faltante."""
    import ingest_cvm_informe_diario  # noqa: F401


def test_dag_tem_id_correto():
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder=str(DAGS_PATH), include_examples=False)
    assert "ingest_cvm_informe_diario" in dagbag.dags
    assert dagbag.import_errors == {}


def test_dag_sem_ciclos():
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder=str(DAGS_PATH), include_examples=False)
    dag = dagbag.dags["ingest_cvm_informe_diario"]
    # test_cycle levanta excecao se houver ciclo
    dag.test_cycle()


def test_dag_tem_tasks_esperadas():
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder=str(DAGS_PATH), include_examples=False)
    dag = dagbag.dags["ingest_cvm_informe_diario"]
    task_ids = {t.task_id for t in dag.tasks}
    assert task_ids == {
        "resolver_periodo",
        "baixar_zip",
        "extrair_e_validar",
        "salvar_particionado",
    }


def test_dag_tem_retries_configurados():
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder=str(DAGS_PATH), include_examples=False)
    dag = dagbag.dags["ingest_cvm_informe_diario"]
    for task in dag.tasks:
        assert task.retries >= 1, f"Task {task.task_id} sem retries"


# ----------------------------------------------------------------------
# Tests: logica das tasks (chamadas como funcao Python)
# ----------------------------------------------------------------------


def test_resolver_periodo_retorna_mes_anterior():
    """logical_date 2026-05-15 deve resolver para 202604."""
    import ingest_cvm_informe_diario as dag_module

    dag = dag_module.ingest_cvm_informe_diario.__wrapped__()  # decoded @dag
    resolver = next(t for t in dag.tasks if t.task_id == "resolver_periodo")
    # Chama a python_callable direto com logical_date mockada
    result = resolver.python_callable(logical_date=datetime(2026, 5, 15))
    assert result == "202604"


def test_resolver_periodo_virada_de_ano():
    """logical_date 2026-01-10 deve resolver para 202512."""
    import ingest_cvm_informe_diario as dag_module

    dag = dag_module.ingest_cvm_informe_diario.__wrapped__()
    resolver = next(t for t in dag.tasks if t.task_id == "resolver_periodo")
    result = resolver.python_callable(logical_date=datetime(2026, 1, 10))
    assert result == "202512"


def test_extrair_e_validar_zip_valido(tmp_path, monkeypatch, zip_cvm_valido):
    """ZIP valido deve passar validacao e gerar parquet temporario."""
    import ingest_cvm_informe_diario as dag_module

    # Redireciona /tmp pra pasta temporaria do pytest
    monkeypatch.setattr(
        "ingest_cvm_informe_diario.Path",
        lambda p: tmp_path / Path(p).name if p == "/tmp" else Path(p),
    )

    dag = dag_module.ingest_cvm_informe_diario.__wrapped__()
    extrair = next(t for t in dag.tasks if t.task_id == "extrair_e_validar")
    # Chama python_callable
    result = extrair.python_callable(zip_bytes=zip_cvm_valido, yyyymm="202604")

    assert result["yyyymm"] == "202604"
    assert result["linhas"] == 3
    assert result["fundos_unicos"] == 3
    assert result["tamanho_bytes"] > 0


def test_extrair_e_validar_falha_se_schema_quebra(zip_cvm_schema_quebrado):
    """Se CVM mudar schema (remover coluna), DAG falha com erro claro."""
    import ingest_cvm_informe_diario as dag_module

    dag = dag_module.ingest_cvm_informe_diario.__wrapped__()
    extrair = next(t for t in dag.tasks if t.task_id == "extrair_e_validar")
    with pytest.raises(ValueError, match="Schema CVM mudou"):
        extrair.python_callable(
            zip_bytes=zip_cvm_schema_quebrado, yyyymm="202604"
        )
