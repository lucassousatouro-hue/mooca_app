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

def salvar_dados(data, dados_torres, materiais=None):
    """
    Salva dados na planilha:
     - dados_torres: dicionário por torre com chaves 'Mpa','Traços','Pavimento','Tipo'
     - materiais: dicionário com keys:
         'Areia Media (Carga)',
         'Areia Fina (carga)',
         'Cimento (un)',
         'Plastmix (un)',
         'Fachada Areia Média (Carga)',
         'Fachada Areia Fina (carga)'
    Observação: a coluna 1 é Data. Materiais serão gravados nas colunas 2..8 (na ordem fornecida).
    """
    creds = get_gcp_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    df = carregar_dados()
    try:
        data_formatada = pd.to_datetime(data).date()
    except Exception:
        st.error("Data inválida.")
        return

    linha_index = df.index[df['Data'] == data_formatada].tolist()

    if not linha_index:
        st.warning("⚠️ Data não encontrada na planilha.")
        st.write("Primeiras datas encontradas:")
        st.dataframe(df['Data'].head(10))
        return

    linha_planilha = linha_index[0] + 2  # porque header na linha 1

    try:
        linha_valores = sheet.row_values(linha_planilha)
    except Exception as e:
        st.error(f"Erro ao verificar a planilha: {e}")
        return

    # calculando colunas alvo
    todas_torres = [t for info in {
        "San Pietro": {"torres": ["San Pietro T1", "San Pietro T2", "San Pietro T3"]},
        "Navona": {"torres": ["Navona T1", "Navona T2", "Navona T3"]},
        "Duomo": {"torres": ["Duomo T1", "Duomo T2", "Duomo T3"]},
        "Veneza": {"torres": ["Veneza T1", "Veneza T2", "Veneza T3"]},
    }.values() for t in info["torres"]]

    # max coluna que podemos acessar = col 1 (data) + 4 * n_torres OR 8 (materiais)
    max_col_needed = max(8, 1 + 4 * len(todas_torres))

    # pad linha_valores para evitar index error (row_values não retorna colunas vazias no final)
    if len(linha_valores) < max_col_needed:
        linha_valores = linha_valores + [""] * (max_col_needed - len(linha_valores))

    # prepara lista de colunas que vamos atualizar e verifica se já há dados nelas
    target_columns = []

    # materiais: colunas 2..8
    materiais_cols = list(range(2, 9))  # 2,3,4,5,6,7,8
    if materiais:
        target_columns += materiais_cols

    # torres: mesmas regras que antes (cada torre 4 colunas: Mpa, Traços, Pavimento, Tipo)
    col_offset = 1
    for torre, valores in dados_torres.items():
        mpa_col = col_offset + 1
        tracos_col = col_offset + 2
        pav_col = col_offset + 3
        tipo_col = col_offset + 4
        target_columns += [mpa_col, tracos_col, pav_col, tipo_col]
        col_offset += 4

    # remover duplicatas e ordenar
    target_columns = sorted(set(target_columns))

    # verificar conflitos: se alguma célula alvo já tiver conteúdo -> não sobrescrever
    conflitos = []
    for col in target_columns:
        val = ""
        try:
            val = linha_valores[col - 1].strip()
        except Exception:
            val = ""
        if val != "":
            conflitos.append((col, val))

    if conflitos:
        st.error("Erro ao preencher: já existem valores nas células que serão atualizadas. Evite sobrescrever registros existentes.")
        st.write("Células ocupadas (coluna : valor):")
        st.write(conflitos[:10])  # mostra até 10
        return

    # se chegou até aqui, podemos construir as atualizações
    updates = []

    # materiais primeiro (ordem correta conforme especificado)
    if materiais:
        materiais_ordem = [
            "Areia Media (Carga)",
            "Areia Fina (carga)",
            "Cimento (un)",
            "Plastmix (un)",
            "Fachada Areia Média (Carga)",
            "Fachada Areia Fina (carga)"
        ]
        # Observação: você descreveu 7 colunas contando Data; aqui são 6 campos além da Data.
        # No seu enunciado original havia 7 colunas após Data? Você listou 6 nomes além de Data.
        # Ajustei para gravar 6 campos nas colunas 2..7. Coluna 8 ficará vazia por compatibilidade.
        # Se você quiser outra ordem/quantidade, me avisa e eu ajusto.
        # Vamos mapear valores às colunas 2..7
        col_for_materiais = list(range(2, 2 + len(materiais_ordem)))  # 2..7

        for col, key in zip(col_for_materiais, materiais_ordem):
            value = materiais.get(key, "")
            updates.append({'range': sheet.cell(linha_planilha, col).address, 'values': [[value]]})

    # caso restasse a 8ª coluna (vazia) não mexemos nela

    # agora torres (mesma lógica que tinha antes)
    col_offset = 1
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
        if updates:
            sheet.batch_update(updates)
            st.success("✅ Dados salvos com sucesso!")
            carregar_dados.clear()
            obter_ultimos_valores.clear()
        else:
            st.info("Nenhuma atualização a ser feita (nenhum dado no formulário).")
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")


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

