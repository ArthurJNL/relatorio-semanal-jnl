import streamlit as st
import pandas as pd
import plotly.express as px
import uuid

# 1. CONFIGURAÇÕES DA PÁGINA
st.set_page_config(page_title="Relatórios Semanais JNL", page_icon="📊", layout="wide")

st.title("📊 RELATÓRIO SEMANAL JNL")
st.write("Transformando planilhas visuais em decisões estratégicas.")

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Filtros do Relatório")
objetivo_global = st.sidebar.selectbox(
    "O que analisar nos gráficos?",
    ["Fornecedor", "Descrição", "Mês"],
    help="O robô buscará essas colunas para agrupar os valores."
)

arquivos_enviados = st.file_uploader(
    "Carregue suas planilhas (Ex: Controle Geral 2026)", 
    type=["xlsx", "xls", "xlsm"], 
    accept_multiple_files=True
)

# --- MOTOR DE INTELIGÊNCIA ---
def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def processar_planilha_visual(df_bruto):
    """
    Identifica sub-tabelas baseadas na presença de cabeçalhos (DATA, DESCRIÇÃO, VALOR).
    """
    tabelas_detectadas = []
    bloco_atual = []
    colunas_referencia = None
    nome_do_bloco = "Geral"

    for _, row in df_bruto.iterrows():
        linha_str = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        
        # Detecta se a linha é um Título de Mês (ex: MARÇO, ABRIL)
        if len(linha_str.split()) == 1 and any(m in linha_str for m in ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']):
            nome_do_bloco = linha_str
            continue

        # Detecta o Cabeçalho (DATA, DESCRIÇÃO, VALOR)
        if 'DATA' in linha_str and 'VALOR' in linha_str:
            if bloco_atual: # Salva o bloco anterior se existir
                df_temp = pd.DataFrame(bloco_atual, columns=colunas_referencia)
                tabelas_detectadas.append((nome_do_bloco, df_temp))
                bloco_atual = []
            
            # Limpa os nomes das colunas (remove espaços e sobe para maiúsculo)
            colunas_referencia = [str(x).strip().upper() for x in row.values if pd.notna(x)]
            continue

        # Adiciona dados ao bloco se tivermos um cabeçalho definido
        if colunas_referencia and any(pd.notna(x) for x in row.values):
            # Garante que a linha de dados tenha o mesmo tamanho das colunas
            dados_linha = list(row.values)[:len(colunas_referencia)]
            bloco_atual.append(dados_linha)

    # Adiciona o último bloco
    if bloco_atual and colunas_referencia:
        df_temp = pd.DataFrame(bloco_atual, columns=colunas_referencia)
        tabelas_detectadas.append((nome_do_bloco, df_temp))

    return tabelas_detectadas

def gerar_grafico(df, titulo_grafico, alvo):
    # Limpeza de valores
    col_valor = next((c for c in df.columns if 'VALOR' in str(c).upper()), None)
    col_cat = next((c for c in df.columns if alvo.upper() in str(c).upper()), df.columns[1])

    if col_valor and col_cat:
        # Trata o valor (remove R$, converte pra número)
        df[col_valor] = df[col_valor].replace('[R$,.]', '', regex=True).astype(float) / 100 if df[col_valor].dtype == object else df[col_valor]
        df[col_valor] = pd.to_numeric(df[col_valor], errors='coerce').fillna(0)
        
        resumo = df.groupby(col_cat)[col_valor].sum().reset_index()
        resumo = resumo[resumo[col_valor] > 0].sort_values(by=col_valor, ascending=False)

        if not resumo.empty:
            fig = px.bar(
                resumo, x=col_cat, y=col_valor, 
                title=f"Análise: {titulo_grafico}",
                color=col_valor, color_continuous_scale='Viridis',
                text_auto=True
            )
            st.plotly_chart(fig, use_container_width=True)
            return resumo
    return None

# --- INTERFACE ---
if arquivos_enviados:
    todos_os_resumos = []

    for arquivo in arquivos_enviados:
        st.subheader(f"📂 Arquivo: {arquivo.name}")
        df_excel = pd.read_excel(arquivo, header=None)
        sub_tabelas = processar_planilha_visual(df_excel)

        for nome, df_sub in sub_tabelas:
            with st.expander(f"📊 Detalhamento de {nome}", expanded=True):
                resumo = gerar_grafico(df_sub, nome, objetivo_global)
                if resumo is not None:
                    todos_os_resumos.append(resumo)

    # --- CONSOLIDAÇÃO FINAL ---
    if todos_os_resumos:
        st.markdown("---")
        st.header("🏆 Resultado Consolidado (Tudo Junto)")
        
        df_total = pd.concat(todos_os_resumos)
        # Padroniza nomes para o agrupamento final
        col_cat_final = df_total.columns[0]
        col_val_final = df_total.columns[1]
        
        final_agrupado = df_total.groupby(col_cat_final)[col_val_final].sum().reset_index().sort_values(by=col_val_final, ascending=False)

        c1, c2 = st.columns([0.6, 0.4])
        with c1:
            fig_pizza = px.pie(final_agrupado, values=col_val_final, names=col_cat_final, title="Participação no Total", hole=0.5)
            st.plotly_chart(fig_pizza, use_container_width=True)
        with c2:
            st.write("**Lista de Maiores Gastos/Ganhos:**")
            final_agrupado[col_val_final] = final_agrupado[col_val_final].apply(formatar_moeda)
            st.table(final_agrupado)

else:
    st.info("Aguardando o senhor carregar a planilha para eu começar a análise.")