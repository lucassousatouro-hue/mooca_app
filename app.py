import streamlit as st
import pandas as pd
import datetime
from openpyxl import load_workbook

# Caminho da planilha no Google Drive
EXCEL_PATH = r"/content/drive/MyDrive/mooca_dados/mooca_dados.xlsx"

# Função para salvar os dados
def salvar_dados(data, dados_torres):
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="dados")
    except FileNotFoundError:
        st.error(f"Erro: Arquivo não encontrado em {EXCEL_PATH}")
        return
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return


    try:
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.date
    except Exception:
        pass

    data_formatada = pd.to_datetime(data).date()
    linha = df.index[df['Data'] == data_formatada].tolist()
    if not linha:
        st.warning("⚠️ Data não encontrada na planilha. Verifique se está correta na coluna A.")
        st.write("Datas encontradas:")
        st.dataframe(df['Data'].head(10))
        return
    linha = linha[0]

    col_index = 1
    for torre, valores in dados_torres.items():
        df.iat[linha, col_index] = valores.get('Mpa', '')
        df.iat[linha, col_index + 1] = valores.get('Traços', '')
        df.iat[linha, col_index + 2] = valores.get('Pavimento', '')
        df.iat[linha, col_index + 3] = valores.get('Tipo', 'A Granel')
        col_index += 4

    # Para salvar no Google Drive com openpyxl, precisamos carregar o workbook
    # e depois salvar no caminho completo.
    # openpyxl não suporta o modo 'a' para sheets existentes da mesma forma que pandas puro.
    # Uma abordagem é carregar o workbook, deletar a sheet existente e escrever a nova.
    # Outra é usar pandas para reescrever o arquivo inteiro (o que 'if_sheet_exists="replace"' faz).
    # Vamos manter a abordagem do pandas, mas precisamos de permissão de escrita no Drive.

    try:
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl", mode="w") as writer: # Usar mode='w' para sobrescrever o arquivo inteiro
             df.to_excel(writer, sheet_name="dados", index=False)
        st.success("✅ Dados salvos com sucesso!!!")
    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")
        st.warning("Verifique se o Google Colab tem permissão de escrita no seu Google Drive e se o caminho do arquivo está correto.")


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
