import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import uuid

# 1. SETUP DA PÁGINA (ESTILO PRETTYMAPP)
st.set_page_config(page_title="JNL Dash Pro", page_icon="📈", layout="wide")

# --- CSS DE ALTO NÍVEL (GLASSMORPHISM & CLEAN DESIGN) ---
st.markdown("""
    <style>
    /* Importando fonte Inter */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Estilizando o Fundo e Sidebar */
    .main { background-color: #F8F9FB; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E4E8; }

    /* Estilo dos Cards (A essência sem a bagunça) */
    .stMetric, .echarts-container, div[data-testid="stExpander"] {
        background: white !important;
        border: 1px solid #E0E4E8 !important;
        border-radius: 15px !important;
        padding: 20px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    }

    /* Ajuste da barra de comando NLU */
    .stTextInput > div > div > input {
        border-radius: 12px;
        border: 1px solid #D0D5DD;
        padding: 12px 20px;
    }

    /* Esconder o lixo visual do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR (LAYOUT PRETTYMAPP) ---
with st.sidebar:
    st.title("🛡️ JNL Control")
    st.markdown("---")
    st.subheader("📁 Upload de Dados")
    arquivos = st.file_uploader("Arraste suas planilhas aqui", type=["xlsx", "xls"], accept_multiple_files=True)
    st.markdown("---")
    st.subheader("🎯 Configurações")
    foco = st.selectbox("Foco Principal", ["FORNECEDOR", "DESCRIÇÃO", "CATEGORIA"])
    meta = st.slider("Meta Semanal (R$)", 0, 50000, 10000)

# --- ÁREA PRINCIPAL ---
st.markdown(f"# Relatório Inteligente: {foco}")
comando_nlu = st.text_input("💬 O que você quer ver hoje?", placeholder="Ex: 'Gastos com transporte' ou 'Maiores fornecedores de Março'")

# --- MOTOR DE DADOS ---
def extrair_valor(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    v = str(v).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try: return float(v)
    except: return 0.0

def processar_excel(df):
    tabelas = []
    mes_atual = "Geral"
    cabecalho = None
    dados_acumulados = []

    for _, row in df.iterrows():
        linha_txt = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        # Detecta Mês
        if len(linha_txt.split()) == 1 and any(m in linha_txt for m in ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO']):
            if dados_acumulados and cabecalho:
                tabelas.append((mes_atual, pd.DataFrame(dados_acumulados, columns=cabecalho)))
            mes_atual = linha_txt
            dados_acumulados = []
            continue
        # Detecta Cabeçalho
        if 'DATA' in linha_txt and 'VALOR' in linha_txt:
            if dados_acumulados and cabecalho:
                tabelas.append((mes_atual, pd.DataFrame(dados_acumulados, columns=cabecalho)))
            cabecalho = [str(x).strip().upper() for x in row.values if pd.notna(x)]
            dados_acumulados = []
            continue
        if cabecalho and any(pd.notna(x) for x in row.values):
            dados_acumulados.append(list(row.values)[:len(cabecalho)])

    if dados_acumulados and cabecalho:
        tabelas.append((mes_atual, pd.DataFrame(dados_acumulados, columns=cabecalho)))
    return tabelas

# --- EXIBIÇÃO ---
if arquivos:
    lista_resumos = []
    
    for arq in arquivos:
        df_raw = pd.read_excel(arq, header=None)
        blocos = processar_excel(df_raw)
        
        for mes, df_mes in blocos:
            col_v = next((c for c in df_mes.columns if 'VALOR' in c), None)
            col_d = next((c for c in df_mes.columns if foco in c), df_mes.columns[1])
            
            if col_v and col_d:
                df_mes[col_v] = df_mes[col_v].apply(extrair_valor)
                # Filtro NLU
                if comando_nlu:
                    df_mes = df_mes[df_mes[col_d].str.contains(comando_nlu, case=False, na=False)]
                
                resumo = df_mes.groupby(col_d)[col_v].sum().reset_index().sort_values(by=col_v, ascending=True)
                lista_resumos.append(resumo)

    if lista_resumos:
        df_final = pd.concat(lista_resumos)
        c_nome = df_final.columns[0]
        c_val = df_final.columns[1]
        consolidado = df_final.groupby(c_nome)[c_val].sum().reset_index().sort_values(by=c_val, ascending=False)
        
        # --- TOP KPIs (Vibe StockPeers, mas organizada) ---
        m1, m2, m3 = st.columns(3)
        total_geral = consolidado[c_val].sum()
        m1.metric("Valor Total", f"R$ {total_geral:,.2f}")
        m2.metric("Principal Destino", consolidado.iloc[0][c_nome])
        m3.metric("Meta Semanal", f"R$ {meta:,.2f}", f"{((total_geral/meta)-1)*100:.1f}%")

        # --- ABAS DE ANÁLISE (O segredo para limpar a bagunça) ---
        aba_grafico, aba_dados, aba_comparativo = st.tabs(["📊 Visão Gráfica", "📋 Detalhes Brutos", "⚖️ Comparativo"])

        with aba_grafico:
            st.write("### Distribuição de Recursos")
            # Gráfico de Pizza Animado (ECharts)
            pizza_options = {
                "tooltip": {"trigger": "item"},
                "legend": {"orient": "vertical", "left": "left", "show": False},
                "series": [
                    {
                        "name": foco,
                        "type": "pie",
                        "radius": ["50%", "85%"],
                        "avoidLabelOverlap": False,
                        "itemStyle": {"borderRadius": 10, "borderColor": "#fff", "borderWidth": 2},
                        "label": {"show": True, "formatter": "{b}: R${c}"},
                        "emphasis": {"label": {"show": True, "fontSize": "16", "fontWeight": "bold"}},
                        "data": [{"value": row[c_val], "name": row[c_nome]} for _, row in consolidado.iterrows()],
                    }
                ],
            }
            st_echarts(options=pizza_options, height="600px")

        with aba_dados:
            st.write("### Listagem Completa")
            st.dataframe(consolidado, use_container_width=True, hide_index=True)

        with aba_comparativo:
            st.write("### Ranking de Fornecedores/Itens")
            bar_options = {
                "xAxis": {"type": "category", "data": consolidado[c_nome].tolist()},
                "yAxis": {"type": "value"},
                "series": [{"data": consolidado[c_val].tolist(), "type": "bar", "itemStyle": {"color": "#004AAD", "borderRadius": 5}}],
                "tooltip": {"trigger": "axis"}
            }
            st_echarts(options=bar_options, height="400px")
else:
    st.info("Aguardando o senhor carregar as planilhas para iniciar a inteligência.")