import streamlit as st

# --- BLOQUEIO COM SENHA ---
SENHA_PADRAO = st.secrets.get("senha", "navona")

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

# --- CONFIGURAÇÕES INICIAIS ---
SPREADSHEET_ID = st.secrets["spreadsheet_id"]
SHEET_NAME = "dados"  # aba original (torres)
SHEET_MATERIAIS = "dados_materiais"  # nova aba para materiais (conforme solicitado)

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

def carregar_dados_materiais():
    """
    Carrega a aba dados_materiais como DataFrame (se existir).
    """
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_MATERIAIS)
    except Exception as e:
        st.error(f"Erro ao acessar aba '{SHEET_MATERIAIS}': {e}")
        return None
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    try:
        if 'Data' in df.columns:
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.date
    except Exception:
        pass
    return df

@st.cache_data(ttl=600)
def obter_ultimos_valores():
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    all_values = sheet.get_all_values()

    if not all_values or len(all_values) == 0:
        return {}

    condominios_local = {
        "San Pietro": {"torres": ["San Pietro T1", "San Pietro T2", "San Pietro T3"], "cor": "#1E90FF"},
        "Navona": {"torres": ["Navona T1", "Navona T2", "Navona T3"], "cor": "#FFA500"},
        "Duomo": {"torres": ["Duomo T1", "Duomo T2", "Duomo T3"], "cor": "#FFD700"},
        "Veneza": {"torres": ["Veneza T1", "Veneza T2", "Veneza T3"], "cor": "#BA55D3"},
    }

    todas_torres_local = [t for info in condominios_local.values() for t in info["torres"]]
    resultados = {}

    col_offset = 1
    n_linhas = len(all_values)

    for torre in todas_torres_local:
        mpa_col = col_offset + 1
        pav_col = col_offset + 3

        ultimo_mpa = ""
        ultimo_pav = ""

        for r in range(n_linhas - 1, 0, -1):
            row = all_values[r]

            try:
                val_mpa = row[mpa_col - 1].strip()
            except:
                val_mpa = ""
            if not ultimo_mpa and val_mpa:
                ultimo_mpa = val_mpa

            try:
                val_pav = row[pav_col - 1].strip()
            except:
                val_pav = ""
            if not ultimo_pav and val_pav:
                ultimo_pav = val_pav

            if ultimo_mpa and ultimo_pav:
                break

        resultados[torre] = {"MPA": ultimo_mpa, "Pavimento": ultimo_pav}
        col_offset += 4

    return resultados

def localizar_linha_por_data_na_aba(sheet, data):
    """
    Retorna número de linha (1-based) onde a coluna 'Data' bate com data (date object).
    Se não encontrar, retorna None.
    sheet: objeto gspread worksheet
    """
    try:
        values = sheet.get_all_records()
        df = pd.DataFrame(values)
        if 'Data' not in df.columns:
            return None
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.date
        matches = df.index[df['Data'] == data].tolist()
        if not matches:
            return None
        # +2 porque get_all_records descarta header: index 0 -> linha 2 na planilha
        return matches[0] + 2
    except Exception:
        # fallback: percorrer get_all_values procurando na coluna 1
        try:
            all_values = sheet.get_all_values()
            # garantir que há pelo menos header + 1 linha
            for i in range(1, len(all_values)):
                row = all_values[i]
                if len(row) >= 1:
                    cell = row[0].strip()
                    try:
                        cell_date = pd.to_datetime(cell, errors='coerce').date()
                        if cell_date == data:
                            return i + 1  # all_values é 0-based para linhas
                    except Exception:
                        continue
        except Exception:
            pass
    return None

