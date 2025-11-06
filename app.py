import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# -----------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------
SPREADSHEET_ID = "COLOQUE_AQUI_O_ID_DA_SUA_PLANILHA"
SHEET_NAME = "Planilha1"

st.set_page_config(page_title="Controle de Concreto", layout="wide")

# -----------------------------------------------------------
# FUNÇÕES DE CONEXÃO
# -----------------------------------------------------------
def get_gcp_credentials():
    return Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

@st.cache_data
def carregar_planilha_completa():
    """Carrega toda a planilha de uma vez, evitando várias chamadas à API."""
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    dados = sheet.get_all_records()
    df = pd.DataFrame(dados)
    return df, sheet

# -----------------------------------------------------------
# FUNÇÃO DE SALVAR DADOS
# -----------------------------------------------------------
def salvar_dados(sheet, df, data, dados_torres):
    data_formatada = pd.to_datetime(data).date()
    linha_index = df.index[df['Data'] == data_formatada].tolist()

    if not linha_index:
        st.warning("⚠️ Data não encontrada na planilha.")
        return

    linha_planilha = linha_index[0] + 2  # +2 por causa do cabeçalho

    try:
        # Verifica se a linha já possui algum dado além da data
        linha_valores = sheet.row_values(linha_planilha)
        if len(linha_valores) > 1 and any(c.strip() for c in linha_valores[1:]):
            st.error("❌ Erro ao preencher: o dia selecionado já possui registros.")
            return
    except Exception as e:
        st.error(f"Erro ao verificar linha: {e}")
        return

    # Monta lista de atualizações
    col_offset = 1
    updates = []
    for torre, valores in dados_torres.items():
        mpa_col = col_offset + 1
        tracos_col = col_offset + 2
        pav_col = col_offset + 3
        tipo_col = col_offset + 4

        updates.append({'range': sheet.cell(linha_planilha, mpa_col).address, 'values': [[valores.get('Mpa', '')]]})
        updates.append({'range': sheet.cell(linha_planilha, tracos_col).address, 'values': [[valores.get('Traços', '')]]})
        updates.append({'range': sheet.cell(linha_planilha, pav_col).address, 'values': [[valores.get('Pavimento', '')]]})
        updates.append({'range': sheet.cell(linha_planilha, tipo_col).address, 'values': [[valores.get('Tipo', 'A Granel')]]})

        col_offset += 4

    try:
        sheet.batch_update(updates)
        st.success("✅ Dados salvos com sucesso!")
        carregar_planilha_completa.clear()
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")

# -----------------------------------------------------------
# INTERFACE STREAMLIT
# -----------------------------------------------------------
st.title("📊 Controle de Concreto - Mooca")

df, sheet = carregar_planilha_completa()

if df.empty:
    st.error("A planilha está vazia ou inacessível.")
    st.stop()

# Seleciona data
data_hoje = datetime.now().date()
data = st.date_input("📅 Escolha a Data do Registro:", value=data_hoje)

# Torres
torres = ["Torre 1", "Torre 2", "Torre 3", "Torre 4", "Torre 5", "Torre 6", "Torre 7", "Torre 8", "Torre 9"]

# Busca padrões de uma vez só (a partir do DataFrame já carregado)
padrao_mpa = {}
padrao_pav = {}
for torre in torres:
    colunas = [col for col in df.columns if torre in col]
    if len(colunas) >= 3:
        mpa_col = colunas[0]
        pav_col = colunas[2]

        padrao_mpa[torre] = next((v for v in reversed(df[mpa_col].tolist()) if str(v).strip()), "")
        padrao_pav[torre] = next((v for v in reversed(df[pav_col].tolist()) if str(v).strip()), "")
    else:
        padrao_mpa[torre] = ""
        padrao_pav[torre] = ""

# Formulário
dados_torres = {}
progresso = 0
sem_consumo = {}

for torre in torres:
    with st.expander(f"🏗️ {torre}", expanded=False):
        mpa = st.text_input(f"MPA ({torre})", value=padrao_mpa.get(torre, ""), key=f"mpa_{torre}")
        tracos = st.text_input(f"Traços ({torre})", key=f"tracos_{torre}")
        pav = st.text_input(f"Pavimento ({torre})", value=padrao_pav.get(torre, ""), key=f"pav_{torre}")
        tipo = st.selectbox(f"Tipo ({torre})", ["A Granel", "Usinado"], key=f"tipo_{torre}")
        sem_consumo[torre] = st.checkbox("Sem consumo", key=f"sem_{torre}")

        if sem_consumo[torre] or (mpa and tracos and pav):
            progresso += 1

        dados_torres[torre] = {"Mpa": mpa, "Traços": tracos, "Pavimento": pav, "Tipo": tipo}

# Barra de progresso
st.progress(progresso / len(torres))

# Botões
col1, col2 = st.columns(2)
with col1:
    if st.button("💾 Salvar Dados"):
        salvar_dados(sheet, df, data, dados_torres)
with col2:
    if st.button("🔄 Atualizar Página (Novo Registro)"):
        st.experimental_rerun()
