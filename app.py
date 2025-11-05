import streamlit as st
import pandas as pd
import datetime
import json # Importando a biblioteca json
from google.oauth2 import service_account # Importando para autenticação

# Caminho da planilha no Google Drive - Agora usaremos a ID da planilha
# Você precisará obter a ID da sua planilha (é a longa string de letras e números na URL)
# Exemplo: https://docs.google.com/spreadsheets/d/SUA_PLANILHA_ID_AQUI/edit
SPREADSHEET_ID = st.secrets["spreadsheet_id"] # A ID da planilha será salva como segredo no Streamlit
# O nome da aba (sheet)
SHEET_NAME = "dados"

# Função para obter credenciais do Google Cloud
def get_gcp_credentials():
    # Lê o segredo como string
    creds_json = st.secrets["gcp_service_account_credentials"]
    # Converte a string JSON em dicionário
    creds_dict = json.loads(creds_json)
    # Cria as credenciais a partir do dicionário
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return creds


# Função para carregar os dados da planilha Google Sheets
@st.cache_data(ttl=600) # Cache para não ler a planilha a cada interação (cache de 10 minutos)
def carregar_dados():
    creds = get_gcp_credentials()
    import gspread # Importando gspread aqui para evitar erro de import antes das credenciais
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # Converter a coluna de data para o formato correto
    try:
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.date
    except Exception:
        pass # Ignora se houver erro na conversão de data inicial

    return df

# Função para salvar os dados na planilha Google Sheets
def salvar_dados(data, dados_torres):
    creds = get_gcp_credentials()
    import gspread
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    # Carregar os dados atuais para encontrar a linha correta
    df = carregar_dados() # Usa a função de carregar dados

    data_formatada = pd.to_datetime(data).date()
    linha_index = df.index[df['Data'] == data_formatada].tolist()

    if not linha_index:
        st.warning("⚠️ Data não encontrada na planilha. Verifique se está correta na coluna A.")
        # Opcional: Mostrar as primeiras datas para o usuário verificar
        st.write("Primeiras datas encontradas na planilha:")
        st.dataframe(df['Data'].head(10))
        return

    # gspread usa indexação baseada em 1 para linhas e colunas
    linha_planilha = linha_index[0] + 2 # +1 para índice baseado em 1, +1 para pular o cabeçalho

    col_offset = 1 # Começa na coluna B (índice 2)
    updates = [] # Lista para armazenar as atualizações a serem feitas em batch

    for torre, valores in dados_torres.items():
        mpa_col = col_offset + 1 # Coluna B + offset
        tracos_col = col_offset + 2 # Coluna C + offset
        pav_col = col_offset + 3 # Coluna D + offset
        tipo_col = col_offset + 4 # Coluna E + offset

        updates.append({'range': sheet.cell(linha_planilha, mpa_col).address, 'values': [[valores.get('Mpa', '')]]})
        updates.append({'range': sheet.cell(linha_planilha, tracos_col).address, 'values': [[valores.get('Traços', '')]]})
        updates.append({'range': sheet.cell(linha_planilha, pav_col).address, 'values': [[valores.get('Pavimento', '')]]})
        updates.append({'range': sheet.cell(linha_planilha, tipo_col).address, 'values': [[valores.get('Tipo', 'A Granel')]]}) # Garante um valor padrão

        col_offset += 4 # Avança 4 colunas para a próxima torre

    try:
        # Atualizar várias células de uma vez (mais eficiente)
        sheet.batch_update(updates)
        st.success("✅ Dados salvos com sucesso!!!")
        # Invalidar o cache para forçar a recarga dos dados atualizados na próxima vez
        carregar_dados.clear()

    except Exception as e:
        st.error(f"Erro ao salvar dados na planilha Google Sheets: {e}")
        st.warning("Verifique as permissões da conta de serviço no Google Cloud e se a planilha está compartilhada com o e-mail da conta de serviço.")


