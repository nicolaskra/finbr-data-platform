# Dockerfile customizado para Airflow com deps das DAGs pre-instaladas.
# Build: docker compose build
# Por que: imagem oficial usa venv interno onde `pip install --user` falha.
#         Pre-instalar via Dockerfile e mais rapido (sem custo de install no startup)
#         e segue best practice oficial Airflow.

FROM apache/airflow:2.10.3-python3.11

# Java necessario para PySpark (DAG ingest_cvm_informe_diario_spark)
# +200 MB na imagem mas garante que a versao Spark funciona localmente.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
USER airflow

COPY requirements.txt /requirements.txt

RUN pip install --no-cache-dir -r /requirements.txt
