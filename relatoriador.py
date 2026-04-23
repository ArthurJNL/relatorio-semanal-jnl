import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import plotly.graph_objects as go
from datetime import datetime

# 1. SETUP DA PÁGINA (LIGHT MODE MINIMALISTA)
st.set_page_config(page_title="JNL Dash Pro", page_icon="🛡️", layout="wide")

# --- DESIGN PREMIUM CLEAN (B&W) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Fundos Claros e Limpos */
    .main { background-color: #F8F9FB; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E4E8; }
    
    /* Cartões, Gráficos e Tabelas (Efeito Vidro Claro) */
    .stMetric, .echarts-container, .js-plotly-plot {
        background: white !important;
        border: 1px solid #E0E4E8 !important;
        border-radius: 15px !important;
        padding: 10px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    }
    
    /* Ajuste da Barra de Pesquisa (Borda Preta ao invés de azul) */
    .stTextInput > div > div > input {
        border-radius: 12px;
        border: 1px solid #D0D5DD;
        padding: 12px 20px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #000000;
        box-shadow: 0 0 0 1px #000000;
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

# --- O ROBÔ DO TEMPO (Cálculo de Vencimento) ---
HOJE = pd.to_datetime('today').normalize()

def calcular_status_vencimento(data_alvo):
    if pd.isnull(data_alvo) or str(data_alvo).strip() == "-":
        return "-"
    
    # Tratamento caso a data venha como string do pandas
    if isinstance(data_alvo, str):
        try:
            data_alvo = pd.to_datetime(data_alvo, format='%d/%m/%Y')
        except:
            return "-"

    dias_diferenca = (data_alvo - HOJE).days
    
    if dias_diferenca < 0:
        return f"🚨 Vencido há {abs(dias_diferenca)} dias"
    elif dias_diferenca == 0:
        return "⚠️ Vence HOJE"
    else:
        return f"✅ Vence em {dias_diferenca} dias"

# --- PROCESSADOR DE EXCEL ---
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
        if not valores_validos: continue
            
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
        
        if nome_mes is None: nome_mes = "SEM DATA"
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
            col_data = next((c for c in df_mes.columns if any(k in c for k in ['DATA', 'PREVISÃO'])), None)
            
            prioridades_nome = ['RAZÃO SOCIAL', 'DESCRIÇÃO', 'FORNECEDOR', 'DEVEDOR']
            col_d = None
            for p in prioridades_nome:
                match = next((c for c in df_mes.columns if p in c), None)
                if match:
                    col_d = match
                    break
            
            if not col_d:
                col_d = df_mes.columns[1] if len(df_mes.columns) > 1 else df_mes.columns[0]
            
            if col_v and col_d and col_data:
                # Tratamento de Valor e Data
                df_mes[col_v] = df_mes[col_v].apply(extrair_valor)
                df_mes[col_data] = pd.to_datetime(df_mes[col_data], errors='coerce').dt.normalize()
                
                # Tratamento de Nomes (Limpeza)
                df_mes[col_d] = df_mes[col_d].astype(str).str.upper().str.strip()
                df_mes[col_d] = df_mes[col_d].replace(r'\s+', ' ', regex=True)
                
                df_mes = df_mes[df_mes[col_d] != ""]
                df_mes = df_mes[df_mes[col_d] != "NAN"]
                df_mes = df_mes[df_mes[col_d] != "NONE"]
                
                if comando_filtro:
                    df_mes = df_mes[df_mes[col_d].str.contains(comando_filtro.strip().upper(), case=False, na=False)]
                
                # Salva o bloco mantendo a coluna de DATA
                resumos_finais.append(df_mes[[col_d, col_data, col_v]])

    if resumos_finais:
        df_total = pd.concat(resumos_finais)
        n_cat = df_total.columns[0]
        n_data = df_total.columns[1]
        n_val = df_total.columns[2]
        
        # --- CÉREBRO 1: O GRÁFICO (Agrupa apenas por nome da Empresa) ---
        dados_grafico = df_total.groupby(n_cat)[n_val].sum().reset_index().sort_values(by=n_val, ascending=False)
        dados_grafico = dados_grafico[dados_grafico[n_val] > 0]
        
        # --- CÉREBRO 2: A TABELA DETALHADA (Agrupa por Empresa + Data) ---
        dados_tabela = df_total.groupby([n_cat, n_data])[n_val].sum().reset_index().sort_values(by=n_data, ascending=True)
        dados_tabela = dados_tabela[dados_tabela[n_val] > 0]
        
        # Formata a data e calcula Status
        dados_tabela['STATUS'] = dados_tabela[n_data].apply(calcular_status_vencimento)
        dados_tabela[n_data] = dados_tabela[n_data].dt.strftime('%d/%m/%Y').fillna("-")
        
        if not dados_grafico.empty:
            m1, m2, m3 = st.columns(3)
            total_cash = dados_grafico[n_val].sum()
            m1.metric("Volume Total (Filtrado)", formatar_contabil(total_cash))
            m2.metric("Principal Entidade", dados_grafico.iloc[0][n_cat])
            m3.metric("Filtro Ativo", f"{len(escolha_meses)} Mês(es)")

            aba_visu, aba_tab = st.tabs(["📊 Gráfico de Ranking", "📋 Tabela Detalhada (Com Vencimentos)"])

            with aba_visu:
                st.write("💡 *Exibindo o Top 15 maiores. Use a Câmera no topo do gráfico para salvar a foto.*")
                top_15 = dados_grafico.head(15).sort_values(by=n_val, ascending=True)
                
                bar_options = {
                    "backgroundColor": "transparent",
                    "toolbox": {"feature": {"saveAsImage": {"show": True, "title": "Baixar Foto", "pixelRatio": 2}}},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "1%", "right": "12%", "bottom": "1%", "containLabel": True},
                    "xAxis": {
                        "type": "value", 
                        "splitLine": {"lineStyle": {"type": "dashed", "color": "#E0E4E8"}}
                    },
                    "yAxis": {
                        "type": "category",
                        "data": top_15[n_cat].tolist(),
                        "axisLabel": {"interval": 0, "width": 200, "overflow": "truncate", "color": "#1A1C1E"}
                    },
                    "series": [{
                        "type": "bar",
                        "data": top_15[n_val].tolist(),
                        "itemStyle": {"color": "#111111", "borderRadius": [0, 8, 8, 0]}, # GRÁFICO PRETO
                        "label": {"show": True, "position": "right", "formatter": "R$ {c}", "color": "#111111"}
                    }]
                }
                st_echarts(options=bar_options, height="600px")

            with aba_tab:
                st.write("💡 *A tabela lista cada vencimento separadamente. Use a Câmera acima da tabela para salvar.*")
                tabela_final = dados_tabela.copy()
                tabela_final[n_val] = tabela_final[n_val].apply(formatar_contabil)
                
                # Montando a Tabela Plotly Light Mode + Black Accent (Ordem: Nome | Data | Valor | Status)
                fig_table = go.Figure(data=[go.Table(
                    header=dict(
                        values=[f"<b>{n_cat}</b>", f"<b>{n_data}</b>", f"<b>{n_val}</b>", "<b>SITUAÇÃO</b>"], 
                        fill_color='#111111', align='left', font=dict(color='white', size=13) # CABEÇALHO PRETO
                    ),
                    cells=dict(
                        values=[tabela_final[n_cat], tabela_final[n_data], tabela_final[n_val], tabela_final['STATUS']], 
                        fill_color='#F8F9FB', align='left', font=dict(color='#1A1C1E', size=12),
                        height=30
                    ))
                ])
                fig_table.update_layout(
                    margin=dict(l=0, r=0, b=0, t=0), 
                    height=500,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_table, use_container_width=True, config={'modeBarButtonsToAdd': ['toImage']})
        else:
            st.info("Todos os valores encontrados estão zerados para os meses selecionados.")
    else:
        st.warning("⚠️ O sistema não encontrou dados válidos. Verifique se o arquivo tem Data, Razão Social e Valor.")
else:
    st.info("Aguardando o envio da planilha (Pagar ou Receber)...")