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

def carregar_dados():
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    dados = sheet.get_all_records()
    return pd.DataFrame(dados)

# -----------------------------------------------------------
# FUNÇÃO SEGURA PARA BUSCAR VALOR PADRÃO
# -----------------------------------------------------------
def buscar_valor_acima(sheet, coluna, ultima_linha):
    """
    Busca o último valor não vazio acima em uma coluna, evitando múltiplas chamadas à API.
    """
    try:
        coluna_valores = sheet.col_values(coluna)
        for valor in reversed(coluna_valores):
            if str(valor).strip() != "":
                return valor
        return ""
    except Exception as e:
        st.warning(f"Erro ao buscar valor padrão: {e}")
        return ""

# -----------------------------------------------------------
# FUNÇÃO DE SALVAR DADOS
# -----------------------------------------------------------
def salvar_dados(data, dados_torres):
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    df = carregar_dados()

    data_formatada = pd.to_datetime(data).date()
    linha_index = df.index[df['Data'] == data_formatada].tolist()

    if not linha_index:
        st.warning("⚠️ Data não encontrada na planilha.")
        st.write("Primeiras datas encontradas:")
        st.dataframe(df['Data'].head(10))
        return

    linha_planilha = linha_index[0] + 2  # +2 por causa do cabeçalho

    try:
        linha_valores = sheet.row_values(linha_planilha)
        if len(linha_valores) > 1 and any(c.strip() for c in linha_valores[1:]):
            st.error("❌ Erro ao preencher: o dia selecionado já possui registros.")
            return
    except Exception as e:
        st.error(f"Erro ao verificar linha na planilha: {e}")
        return

    # Se chegou aqui, pode salvar normalmente
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
        carregar_dados.clear()
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")

# -----------------------------------------------------------
# INTERFACE STREAMLIT
# -----------------------------------------------------------
st.title("📊 Controle de Concreto - Mooca")

# Carrega planilha e cliente
creds = get_gcp_credentials()
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# Garante que a planilha tem dados
df = carregar_dados()
if df.empty:
    st.error("A planilha está vazia ou inacessível.")
    st.stop()

# -----------------------------------------------------------
# SELEÇÃO DE DATA
# -----------------------------------------------------------
data_hoje = datetime.now().date()
data = st.date_input("📅 Escolha a Data do Registro:", value=data_hoje)

# -----------------------------------------------------------
# FORMULÁRIO DAS TORRES
# -----------------------------------------------------------
torres = ["Torre 1", "Torre 2", "Torre 3", "Torre 4", "Torre 5", "Torre 6", "Torre 7", "Torre 8", "Torre 9"]

padrao_mpa = {}
padrao_pav = {}

col_offset = 1
for torre in torres:
    mpa_col = col_offset + 1
    pav_col = col_offset + 3
    padrao_mpa[torre] = buscar_valor_acima(sheet, mpa_col, sheet.row_count)
    padrao_pav[torre] = buscar_valor_acima(sheet, pav_col, sheet.row_count)
    col_offset += 4

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

# -----------------------------------------------------------
# BARRA DE PROGRESSO
# -----------------------------------------------------------
st.progress(progresso / len(torres))

# -----------------------------------------------------------
# BOTÕES DE AÇÃO
# -----------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    if st.button("💾 Salvar Dados"):
        salvar_dados(data, dados_torres)
with col2:
    if st.button("🔄 Atualizar Página (Novo Registro)"):
        st.experimental_rerun()
