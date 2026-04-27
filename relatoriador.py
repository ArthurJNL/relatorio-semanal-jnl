import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import plotly.graph_objects as go
from datetime import datetime
import math

# --- MOTORES EXTERNOS ---
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# 1. SETUP DA PÁGINA (LIGHT MODE MINIMALISTA)
st.set_page_config(page_title="RELATORIADOR", page_icon="🛡️", layout="wide")

# --- DESIGN PREMIUM CLEAN (B&W) ---
st.markdown("""
    <style>
    /* Mudança para a fonte Calibri exigida pelo Senhor */
    html, body, [class*="css"] { font-family: 'Calibri', sans-serif; }
    .main { background-color: #F8F9FB; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E4E8; }
    .stMetric, .echarts-container, .js-plotly-plot {
        background: white !important;
        border: 1px solid #E0E4E8 !important;
        border-radius: 15px !important;
        padding: 10px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    }
    .stTextInput > div > div > input {
        border-radius: 12px; border: 1px solid #D0D5DD; padding: 12px 20px;
        font-family: 'Calibri', sans-serif;
    }
    .stTextInput > div > div > input:focus {
        border-color: #000000; box-shadow: 0 0 0 1px #000000;
    }
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

MESES_PT = {1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO",
            7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"}

def formatar_contabil(valor):
    try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def extrair_valor(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    v = str(v).upper().replace('R$', '').replace(' ', '')
    if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
    elif ',' in v: v = v.replace(',', '.')
    try: return float(v)
    except: return 0.0

def converter_para_data(v):
    return pd.to_datetime(v, errors='coerce', dayfirst=True)

HOJE = pd.to_datetime('today').normalize()

def calcular_status_vencimento(data_alvo):
    if pd.isnull(data_alvo) or str(data_alvo).strip() == "-": return "-"
    if isinstance(data_alvo, str):
        try: data_alvo = pd.to_datetime(data_alvo, format='%d/%m/%Y')
        except: return "-"
    dias_diferenca = (data_alvo - HOJE).days
    if dias_diferenca < 0: return f"🚨 Vencido há {abs(dias_diferenca)} dias"
    elif dias_diferenca == 0: return "⚠️ Vence HOJE"
    else: return f"✅ Vence em {dias_diferenca} dias"

def processar_excel_hibrido(df):
    blocos = {}
    mes_atual_separador = None
    cabecalho = None
    
    for i, row in df.iterrows():
        valores_preenchidos = [str(x).strip().upper() for x in row.values if pd.notna(x)]
        linha_txt = " ".join(valores_preenchidos)
        palavras_chave = ['DATA', 'PREVISÃO', 'VALOR', 'A RECEBER', 'RECEBIDO', 'RAZÃO SOCIAL', 'CLIENTE']
        if len(valores_preenchidos) >= 3 and any(k in linha_txt for k in palavras_chave):
            cabecalho = [str(val).strip().upper() if pd.notna(val) and str(val).strip() != "" else f"COL_{idx}" for idx, val in enumerate(row.values)]
            df_dados = df.iloc[i+1:].reset_index(drop=True)
            break
            
    if cabecalho is None: return []

    col_data_idx = next((i for i, c in enumerate(cabecalho) if any(k in c for k in ['DATA', 'PREVISÃO', 'VENCIMENTO', 'CRÉDITO'])), None)
    
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
        while len(valores_linha) < len(cabecalho): valores_linha.append(None)
            
        nome_mes = mes_atual_separador
        if nome_mes is None and col_data_idx is not None and col_data_idx < len(valores_linha):
            dt = converter_para_data(valores_linha[col_data_idx])
            if pd.notnull(dt): nome_mes = f"{MESES_PT[dt.month]} / {dt.year}"
        
        if len(valores_validos) <= 2 and col_data_idx is not None and pd.isna(valores_linha[col_data_idx]): continue
        if nome_mes is None: nome_mes = "SEM DATA"
        if nome_mes not in blocos: blocos[nome_mes] = []
        blocos[nome_mes].append(valores_linha)

    return [(m, pd.DataFrame(d, columns=cabecalho)) for m, d in blocos.items()]

# --- MOTORES DE RELATÓRIO PDF DINÂMICO (JNL) ---
def limpar_texto(t):
    return str(t).encode('latin-1', 'replace').decode('latin-1')

if FPDF is not None:
    class PDFReport(FPDF):
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def gerar_pdf_tabela(df, titulo):
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, limpar_texto(titulo), 0, 1, 'C')
        pdf.ln(5)
        
        colunas = list(df.columns)
        if len(colunas) == 4: widths = [80, 25, 35, 50]
        else: widths = [100, 45, 45]
            
        pdf.set_fill_color(17, 17, 17)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 9)
        
        for i, col in enumerate(colunas):
            pdf.cell(widths[i], 8, limpar_texto(col), border=1, fill=True, align='C')
        pdf.ln()
        
        line_height = 5
        
        for _, row in df.iterrows():
            is_total = "TOTAL" in str(row.iloc[0])
            if is_total:
                pdf.set_font("Arial", 'B', 9)
                pdf.set_fill_color(230, 230, 230)
                pdf.set_text_color(17, 17, 17)
            else:
                pdf.set_font("Arial", '', 8)
                pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(26, 28, 30)
                
            max_linhas = 1
            for i, item in enumerate(row):
                texto = limpar_texto(item)
                w_util = widths[i] - 2
                w_texto = pdf.get_string_width(texto)
                linhas = math.ceil(w_texto / w_util) if w_util > 0 else 1
                if linhas > max_linhas:
                    max_linhas = linhas
                    
            h_linha = (max_linhas * line_height) + 2
            
            if pdf.get_y() + h_linha > 275:
                pdf.add_page()
                pdf.set_fill_color(17, 17, 17)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", 'B', 9)
                for i, col in enumerate(colunas):
                    pdf.cell(widths[i], 8, limpar_texto(col), border=1, fill=True, align='C')
                pdf.ln()
                if is_total:
                    pdf.set_font("Arial", 'B', 9)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.set_text_color(17, 17, 17)
                else:
                    pdf.set_font("Arial", '', 8)
                    pdf.set_fill_color(255, 255, 255)
                    pdf.set_text_color(26, 28, 30)
                    
            start_x = pdf.get_x()
            start_y = pdf.get_y()
            
            for i, item in enumerate(row):
                texto = limpar_texto(item)
                w = widths[i]
                x = start_x + sum(widths[:i])
                y = start_y
                
                style = 'DF' if is_total else 'D'
                pdf.rect(x, y, w, h_linha, style)
                
                # CÁLCULO DE CENTRALIZAÇÃO VERTICAL
                w_util = w - 2
                w_texto = pdf.get_string_width(texto)
                linhas_deste_texto = math.ceil(w_texto / w_util) if w_util > 0 else 1
                offset_y = y + (h_linha - (linhas_deste_texto * line_height)) / 2
                
                pdf.set_xy(x, offset_y)
                # Alinhamento horizontal forçado para o centro ("C") conforme pedido
                pdf.multi_cell(w, line_height, texto, border=0, align='C')
                
            pdf.set_xy(start_x, start_y + h_linha)
            
        res = pdf.output(dest='S')
        if isinstance(res, str): return res.encode('latin-1')
        return bytes(res)

    def gerar_pdf_ranking(df, titulo):
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, limpar_texto(titulo), 0, 1, 'C')
        pdf.ln(5)
        
        pdf.set_fill_color(17, 17, 17)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 9)
        widths = [20, 120, 50]
        colunas = ["POS.", "RAZAO SOCIAL / DESCRICAO", "VALOR TOTAL"]
        for i, col in enumerate(colunas):
            pdf.cell(widths[i], 8, col, border=1, fill=True, align='C')
        pdf.ln()
        
        pdf.set_text_color(26, 28, 30)
        pdf.set_font("Arial", '', 8)
        line_height = 5
        df_ord = df.sort_values(by='VALOR', ascending=False).reset_index(drop=True)
        
        for i, row in df_ord.iterrows():
            pos = f"{i + 1}."
            nome = limpar_texto(row['ENTIDADE']) 
            valor = f"R$ {row['VALOR']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            linha_dados = [pos, nome, valor]
            
            max_linhas = 1
            for j, item in enumerate(linha_dados):
                w_util = widths[j] - 2
                w_texto = pdf.get_string_width(item)
                linhas = math.ceil(w_texto / w_util) if w_util > 0 else 1
                if linhas > max_linhas:
                    max_linhas = linhas
                    
            h_linha = (max_linhas * line_height) + 2
            
            if pdf.get_y() + h_linha > 275:
                pdf.add_page()
                pdf.set_fill_color(17, 17, 17)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", 'B', 9)
                for j, col in enumerate(colunas):
                    pdf.cell(widths[j], 8, col, border=1, fill=True, align='C')
                pdf.ln()
                pdf.set_text_color(26, 28, 30)
                pdf.set_font("Arial", '', 8)
                
            start_x = pdf.get_x()
            start_y = pdf.get_y()
            
            for j, item in enumerate(linha_dados):
                w = widths[j]
                x = start_x + sum(widths[:j])
                y = start_y
                
                pdf.rect(x, y, w, h_linha, 'D')
                
                # CÁLCULO DE CENTRALIZAÇÃO VERTICAL
                w_util = w - 2
                w_texto = pdf.get_string_width(item)
                linhas_deste_texto = math.ceil(w_texto / w_util) if w_util > 0 else 1
                offset_y = y + (h_linha - (linhas_deste_texto * line_height)) / 2
                
                pdf.set_xy(x, offset_y)
                # Alinhamento horizontal forçado para o centro ("C") conforme pedido
                pdf.multi_cell(w, line_height, item, border=0, align='C')
                
            pdf.set_xy(start_x, start_y + h_linha)
            
        res = pdf.output(dest='S')
        if isinstance(res, str): return res.encode('latin-1')
        return bytes(res)

# --- INTERFACE SIDEBAR ---
with st.sidebar:
    st.title("🛡️ RELATORIADOR")
    st.markdown("---")
    st.subheader("📁 GERADOR")
    arquivos = st.file_uploader("Suba as planilhas que deseja transformar", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

# --- LÓGICA PRINCIPAL ---
if arquivos:
    todos_os_blocos = []
    
    for arq in arquivos:
        if arq.name.endswith('.csv'):
            arq.seek(0)
            try:
                df_bruto = pd.read_csv(arq, header=None, sep=';')
                if len(df_bruto.columns) <= 2:
                    arq.seek(0)
                    df_bruto = pd.read_csv(arq, header=None, sep=',')
            except:
                arq.seek(0)
                df_bruto = pd.read_csv(arq, header=None)
        else:
            df_bruto = pd.read_excel(arq, header=None)
            
        resultados = processar_excel_hibrido(df_bruto)
        for nome_mes, dados in resultados:
            todos_os_blocos.append((nome_mes, dados))

    resumos_limpos = []
    for mes, df_mes in todos_os_blocos:
        prioridades_valor = ['RECEBIDO', 'PAGO', 'VALOR', 'A RECEBER', 'A PAGAR']
        col_v = None
        for p in prioridades_valor:
            match = next((c for c in df_mes.columns if p in c), None)
            if match:
                col_v = match
                break
                
        prioridades_data = ['DATA', 'PREVISÃO', 'VENCIMENTO', 'PAGAMENTO', 'CRÉDITO']
        col_data = None
        for p in prioridades_data:
            match = next((c for c in df_mes.columns if p in c), None)
            if match:
                col_data = match
                break
        
        prioridades_nome = ['RAZÃO SOCIAL', 'DESCRIÇÃO', 'FORNECEDOR', 'DEVEDOR', 'CLIENTE']
        col_d = None
        for p in prioridades_nome:
            match = next((c for c in df_mes.columns if p in c), None)
            if match:
                col_d = match
                break
        if not col_d: col_d = df_mes.columns[1] if len(df_mes.columns) > 1 else df_mes.columns[0]
        
        if col_v and col_d and col_data:
            df_tmp = df_mes.copy()
            df_tmp[col_v] = df_tmp[col_v].apply(extrair_valor)
            df_tmp[col_data] = pd.to_datetime(df_tmp[col_data], errors='coerce', dayfirst=True).dt.normalize()
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
                periodo_selecionado = st.date_input("Selecione De / Até:", value=(data_min, data_max), min_value=data_min, max_value=data_max, format="DD/MM/YYYY")
            
            if isinstance(periodo_selecionado, tuple) and len(periodo_selecionado) == 2: dt_inicio, dt_fim = periodo_selecionado
            elif isinstance(periodo_selecionado, tuple) and len(periodo_selecionado) == 1: dt_inicio = dt_fim = periodo_selecionado[0]
            else: dt_inicio, dt_fim = data_min, data_max
                
            mask_data = (df_master['DATA'] >= pd.to_datetime(dt_inicio)) & (df_master['DATA'] <= pd.to_datetime(dt_fim))
            df_filtrado = df_master[mask_data]

            st.markdown("# Relatório gerado")
            comando_filtro = st.text_input("💬 Filtro de pesquisa...", placeholder="Ex: IMPORPECAS, KS MAQUINAS...")
            if comando_filtro: df_filtrado = df_filtrado[df_filtrado['ENTIDADE'].str.contains(comando_filtro.strip().upper(), case=False, na=False)]

            dados_grafico = df_filtrado.groupby('ENTIDADE')['VALOR'].sum().reset_index().sort_values(by='VALOR', ascending=False)
            dados_grafico = dados_grafico[dados_grafico['VALOR'] > 0]
            
            dados_tabela = df_filtrado.groupby(['ENTIDADE', 'DATA'])['VALOR'].sum().reset_index().sort_values(by=['ENTIDADE', 'DATA'], ascending=[True, True])
            dados_tabela = dados_tabela[dados_tabela['VALOR'] > 0]
            
            dados_tabela['STATUS'] = dados_tabela['DATA'].apply(calcular_status_vencimento)
            dados_tabela['DATA'] = dados_tabela['DATA'].dt.strftime('%d/%m/%Y').fillna("-")
            
            if not dados_grafico.empty:
                m1, m2, m3, m4 = st.columns(4)
                total_cash = dados_grafico['VALOR'].sum()
                dias_periodo = (dt_fim - dt_inicio).days + 1
                total_linhas = len(dados_tabela)
                
                m1.metric("Volume Total (Filtrado)", formatar_contabil(total_cash))
                m2.metric("Principal Entidade", dados_grafico.iloc[0]['ENTIDADE'])
                m3.metric("Período Analisado", f"{dias_periodo} Dia(s)")
                m4.metric("Quantidade de itens", f"{total_linhas} Linha(s)")

                aba_visu, aba_tab = st.tabs(["📊 Gráfico", "📋 Tabela Detalhada"])

                with aba_visu:
                    titulo_customizado_grafico = st.text_input("📝 Título Customizado (Gráfico):", value=f"RELAÇÃO DE VALORES ({dt_inicio.strftime('%d/%m/%Y')} até {dt_fim.strftime('%d/%m/%Y')})")
                    
                    col_g1, col_g2 = st.columns([3, 1])
                    with col_g1:
                        st.write("💡 *Baixe em PNG ou PDF.*")
                    with col_g2:
                        if FPDF is not None:
                            pdf_ranking_bytes = gerar_pdf_ranking(dados_grafico, titulo_customizado_grafico)
                            st.download_button(label="📄 Baixar gráfico em PDF", data=pdf_ranking_bytes, file_name=f"Ranking_JNL_{dt_inicio.strftime('%d%m%y')}.pdf", mime="application/pdf", use_container_width=True)
                    
                    dados_completos = dados_grafico.sort_values(by='VALOR', ascending=True)
                    dados_barras_formatados = [{"value": row['VALOR'], "label": {"show": True, "position": "right", "formatter": f"R$ {row['VALOR']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "color": "#111111"}} for _, row in dados_completos.iterrows()]
                    
                    altura_dinamica = max(600, len(dados_completos) * 50) 
                    
                    bar_options = {
                        "backgroundColor": "transparent",
                        "title": {"text": titulo_customizado_grafico, "left": "center", "textStyle": {"color": "#111111", "fontSize": 18, "fontFamily": "Calibri"}},
                        "toolbox": {"feature": {"saveAsImage": {"show": True, "title": "Baixar Foto", "pixelRatio": 2}}},
                        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                        "grid": {"top": 80, "left": "1%", "right": "15%", "bottom": "1%", "containLabel": True},
                        "xAxis": {"type": "value", "splitLine": {"lineStyle": {"type": "dashed", "color": "#E0E4E8"}}},
                        "yAxis": {
                            "type": "category", 
                            "data": dados_completos['ENTIDADE'].tolist(), 
                            "axisLabel": {
                                "interval": 0, 
                                "width": 220, 
                                "overflow": "break", 
                                "lineHeight": 14,
                                "color": "#1A1C1E"
                            }
                        },
                        "series": [{"type": "bar", "data": dados_barras_formatados, "itemStyle": {"color": "#111111", "borderRadius": [0, 8, 8, 0]}}]
                    }
                    st_echarts(options=bar_options, height=f"{altura_dinamica}px")

                with aba_tab:
                    titulo_tabela = st.text_input("📝 Título Customizado (Tabela):", value=titulo_customizado_grafico)
                    
                    col_t1, col_t2 = st.columns([3, 1])
                    with col_t1:
                        st.write("💡 *Baixe em PNG ou PDF.*")
                    with col_t2:
                        mostrar_situacao = st.toggle("Mostrar Coluna 'Situação'", value=True)

                    tabela_final = dados_tabela.copy()
                    tabela_final['VALOR_STR'] = tabela_final['VALOR'].apply(formatar_contabil)
                    
                    soma_total = tabela_final['VALOR'].sum()
                    soma_total_str = formatar_contabil(soma_total)
                    
                    lista_entidades = tabela_final['ENTIDADE'].tolist() + ["TOTAL GERAL"]
                    lista_datas = tabela_final['DATA'].tolist() + ["-"]
                    lista_valores = tabela_final['VALOR_STR'].tolist() + [soma_total_str]
                    lista_status = tabela_final['STATUS'].tolist() + ["-"]

                    lista_entidades_visual = tabela_final['ENTIDADE'].tolist() + ["<b>TOTAL GERAL</b>"]
                    lista_datas_visual = tabela_final['DATA'].tolist() + ["<b>-</b>"]
                    lista_valores_visual = tabela_final['VALOR_STR'].tolist() + [f"<b>{soma_total_str}</b>"]
                    lista_status_visual = tabela_final['STATUS'].tolist() + ["<b>-</b>"]
                    
                    if mostrar_situacao:
                        df_pdf = pd.DataFrame({"RAZAO SOCIAL / DESCRICAO": lista_entidades, "DATA": lista_datas, "VALOR": lista_valores, "SITUACAO": lista_status})
                        cabecalhos = ["<b>RAZÃO SOCIAL / DESCRIÇÃO</b>", "<b>DATA</b>", "<b>VALOR</b>", "<b>SITUAÇÃO</b>"]
                        celulas = [lista_entidades_visual, lista_datas_visual, lista_valores_visual, lista_status_visual]
                        larguras_colunas = [350, 100, 120, 120]
                    else:
                        df_pdf = pd.DataFrame({"RAZAO SOCIAL / DESCRICAO": lista_entidades, "DATA": lista_datas, "VALOR": lista_valores})
                        cabecalhos = ["<b>RAZÃO SOCIAL / DESCRIÇÃO</b>", "<b>DATA</b>", "<b>VALOR</b>"]
                        celulas = [lista_entidades_visual, lista_datas_visual, lista_valores_visual]
                        larguras_colunas = [350, 120, 120]

                    if FPDF is not None:
                        pdf_bytes = gerar_pdf_tabela(df_pdf, titulo_tabela)
                        st.download_button(label="📄 Baixar tabela em PDF", data=pdf_bytes, file_name=f"Detalhado_JNL_{dt_inicio.strftime('%d%m%y')}.pdf", mime="application/pdf", use_container_width=True)
                    else:
                        st.error("⚠️ Biblioteca 'fpdf' não instalada. Atualize o ficheiro requirements.txt.")

                    cor_linhas_normais = '#F8F9FB'
                    cor_linha_total = '#D0D5DD'
                    cores_tabela = [cor_linhas_normais] * len(tabela_final) + [cor_linha_total]
                    array_cores_fundo = [cores_tabela] * len(cabecalhos)

                    fig_table = go.Figure(data=[go.Table(
                        columnwidth=larguras_colunas,
                        # Plotly configurado com Calibri e alinhamento central ('center')
                        header=dict(values=cabecalhos, fill_color='#111111', align='center', font=dict(family='Calibri', color='white', size=13)),
                        cells=dict(
                            values=celulas, 
                            fill_color=array_cores_fundo,
                            align='center', 
                            font=dict(family='Calibri', color='#1A1C1E', size=12), 
                            height=55 
                        )
                    )])
                    
                    fig_table.update_layout(
                        title=dict(text=f"<b>{titulo_tabela}</b>", font=dict(family='Calibri', color='#111111', size=16)),
                        margin=dict(l=0, r=0, b=0, t=40), 
                        height=550, 
                        paper_bgcolor='rgba(0,0,0,0)', 
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_table, use_container_width=True, config={'modeBarButtonsToAdd': ['toImage']})
                    
            else: st.info("Todos os valores encontrados estão zerados no período selecionado.")
        else: st.warning("⚠️ Nenhuma data válida encontrada no ficheiro. Verifique a coluna de datas.")
else: st.info("Aguardando o envio da planilha...")