def salvar_tudo(data, dados_torres, materiais):
    """
    Valida conflitos nas duas abas e, se tudo ok, salva:
     - dados_torres na aba 'dados' (mesma lógica antiga)
     - materiais na aba 'dados_materiais' (colunas 2..8: Areia Média..Fachada Areia Fina)
    Bloqueio completo: se qualquer célula (colunas 2 em diante) na linha estiver preenchida -> aborta.
    """
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)

    # abrir abas
    try:
        sheet_dados = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    except Exception as e:
        st.error(f"Erro ao abrir aba '{SHEET_NAME}': {e}")
        return

    try:
        sheet_mat = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_MATERIAIS)
    except Exception as e:
        st.error(f"Erro ao abrir aba '{SHEET_MATERIAIS}': {e}")
        return

    # localizar linhas por data em ambas as abas
    try:
        data_formatada = pd.to_datetime(data).date()
    except Exception:
        st.error("Data inválida.")
        return

    linha_dados = localizar_linha_por_data_na_aba(sheet_dados, data_formatada)
    if not linha_dados:
        st.warning(f"⚠️ Data não encontrada na aba '{SHEET_NAME}'.")
        df_temp = carregar_dados()
        if df_temp is not None:
            st.write("Primeiras datas encontradas:")
            st.dataframe(df_temp['Data'].head(10))
        return

    linha_mat = localizar_linha_por_data_na_aba(sheet_mat, data_formatada)
    if not linha_mat:
        st.warning(f"⚠️ Data não encontrada na aba '{SHEET_MATERIAIS}'.")
        df_temp = carregar_dados_materiais()
        if df_temp is not None:
            st.write("Primeiras datas encontradas (materiais):")
            st.dataframe(df_temp['Data'].head(10))
        return

    # pegar valores das linhas (row_values não retorna colunas vazias no final)
    try:
        valores_linha_dados = sheet_dados.row_values(linha_dados)
    except Exception as e:
        st.error(f"Erro ao ler linha na aba '{SHEET_NAME}': {e}")
        return

    try:
        valores_linha_mat = sheet_mat.row_values(linha_mat)
    except Exception as e:
        st.error(f"Erro ao ler linha na aba '{SHEET_MATERIAIS}': {e}")
        return

    # vamos padronizar o comprimento para checar todas as colunas (assumir que header tem pelo menos 8 colunas)
    # Determinamos um tamanho mínimo para checagem:  max( len(header_dados), len(header_mat), 8 )
    try:
        header_dados = sheet_dados.row_values(1)
    except:
        header_dados = []
    try:
        header_mat = sheet_mat.row_values(1)
    except:
        header_mat = []

    min_len_dados = max(len(header_dados), 2)  # data + algo
    min_len_mat = max(len(header_mat), 8)  # queremos pelo menos até coluna 8 para materiais

    if len(valores_linha_dados) < min_len_dados:
        valores_linha_dados += [""] * (min_len_dados - len(valores_linha_dados))
    if len(valores_linha_mat) < min_len_mat:
        valores_linha_mat += [""] * (min_len_mat - len(valores_linha_mat))

    # Verificação de conflito: qualquer célula (exceto a coluna 1 / index 0) preenchida -> bloqueio
    conflicto_dados = any(str(v).strip() != "" for v in valores_linha_dados[1:])
    conflicto_mat = any(str(v).strip() != "" for v in valores_linha_mat[1:])

    if conflicto_dados or conflicto_mat:
        st.error("Erro ao preencher: já existem valores na(s) linha(s) do dia selecionado. Operação abortada para evitar sobrescrita.")
        detalhes = {}
        if conflicto_dados:
            detalhes['dados'] = "Existem valores preenchidos na aba 'dados' (colunas 2 em diante)."
        if conflicto_mat:
            detalhes['dados_materiais'] = "Existem valores preenchidos na aba 'dados_materiais' (colunas 2 em diante)."
        st.write(detalhes)
        return

    # preparar updates para aba 'dados' (torres) - mesma lógica que antes
    updates_dados = []
    col_offset = 1
    for torre, valores in dados_torres.items():
        mpa_col = col_offset + 1
        tracos_col = col_offset + 2
        pav_col = col_offset + 3
        tipo_col = col_offset + 4

        updates_dados.append({'range': sheet_dados.cell(linha_dados, mpa_col).address, 'values': [[valores.get('Mpa', '')]]})
        updates_dados.append({'range': sheet_dados.cell(linha_dados, tracos_col).address, 'values': [[valores.get('Traços', '')]]})
        updates_dados.append({'range': sheet_dados.cell(linha_dados, pav_col).address, 'values': [[valores.get('Pavimento', '')]]})
        updates_dados.append({'range': sheet_dados.cell(linha_dados, tipo_col).address, 'values': [[valores.get('Tipo', 'A Granel')]]})

        col_offset += 4

    # preparar updates para aba 'dados_materiais' (colunas 2..8 conforme combinado)
    updates_mat = []
    materiais_ordem = [
        "Areia Média (Carga)",
        "Areia Fina (Carga)",
        "Cimento (un)",
        "Plastmix (un)",
        "Fachada Areia Média (Carga)",
        "Fachada Areia Fina (Carga)"
    ]
    # Colunas alvo: 2..(1 + len(materiais_ordem)) => 2..7 (coluna 1 é Data)
    col_for_materiais = list(range(2, 2 + len(materiais_ordem)))  # 2..7

    for col, key in zip(col_for_materiais, materiais_ordem):
        value = materiais.get(key, "")
        updates_mat.append({'range': sheet_mat.cell(linha_mat, col).address, 'values': [[value]]})

    # tudo pronto — escrever em sequência (dados -> materiais)
    try:
        if updates_dados:
            sheet_dados.batch_update(updates_dados)
        if updates_mat:
            sheet_mat.batch_update(updates_mat)
        st.success("✅ Dados salvos com sucesso em ambas as abas!")
        # limpar cache para recarregar valores
        try:
            carregar_dados.clear()
        except:
            pass
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")
        return

