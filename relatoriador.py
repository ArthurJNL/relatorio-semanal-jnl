import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
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
    .stMetric, .echarts-container, div[data-testid="stExpander"] {
        background: white !important;
        border: 1px solid #E0E4E8 !important;
        border-radius: 15px !important;
        padding: 20px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    }
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE INTELIGÊNCIA JNL ---
def extrair_valor(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    v = str(v).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try: return float(v)
    except: return 0.0

def processar_excel_jnl(df):
    """
    Motor customizado para o padrão JNL: 
    Detecta 'MÊS: NOME / ANO' e agrupa os dados seguintes.
    """
    blocos_detectados = []
    mes_atual = None
    cabecalho = None
    dados_temporarios = []

    for _, row in df.iterrows():
        # Transforma a linha em string para análise de padrão
        linha_limpa = [str(x).strip().upper() for x in row.values if pd.notna(x)]
        texto_linha = " ".join(linha_limpa)

        # 1. Detecta o Separador de Mês (Ex: MÊS: MARÇO / 2026)
        if 'MÊS:' in texto_linha:
            # Se já vínhamos processando um mês, salva o anterior antes de mudar
            if mes_atual and dados_temporarios and cabecalho:
                blocos_detectados.append((mes_atual, pd.DataFrame(dados_temporarios, columns=cabecalho)))
                dados_temporarios = []
            
            # Extrai o nome do mês (ex: MARÇO / 2026)
            mes_atual = texto_linha.replace('MÊS:', '').strip()
            continue

        # 2. Detecta a linha de Cabeçalho (DATA, DESCRIÇÃO...)
        if 'DATA' in texto_linha and 'VALOR' in texto_linha:
            cabecalho = [str(x).strip().upper() for x in row.values if pd.notna(x)]
            continue

        # 3. Se temos um mês e um cabeçalho, a linha atual é dado bruto
        if mes_atual and cabecalho and any(pd.notna(x) for x in row.values):
            # Ignora linhas que repetem o cabeçalho ou o título
            if 'DATA' in texto_linha or 'CONTAS A PAGAR' in texto_linha:
                continue
            
            linha_dados = list(row.values)[:len(cabecalho)]
            dados_temporarios.append(linha_dados)

    # Adiciona o último bloco processado
    if mes_atual and dados_temporarios and cabecalho:
        blocos_detectados.append((mes_atual, pd.DataFrame(dados_temporarios, columns=cabecalho)))
    
    return blocos_detectados

# --- INTERFACE SIDEBAR ---
with st.sidebar:
    st.title("🛡️ JNL Intelligence")
    st.markdown("---")
    st.subheader("📁 Importação")
    arquivos = st.file_uploader("Suba o arquivo TESTE.xlsx", type=["xlsx", "xls"], accept_multiple_files=True)
    st.markdown("---")
    st.subheader("📅 Filtro Temporal")
    # Placeholder que será preenchido após leitura
    espaco_filtro_meses = st.empty()

# --- LÓGICA PRINCIPAL ---
if arquivos:
    todos_os_blocos = []
    meses_disponiveis = []

    # Passo 1: Varredura total para identificar os meses
    for arq in arquivos:
        df_bruto = pd.read_excel(arq, header=None)
        resultados = processar_excel_jnl(df_bruto)
        for nome_mes, dados in resultados:
            todos_os_blocos.append((nome_mes, dados))
            if nome_mes not in meses_disponiveis:
                meses_disponiveis.append(nome_mes)

    # Passo 2: Criar o filtro dinâmico
    if meses_disponiveis:
        with st.sidebar:
            escolha_meses = st.multiselect(
                "Quais meses deseja analisar?",
                options=meses_disponiveis,
                default=meses_disponiveis
            )
    
    # Passo 3: Filtrar e Consolidar
    st.markdown("# Painel Estratégico JNL")
    comando_filtro = st.text_input("💬 Filtrar por Fornecedor ou Item...", placeholder="Ex: Grillo, Itau, Aluguel...")

    resumos_finais = []
    for mes, df_mes in todos_os_blocos:
        if mes in escolha_meses:
            # Identifica colunas
            col_v = next((c for c in df_mes.columns if 'VALOR' in c), None)
            col_d = next((c for c in df_mes.columns if 'DESCRIÇÃO' in c or 'DEVEDOR' in c or 'FORNECEDOR' in c), df_mes.columns[1])
            
            if col_v and col_d:
                df_mes[col_v] = df_mes[col_v].apply(extrair_valor)
                
                # Filtro de texto (NLU)
                if comando_filtro:
                    mask = df_mes[col_d].astype(str).str.contains(comando_filtro, case=False, na=False)
                    df_mes = df_mes[mask]
                
                resumos_finais.append(df_mes[[col_d, col_v]])

    if resumos_finais:
        df_total = pd.concat(resumos_finais)
        nome_cat = df_total.columns[0]
        nome_val = df_total.columns[1]
        consolidado = df_total.groupby(nome_cat)[nome_val].sum().reset_index().sort_values(by=nome_val, ascending=False)
        
        # --- EXIBIÇÃO ---
        m1, m2, m3 = st.columns(3)
        total_cash = consolidado[nome_val].sum()
        m1.metric("Total no Período", f"R$ {total_cash:,.2f}")
        m2.metric("Maior Despesa", consolidado.iloc[0][nome_cat] if not consolidado.empty else "-")
        m3.metric("Meses em Análise", len(escolha_meses))

        aba_visu, aba_tab = st.tabs(["📊 Gráfico Interativo", "📋 Tabela Detalhada"])

        with aba_visu:
            # Gráfico de Rosca (ECharts)
            donut_options = {
                "tooltip": {"trigger": "item"},
                "legend": {"show": False},
                "series": [{
                    "name": "Valor Pago",
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "avoidLabelOverlap": False,
                    "itemStyle": {"borderRadius": 10, "borderColor": "#fff", "borderWidth": 2},
                    "label": {"show": True, "formatter": "{b}: R${c}"},
                    "data": [{"value": row[nome_val], "name": row[nome_cat]} for _, row in consolidado.iterrows()]
                }]
            }
            st_echarts(options=donut_options, height="500px")

        with aba_tab:
            st.dataframe(consolidado, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Selecione ao menos um mês na barra lateral para carregar os gráficos.")

else:
    st.info("Aguardando o envio da planilha para mapear os meses (Março, Abril...).")