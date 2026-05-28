"""
Tests para airflow/dags/ingest_cvm_informe_diario.py

Cobre:
- DAG estruturalmente valida (carrega sem ImportError, sem ciclos)
- Resolver periodo retorna YYYYMM correto
- Validacao de schema falha se coluna obrigatoria faltar
- Extracao + parquet OK para ZIP valido

Rodar:
    pytest tests/dags/test_ingest_cvm_informe_diario.py -v
"""

from __future__ import annotations

import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

DAGS_PATH = Path(__file__).resolve().parents[2] / "airflow" / "dags"
# Permite `import ingest_cvm_informe_diario` nos tests (DAGs nao sao package Python)
sys.path.insert(0, str(DAGS_PATH))


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def dagbag():
    """Carrega DagBag uma vez por modulo (caro)."""
    from airflow.models import DagBag

    return DagBag(dag_folder=str(DAGS_PATH), include_examples=False)


@pytest.fixture(scope="module")
def dag(dagbag):
    """Retorna a DAG sob teste."""
    return dagbag.dags["ingest_cvm_informe_diario"]


@pytest.fixture
def csv_cvm_valido() -> bytes:
    """CSV no formato CVM (pos-Resolucao 175/2024 - Classes/Subclasses)."""
    df = pd.DataFrame(
        {
            "TP_FUNDO_CLASSE": ["CLASSES - FIF", "CLASSES - FIF", "CLASSES - FIF"],
            "CNPJ_FUNDO_CLASSE": [
                "00.000.001/0001-01",
                "00.000.002/0001-02",
                "00.000.003/0001-03",
            ],
            "ID_SUBCLASSE": ["", "", ""],
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
    """ZIP com CSV faltando colunas obrigatorias (simula mudanca CVM)."""
    df = pd.DataFrame({"CNPJ_FUNDO_CLASSE": ["01"], "DT_COMPTC": ["2026-04-01"]})
    csv = df.to_csv(sep=";", index=False, encoding="latin-1").encode("latin-1")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inf_diario_fi_202604.csv", csv)
    return buffer.getvalue()


# ----------------------------------------------------------------------
# Tests: estrutura da DAG
# ----------------------------------------------------------------------


def test_dagbag_sem_import_errors(dagbag):
    """DagBag carrega tudo sem ImportError, SyntaxError, ou ciclos."""
    assert dagbag.import_errors == {}, f"Import errors na DagBag: {dagbag.import_errors}"


def test_dag_existe(dag):
    """DAG `ingest_cvm_informe_diario` existe no DagBag."""
    assert dag is not None
    assert dag.dag_id == "ingest_cvm_informe_diario"


def test_dag_tem_tasks_esperadas(dag):
    """As 4 tasks do pipeline existem."""
    task_ids = {t.task_id for t in dag.tasks}
    assert task_ids == {
        "resolver_periodo",
        "baixar_zip",
        "extrair_e_validar",
        "salvar_particionado",
    }


def test_dag_tem_retries_configurados(dag):
    """Toda task tem retries para resiliencia HTTP."""
    for task in dag.tasks:
        assert task.retries >= 1, f"Task {task.task_id} sem retries"


def test_dag_topologia_correta(dag):
    """Pipeline e linear: resolver -> baixar -> extrair -> salvar."""
    expected_downstream = {
        "resolver_periodo": {"baixar_zip", "extrair_e_validar"},
        "baixar_zip": {"extrair_e_validar"},
        "extrair_e_validar": {"salvar_particionado"},
        "salvar_particionado": set(),
    }
    for task in dag.tasks:
        downstream_ids = {t.task_id for t in task.downstream_list}
        assert downstream_ids == expected_downstream[task.task_id], (
            f"Topologia incorreta em {task.task_id}: "
            f"esperado {expected_downstream[task.task_id]}, obtido {downstream_ids}"
        )


# ----------------------------------------------------------------------
# Tests: logica das tasks via python_callable
# ----------------------------------------------------------------------


def test_resolver_periodo_retorna_mes_anterior(dag):
    """logical_date 2026-05-15 deve resolver para 202604."""
    task = dag.get_task("resolver_periodo")
    result = task.python_callable(logical_date=datetime(2026, 5, 15))
    assert result == "202604"


def test_resolver_periodo_virada_de_ano(dag):
    """logical_date 2026-01-10 deve resolver para 202512."""
    task = dag.get_task("resolver_periodo")
    result = task.python_callable(logical_date=datetime(2026, 1, 10))
    assert result == "202512"


def test_resolver_periodo_sem_logical_date(dag):
    """Sem logical_date usa utcnow() — retorna mes anterior do mes atual."""
    task = dag.get_task("resolver_periodo")
    result = task.python_callable()
    assert len(result) == 6
    assert result.isdigit()
    # Mes resolvido deve ser <= mes atual
    from datetime import UTC

    now = datetime.now(UTC)
    yyyymm_atual = now.strftime("%Y%m")
    assert result <= yyyymm_atual


def test_extrair_e_validar_zip_valido(tmp_path, monkeypatch, dag, zip_cvm_valido):
    """ZIP valido passa validacao e gera parquet temporario."""
    import ingest_cvm_informe_diario as dag_module  # noqa: F401  (forca import)

    # Redireciona "/tmp" pra tmp_path do pytest (cross-platform)
    original_path = dag_module.Path

    class FakePath(type(Path())):
        def __new__(cls, *args, **kwargs):
            arg = args[0] if args else ""
            if arg == "/tmp":
                return original_path(tmp_path)
            return original_path(*args, **kwargs)

    monkeypatch.setattr(dag_module, "Path", FakePath)

    task = dag.get_task("extrair_e_validar")
    result = task.python_callable(zip_bytes=zip_cvm_valido, yyyymm="202604")

    assert result["yyyymm"] == "202604"
    assert result["linhas"] == 3
    assert result["fundos_unicos"] == 3
    assert result["tamanho_bytes"] > 0
    assert Path(result["tmp_path"]).exists()


def test_extrair_e_validar_falha_se_schema_quebra(dag, zip_cvm_schema_quebrado):
    """Se CVM mudar schema (remover coluna), DAG falha com erro claro."""
    task = dag.get_task("extrair_e_validar")
    with pytest.raises(ValueError, match="Schema CVM mudou"):
        task.python_callable(zip_bytes=zip_cvm_schema_quebrado, yyyymm="202604")
