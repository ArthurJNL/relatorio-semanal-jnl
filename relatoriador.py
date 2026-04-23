import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import uuid

# 1. CONFIGURAÇÕES DE ALTA PERFORMANCE
st.set_page_config(page_title="JNL Intelligence | NLU Dashboard", page_icon="📈", layout="wide")

# --- DESIGN PREMIUM (CSS CUSTOMIZADO) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    
    .main { background-color: #f4f7f9; }
    /* Estilo para as caixas de Gráfico (ECharts Container) */
    .stPlotlyChart, .echarts-container { 
        background: white; border-radius: 20px; padding: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #eef2f6;
    }
    /* Estilo "NLU Command" */
    .stTextInput > div > div > input {
        background-color: #ffffff; border-radius: 50px; border: 2px solid #004AAD;
        padding: 20px; font-size: 18px; color: #004AAD;
    }
    .stMetric { background: white; border-radius: 15px; padding: 15px; border-left: 5px solid #004AAD; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER NLU STYLE ---
st.image("https://cdn-icons-png.flaticon.com/512/2103/2103633.png", width=60)
st.title("🛡️ JNL INTELLIGENCE ENGINE")
st.write("Análise de Dados com motor de compreensão visual.")

# --- BARRA DE COMANDO NLU (Vibe JohnSnowLabs) ---
comando_nlu = st.text_input("💬 O que deseja analisar hoje?", placeholder="Ex: Analisar fornecedores de Março / Filtrar gastos acima de R$ 500")

# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.header("⚙️ ENGINE SETTINGS")
    tema_grafico = st.selectbox("Estilo dos Gráficos", ["light", "dark"])
    meta_orcamento = st.number_input("Meta de Gastos Semanal (R$)", value=5000)
    st.markdown("---")
    arquivos = st.file_uploader("📂 Importar Planilhas", type=["xlsx", "xls"], accept_multiple_files=True)

# --- FUNÇÕES DE LIMPEZA JNL ---
def extrair_valor_numerico(valor):
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try: return float(v)
    except: return 0.0

def identificar_blocos(df):
    blocos = []
    temp_dados = []
    mes_atual = "Geral"
    cabecalho = None
    
    for _, row in df.iterrows():
        linha_txt = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        
        # Detecta Mês
        if len(linha_txt.split()) == 1 and any(m in linha_txt for m in ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO']):
            if temp_dados and cabecalho:
                blocos.append((mes_atual, pd.DataFrame(temp_dados, columns=cabecalho)))
            mes_atual = linha_txt
            temp_dados = []
            continue
            
        # Detecta Cabeçalho
        if 'DATA' in linha_txt and 'VALOR' in linha_txt:
            if temp_dados and cabecalho:
                blocos.append((mes_atual, pd.DataFrame(temp_dados, columns=cabecalho)))
            cabecalho = [str(x).strip().upper() for x in row.values if pd.notna(x)]
            temp_dados = []
            continue
            
        if cabecalho and any(pd.notna(x) for x in row.values):
            temp_dados.append(list(row.values)[:len(cabecalho)])
            
    if temp_dados and cabecalho:
        blocos.append((mes_atual, pd.DataFrame(temp_dados, columns=cabecalho)))
    return blocos

# --- DASHBOARD ENGINE ---
if arquivos:
    all_data = []
    
    for arq in arquivos:
        df_bruto = pd.read_excel(arq, header=None)
        blocos = identificar_blocos(df_bruto)
        
        for nome_mes, df_mes in blocos:
            st.markdown(f"### 📊 Dashboard: {nome_mes}")
            
            # Limpeza e Filtro NLU
            col_v = next((c for c in df_mes.columns if 'VALOR' in c), None)
            col_d = next((c for c in df_mes.columns if 'DESCRIÇÃO' in c or 'FORNECEDOR' in c), df_mes.columns[1])
            
            if col_v and col_d:
                df_mes[col_v] = df_mes[col_v].apply(extrair_valor_numerico)
                
                # Simulação de NLU: Se o usuário digitar um nome, o gráfico filtra na hora!
                if comando_nlu:
                    df_mes = df_mes[df_mes[col_d].str.contains(comando_nlu, case=False, na=False)]

                resumo = df_mes.groupby(col_d)[col_v].sum().reset_index().sort_values(by=col_v, ascending=True)
                
                # --- ECHARTS BAR CHART (Vibe Streamlit-ECharts) ---
                options = {
                    "title": {"text": f"Distribuição em {nome_mes}", "left": "center"},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                    "xAxis": {"type": "value", "boundaryGap": [0, 0.01]},
                    "yAxis": {"type": "category", "data": resumo[col_d].tolist()},
                    "series": [
                        {
                            "name": "Total Gasto",
                            "type": "bar",
                            "data": resumo[col_v].tolist(),
                            "itemStyle": {"color": "#004AAD", "borderRadius": [0, 10, 10, 0]},
                            "label": {"show": True, "position": "right", "formatter": 'R$ {c}'}
                        }
                    ],
                }
                
                st_echarts(options=options, height="400px")
                all_data.append(resumo)

    # --- CONSOLIDAÇÃO FINAL (PIZZA ECHARTS) ---
    if all_data:
        st.markdown("---")
        st.header("🏆 INTELLIGENCE CONSOLIDATED")
        
        df_final = pd.concat(all_data)
        col_cat = df_final.columns[0]
        col_val = df_final.columns[1]
        consolidado = df_final.groupby(col_cat)[col_val].sum().reset_index()
        
        # Prepara dados para o Gráfico de Pizza do ECharts
        pizza_data = [{"value": row[col_val], "name": row[col_cat]} for _, row in consolidado.iterrows()]
        
        c1, c2 = st.columns([0.6, 0.4])
        with c1:
            option_pizza = {
                "tooltip": {"trigger": "item"},
                "legend": {"top": "5%", "left": "center"},
                "series": [
                    {
                        "name": "Volume Total",
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "avoidLabelOverlap": False,
                        "itemStyle": {"borderRadius": 10, "borderColor": "#fff", "borderWidth": 2},
                        "label": {"show": False, "position": "center"},
                        "emphasis": {"label": {"show": True, "fontSize": "20", "fontWeight": "bold"}},
                        "labelLine": {"show": False},
                        "data": pizza_data,
                    }
                ],
            }
            st_echarts(options=option_pizza, height="500px")
        
        with c2:
            total = consolidado[col_val].sum()
            st.metric("GASTO TOTAL ACUMULADO", f"R$ {total:,.2f}")
            if total > meta_orcamento:
                st.error(f"🚨 Atenção: Gastos superaram a meta de R$ {meta_orcamento:,.2f}")
            else:
                st.success("✅ Dentro da meta semanal.")
            st.write("**Top Fornecedores:**")
            st.table(consolidado.sort_values(by=col_val, ascending=False).head(5))

else:
    st.info("Aguardando o upload das planilhas para processar o relatório semanal.")