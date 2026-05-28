# Deploy no Streamlit Community Cloud

Passo a passo para publicar o dashboard em https://share.streamlit.io (free tier).

## Pré-requisitos

- Repo público no GitHub: `nicolaskra/finbr-data-platform`
- Branch com:
  - `requirements.txt` na raiz (já criado)
  - `.streamlit/config.toml` (já criado)
  - `data/warehouse/finbr.duckdb` commitado (~19 MB)
  - `app/dashboard/streamlit_app.py` com suporte a `FINBR_MODE=duckdb`

## Passos

1. Login em https://share.streamlit.io com a conta GitHub.
2. Clicar em **"New app"**.
3. Preencher:
   - **Repository:** `nicolaskra/finbr-data-platform`
   - **Branch:** `main` (ou a branch desejada)
   - **Main file path:** `app/dashboard/streamlit_app.py`
   - **App URL (opcional):** `finbr-data-platform` → vira `https://finbr-data-platform.streamlit.app`
4. Em **"Advanced settings → Secrets"**, colar:
   ```toml
   FINBR_MODE = "duckdb"
   FINBR_DEFAULT_MES = "2026-04-01"
   ```
5. **Deploy.** Primeiro build ~3-5 min (instala `duckdb`, `pandas`, `pyarrow`).
6. **Tornar público (OBRIGATÓRIO para portfolio):**
   - Default do Streamlit Cloud é **Restricted** (exige login Streamlit). Recrutador sem conta bate em `share.streamlit.io/-/auth/app` e vai embora.
   - Em **Manage app → Settings → Sharing**, mudar visibility para **Public** ("Anyone with the link can view").
7. Validar:
   - Sidebar mostra "DuckDB OK" + counts (~25k classes, ~25k fct rows)
   - Top fundos retorna dados para `2026-04-01`
   - Série histórica retorna para CNPJ `00.017.024/0001-53`

URL atual do deploy: https://finbr-data-platform-fmwlw5fpfhdduskgn8zlrt.streamlit.app/

## Atualizar warehouse

Para refrescar dados: rodar o pipeline local, copiar `data/warehouse/finbr.duckdb` novo, commitar e push. Streamlit Cloud redeploya automaticamente.

## Reverter

Em **"Manage app → Settings → Delete"** remove o app sem afetar o repo.