# --- Interface ---
# Configuração da página com título e ícone (opcionalmente logo)
st.set_page_config(
    page_title="App Mooca",
    layout="wide",
    # icon="🧊", # Você pode usar um ícone emoji aqui
    # ou especificar o caminho para um arquivo de imagem para o favicon:
    # icon="path/to/your/favicon.png"
)

# Adicionar a logo
st.markdown('<img src="https://rtsargamassas.com.br/wp-content/uploads/2023/03/rts_logo.png" class="logo-img">', unsafe_allow_html=True)

st.header("Obra Mooca")
st.title("Controle de Traços de Argamassa")

# Adicionar CSS para personalizar a largura e as cores dos inputs
st.markdown("""
<style>
    /* Diminuir a largura dos inputs dentro do form-block */
    .form-block div[data-testid="stTextInput"] > div > input,
    .form-block div[data-testid="stSelectbox"] > div > button {
        width: 100%; /* Ajusta a largura para 100% do contêiner pai */
        box-sizing: border-box; /* Inclui padding e border na largura total */
    }

    /* Estilo para os inputs de texto dentro dos blocos coloridos */
    .form-block .stTextInput > div > div > input {
        background-color: white !important;
        color: black !important;
    }

    /* Estilo para o texto dos labels dos inputs dentro do form-block */
    .form-block .stMarkdown p {
        color: black !important; /* Define a cor do texto dos labels como preto */
    }

    /* Estilo para o selectbox dentro dos blocos coloridos */
    .form-block .stSelectbox > div > div > button {
        background-color: white !important;
        color: black !important;
    }

    /* Estilo para o bloco do formulário com cor de fundo e borda */
    .form-block {
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }

    /* Ajustar o espaçamento entre as colunas, se necessário */
    .stColumns {
        gap: 1rem; /* Ajuste o espaçamento entre as colunas */
    }

    /* CSS para adicionar a logo ao lado do título */
    .stApp > header {
        align-items: center;
    }

    .stApp > header .st-emotion-cache-zq5wmo { /* Classe do container do título e logo */
         display: flex;
         align-items: center;
         gap: 10px; /* Espaço entre a logo e o título */
    }

    .logo-img {
        height: 50px; /* Ajuste o tamanho da logo conforme necessário */
        margin-right: 10px; /* Espaço entre a logo e o título */
    }


</style>
""", unsafe_allow_html=True)


# Seleção de data
data = st.date_input("Selecione a data:", datetime.date.today())

# Grupos de torres com cores
condominios = {
    "San Pietro": {"torres": ["San Pietro T1", "San Pietro T2", "San Pietro T3"], "cor": "#1E90FF"},  # azul
    "Navona": {"torres": ["Navona T1", "Navona T2", "Navona T3"], "cor": "#FFA500"},  # laranja
    "Duomo": {"torres": ["Duomo T1", "Duomo T2", "Duomo T3"], "cor": "#FFD700"},  # amarelo
    "Veneza": {"torres": ["Veneza T1", "Veneza T2", "Veneza T3"], "cor": "#BA55D3"},  # lilás
}

# Inicializar estados
if "sem_consumo" not in st.session_state:
    st.session_state["sem_consumo"] = {}
if "preenchidas" not in st.session_state:
    st.session_state["preenchidas"] = {}

sem_consumo = st.session_state["sem_consumo"]
preenchidas = st.session_state["preenchidas"]
dados_torres = {}

# Lista completa de torres (útil para reset)
todas_torres = [t for info in condominios.values() for t in info["torres"]]


# --- Layout visual ---
def hex_with_alpha(hex_color: str, alpha_hex: str = "22"):
    """
    Retorna o hex com alpha (8 dígitos). Ex: '#1E90FF' + '22' -> '#1E90FF22'
    alpha_hex padrão '22' é ~13% de opacidade (sutil).
    """
    hex_clean = hex_color.lstrip("#")
    if len(hex_clean) == 6:
        return f"#{hex_clean}{alpha_hex}"
    return hex_color

