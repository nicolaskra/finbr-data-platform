"""
DAG: dbt_transform

Orquestra a camada de transformacao (dbt run + dbt test) sobre o warehouse
DuckDB local apos a ingestao do CVM.

Pipeline:
    ingest_cvm_informe_diario  -->  (dado raw em Parquet)
                                          |
                                          v
    dbt_transform              -->  dbt run + dbt test
                                          |
                                          v
                                  warehouse populado (DuckDB)
                                  staging / intermediate / marts
                                  + analytics: top_fundos_rentabilidade_mes
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag
from airflow.operators.bash import BashOperator

DBT_DIR = "/opt/airflow/dbt"
DBT_BASE_CMD = f"cd {DBT_DIR} && dbt"
DBT_PROFILES = "--profiles-dir ."


@dag(
    dag_id="dbt_transform",
    description="Roda dbt run + dbt test sobre o warehouse DuckDB apos ingestao CVM",
    schedule="0 7 5 * *",  # 1h apos ingest_cvm_informe_diario (06:00 dia 5)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "nicolas",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["dbt", "transform", "duckdb"],
    doc_md=__doc__,
)
def dbt_transform():
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT_BASE_CMD} deps {DBT_PROFILES}",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"{DBT_BASE_CMD} run {DBT_PROFILES}",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT_BASE_CMD} test {DBT_PROFILES}",
    )

    dbt_deps >> dbt_run >> dbt_test


dbt_transform()
