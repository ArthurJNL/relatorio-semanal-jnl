import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import plotly.graph_objects as go

# 1. SETUP DA PÁGINA
st.set_page_config(page_title="JNL Dash Pro", page_icon="🛡️", layout="wide")

# --- DESIGN PREMIUM (GLASSMORPHISM) ---
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

# --- TRADUÇÃO DE MESES ---
MESES_PT = {
    1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO",
    7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
}

# --- MOTOR DE INTELIGÊNCIA JNL ---
def formatar_contabil(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def extrair_valor(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    v = str(v).upper().replace('R$', '').replace(' ', '')
    if ',' in v and '.' in v:
        v = v.replace('.', '').replace(',', '.')
    elif ',' in v:
        v = v.replace(',', '.')
    try: return float(v)
    except: return 0.0

def converter_para_data(v):
    return pd.to_datetime(v, errors='coerce')

def processar_excel_hibrido(df):
    blocos = {}
    mes_atual_separador = None
    cabecalho = None
    
    for i, row in df.iterrows():
        valores_preenchidos = [str(x).strip().upper() for x in row.values if pd.notna(x)]
        linha_txt = " ".join(valores_preenchidos)
        
        if len(valores_preenchidos) >= 3 and any(k in linha_txt for k in ['DATA', 'PREVISÃO', 'VALOR', 'A RECEBER', 'RAZÃO SOCIAL']):
            cabecalho = []
            for idx, val in enumerate(row.values):
                if pd.notna(val) and str(val).strip() != "":
                    cabecalho.append(str(val).strip().upper())
                else:
                    cabecalho.append(f"COL_{idx}")
            
            df_dados = df.iloc[i+1:].reset_index(drop=True)
            break
            
    if cabecalho is None: return []

    col_data_idx = next((i for i, c in enumerate(cabecalho) if 'DATA' in c or 'PREVISÃO' in c), None)
    
    for _, row in df_dados.iterrows():
        valores_validos = [str(x).upper() for x in row.values if pd.notna(x)]
        if not valores_validos:
            continue
            
        linha_txt = " ".join(valores_validos)
        
        if 'MÊS:' in linha_txt:
            mes_atual_separador = linha_txt.replace('MÊS:', '').strip()
            continue
        
        if ('DATA' in linha_txt or 'PREVISÃO' in linha_txt) and ('VALOR' in linha_txt or 'A RECEBER' in linha_txt):
            continue
            
        valores_linha = list(row.values)[:len(cabecalho)]
        while len(valores_linha) < len(cabecalho):
            valores_linha.append(None)
            
        nome_mes = mes_atual_separador
        
        if nome_mes is None and col_data_idx is not None and col_data_idx < len(valores_linha):
            dt = converter_para_data(valores_linha[col_data_idx])
            if pd.notnull(dt):
                nome_mes = f"{MESES_PT[dt.month]} / {dt.year}"
        
        if len(valores_validos) <= 2 and col_data_idx is not None and pd.isna(valores_linha[col_data_idx]):
            continue
        
        if nome_mes is None: 
            nome_mes = "SEM DATA"
            
        if nome_mes not in blocos: blocos[nome_mes] = []
        blocos[nome_mes].append(valores_linha)

    return [(m, pd.DataFrame(d, columns=cabecalho)) for m, d in blocos.items()]

# --- INTERFACE SIDEBAR ---
with st.sidebar:
    st.title("🛡️ JNL Intelligence")
    st.markdown("---")
    arquivos = st.file_uploader("Suba as planilhas (Pagar/Receber)", type=["xlsx", "xls"], accept_multiple_files=True)
    st.markdown("---")
    st.subheader("📅 Filtro de Meses")

# --- LÓGICA PRINCIPAL ---
if arquivos:
    todos_os_blocos = []
    meses_disponiveis = []

    for arq in arquivos:
        df_bruto = pd.read_excel(arq, header=None)
        resultados = processar_excel_hibrido(df_bruto)
        for nome_mes, dados in resultados:
            todos_os_blocos.append((nome_mes, dados))
            if nome_mes not in meses_disponiveis:
                meses_disponiveis.append(nome_mes)

    if meses_disponiveis:
        with st.sidebar:
            escolha_meses = st.multiselect("Filtrar meses:", options=sorted(meses_disponiveis), default=meses_disponiveis)
    
    st.markdown("# Painel Estratégico JNL")
    comando_filtro = st.text_input("💬 Buscar por Razão Social ou Descrição...", placeholder="Ex: IMPORPECAS, KS MAQUINAS...")

    resumos_finais = []
    for mes, df_mes in todos_os_blocos:
        if mes in escolha_meses:
            col_v = next((c for c in df_mes.columns if any(k in c for k in ['VALOR', 'A RECEBER'])), None)
            
            prioridades_nome = ['RAZÃO SOCIAL', 'DESCRIÇÃO', 'FORNECEDOR', 'DEVEDOR']
            col_d = None
            for p in prioridades_nome:
                match = next((c for c in df_mes.columns if p in c), None)
                if match:
                    col_d = match
                    break
            
            if not col_d:
                col_d = df_mes.columns[1] if len(df_mes.columns) > 1 else df_mes.columns[0]
            
            if col_v and col_d:
                df_mes[col_v] = df_mes[col_v].apply(extrair_valor)
                df_mes = df_mes.dropna(subset=[col_d])
                df_mes = df_mes[df_mes[col_d].astype(str).str.strip() != ""]
                
                if comando_filtro:
                    df_mes = df_mes[df_mes[col_d].astype(str).str.contains(comando_filtro, case=False, na=False)]
                
                resumos_finais.append(df_mes[[col_d, col_v]])

    if resumos_finais:
        df_total = pd.concat(resumos_finais)
        n_cat, n_val = df_total.columns[0], df_total.columns[1]
        consolidado = df_total.groupby(n_cat)[n_val].sum().reset_index().sort_values(by=n_val, ascending=False)
        
        consolidado = consolidado[consolidado[n_val] > 0]
        
        if not consolidado.empty:
            # --- KPIs ---
            m1, m2, m3 = st.columns(3)
            total_cash = consolidado[n_val].sum()
            m1.metric("Volume Total (Filtrado)", formatar_contabil(total_cash))
            m2.metric("Principal Entidade", consolidado.iloc[0][n_cat])
            m3.metric("Filtro Ativo", f"{len(escolha_meses)} Mês(es)")

            aba_visu, aba_tab = st.tabs(["📊 Gráfico de Ranking", "📋 Tabela Detalhada (Contábil)"])

            with aba_visu:
                st.write("💡 *Exibindo o Top 15 maiores. Use a Câmera no topo do gráfico para salvar a foto.*")
                
                # Prepara os dados para Barras Horizontais (Inverte a ordem para o maior ficar no topo)
                top_15 = consolidado.head(15).sort_values(by=n_val, ascending=True)
                
                bar_options = {
                    "toolbox": {"feature": {"saveAsImage": {"show": True, "title": "Baixar Foto", "pixelRatio": 2}}},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "1%", "right": "12%", "bottom": "1%", "containLabel": True},
                    "xAxis": {"type": "value", "splitLine": {"lineStyle": {"type": "dashed", "color": "#E0E4E8"}}},
                    "yAxis": {
                        "type": "category",
                        "data": top_15[n_cat].tolist(),
                        "axisLabel": {
                            "interval": 0, 
                            "width": 200, 
                            "overflow": "truncate" # Se o nome da empresa for gigante, ele corta com "..."
                        }
                    },
                    "series": [{
                        "type": "bar",
                        "data": top_15[n_val].tolist(),
                        "itemStyle": {"color": "#004AAD", "borderRadius": [0, 8, 8, 0]},
                        "label": {
                            "show": True, 
                            "position": "right", 
                            "formatter": "R$ {c}" # Mostra o valor no final da barra
                        }
                    }]
                }
                # Aumentei a altura para 600px para as barras "respirarem"
                st_echarts(options=bar_options, height="600px")

            with aba_tab:
                st.write("💡 *Use a Câmera acima da tabela para salvar a foto.*")
                tabela_final = consolidado.copy()
                tabela_final[n_val] = tabela_final[n_val].apply(formatar_contabil)
                
                fig_table = go.Figure(data=[go.Table(
                    header=dict(values=[f"<b>{n_cat}</b>", f"<b>{n_val}</b>"], fill_color='#004AAD', align='left', font=dict(color='white')),
                    cells=dict(values=[tabela_final[n_cat], tabela_final[n_val]], fill_color='#F8F9FB', align='left'))
                ])
                fig_table.update_layout(margin=dict(l=0, r=0, b=0, t=0), height=450)
                st.plotly_chart(fig_table, use_container_width=True, config={'modeBarButtonsToAdd': ['toImage']})
        else:
            st.info("Todos os valores encontrados estão zerados para os meses selecionados.")
    else:
        st.warning("⚠️ O sistema não encontrou colunas de Valor/Razão Social válidas nestes meses.")
else:
    st.info("Aguardando o envio da planilha (Pagar ou Receber)...")