import streamlit as st

# --- BLOQUEIO COM SENHA ---
SENHA_PADRAO = st.secrets.get("senha", "navona")

# Se o usuário já passou pela senha, guardamos na sessão
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔒 Acesso Restrito")
    senha = st.text_input("Digite a senha para acessar o aplicativo:", type="password")

    if senha == SENHA_PADRAO:
        st.session_state["autenticado"] = True
        st.success("Acesso liberado ✅")
        st.rerun()
    elif senha:
        st.error("Senha incorreta. Tente novamente.")
    st.stop()

# --- SE O USUÁRIO PASSAR, O RESTO DO APP CARREGA ---
import pandas as pd
import datetime
import json
from google.oauth2 import service_account
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÕES INICIAIS ---
SPREADSHEET_ID = st.secrets["spreadsheet_id"]
SHEET_NAME = "dados"

def get_gcp_credentials():
    creds_json = st.secrets["gcp_service_account_credentials"]
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return creds

@st.cache_data(ttl=600)
def carregar_dados():
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    try:
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.date
    except Exception:
        pass
    return df

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

    linha_planilha = linha_index[0] + 2
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

# --- INTERFACE ---
st.set_page_config(page_title="App Mooca", layout="wide")

st.markdown('<img src="https://rtsargamassas.com.br/wp-content/uploads/2023/03/rts_logo.png" class="logo-img">', unsafe_allow_html=True)
st.header("Obra Mooca")
st.title("Controle de Traços de Argamassa")

# --- CSS ---
st.markdown("""
<style>
    .form-block div[data-testid="stTextInput"] > div > input,
    .form-block div[data-testid="stSelectbox"] > div > button {
        width: 100%;
        box-sizing: border-box;
    }
    .form-block .stTextInput > div > div > input {
        background-color: white !important;
        color: black !important;
    }
    .form-block .stMarkdown p {
        color: black !important;
    }
    .form-block .stSelectbox > div > div > button {
        background-color: white !important;
        color: black !important;
    }
    .form-block {
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .logo-img {
        height: 50px;
        margin-right: 10px;
    }
</style>
""", unsafe_allow_html=True)

data = st.date_input("Selecione a data:", datetime.date.today())

condominios = {
    "San Pietro": {"torres": ["San Pietro T1", "San Pietro T2", "San Pietro T3"], "cor": "#1E90FF"},
    "Navona": {"torres": ["Navona T1", "Navona T2", "Navona T3"], "cor": "#FFA500"},
    "Duomo": {"torres": ["Duomo T1", "Duomo T2", "Duomo T3"], "cor": "#FFD700"},
    "Veneza": {"torres": ["Veneza T1", "Veneza T2", "Veneza T3"], "cor": "#BA55D3"},
}

if "sem_consumo" not in st.session_state:
    st.session_state["sem_consumo"] = {}
if "preenchidas" not in st.session_state:
    st.session_state["preenchidas"] = {}

sem_consumo = st.session_state["sem_consumo"]
preenchidas = st.session_state["preenchidas"]
dados_torres = {}

todas_torres = [t for info in condominios.values() for t in info["torres"]]

def hex_with_alpha(hex_color: str, alpha_hex: str = "22"):
    hex_clean = hex_color.lstrip("#")
    if len(hex_clean) == 6:
        return f"#{hex_clean}{alpha_hex}"
    return hex_color

df_dados = carregar_dados()
if df_dados is None:
    st.error("Erro ao carregar os dados da planilha.")
elif df_dados.empty:
    st.warning("A planilha 'dados' está vazia.")

for nome_condominio, info in condominios.items():
    st.markdown(f"<h3 style='color:{info['cor']}; margin-bottom:6px'>{nome_condominio}</h3>", unsafe_allow_html=True)
    cols = st.columns(3)
    for i, torre in enumerate(info["torres"]):
        with cols[i % 3]:
            bg_color = hex_with_alpha(info['cor'], "22")
            st.markdown(f"<div class='form-block' style='background:{bg_color}; border:2px solid {info['cor']};'>", unsafe_allow_html=True)
            st.markdown(f"**{torre}**", unsafe_allow_html=True)

            if sem_consumo.get(torre, False):
                st.info("🚫 Torre marcada como 'Sem consumo'.")
                if st.button(f"Desfazer - {torre}", key=f"desf_{torre}"):
                    sem_consumo[torre] = False
                    st.session_state["sem_consumo"] = sem_consumo
                    st.rerun()
                dados_torres[torre] = {"Mpa": "", "Traços": "", "Pavimento": "", "Tipo": ""}
            else:
                mpa = st.text_input("Mpa", key=f"mpa_{torre}")
                tracos = st.text_input("Traços", key=f"tracos_{torre}")
                pavimento = st.text_input("Pavimento", key=f"pav_{torre}")
                tipo = st.selectbox("Tipo", ["A Granel", "Ensacada"], key=f"tipo_{torre}")
                if st.button(f"🚫 Sem consumo - {torre}", key=f"semc_{torre}"):
                    sem_consumo[torre] = True
                    st.session_state["sem_consumo"] = sem_consumo
                    st.rerun()
                preenchidas[torre] = any([mpa, tracos, pavimento])
                st.session_state["preenchidas"] = preenchidas
                dados_torres[torre] = {"Mpa": mpa, "Traços": tracos, "Pavimento": pavimento, "Tipo": tipo}
            st.markdown("</div>", unsafe_allow_html=True)

st.write("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("💾 Salvar Dados"):
        salvar_dados(data, dados_torres)
with col2:
    if st.button("🔄 Atualizar Página (Novo Registro)"):
        for torre in todas_torres:
            for prefix in ("mpa_", "tracos_", "pav_", "tipo_"):
                key = f"{prefix}{torre}"
                if key in st.session_state:
                    del st.session_state[key]
        st.session_state["sem_consumo"] = {}
        st.session_state["preenchidas"] = {}
        st.rerun()

total = len(todas_torres)
concluidas = sum(1 for t in todas_torres if sem_consumo.get(t, False) or preenchidas.get(t, False))
st.progress(concluidas / total if total > 0 else 0)
st.caption(f"Progresso: {concluidas}/{total} torres concluídas")
