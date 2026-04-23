import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import plotly.graph_objects as go
import uuid

# 1. SETUP DA PÁGINA (ESTILO PRETTYMAPP / GLASSMORPHISM)
st.set_page_config(page_title="JNL Dash Pro", page_icon="🛡️", layout="wide")

# --- DESIGN PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #F8F9FB; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E4E8; }
    .stMetric, .echarts-container, .js-plotly-plot {
        background: white !important;
        border: 1px solid #E0E4E8 !important;
        border-radius: 15px !important;
        padding: 10px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    }
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE INTELIGÊNCIA JNL ---
def formatar_contabil(valor):
    """ Transforma número em string formato contábil R$ 1.234,56 """
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def extrair_valor(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    v = str(v).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try: return float(v)
    except: return 0.0

def processar_excel_jnl(df):
    blocos_detectados = []
    mes_atual = None
    cabecalho = None
    dados_temporarios = []
    lista_meses = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

    for _, row in df.iterrows():
        linha_limpa = [str(x).strip().upper() for x in row.values if pd.notna(x)]
        texto_linha = " ".join(linha_limpa)

        if 'MÊS:' in texto_linha:
            if mes_atual and dados_temporarios and cabecalho:
                blocos_detectados.append((mes_atual, pd.DataFrame(dados_temporarios, columns=cabecalho)))
                dados_temporarios = []
            mes_atual = texto_linha.replace('MÊS:', '').strip()
            continue

        if 'DATA' in texto_linha and 'VALOR' in texto_linha:
            cabecalho = [str(x).strip().upper() for x in row.values if pd.notna(x)]
            continue

        if mes_atual and cabecalho and any(pd.notna(x) for x in row.values):
            if 'DATA' in texto_linha or 'CONTAS A PAGAR' in texto_linha:
                continue
            linha_dados = list(row.values)[:len(cabecalho)]
            dados_temporarios.append(linha_dados)

    if mes_atual and dados_temporarios and cabecalho:
        blocos_detectados.append((mes_atual, pd.DataFrame(dados_temporarios, columns=cabecalho)))
    return blocos_detectados

# --- INTERFACE SIDEBAR ---
with st.sidebar:
    st.title("🛡️ JNL Intelligence")
    st.markdown("---")
    arquivos = st.file_uploader("Suba as planilhas (Ex: TESTE.xlsx)", type=["xlsx", "xls"], accept_multiple_files=True)
    st.markdown("---")
    st.subheader("📅 Filtro Temporal")
    espaco_filtro_meses = st.empty()

# --- LÓGICA PRINCIPAL ---
if arquivos:
    todos_os_blocos = []
    meses_disponiveis = []

    for arq in arquivos:
        df_bruto = pd.read_excel(arq, header=None)
        resultados = processar_excel_jnl(df_bruto)
        for nome_mes, dados in resultados:
            todos_os_blocos.append((nome_mes, dados))
            if nome_mes not in meses_disponiveis:
                meses_disponiveis.append(nome_mes)

    if meses_disponiveis:
        with st.sidebar:
            escolha_meses = st.multiselect("Selecione os meses:", options=meses_disponiveis, default=meses_disponiveis)
    
    st.markdown("# Painel Estratégico JNL")
    comando_filtro = st.text_input("💬 Buscar Fornecedor ou Item...", placeholder="Ex: Grillo, Aluguel, Itaú...")

    resumos_finais = []
    for mes, df_mes in todos_os_blocos:
        if mes in escolha_meses:
            col_v = next((c for c in df_mes.columns if 'VALOR' in c), None)
            col_d = next((c for c in df_mes.columns if any(x in c for x in ['DESCRIÇÃO', 'DEVEDOR', 'FORNECEDOR'])), df_mes.columns[1])
            
            if col_v and col_d:
                df_mes[col_v] = df_mes[col_v].apply(extrair_valor)
                if comando_filtro:
                    df_mes = df_mes[df_mes[col_d].astype(str).str.contains(comando_filtro, case=False, na=False)]
                resumos_finais.append(df_mes[[col_d, col_v]])

    if resumos_finais:
        df_total = pd.concat(resumos_finais)
        nome_cat = df_total.columns[0]
        nome_val = df_total.columns[1]
        consolidado = df_total.groupby(nome_cat)[nome_val].sum().reset_index().sort_values(by=nome_val, ascending=False)
        
        # --- KPIs ---
        m1, m2, m3 = st.columns(3)
        total_cash = consolidado[nome_val].sum()
        m1.metric("Total Acumulado", formatar_contabil(total_cash))
        m2.metric("Maior Despesa", consolidado.iloc[0][nome_cat] if not consolidado.empty else "-")
        m3.metric("Meses Ativos", len(escolha_meses))

        aba_visu, aba_tab = st.tabs(["📊 Gráfico Interativo", "📋 Tabela Detalhada (Contábil)"])

        with aba_visu:
            st.write("💡 *Passe o mouse no gráfico e clique na Câmera no canto superior para baixar como foto.*")
            donut_options = {
                "toolbox": {
                    "show": True,
                    "feature": {"saveAsImage": {"show": True, "title": "Baixar Foto", "pixelRatio": 2}}
                },
                "tooltip": {"trigger": "item"},
                "series": [{
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "itemStyle": {"borderRadius": 10, "borderColor": "#fff", "borderWidth": 2},
                    "label": {"show": True, "formatter": "{b}: {c}"},
                    "data": [{"value": row[nome_val], "name": row[nome_cat]} for _, row in consolidado.iterrows()]
                }]
            }
            st_echarts(options=donut_options, height="550px")

        with aba_tab:
            st.write("💡 *Use o ícone de Câmera acima da tabela para baixar esta lista como foto.*")
            
            # Formatação para exibição
            tabela_final = consolidado.copy()
            tabela_final[nome_val] = tabela_final[nome_val].apply(formatar_contabil)
            
            # Criando Tabela via Plotly para permitir download como foto
            fig_table = go.Figure(data=[go.Table(
                header=dict(values=[f"<b>{nome_cat}</b>", f"<b>{nome_val}</b>"],
                            fill_color='#004AAD', align='left', font=dict(color='white', size=12)),
                cells=dict(values=[tabela_final[nome_cat], tabela_final[nome_val]],
                           fill_color='#F8F9FB', align='left', font=dict(size=12)))
            ])
            fig_table.update_layout(margin=dict(l=0, r=0, b=0, t=0), height=450)
            st.plotly_chart(fig_table, use_container_width=True, config={'displaylogo': False, 'modeBarButtonsToAdd': ['toImage']})

    else:
        st.warning("⚠️ Selecione ao menos um mês para exibir os dados.")
else:
    st.info("Aguardando o envio da planilha...")