# Renderiza os formulários por condomínio/torre (mesma lógica de antes)
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

# Campos conforme você especificou:
# Data | Areia Média (Carga) | Areia Fina (carga) | Cimento (un) | Plastmix (un) | Fachada Areia Média (Carga) | Fachada Areia Fina (carga)
# Observação: o app já possui o seletor de data no topo; aqui vamos simplesmente preencher os campos relativos à data selecionada.

# Tentar obter valores padrão da planilha para a data selecionada (se existirem)
default_vals_materiais = {
    "Areia Media (Carga)": "",
    "Areia Fina (carga)": "",
    "Cimento (un)": "",
    "Plastmix (un)": "",
    "Fachada Areia Média (Carga)": "",
    "Fachada Areia Fina (carga)": ""
}

if df_dados is not None and not df_dados.empty:
    try:
        data_formatada = pd.to_datetime(data).date()
        linha_index = df_dados.index[df_dados['Data'] == data_formatada].tolist()
        if linha_index:
            linha_df = df_dados.loc[linha_index[0]]
            # tenta preencher a partir dos nomes das colunas (se existirem na planilha)
            for key in list(default_vals_materiais.keys()):
                # tentar colunas parecidas (sem acento/espaco diferente)
                for colname in df_dados.columns:
                    if colname.strip().lower().replace("ú","u").replace("í","i").replace("á","a").replace("é","e").replace("ã","a").replace("õ","o").replace("ç","c") == key.strip().lower().replace("ú","u").replace("í","i").replace("á","a").replace("é","e").replace("ã","a").replace("õ","o").replace("ç","c"):
                        try:
                            default_vals_materiais[key] = str(linha_df[colname]) if pd.notna(linha_df[colname]) else ""
                        except:
                            pass
                        break
    except Exception:
        pass

areia_media = st.text_input("Areia Média (Carga)", key="mat_areia_media", value=default_vals_materiais["Areia Media (Carga)"])
areia_fina = st.text_input("Areia Fina (carga)", key="mat_areia_fina", value=default_vals_materiais["Areia Fina (carga)"])
cimento = st.text_input("Cimento (un)", key="mat_cimento", value=default_vals_materiais["Cimento (un)"])
plastmix = st.text_input("Plastmix (un)", key="mat_plastmix", value=default_vals_materiais["Plastmix (un)"])
fach_fera_media = st.text_input("Fachada Areia Média (Carga)", key="mat_fach_a_media", value=default_vals_materiais["Fachada Areia Média (Carga)"])
fach_fera_fina = st.text_input("Fachada Areia Fina (carga)", key="mat_fach_a_fina", value=default_vals_materiais["Fachada Areia Fina (carga)"])

st.markdown("</div>", unsafe_allow_html=True)

# --- BOTÕES DE AÇÃO ---
st.write("---")
col1, col2 = st.columns(2)

with col1:
    if st.button("💾 Salvar Dados"):
        # monta o dicionário de materiais na mesma nomenclatura usada em salvar_dados()
        materiais_para_salvar = {
            "Areia Media (Carga)": areia_media,
            "Areia Fina (carga)": areia_fina,
            "Cimento (un)": cimento,
            "Plastmix (un)": plastmix,
            "Fachada Areia Média (Carga)": fach_fera_media,
            "Fachada Areia Fina (carga)": fach_fera_fina
        }
        salvar_dados(data, dados_torres, materiais=materiais_para_salvar)

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
