import streamlit as st
import pandas as pd
import plotly.express as px
import uuid

# 1. CONFIGURAÇÕES DA PÁGINA (DESIGN WIDE)
st.set_page_config(page_title="Relatórios Semanais JNL", page_icon="📊", layout="wide")

# --- INJEÇÃO DE ESTILO CSS (Aparência Profissional) ---
st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stPlotlyChart { background-color: #ffffff; border-radius: 15px; padding: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    div[data-testid="stExpander"] { border: none !important; box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important; background-color: white !important; border-radius: 10px !important; }
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

st.title("📊 RELATÓRIO SEMANAL JNL")
st.write("Análise estratégica de fluxo de caixa e fornecedores.")

# --- BARRA LATERAL ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3222/3222800.png", width=100) # Ícone decorativo
st.sidebar.header("⚙️ Configurações")
objetivo_global = st.sidebar.selectbox(
    "Foco da Análise",
    ["FORNECEDOR", "DESCRIÇÃO", "CATEGORIA"],
    help="O sistema tentará agrupar os gastos por esta coluna."
)

arquivos_enviados = st.file_uploader(
    "Suba suas planilhas de Controle Geral", 
    type=["xlsx", "xls", "xlsm"], 
    accept_multiple_files=True
)

# --- FUNÇÕES DE INTELIGÊNCIA ---
def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def identificar_tabelas_na_foto(df_bruto):
    """
    Motor que identifica blocos de dados separados por nomes de meses 
    e cabeçalhos DATA/VALOR, conforme o padrão da foto enviada.
    """
    tabelas_finais = []
    bloco_atual = []
    colunas_encontradas = None
    mes_atual = "Geral"

    lista_meses = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 
                   'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

    for _, row in df_bruto.iterrows():
        # Transforma a linha em texto para busca
        linha_texto = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        
        # 1. Detecta se a linha é o título do Mês
        if len(linha_texto.split()) == 1 and any(m in linha_texto for m in lista_meses):
            if bloco_atual and colunas_encontradas:
                df_temp = pd.DataFrame(bloco_atual, columns=colunas_encontradas)
                tabelas_finais.append((mes_atual, df_temp))
                bloco_atual = []
            mes_atual = linha_texto
            continue

        # 2. Detecta a linha de Cabeçalho
        if 'DATA' in linha_texto and 'VALOR' in linha_texto:
            # Salva o que tinha antes caso mude o cabeçalho
            if bloco_atual and colunas_encontradas:
                df_temp = pd.DataFrame(bloco_atual, columns=colunas_encontradas)
                tabelas_finais.append((mes_atual, df_temp))
                bloco_atual = []
            
            # Pega os nomes das colunas exatamente como estão na linha
            colunas_encontradas = [str(x).strip().upper() for x in row.values if pd.notna(x)]
            continue

        # 3. Adiciona dados ao bloco
        if colunas_encontradas and any(pd.notna(x) for x in row.values):
            # Garante que a linha de dados bata com o número de colunas
            dados = list(row.values)[:len(colunas_encontradas)]
            bloco_atual.append(dados)

    # Adiciona o último bloco processado
    if bloco_atual and colunas_encontradas:
        df_temp = pd.DataFrame(bloco_atual, columns=colunas_encontradas)
        tabelas_finais.append((mes_atual, df_temp))

    return tabelas_finais

def extrair_valor_numerico(valor):
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    # Remove símbolos de moeda e trata vírgula/ponto
    v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try: return float(v)
    except: return 0.0

# --- PROCESSAMENTO PRINCIPAL ---
if arquivos_enviados:
    resumos_para_consolidar = []

    for arquivo in arquivos_enviados:
        st.markdown(f"### 📄 Arquivo: `{arquivo.name.upper()}`")
        df_bruto = pd.read_excel(arquivo, header=None)
        
        sub_tabelas = identificar_tabelas_na_foto(df_bruto)
        
        if not sub_tabelas:
            st.warning(f"⚠️ Não identifiquei o padrão DATA/VALOR no arquivo {arquivo.name}.")
            continue

        # Layout em colunas para os gráficos do arquivo atual
        for nome_mes, df_sub in sub_tabelas:
            with st.expander(f"📅 Visualizar dados de {nome_mes}", expanded=True):
                # Localiza colunas de interesse
                col_v = next((c for c in df_sub.columns if 'VALOR' in c), None)
                col_c = next((c for c in df_sub.columns if objetivo_global in c), df_sub.columns[1])

                if col_v and col_c:
                    df_sub[col_v] = df_sub[col_v].apply(extrair_valor_numerico)
                    
                    # Agrupa e gera o gráfico individual
                    resumo = df_sub.groupby(col_c)[col_v].sum().reset_index()
                    resumo = resumo[resumo[col_v] > 0].sort_values(by=col_v, ascending=False)
                    
                    if not resumo.empty:
                        resumos_para_consolidar.append(resumo)
                        
                        c1, c2 = st.columns([0.6, 0.4])
                        with c1:
                            fig = px.bar(resumo, x=col_c, y=col_v, text_auto='.2s',
                                         title=f"Gastos em {nome_mes} por {objetivo_global}",
                                         color=col_v, color_continuous_scale='Blues')
                            st.plotly_chart(fig, use_container_width=True)
                        with c2:
                            st.write(f"**Top {objetivo_global}:**")
                            resumo_formatado = resumo.copy()
                            resumo_formatado[col_v] = resumo_formatado[col_v].apply(formatar_moeda)
                            st.dataframe(resumo_formatado, use_container_width=True, hide_index=True)

    # --- SEÇÃO DE CONSOLIDAÇÃO FINAL ---
    if resumos_para_consolidar:
        st.markdown("---")
        st.header("🏆 VISÃO GERAL ACUMULADA")
        st.write("Aqui somamos todos os meses e arquivos enviados acima.")

        df_total = pd.concat(resumos_para_consolidar)
        nome_cat = df_total.columns[0]
        nome_val = df_total.columns[1]
        
        final = df_total.groupby(nome_cat)[nome_val].sum().reset_index().sort_values(by=nome_val, ascending=False)

        col_pie, col_met = st.columns([0.6, 0.4])
        
        with col_pie:
            fig_pizza = px.pie(final, values=nome_val, names=nome_cat, hole=0.4,
                               title=f"Participação Total por {objetivo_global}")
            st.plotly_chart(fig_pizza, use_container_width=True)
        
        with col_met:
            total_geral = final[nome_val].sum()
            st.metric("VALOR TOTAL PROCESSADO", formatar_moeda(total_geral))
            st.write("**Resumo Consolidado:**")
            final[nome_val] = final[nome_val].apply(formatar_moeda)
            st.table(final.head(10))

else:
    st.info("Aguardando o senhor carregar as planilhas para gerar a mágica!")