import streamlit as st
import pandas as pd
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
    .stMetric, .js-plotly-plot {
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

# --- LÓGICA PRINCIPAL ---
if arquivos:
    todos_os_blocos = []
    
    # 1. Lê todos os arquivos
    for arq in arquivos:
        df_bruto = pd.read_excel(arq, header=None)
        resultados = processar_excel_hibrido(df_bruto)
        for nome_mes, dados in resultados:
            todos_os_blocos.append((nome_mes, dados))

    # 2. Reúne e limpa todos os dados
    resumos_limpos = []
    for mes, df_mes in todos_os_blocos:
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
            df_tmp = df_mes.copy()
            df_tmp[col_v] = df_tmp[col_v].apply(extrair_valor)
            df_tmp[col_data] = pd.to_datetime(df_tmp[col_data], errors='coerce').dt.normalize()
            
            df_tmp[col_d] = df_tmp[col_d].astype(str).str.upper().str.strip()
            df_tmp[col_d] = df_tmp[col_d].replace(r'\s+', ' ', regex=True)
            
            df_tmp = df_tmp[df_tmp[col_d] != ""]
            df_tmp = df_tmp[df_tmp[col_d] != "NAN"]
            df_tmp = df_tmp[df_tmp[col_d] != "NONE"]
            
            df_tmp = df_tmp.rename(columns={col_d: 'ENTIDADE', col_data: 'DATA', col_v: 'VALOR'})
            resumos_limpos.append(df_tmp[['ENTIDADE', 'DATA', 'VALOR']])

    if resumos_limpos:
        df_master = pd.concat(resumos_limpos)
        df_master = df_master.dropna(subset=['DATA'])
        
        if not df_master.empty:
            data_min = df_master['DATA'].min().date()
            data_max = df_master['DATA'].max().date()
            
            with st.sidebar:
                st.subheader("📅 Filtro de Período")
                periodo_selecionado = st.date_input(
                    "Selecione De / Até:",
                    value=(data_min, data_max),
                    min_value=data_min,
                    max_value=data_max,
                    format="DD/MM/YYYY"
                )
            
            if isinstance(periodo_selecionado, tuple) and len(periodo_selecionado) == 2:
                dt_inicio, dt_fim = periodo_selecionado
            elif isinstance(periodo_selecionado, tuple) and len(periodo_selecionado) == 1:
                dt_inicio = dt_fim = periodo_selecionado[0]
            else:
                dt_inicio, dt_fim = data_min, data_max
                
            mask_data = (df_master['DATA'] >= pd.to_datetime(dt_inicio)) & (df_master['DATA'] <= pd.to_datetime(dt_fim))
            df_filtrado = df_master[mask_data]

            st.markdown("# Painel Estratégico JNL")
            comando_filtro = st.text_input("💬 Buscar por Razão Social ou Descrição...", placeholder="Ex: IMPORPECAS, KS MAQUINAS...")
            
            if comando_filtro:
                df_filtrado = df_filtrado[df_filtrado['ENTIDADE'].str.contains(comando_filtro.strip().upper(), case=False, na=False)]

            # --- CÉREBROS DE AGRUPAMENTO ---
            dados_grafico = df_filtrado.groupby('ENTIDADE')['VALOR'].sum().reset_index().sort_values(by='VALOR', ascending=False)
            dados_grafico = dados_grafico[dados_grafico['VALOR'] > 0]
            
            dados_tabela = df_filtrado.groupby(['ENTIDADE', 'DATA'])['VALOR'].sum().reset_index().sort_values(by='DATA', ascending=True)
            dados_tabela = dados_tabela[dados_tabela['VALOR'] > 0]
            
            dados_tabela['STATUS'] = dados_tabela['DATA'].apply(calcular_status_vencimento)
            dados_tabela['DATA'] = dados_tabela['DATA'].dt.strftime('%d/%m/%Y').fillna("-")
            
            if not dados_grafico.empty:
                m1, m2, m3 = st.columns(3)
                total_cash = dados_grafico['VALOR'].sum()
                dias_periodo = (dt_fim - dt_inicio).days + 1
                
                m1.metric("Volume Total (Filtrado)", formatar_contabil(total_cash))
                m2.metric("Principal Entidade", dados_grafico.iloc[0]['ENTIDADE'])
                m3.metric("Período Analisado", f"{dias_periodo} Dia(s)")

                aba_visu, aba_tab = st.tabs(["📊 Gráfico de Ranking", "📋 Tabela Detalhada (Com Vencimentos)"])

                with aba_visu:
                    titulo_customizado = st.text_input(
                        "📝 Título Customizado do Gráfico (Aparecerá na foto baixada):", 
                        value=f"Ranking de Valores ({dt_inicio.strftime('%d/%m/%Y')} até {dt_fim.strftime('%d/%m/%Y')})"
                    )
                    
                    st.write("💡 *Exibindo o Top 15 maiores. Use a Câmera no topo do gráfico para salvar a imagem em SVG (Vetor de Alta Resolução).*")
                    top_15 = dados_grafico.head(15).sort_values(by='VALOR', ascending=True)
                    
                    # CÚPULA DE FORMATAÇÃO: Forçando exatamente 2 casas decimais na escrita
                    text_valores = top_15['VALOR'].apply(lambda x: f"<b>R$ {x:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."))
                    
                    # NOVO GRÁFICO (PLOTLY) PARA GARANTIR PDF/SVG E CASAS DECIMAIS EXATAS
                    fig_bar = go.Figure(go.Bar(
                        x=top_15['VALOR'],
                        y=top_15['ENTIDADE'],
                        orientation='h',
                        marker_color='#111111',
                        text=text_valores,
                        textposition='outside',
                        textfont=dict(color='#111111', family="Inter", size=12)
                    ))

                    fig_bar.update_layout(
                        title=dict(text=titulo_customizado, x=0.5, font=dict(color='#111111', size=18, family="Inter")),
                        xaxis=dict(showgrid=True, gridcolor='#E0E4E8', showticklabels=False), # Esconde números do rodapé para ficar limpo
                        yaxis=dict(tickfont=dict(color='#1A1C1E', size=11)),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        margin=dict(l=0, r=90, t=60, b=0), # Margem direita maior para caber as 2 casas decimais
                        height=600
                    )

                    st.plotly_chart(fig_bar, use_container_width=True, config={
                        'modeBarButtonsToAdd': ['toImage'],
                        'toImageButtonOptions': {'format': 'svg', 'filename': 'Ranking_JNL_Dash'}
                    })

                with aba_tab:
                    st.write("💡 *A tabela lista cada vencimento separadamente. Use a Câmera acima da tabela para salvar.*")
                    tabela_final = dados_tabela.copy()
                    tabela_final['VALOR'] = tabela_final['VALOR'].apply(formatar_contabil)
                    
                    fig_table = go.Figure(data=[go.Table(
                        header=dict(
                            values=["<b>RAZÃO SOCIAL / DESCRIÇÃO</b>", "<b>DATA</b>", "<b>VALOR</b>", "<b>SITUAÇÃO</b>"], 
                            fill_color='#111111', align='left', font=dict(color='white', size=13) 
                        ),
                        cells=dict(
                            values=[tabela_final['ENTIDADE'], tabela_final['DATA'], tabela_final['VALOR'], tabela_final['STATUS']], 
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
                    st.plotly_chart(fig_table, use_container_width=True, config={
                        'modeBarButtonsToAdd': ['toImage'],
                        'toImageButtonOptions': {'format': 'svg', 'filename': 'Tabela_JNL_Dash'}
                    })
            else:
                st.info("Todos os valores encontrados estão zerados no período selecionado.")
        else:
            st.warning("⚠️ Nenhuma data válida encontrada no arquivo. Verifique a coluna de datas.")
else:
    st.info("Aguardando o envio da planilha (Pagar ou Receber)...")