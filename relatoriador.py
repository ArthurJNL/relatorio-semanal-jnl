import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import plotly.graph_objects as go
from datetime import datetime
import math
import unicodedata
import re

# --- MOTORES EXTERNOS ---
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

try:
    from streamlit_sortables import sort_items
except ImportError:
    sort_items = None

# 1. SETUP DA PÁGINA (LIGHT MODE MINIMALISTA)
st.set_page_config(page_title="RELATORIADOR", page_icon="🛡️", layout="wide")

# --- DESIGN PREMIUM CLEAN (B&W) ---
st.markdown("""
    <style>
    /* Fonte Calibri exigida pelo Senhor */
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

    col_data_idx = None
    for k in ['PREVISÃO', 'VENCIMENTO', 'DATA', 'CRÉDITO']:
        idx = next((i for i, c in enumerate(cabecalho) if k in c), None)
        if idx is not None:
            col_data_idx = idx
            break
    
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

def limpar_texto(t):
    if pd.isna(t): return ""
    texto = str(t)
    texto = texto.replace('🚨', '(!)').replace('⚠️', '(!)').replace('✅', '(OK)').replace('🛡️', '')
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def remover_acentos(texto):
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8').upper()

# MOTOR FALSO DE IMPRESSÃO - Calcula quebras reais de linha do FPDF
def obter_linhas_reais(pdf, largura, texto):
    if pd.isna(texto) or str(texto).strip() == "": return 1
    texto = str(texto)
    w_util = largura - 3 
    if w_util <= 0: return 1
    
    linhas = 0
    for paragrafo in texto.split('\n'):
        palavras = paragrafo.split(' ')
        linha_atual = ""
        linhas_neste_paragrafo = 1
        for p in palavras:
            teste_linha = p if not linha_atual else linha_atual + " " + p
            if pdf.get_string_width(teste_linha) > w_util:
                if linha_atual == "": 
                    linhas_neste_paragrafo += max(1, math.ceil(pdf.get_string_width(p) / w_util)) - 1
                    linha_atual = p
                else:
                    linhas_neste_paragrafo += 1
                    linha_atual = p
            else:
                linha_atual = teste_linha
        linhas += linhas_neste_paragrafo
    return max(1, linhas)

# ==========================================
# MOTOR UNIFICADO DE PDF (FUSÃO DE RELATÓRIOS)
# ==========================================
if FPDF is not None:
    class PDFReport(FPDF):
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def append_pdf_tabela(pdf, df, titulo, colunas, widths):
        pdf.add_page()
        if titulo:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, limpar_texto(titulo), 0, 1, 'C')
            pdf.ln(5)
            
        fator = 190 / sum(widths)
        widths_norm = [w * fator for w in widths]
            
        pdf.set_fill_color(17, 17, 17)
        pdf.set_text_color(255, 255, 255)
        
        for i, col in enumerate(colunas):
            col_text = limpar_texto(col)
            pdf.set_font("Arial", 'B', 9)
            font_size = 9.0
            while pdf.get_string_width(col_text) > widths_norm[i] - 2 and font_size > 5:
                font_size -= 0.5
                pdf.set_font("Arial", 'B', font_size)
            pdf.cell(widths_norm[i], 8, col_text, border=1, fill=True, align='C')
            pdf.set_font("Arial", 'B', 9)
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
                linhas = obter_linhas_reais(pdf, widths_norm[i], texto)
                if linhas > max_linhas:
                    max_linhas = linhas
                    
            h_linha = (max_linhas * line_height) + 2
            
            if pdf.get_y() + h_linha > 275:
                pdf.add_page()
                pdf.set_fill_color(17, 17, 17)
                pdf.set_text_color(255, 255, 255)
                
                for i, col in enumerate(colunas):
                    col_text = limpar_texto(col)
                    pdf.set_font("Arial", 'B', 9)
                    font_size = 9.0
                    while pdf.get_string_width(col_text) > widths_norm[i] - 2 and font_size > 5:
                        font_size -= 0.5
                        pdf.set_font("Arial", 'B', font_size)
                    pdf.cell(widths_norm[i], 8, col_text, border=1, fill=True, align='C')
                    pdf.set_font("Arial", 'B', 9)
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
                w = widths_norm[i]
                x = start_x + sum(widths_norm[:i])
                y = start_y
                
                style = 'DF' if is_total else 'D'
                pdf.rect(x, y, w, h_linha, style)
                
                linhas_deste_texto = obter_linhas_reais(pdf, w, texto)
                offset_y = y + (h_linha - (linhas_deste_texto * line_height)) / 2
                
                pdf.set_xy(x, offset_y)
                
                col_upper = str(colunas[i]).upper()
                if "RAZÃO" in col_upper or "DESCRI" in col_upper: align_h = 'L'
                elif "DATA" in col_upper: align_h = 'C'
                elif "DOC" in col_upper: align_h = 'C'
                elif "NOTA" in col_upper or "NF" in col_upper: align_h = 'C'
                elif "PARC" in col_upper: align_h = 'C'
                elif "DESPESA" in col_upper: align_h = 'C'
                elif "VALOR" in col_upper: align_h = 'R'
                elif "SITUA" in col_upper: align_h = 'C'
                else: align_h = 'C'
                
                pdf.multi_cell(w, line_height, texto, border=0, align=align_h)
                
            pdf.set_xy(start_x, start_y + h_linha)

    def append_pdf_ranking(pdf, df, titulo):
        pdf.add_page()
        if titulo:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, limpar_texto(titulo), 0, 1, 'C')
            pdf.ln(5)
        
        pdf.set_fill_color(17, 17, 17)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 9)
        widths = [20, 120, 50]
        
        df_ord = df.copy() # Já vem ordenado
        col_nome_dinamico = str(df_ord.columns[0]).upper()
        col_valor_dinamico = df_ord.columns[1]
        
        colunas = ["POS.", col_nome_dinamico, "VALOR TOTAL"]
        for i, col in enumerate(colunas):
            pdf.cell(widths[i], 8, limpar_texto(col), border=1, fill=True, align='C')
        pdf.ln()
        
        pdf.set_text_color(26, 28, 30)
        pdf.set_font("Arial", '', 8)
        line_height = 5
        
        for i, row in df_ord.iterrows():
            pos = f"{i + 1}."
            nome = limpar_texto(row[df_ord.columns[0]]) 
            valor = f"R$ {row[col_valor_dinamico]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            linha_dados = [pos, nome, valor]
            
            max_linhas = 1
            for j, item in enumerate(linha_dados):
                linhas = obter_linhas_reais(pdf, widths[j], item)
                if linhas > max_linhas:
                    max_linhas = linhas
                    
            h_linha = (max_linhas * line_height) + 2
            
            if pdf.get_y() + h_linha > 275:
                pdf.add_page()
                pdf.set_fill_color(17, 17, 17)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", 'B', 9)
                for j, col in enumerate(colunas):
                    pdf.cell(widths[j], 8, limpar_texto(col), border=1, fill=True, align='C')
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
                
                linhas_deste_texto = obter_linhas_reais(pdf, w, item)
                offset_y = y + (h_linha - (linhas_deste_texto * line_height)) / 2
                
                pdf.set_xy(x, offset_y)
                
                align_h = 'C' if j == 0 else ('L' if j == 1 else 'R')
                pdf.multi_cell(w, line_height, item, border=0, align=align_h)
                
            pdf.set_xy(start_x, start_y + h_linha)

    # Para manter o botão individual na aba de tabela funcionando
    def gerar_pdf_tabela(df, titulo, colunas, widths):
        pdf = PDFReport()
        append_pdf_tabela(pdf, df, titulo, colunas, widths)
        res = pdf.output(dest='S')
        if isinstance(res, str): return res.encode('latin-1')
        return bytes(res)

# --- INTERFACE SIDEBAR ---
with st.sidebar:
    st.title("🛡️ RELATORIADOR")
    st.markdown("---")
    st.subheader("📁 GERADOR")
    arquivos = st.file_uploader("Suba as planilhas que deseja transformar", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

# --- LISTA MESTRE DE DESPESAS ---
DESPESAS_VALIDAS = [
    'ALUGUEL', 'CARTÃO DE CRÉDITO', 'MFC', 'CONSUMO', 'DESPACHANTE ADUANEIRO', 
    'DESPESA VARIAVEL', 'EMPRESTIMO', 'DOAÇÃO', 'FORNECEDOR EXTERIOR', 
    'FORNECEDORES', 'FUNCIONÁRIOS', 'IMPOSTO', 'MARKETING', 'PATRIMONIO', 
    'PRESTADOR DE SERVIÇO', 'RENEGOCIAÇÃO - ACORDO', 'SEGURO', 'SÓCIOS', 'TRANSPORTADORA'
]
DESPESAS_VALIDAS_LIMPAS = [remover_acentos(d) for d in DESPESAS_VALIDAS]

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
        col_v = None
        cols_valores_possiveis = [c for c in df_mes.columns if c.upper().strip() in ['RECEBIDO', 'A RECEBER']]
        if len(cols_valores_possiveis) == 2:
            c1, c2 = cols_valores_possiveis
            v1_count = df_mes[c1].apply(extrair_valor).apply(lambda x: 1 if x > 0 else 0).sum()
            v2_count = df_mes[c2].apply(extrair_valor).apply(lambda x: 1 if x > 0 else 0).sum()
            col_v = c1 if v1_count >= v2_count else c2
        elif len(cols_valores_possiveis) == 1:
            col_v = cols_valores_possiveis[0]
        else:
            prioridades_valor = ['VALOR', 'PAGO', 'A PAGAR']
            for p in prioridades_valor:
                match = next((c for c in df_mes.columns if p in c.upper()), None)
                if match:
                    col_v = match
                    break
                
        col_data = None
        for p in ['PREVISÃO', 'VENCIMENTO', 'DATA', 'PAGAMENTO', 'CRÉDITO']:
            match = next((c for c in df_mes.columns if p in c.upper()), None)
            if match:
                col_data = match
                break
                
        prioridades_doc = ['DOCUMENTO', 'DOC', 'FORMA DE PAGAMENTO', 'TIPO', 'MODALIDADE']
        col_doc = None
        for p in prioridades_doc:
            match = next((c for c in df_mes.columns if p in c.upper()), None)
            if match:
                col_doc = match
                break
                
        prioridades_nf = ['NOTA FISCAL', 'NF', 'N.F', 'NOTA']
        col_nf = None
        for p in prioridades_nf:
            match = next((c for c in df_mes.columns if p in c.upper() or p == c.upper().strip()), None)
            if match:
                col_nf = match
                break
                
        prioridades_parc = ['PARCELA', 'PARC', 'Nº PARCELA', 'NUMERO PARCELA']
        col_parc = None
        for p in prioridades_parc:
            match = next((c for c in df_mes.columns if p in c.upper() or p == c.upper().strip()), None)
            if match:
                col_parc = match
                break
        
        col_d = None
        prioridades_nome = ['RAZÃO SOCIAL', 'CLIENTE', 'DESCRIÇÃO', 'FORNECEDOR', 'DEVEDOR']
        for p in prioridades_nome:
            matches = [c for c in df_mes.columns if p in c.upper() and 'MINHA EMPRESA' not in c.upper()]
            if matches:
                col_d = matches[0]
                break
        if not col_d: col_d = df_mes.columns[1] if len(df_mes.columns) > 1 else df_mes.columns[0]
        
        if col_v and col_d and col_data:
            df_tmp = df_mes.copy()
            df_tmp[col_v] = df_tmp[col_v].apply(extrair_valor)
            df_tmp[col_data] = pd.to_datetime(df_tmp[col_data], errors='coerce', dayfirst=True).dt.normalize()
            df_tmp[col_d] = df_tmp[col_d].astype(str).str.upper().str.strip()
            
            df_tmp = df_tmp[~df_tmp[col_d].str.contains('JNL IMPORTADORA', na=False)]
            df_tmp = df_tmp[~df_tmp[col_d].str.contains('01.718.395', na=False)]
            df_tmp = df_tmp[~df_tmp[col_d].str.contains('MINHA EMPRESA', na=False)]
            
            df_tmp[col_d] = df_tmp[col_d].replace(r'\s+', ' ', regex=True)
            df_tmp = df_tmp[df_tmp[col_d] != ""]
            df_tmp = df_tmp[df_tmp[col_d] != "NAN"]
            df_tmp = df_tmp[df_tmp[col_d] != "NONE"]
            
            if col_doc:
                df_tmp['DOCUMENTO'] = df_tmp[col_doc].astype(str).str.upper().str.strip()
                df_tmp['DOCUMENTO'] = df_tmp['DOCUMENTO'].replace(['NAN', 'NONE', ''], '-')
            else:
                df_tmp['DOCUMENTO'] = "-"
                
            if col_nf:
                df_tmp['NOTA FISCAL'] = df_tmp[col_nf].astype(str).str.upper().str.strip()
                df_tmp['NOTA FISCAL'] = df_tmp['NOTA FISCAL'].replace(['NAN', 'NONE', ''], '-')
            else:
                df_tmp['NOTA FISCAL'] = "-"
                
            if col_parc:
                df_tmp['PARCELA'] = df_tmp[col_parc].astype(str).str.upper().str.strip()
                df_tmp['PARCELA'] = df_tmp['PARCELA'].replace(['NAN', 'NONE', ''], '-')
            else:
                df_tmp['PARCELA'] = "-"
                
            # MOTOR DE EXTRAÇÃO DE DESPESA
            def extrair_despesa_linha(row):
                txt_linha = remover_acentos(" ".join([str(x) for x in row.values if pd.notnull(x)]))
                for idx_d, d_limpo in enumerate(DESPESAS_VALIDAS_LIMPAS):
                    if d_limpo in txt_linha:
                        return DESPESAS_VALIDAS[idx_d] 
                return ""

            df_tmp['DESPESA'] = df_mes.apply(extrair_despesa_linha, axis=1)
            
            df_tmp = df_tmp.rename(columns={col_d: 'ENTIDADE', col_data: 'DATA', col_v: 'VALOR'})
            resumos_limpos.append(df_tmp[['ENTIDADE', 'DATA', 'DOCUMENTO', 'NOTA FISCAL', 'PARCELA', 'DESPESA', 'VALOR']])

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

            # PREPARAÇÃO DOS DADOS DOS GRÁFICOS (Para serem usados em ambas as abas)
            
            # 1. Por Entidade
            dados_grafico_ent = df_filtrado.groupby('ENTIDADE')['VALOR'].sum().reset_index().sort_values(by='VALOR', ascending=False)
            dados_grafico_ent = dados_grafico_ent[dados_grafico_ent['VALOR'] > 0]
            
            # 2. Por Categoria (Pagamento)
            def categorizar_pagamento(d):
                d = str(d).upper()
                if 'BOLETO' in d: return 'Boleto'
                elif 'CART' in d: return 'Cartão'
                elif any(x in d for x in ['DEP', 'PIX', 'VISTA', 'TRANSF', 'TED', 'DOC']): return 'Depósito/à vista/pix'
                elif 'DIN' in d or 'ESP' in d: return 'Dinheiro'
                else: return 'Outros'
                
            df_cat = df_filtrado.copy()
            df_cat['CATEGORIA'] = df_cat['DOCUMENTO'].apply(categorizar_pagamento)
            dados_grafico_cat = df_cat.groupby('CATEGORIA')['VALOR'].sum().reset_index()
            dados_grafico_cat = dados_grafico_cat[dados_grafico_cat['VALOR'] > 0].sort_values(by='VALOR', ascending=False)
            
            # 3. Por Despesa
            df_desp = df_filtrado[df_filtrado['DESPESA'] != ""]
            if df_desp.empty:
                dados_grafico_desp = pd.DataFrame()
            else:
                dados_grafico_desp = df_desp.groupby('DESPESA')['VALOR'].sum().reset_index()
                dados_grafico_desp = dados_grafico_desp[dados_grafico_desp['VALOR'] > 0].sort_values(by='VALOR', ascending=False)

            # Tabela Detalhada Base
            dados_tabela = df_filtrado.groupby(['ENTIDADE', 'DATA', 'DOCUMENTO', 'NOTA FISCAL', 'PARCELA', 'DESPESA'])['VALOR'].sum().reset_index().sort_values(by=['DATA', 'ENTIDADE'], ascending=[True, True])
            dados_tabela = dados_tabela[dados_tabela['VALOR'] > 0]
            
            dados_tabela['STATUS'] = dados_tabela['DATA'].apply(calcular_status_vencimento)
            dados_tabela['DATA'] = dados_tabela['DATA'].dt.strftime('%d/%m/%Y').fillna("-")
            
            if not dados_grafico_ent.empty:
                m1, m2, m3, m4 = st.columns(4)
                total_cash = dados_grafico_ent['VALOR'].sum()
                dias_periodo = (dt_fim - dt_inicio).days + 1
                total_linhas = len(dados_tabela)
                
                m1.metric("Volume Total (Filtrado)", formatar_contabil(total_cash))
                m2.metric("Principal Entidade", dados_grafico_ent.iloc[0]['ENTIDADE'])
                m3.metric("Período Analisado", f"{dias_periodo} Dia(s)")
                m4.metric("Quantidade de itens", f"{total_linhas} Linha(s)")

                # NOVA DIVISÃO DE ABAS (Com Relatório Completo)
                aba_visu, aba_tab, aba_rel = st.tabs(["📊 Gráfico", "📋 Tabela Detalhada", "📑 Relatório Completo"])

                with aba_visu:
                    titulo_customizado_grafico = st.text_input("📝 Título Customizado (Sistema):", value=f"RELAÇÃO DE VALORES ({dt_inicio.strftime('%d/%m/%Y')} até {dt_fim.strftime('%d/%m/%Y')})")
                    st.write("💡 *Use o ícone 📷 no canto superior direito do gráfico abaixo para baixar a imagem (JPG fundo branco).*")
                    
                    tipo_grafico = st.radio("📊 Escolha o modelo do Gráfico:", ["Por Entidade (Padrão)", "Categorizado (Por Tipo de Pagamento)", "Por Categoria de Despesa"], horizontal=True)
                    
                    if tipo_grafico == "Por Entidade (Padrão)":
                        dados_completos = dados_grafico_ent.sort_values(by='VALOR', ascending=True)
                        dados_barras_formatados = [{"value": row['VALOR'], "label": {"show": True, "position": "right", "formatter": f"R$ {row['VALOR']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "color": "#111111"}} for _, row in dados_completos.iterrows()]
                        
                        altura_dinamica = max(600, len(dados_completos) * 50) 
                        
                        bar_options = {
                            "backgroundColor": "transparent",
                            "title": {"text": titulo_customizado_grafico, "left": "center", "textStyle": {"color": "#111111", "fontSize": 18, "fontFamily": "Calibri"}},
                            "toolbox": {"feature": {"saveAsImage": {"show": True, "title": "Baixar JPG", "type": "jpeg", "backgroundColor": "#FFFFFF", "pixelRatio": 2}}},
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                            "grid": {"top": 80, "left": "1%", "right": "15%", "bottom": "1%", "containLabel": True},
                            "xAxis": {"type": "value", "splitLine": {"lineStyle": {"type": "dashed", "color": "#E0E4E8"}}},
                            "yAxis": {"type": "category", "data": dados_completos['ENTIDADE'].tolist(), "axisLabel": {"interval": 0, "width": 220, "overflow": "break", "lineHeight": 14, "color": "#1A1C1E"}},
                            "series": [{"type": "bar", "data": dados_barras_formatados, "itemStyle": {"color": "#111111", "borderRadius": [0, 8, 8, 0]}}]
                        }
                        st_echarts(options=bar_options, height=f"{altura_dinamica}px")
                        
                    elif tipo_grafico == "Categorizado (Por Tipo de Pagamento)":
                        dados_completos = dados_grafico_cat.sort_values(by='VALOR', ascending=True)
                        categorias_lista = dados_completos['CATEGORIA'].tolist()
                        
                        dados_barras_cat = [{"value": row['VALOR'], "label": {"show": True, "position": "right", "formatter": f"R$ {row['VALOR']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "color": "#111111"}} for _, row in dados_completos.iterrows()]
                        altura_dinamica_cat = max(400, len(categorias_lista) * 80)
                        
                        bar_options_cat = {
                            "backgroundColor": "transparent",
                            "title": {"text": titulo_customizado_grafico + " - Categorizado", "left": "center", "textStyle": {"color": "#111111", "fontSize": 18, "fontFamily": "Calibri"}},
                            "toolbox": {"feature": {"saveAsImage": {"show": True, "title": "Baixar JPG", "type": "jpeg", "backgroundColor": "#FFFFFF", "pixelRatio": 2}}},
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, 
                            "grid": {"top": 80, "left": "1%", "right": "15%", "bottom": "5%", "containLabel": True},
                            "xAxis": {"type": "value", "splitLine": {"lineStyle": {"type": "dashed", "color": "#E0E4E8"}}},
                            "yAxis": {"type": "category", "data": categorias_lista, "axisLabel": {"color": "#1A1C1E", "fontWeight": "bold"}},
                            "series": [{"type": "bar", "data": dados_barras_cat, "itemStyle": {"color": "#111111", "borderRadius": [0, 8, 8, 0]}}]
                        }
                        st_echarts(options=bar_options_cat, height=f"{altura_dinamica_cat}px")

                    elif tipo_grafico == "Por Categoria de Despesa":
                        if dados_grafico_desp.empty:
                            st.warning("⚠️ Nenhuma despesa reconhecida foi encontrada no período filtrado.")
                        else:
                            dados_completos = dados_grafico_desp.sort_values(by='VALOR', ascending=True)
                            categorias_desp_lista = dados_completos['DESPESA'].tolist()
                            
                            dados_barras_desp = [{"value": row['VALOR'], "label": {"show": True, "position": "right", "formatter": f"R$ {row['VALOR']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "color": "#111111"}} for _, row in dados_completos.iterrows()]
                            altura_dinamica_desp = max(400, len(categorias_desp_lista) * 60)
                            
                            bar_options_desp = {
                                "backgroundColor": "transparent",
                                "title": {"text": titulo_customizado_grafico + " - Despesas", "left": "center", "textStyle": {"color": "#111111", "fontSize": 18, "fontFamily": "Calibri"}},
                                "toolbox": {"feature": {"saveAsImage": {"show": True, "title": "Baixar JPG", "type": "jpeg", "backgroundColor": "#FFFFFF", "pixelRatio": 2}}},
                                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, 
                                "grid": {"top": 80, "left": "1%", "right": "15%", "bottom": "5%", "containLabel": True},
                                "xAxis": {"type": "value", "splitLine": {"lineStyle": {"type": "dashed", "color": "#E0E4E8"}}},
                                "yAxis": {"type": "category", "data": categorias_desp_lista, "axisLabel": {"interval": 0, "width": 180, "overflow": "break", "lineHeight": 14, "color": "#1A1C1E", "fontWeight": "bold"}},
                                "series": [{"type": "bar", "data": dados_barras_desp, "itemStyle": {"color": "#111111", "borderRadius": [0, 8, 8, 0]}}]
                            }
                            st_echarts(options=bar_options_desp, height=f"{altura_dinamica_desp}px")

                with aba_tab:
                    st.write("💡 *Controle as colunas, arraste-as com o mouse para alterar a ordem e clique para baixar.*")
                    
                    colunas_disponiveis = ["RAZÃO SOCIAL / DESCRIÇÃO", "DATA", "DOCUMENTO", "NOTA FISCAL", "PARCELA", "DESPESA", "VALOR", "SITUAÇÃO"]
                    colunas_padrao = ["RAZÃO SOCIAL / DESCRIÇÃO", "DATA", "DOCUMENTO", "NOTA FISCAL", "PARCELA", "VALOR", "SITUAÇÃO"]
                    
                    if sort_items is not None:
                        st.markdown("⚙️ **1. Escolha quais colunas exibir:**")
                        colunas_ativas = st.multiselect("Oculte ou revele as colunas:", options=colunas_disponiveis, default=colunas_padrao, label_visibility="collapsed")
                        
                        if colunas_ativas:
                            st.markdown("↕️ **2. Arraste as caixas abaixo para ordenar (Muda o visual e o PDF):**")
                            colunas_selecionadas = sort_items(colunas_ativas, direction='vertical', key="ordenador_colunas")
                        else: colunas_selecionadas = []
                    else:
                        colunas_selecionadas = st.multiselect("⚙️ Selecione as colunas e a ordem (Instale 'streamlit-sortables' no terminal para poder arrastar com o mouse!):", options=colunas_disponiveis, default=colunas_padrao)
                    
                    if not colunas_selecionadas:
                        colunas_selecionadas = ["RAZÃO SOCIAL / DESCRIÇÃO", "VALOR"] # Failsafe

                    tabela_final = dados_tabela.copy()
                    tabela_final['VALOR_STR'] = tabela_final['VALOR'].apply(formatar_contabil)
                    
                    soma_total = tabela_final['VALOR'].sum()
                    soma_total_str = formatar_contabil(soma_total)
                    
                    # MAPAS DE INJEÇÃO DINÂMICA
                    mapa_pdf = {
                        "RAZÃO SOCIAL / DESCRIÇÃO": tabela_final['ENTIDADE'].tolist() + ["TOTAL GERAL"],
                        "DATA": tabela_final['DATA'].tolist() + ["-"],
                        "DOCUMENTO": tabela_final['DOCUMENTO'].tolist() + ["-"],
                        "NOTA FISCAL": tabela_final['NOTA FISCAL'].tolist() + ["-"],
                        "PARCELA": tabela_final['PARCELA'].tolist() + ["-"],
                        "DESPESA": tabela_final['DESPESA'].tolist() + [""],
                        "VALOR": tabela_final['VALOR_STR'].tolist() + [soma_total_str],
                        "SITUAÇÃO": tabela_final['STATUS'].tolist() + ["-"]
                    }
                    
                    mapa_visual = {
                        "RAZÃO SOCIAL / DESCRIÇÃO": tabela_final['ENTIDADE'].tolist() + ["<b>TOTAL GERAL</b>"],
                        "DATA": tabela_final['DATA'].tolist() + ["<b>-</b>"],
                        "DOCUMENTO": tabela_final['DOCUMENTO'].tolist() + ["<b>-</b>"],
                        "NOTA FISCAL": tabela_final['NOTA FISCAL'].tolist() + ["<b>-</b>"],
                        "PARCELA": tabela_final['PARCELA'].tolist() + ["<b>-</b>"],
                        "DESPESA": tabela_final['DESPESA'].tolist() + ["<b></b>"],
                        "VALOR": tabela_final['VALOR_STR'].tolist() + [f"<b>{soma_total_str}</b>"],
                        "SITUAÇÃO": tabela_final['STATUS'].tolist() + ["<b>-</b>"]
                    }
                    
                    mapa_larguras = {
                        "RAZÃO SOCIAL / DESCRIÇÃO": 300, "DATA": 90, "DOCUMENTO": 90, "NOTA FISCAL": 90,
                        "PARCELA": 80, "DESPESA": 130, "VALOR": 110, "SITUAÇÃO": 120
                    }
                    
                    cols_pdf = {}
                    cabecalhos = []
                    celulas = []
                    larguras_colunas = []
                    
                    for col in colunas_selecionadas:
                        cols_pdf[col] = mapa_pdf[col]
                        cabecalhos.append(f"<b>{col}</b>")
                        celulas.append(mapa_visual[col])
                        larguras_colunas.append(mapa_larguras[col])
                        
                    df_pdf = pd.DataFrame(cols_pdf)

                    if FPDF is not None:
                        pdf_bytes = gerar_pdf_tabela(df_pdf, titulo_customizado_grafico + " (Tabela)", colunas_selecionadas, larguras_colunas)
                        st.download_button(label="📄 Baixar Tabela em PDF isolada", data=pdf_bytes, file_name=f"Tabela_JNL_{dt_inicio.strftime('%d%m%y')}.pdf", mime="application/pdf", use_container_width=True, key="btn_pdf_tabela")
                    else:
                        st.error("⚠️ Biblioteca 'fpdf' não instalada.")

                    cor_linhas_normais = '#F8F9FB'
                    cor_linha_total = '#D0D5DD'
                    cores_tabela = [cor_linhas_normais] * len(tabela_final) + [cor_linha_total]
                    array_cores_fundo = [cores_tabela] * len(cabecalhos)
                    
                    alinhamentos_plotly = []
                    for cab in cabecalhos:
                        cab_up = cab.upper()
                        if "RAZÃO" in cab_up or "DESCRIÇÃO" in cab_up: alinhamentos_plotly.append('left')
                        elif "VALOR" in cab_up: alinhamentos_plotly.append('right')
                        else: alinhamentos_plotly.append('center')

                    fig_table = go.Figure(data=[go.Table(
                        columnwidth=larguras_colunas,
                        header=dict(values=cabecalhos, fill_color='#111111', align=alinhamentos_plotly, font=dict(family='Calibri', color='white', size=13)),
                        cells=dict(values=celulas, fill_color=array_cores_fundo, align=alinhamentos_plotly, font=dict(family='Calibri', color='#1A1C1E', size=12), height=55)
                    )])
                    
                    fig_table.update_layout(
                        title=dict(text=f"<b>{titulo_customizado_grafico}</b>", font=dict(family='Calibri', color='#111111', size=16)),
                        margin=dict(l=0, r=0, b=0, t=40), height=550, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_table, use_container_width=True, config={'modeBarButtonsToAdd': ['toImage']})

                with aba_rel:
                    st.write("⚙️ **Monte o seu Relatório Completo**")
                    st.write("Selecione quais os blocos e a ordem em que devem aparecer no PDF final (cada gráfico ocupará 1 página e a tabela ocupará o restante).")
                    
                    opcoes_relatorio = [
                        "Gráfico: Por Entidade (Padrão)",
                        "Gráfico: Categorizado (Tipo Pagamento)",
                        "Gráfico: Por Categoria de Despesa",
                        "Tabela Detalhada"
                    ]
                    
                    if sort_items is not None:
                        ordem_relatorio = sort_items(opcoes_relatorio, direction='vertical', key="ordem_rel_pdf")
                    else:
                        ordem_relatorio = st.multiselect("Selecione e ordene os itens do relatório:", options=opcoes_relatorio, default=opcoes_relatorio)
                        
                    if ordem_relatorio:
                        safe_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', titulo_customizado_grafico).strip().replace(" ", "_")
                        if not safe_title: safe_title = "Relatorio_JNL"
                        file_name_final = f"{safe_title}.pdf"
                        
                        if FPDF is not None:
                            pdf_relatorio = PDFReport()
                            
                            for item in ordem_relatorio:
                                if item == "Gráfico: Por Entidade (Padrão)" and not dados_grafico_ent.empty:
                                    append_pdf_ranking(pdf_relatorio, dados_grafico_ent, f"{titulo_customizado_grafico} - Entidades")
                                elif item == "Gráfico: Categorizado (Tipo Pagamento)" and not dados_grafico_cat.empty:
                                    append_pdf_ranking(pdf_relatorio, dados_grafico_cat, f"{titulo_customizado_grafico} - Pagamentos")
                                elif item == "Gráfico: Por Categoria de Despesa" and not dados_grafico_desp.empty:
                                    append_pdf_ranking(pdf_relatorio, dados_grafico_desp, f"{titulo_customizado_grafico} - Despesas")
                                elif item == "Tabela Detalhada" and not df_pdf.empty:
                                    append_pdf_tabela(pdf_relatorio, df_pdf, f"{titulo_customizado_grafico} - Detalhado", colunas_selecionadas, larguras_colunas)
                                    
                            res = pdf_relatorio.output(dest='S')
                            if isinstance(res, str): pdf_bytes = res.encode('latin-1')
                            else: pdf_bytes = bytes(res)
                            
                            st.download_button(label="🚀 Baixar Relatório Completo (PDF)", data=pdf_bytes, file_name=file_name_final, mime="application/pdf", use_container_width=True, key="btn_relatorio_completo")
                        else:
                            st.error("⚠️ Biblioteca 'fpdf' não instalada.")
                            
            else: st.info("Todos os valores encontrados estão zerados no período selecionado.")
        else: st.warning("⚠️ Nenhuma data válida encontrada no ficheiro. Verifique a coluna de datas.")
else: st.info("Aguardando o envio da planilha...")