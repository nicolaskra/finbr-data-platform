# Dockerfile customizado para Airflow com deps das DAGs pre-instaladas.
# Build: docker compose build
# Por que: imagem oficial usa venv interno onde `pip install --user` falha.
#         Pre-instalar via Dockerfile e mais rapido (sem custo de install no startup)
#         e segue best practice oficial Airflow.

FROM apache/airflow:2.10.3-python3.11

COPY requirements.txt /requirements.txt

RUN pip install --no-cache-dir -r /requirements.txt
