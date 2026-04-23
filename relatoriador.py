import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import uuid

# 1. SETUP DA PÁGINA (ESTILO PRETTYMAPP)
st.set_page_config(page_title="JNL Dash Pro", page_icon="📈", layout="wide")

# --- CSS DE ALTO NÍVEL (GLASSMORPHISM & CLEAN DESIGN) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #F8F9FB; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E4E8; }
    .stMetric, .echarts-container, div[data-testid="stExpander"] {
        background: white !important;
        border: 1px solid #E0E4E8 !important;
        border-radius: 15px !important;
        padding: 20px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    }
    .stTextInput > div > div > input { border-radius: 12px; border: 1px solid #D0D5DD; padding: 12px 20px; }
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE DADOS ---
def extrair_valor(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    v = str(v).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try: return float(v)
    except: return 0.0

def processar_excel(df):
    tabelas = []
    mes_atual = "GERAL"
    cabecalho = None
    dados_acumulados = []
    lista_meses = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

    for _, row in df.iterrows():
        linha_txt = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        
        # Detecta Título do Mês
        if len(linha_txt.split()) == 1 and any(m in linha_txt for m in lista_meses):
            if dados_acumulados and cabecalho:
                tabelas.append((mes_atual, pd.DataFrame(dados_acumulados, columns=cabecalho)))
            mes_atual = linha_txt
            dados_acumulados = []
            continue
            
        # Detecta Cabeçalho DATA/VALOR
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

# --- ÁREA DE UPLOAD E SIDEBAR ---
with st.sidebar:
    st.title("🛡️ JNL Control")
    st.markdown("---")
    st.subheader("📁 Upload de Dados")
    arquivos = st.file_uploader("Suba as planilhas aqui", type=["xlsx", "xls"], accept_multiple_files=True)
    st.markdown("---")
    
    # Placeholder para o filtro de meses (será preenchido após o processamento)
    st.subheader("📅 Filtrar por Mês")
    meses_selecionados = []

# --- LÓGICA PRINCIPAL ---
if arquivos:
    todos_os_blocos = []
    lista_meses_encontrados = []
    
    # 1. Primeiro passo: Ler tudo para descobrir quais meses existem
    for arq in arquivos:
        df_raw = pd.read_excel(arq, header=None)
        blocos = processar_excel(df_raw)
        for mes, df_mes in blocos:
            todos_os_blocos.append((mes, df_mes))
            if mes not in lista_meses_encontrados:
                lista_meses_encontrados.append(mes)
    
    # 2. Criar o filtro na Sidebar com os meses reais encontrados
    with st.sidebar:
        meses_selecionados = st.multiselect(
            "Selecione um ou mais meses:",
            options=lista_meses_encontrados,
            default=lista_meses_encontrados # Por padrão, todos vêm marcados
        )
    
    st.markdown(f"# Relatório Semanal JNL")
    comando_nlu = st.text_input("💬 Filtrar por nome ou descrição...", placeholder="Ex: 'Hyundai' ou 'Pagamento luz'")

    # 3. Filtrar os dados com base na seleção do usuário
    lista_resumos = []
    for mes, df_mes in todos_os_blocos:
        if mes in meses_selecionados:
            col_v = next((c for c in df_mes.columns if 'VALOR' in c), None)
            col_d = next((c for c in df_mes.columns if 'FORNECEDOR' in c or 'DESCRIÇÃO' in c or 'ITEM' in c), df_mes.columns[1])
            
            if col_v and col_d:
                df_mes[col_v] = df_mes[col_v].apply(extrair_valor)
                if comando_nlu:
                    df_mes = df_mes[df_mes[col_d].str.contains(comando_nlu, case=False, na=False)]
                
                resumo = df_mes.groupby(col_d)[col_v].sum().reset_index()
                lista_resumos.append(resumo)

    if lista_resumos:
        df_final = pd.concat(lista_resumos)
        c_nome = df_final.columns[0]
        c_val = df_final.columns[1]
        consolidado = df_final.groupby(c_nome)[c_val].sum().reset_index().sort_values(by=c_val, ascending=False)
        
        # --- KPIs ---
        m1, m2, m3 = st.columns(3)
        total_geral = consolidado[c_val].sum()
        m1.metric("Valor Total (Selecionado)", f"R$ {total_geral:,.2f}")
        m2.metric("Principal Credor", consolidado.iloc[0][c_nome] if not consolidado.empty else "N/A")
        m3.metric("Meses Ativos", len(meses_selecionados))

        # --- ABAS ---
        aba_grafico, aba_dados = st.tabs(["📊 Gráfico de Distribuição", "📋 Tabela de Valores"])

        with aba_grafico:
            pizza_options = {
                "tooltip": {"trigger": "item"},
                "series": [
                    {
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "itemStyle": {"borderRadius": 10, "borderColor": "#fff", "borderWidth": 2},
                        "label": {"show": True, "formatter": "{b}: R${c}"},
                        "data": [{"value": row[c_val], "name": row[c_nome]} for _, row in consolidado.iterrows()],
                    }
                ],
            }
            st_echarts(options=pizza_options, height="500px")

        with aba_dados:
            consolidado_show = consolidado.copy()
            consolidado_show[c_val] = consolidado_show[c_val].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(consolidado_show, use_container_width=True, hide_index=True)
    else:
        st.warning("Selecione ao menos um mês na barra lateral para visualizar os dados.")
else:
    st.info("Aguardando o senhor subir a planilha para processar os meses...")