# -------- INTERFACE --------
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

# inicializa chaves de sessão de forma segura (apenas uma vez)
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

try:
    defaults_por_torre = obter_ultimos_valores()
except Exception:
    defaults_por_torre = {}

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
                preenchidas[torre] = True

            else:
                default_mpa = ""
                default_pav = ""

                if torre in defaults_por_torre:
                    default_mpa = defaults_por_torre[torre].get('MPA', '') or ""
                    default_pav = defaults_por_torre[torre].get('Pavimento', '') or ""

                mpa = st.text_input("Mpa", key=f"mpa_{torre}", value=str(default_mpa))
                tracos = st.text_input("Traços", key=f"tracos_{torre}", value="")
                pavimento = st.text_input("Pavimento", key=f"pav_{torre}", value=str(default_pav))
                tipo = st.selectbox("Tipo", ["A Granel", "Ensacada"], index=0, key=f"tipo_{torre}")

                if st.button(f"🚫 Sem consumo - {torre}", key=f"semc_{torre}"):
                    sem_consumo[torre] = True
                    st.session_state["sem_consumo"] = sem_consumo
                    st.rerun()

                if all([mpa.strip(), tracos.strip(), pavimento.strip()]):
                    preenchidas[torre] = True
                else:
                    preenchidas[torre] = False

                st.session_state["preenchidas"] = preenchidas
                dados_torres[torre] = {"Mpa": mpa, "Traços": tracos, "Pavimento": pavimento, "Tipo": tipo}

            st.markdown("</div>", unsafe_allow_html=True)

# ----------------- NOVO FORMULÁRIO: DADOS DE MATERIAIS -----------------
st.markdown("<h3 style='margin-top:10px'>Dados de Materiais</h3>", unsafe_allow_html=True)
st.markdown("<div class='form-block'>", unsafe_allow_html=True)

# Campos conforme confirmado:
# Data | Areia Média (Carga) | Areia Fina (Carga) | Cimento (un) | Plastmix (un) | Fachada Areia Média (Carga) | Fachada Areia Fina (Carga)
# Usaremos text_input para permitir campo vazio (opcional). Se preferir number_input, me avisa e troco.

areia_media = st.text_input("Areia Média (Carga)", key="mat_areia_media", value="")
areia_fina = st.text_input("Areia Fina (Carga)", key="mat_areia_fina", value="")
cimento = st.text_input("Cimento (un)", key="mat_cimento", value="")
plastmix = st.text_input("Plastmix (un)", key="mat_plastmix", value="")
fach_fera_media = st.text_input("Fachada Areia Média (Carga)", key="mat_fach_a_media", value="")
fach_fera_fina = st.text_input("Fachada Areia Fina (Carga)", key="mat_fach_a_fina", value="")

st.markdown("</div>", unsafe_allow_html=True)

# --- BOTÕES DE AÇÃO ---
st.write("---")
col1, col2 = st.columns(2)

with col1:
    if st.button("💾 Salvar Dados"):
        # montar dicionários para salvar
        materiais_para_salvar = {
            "Areia Média (Carga)": areia_media,
            "Areia Fina (Carga)": areia_fina,
            "Cimento (un)": cimento,
            "Plastmix (un)": plastmix,
            "Fachada Areia Média (Carga)": fach_fera_media,
            "Fachada Areia Fina (Carga)": fach_fera_fina
        }
        salvar_tudo(data, dados_torres, materiais_para_salvar)

with col2:
    if st.button("🔄 Atualizar Página (Novo Registro)"):

        # --- LIMPA COMPLETAMENTE A SESSÃO ---
        keys = list(st.session_state.keys())
        for key in keys:
            del st.session_state[key]

        # --- LIMPA CACHE PARA GARANTIR RELOAD REAL ---
        try:
            carregar_dados.clear()
            obter_ultimos_valores.clear()
        except:
            pass

        # --- F5 REAL ---
        st.rerun()

# --- BARRA DE PROGRESSO ---
total = len(todas_torres)
concluidas = sum(1 for t in todas_torres if sem_consumo.get(t, False) or preenchidas.get(t, False))
st.progress(concluidas / total if total > 0 else 0)
st.caption(f"Progresso: {concluidas}/{total} torres concluídas")