# Carregar dados ao iniciar ou atualizar a página
df_dados = carregar_dados()
if df_dados is not None and not df_dados.empty:
    st.write("Dados carregados da planilha:")
    st.dataframe(df_dados.head())
elif df_dados is not None and df_dados.empty:
     st.warning("A planilha 'dados' está vazia. Certifique-se de que ela contenha os cabeçalhos esperados.")
else:
    st.error("Não foi possível carregar os dados da planilha. Verifique as credenciais, a ID da planilha e o nome da aba.")


for nome_condominio, info in condominios.items():
    st.markdown(f"<h3 style='color:{info['cor']}; margin-bottom:6px'>{nome_condominio}</h3>", unsafe_allow_html=True)
    # Usar colunas para organizar os formulários lado a lado e controlar a largura
    cols = st.columns(3) # Ajuste o número de colunas conforme necessário (aqui, 3 colunas)

    for i, torre in enumerate(info["torres"]):
        with cols[i % 3]: # Distribui as torres entre as colunas
            # cor de fundo levemente transparente
            bg_color = hex_with_alpha(info['cor'], "22")
            # Aplicar a cor de fundo e borda ao div que engloba o formulário
            st.markdown(f"<div class='form-block' style='background:{bg_color}; border:2px solid {info['cor']};'>", unsafe_allow_html=True)
            st.markdown(f"**{torre}**", unsafe_allow_html=True) # Adiciona o nome da torre

            if sem_consumo.get(torre, False):
                st.info("🚫 Torre marcada como 'Sem consumo'.")
                if st.button(f"Desfazer - {torre}", key=f"desf_{torre}"):
                    sem_consumo[torre] = False
                    st.session_state["sem_consumo"] = sem_consumo
                    st.rerun()

                dados_torres[torre] = {"Mpa": "", "Traços": "", "Pavimento": "", "Tipo": ""}
            else:
                # usar keys para cada input pra permitir reset manual
                mpa_key = f"mpa_{torre}"
                tracos_key = f"tracos_{torre}"
                pav_key = f"pav_{torre}"
                tipo_key = f"tipo_{torre}"

                # Remover o nome da torre do label do input para evitar repetição
                mpa = st.text_input("Mpa", key=mpa_key)
                tracos = st.text_input("Traços", key=tracos_key)
                pavimento = st.text_input("Pavimento", key=pav_key)
                tipo = st.selectbox("Tipo", ["A Granel", "Ensacada"], key=tipo_key)

                if st.button(f"🚫 Sem consumo - {torre}", key=f"semc_{torre}"):
                    sem_consumo[torre] = True
                    st.session_state["sem_consumo"] = sem_consumo
                    st.rerun()

                preenchidas[torre] = any([mpa, tracos, pavimento])
                st.session_state["preenchidas"] = preenchidas

                dados_torres[torre] = {"Mpa": mpa, "Traços": tracos, "Pavimento": pavimento, "Tipo": tipo}

            st.markdown("</div>", unsafe_allow_html=True)


# --- Botões finais ---
st.write("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("💾 Salvar Dados"):
        salvar_dados(data, dados_torres)

with col2:
    # Botão que reseta os campos do formulário (não altera a planilha)
    if st.button("🔄 Atualizar Página (Novo Registro)"):
        # Remover keys de inputs individuais
        for torre in todas_torres:
            for prefix in ("mpa_", "tracos_", "pav_", "tipo_"):
                key = f"{prefix}{torre}"
                if key in st.session_state:
                    del st.session_state[key]

        # Resetar marcadores de sem consumo e preenchidas
        st.session_state["sem_consumo"] = {}
        st.session_state["preenchidas"] = {}

        # Forçar recarregamento da página com estado limpo
        st.rerun()

# Barra de progresso movida para a parte inferior
total = len(todas_torres)
concluidas = sum(1 for t in todas_torres if sem_consumo.get(t, False) or preenchidas.get(t, False))
st.progress(concluidas / total if total > 0 else 0)
st.caption(f"Progresso: {concluidas}/{total} torres concluídas")
