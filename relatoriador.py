# -*- coding: utf-8 -*-

import io 
import math 
import re 
import traceback 
import unicodedata 
from decimal import Decimal ,InvalidOperation ,ROUND_HALF_UP
from pathlib import Path

import pandas as pd
import streamlit as st

from erp_adapter import adaptar_exportacao_novo_erp ,prioridade_arquivo ,tipo_legado_por_nome


try :
    from fpdf import FPDF 
except Exception :
    FPDF =None 

try :
    from streamlit_sortables import sort_items 
except Exception :
    sort_items =None 

try :
    from pypdf import PdfReader ,PdfWriter
except Exception :
    PdfReader =None
    PdfWriter =None


st .set_page_config (page_title ='RELATORIADOR',page_icon ='\U0001f6e1\ufe0f',layout ='wide')

st .markdown (
'\n    <style>\n    html, body, [class*="css"] { font-family: \'Calibri\', sans-serif; }\n    .stApp { background-color: #F8F9FB; }\n    [data-testid="stSidebar"] {\n        background-color: #FFFFFF;\n        border-right: 1px solid #E0E4E8;\n    }\n    [data-testid="stMetric"], .echarts-container, .js-plotly-plot {\n        background: white !important;\n        border: 1px solid #E0E4E8 !important;\n        border-radius: 15px !important;\n        padding: 10px !important;\n        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;\n    }\n    .stTextInput > div > div > input {\n        border-radius: 12px;\n        border: 1px solid #D0D5DD;\n        padding: 12px 20px;\n        font-family: \'Calibri\', sans-serif;\n    }\n    .stTextInput > div > div > input:focus {\n        border-color: #000000;\n        box-shadow: 0 0 0 1px #000000;\n    }\n    .stDeployButton { display: none; }\n    </style>\n    ',
unsafe_allow_html =True ,
)


MESES_PT ={
1 :'JANEIRO',
2 :'FEVEREIRO',
3 :'MAR\xc7O',
4 :'ABRIL',
5 :'MAIO',
6 :'JUNHO',
7 :'JULHO',
8 :'AGOSTO',
9 :'SETEMBRO',
10 :'OUTUBRO',
11 :'NOVEMBRO',
12 :'DEZEMBRO',
}

DESPESAS_VALIDAS =[
'ALUGUEL',
'CART\xc3O DE CR\xc9DITO',
'MFC',
'CONSUMO',
'DESPACHANTE ADUANEIRO',
'DESPESA VARIAVEL',
'EMPRESTIMO',
'DOA\xc7\xc3O',
'FORNECEDOR EXTERIOR',
'FORNECEDORES',
'FUNCION\xc1RIOS',
'IMPOSTO',
'MARKETING',
'PATRIMONIO',
'PRESTADOR DE SERVI\xc7O',
'RENEGOCIA\xc7\xc3O - ACORDO',
'SEGURO',
'S\xd3CIOS',
'TRANSPORTADORA',
]


def remover_acentos (texto ):
    return (
    unicodedata .normalize ('NFKD',str (texto ))
    .encode ('ASCII','ignore')
    .decode ('utf-8')
    .upper ()
    )


DESPESAS_VALIDAS_LIMPAS =[remover_acentos (item )for item in DESPESAS_VALIDAS ]
PADRAO_MOEDA_BRL =re .compile (r'^R\$ -?(?:0|[1-9]\d{0,2}(?:\.\d{3})*),\d{2}$')


def forcar_virgula_nos_centavos (texto ):
    texto =str (texto ).strip ()
    texto =re .sub (r'[.,](\d{2})$',r',\1',texto )
    return texto


def validar_mascara_brl (texto ):
    texto =str (texto ).strip ()
    if not PADRAO_MOEDA_BRL .fullmatch (texto ):
        raise ValueError (f'Máscara monetária inválida: {texto}')
    return texto


def formatar_contabil (valor ):
    try :
        if isinstance (valor ,str ):
            numero =Decimal (str (extrair_valor (valor )))
        else :
            numero =Decimal (str (valor ))
        if not numero .is_finite ():
            numero =Decimal ('0')
    except (InvalidOperation ,TypeError ,ValueError ):
        numero =Decimal ('0')

    numero =numero .quantize (Decimal ('0.01'),rounding =ROUND_HALF_UP )
    sinal ='-'if numero <0 else ''
    inteiro ,centavos =f"{abs (numero ):.2f}".split ('.')
    grupos =[]
    while inteiro :
        grupos .append (inteiro [-3 :])
        inteiro =inteiro [:-3 ]
    parte_inteira ='.'.join (reversed (grupos ))or '0'
    texto_final =f"R$ {sinal}{parte_inteira},{centavos}"
    texto_final =forcar_virgula_nos_centavos (texto_final )
    return validar_mascara_brl (texto_final )


def extrair_valor (valor ):
    if pd .isna (valor ):
        return 0.0 
    if isinstance (valor ,(int ,float )):
        return float (valor )

    texto_original =str (valor ).upper ().replace ('R$','').replace (' ','').strip ()
    negativo =texto_original .startswith ('-')or (
        texto_original .startswith ('(')and texto_original .endswith (')')
    )
    texto =re .sub ('[^0-9,.]','',texto_original )

    if ','in texto and '.'in texto :
        if texto .rfind (',')>texto .rfind ('.'):
            texto =texto .replace ('.','').replace (',','.')
        else :
            texto =texto .replace (',','')
    elif texto .count ('.')>1 :
        partes =texto .split ('.')
        texto =''.join (partes [:-1 ])+'.'+partes [-1 ]if len (partes [-1 ])==2 else ''.join (partes )
    elif texto .count ('.')==1 :
        inteiro ,decimal =texto .split ('.')
        texto =inteiro +decimal if len (decimal )==3 else inteiro +'.'+decimal
    elif texto .count (',')>1 :
        partes =texto .split (',')
        texto =''.join (partes [:-1 ])+'.'+partes [-1 ]if len (partes [-1 ])==2 else ''.join (partes )
    elif ','in texto :
        texto =texto .replace (',','.')

    try :
        numero =float (texto )
        return -abs (numero )if negativo else numero
    except (TypeError ,ValueError ):
        return 0.0 


def normalizar_texto_exibicao (valor ):
    if pd .isna (valor ):
        return ''
    texto =re .sub (r'\s+',' ',str (valor ).upper ().strip ())
    texto =re .sub (r'\bLOCAC(?:AO|ÃO)\b','LOCAÇÃO',texto )
    texto =re .sub (r'\bLOCAC(?:OES|ÕES)\b','LOCAÇÕES',texto )
    return texto


def converter_para_data (valor ):
    return pd .to_datetime (valor ,errors ='coerce',dayfirst =True )


def calcular_status_vencimento (data_alvo ,data_referencia =None ):
    if pd .isna (data_alvo ):
        return '-'
    hoje =(
    pd .Timestamp (data_referencia ).normalize ()
    if data_referencia is not None
    else pd .Timestamp .today ().normalize ()
    )
    data =pd .Timestamp (data_alvo ).normalize ()
    diferenca =(data -hoje ).days 
    if diferenca <0 :
        return f"\U0001f6a8 Vencido h\u00e1 {abs (diferenca )} dias"
    if diferenca ==0 :
        return '\u26a0\ufe0f Vence HOJE'
    return f"\u2705 Vence em {diferenca } dias"


def limpar_texto_pdf (texto ):
    if pd .isna (texto ):
        return ''
    texto =str (texto )
    texto =(
    texto .replace ('\U0001f6a8','(!)')
    .replace ('\u26a0\ufe0f','(!)')
    .replace ('\u2705','(OK)')
    .replace ('\U0001f6e1\ufe0f','')
    )
    return texto .encode ('latin-1','ignore').decode ('latin-1')


def limpar_nome_arquivo (nome ):
    nome =re .sub ('[\\\\/*?:"<>|]','',str (nome )).strip ()
    return nome [:120 ]or 'Relatorio_JNL'


def tornar_cabecalhos_unicos (cabecalhos ):
    usados ={}
    resultado =[]
    for indice ,cabecalho in enumerate (cabecalhos ):
        texto =str (cabecalho ).strip ().upper ()
        if not texto or texto in {'NAN','NONE'}:
            texto =f"COL_{indice }"
        quantidade =usados .get (texto ,0 )
        usados [texto ]=quantidade +1 
        resultado .append (texto if quantidade ==0 else f"{texto }_{quantidade +1 }")
    return resultado 


def processar_excel_hibrido (df ):
    cabecalho =None 
    inicio_dados =None 
    palavras_chave =[
    'DATA',
    'PREVIS\xc3O',
    'PREVISAO',
    'VALOR',
    'A RECEBER',
    'RECEBIDO',
    'RAZ\xc3O SOCIAL',
    'RAZAO SOCIAL',
    'CLIENTE',
    'FORNECEDOR',
    'DEVEDOR',
    ]

    for indice ,linha in df .iterrows ():
        preenchidos =[str (x ).strip ().upper ()for x in linha .values if pd .notna (x )]
        texto_linha =' '.join (preenchidos )
        if len (preenchidos )>=3 and any (chave in texto_linha for chave in palavras_chave ):
            cabecalho =tornar_cabecalhos_unicos (linha .values )
            inicio_dados =indice +1 
            break 

    if cabecalho is None or inicio_dados is None :
        return []

    df_dados =df .iloc [inicio_dados :].reset_index (drop =True )
    indice_data =None 
    for chave in ['PREVIS\xc3O','PREVISAO','VENCIMENTO','DATA','CR\xc9DITO','CREDITO']:
        indice_data =next ((i for i ,coluna in enumerate (cabecalho )if chave in coluna ),None )
        if indice_data is not None :
            break 

    blocos ={}
    mes_separador =None 

    for _ ,linha in df_dados .iterrows ():
        valores_validos =[str (x ).strip ().upper ()for x in linha .values if pd .notna (x )]
        if not valores_validos :
            continue 

        texto_linha =' '.join (valores_validos )
        texto_sem_acento =remover_acentos (texto_linha )

        if 'MES:'in texto_sem_acento :
            mes_separador =texto_linha .split (':',1 )[-1 ].strip ()
            continue 

        if (
        ('DATA'in texto_sem_acento or 'PREVISAO'in texto_sem_acento )
        and ('VALOR'in texto_sem_acento or 'A RECEBER'in texto_sem_acento )
        ):
            continue 

        valores =list (linha .values )[:len (cabecalho )]
        valores .extend ([None ]*(len (cabecalho )-len (valores )))

        nome_mes =mes_separador 
        if nome_mes is None and indice_data is not None and indice_data <len (valores ):
            data =converter_para_data (valores [indice_data ])
            if pd .notna (data ):
                nome_mes =f"{MESES_PT [data .month ]} / {data .year }"

        if indice_data is not None and len (valores_validos )<=2 and pd .isna (valores [indice_data ]):
            continue 

        nome_mes =nome_mes or 'SEM DATA'
        blocos .setdefault (nome_mes ,[]).append (valores )

    return [
    (nome_mes ,pd .DataFrame (linhas ,columns =cabecalho ))
    for nome_mes ,linhas in blocos .items ()
    ]


def encontrar_coluna (colunas ,prioridades ,excluir =None ):
    excluir =excluir or []
    for prioridade in prioridades :
        prioridade_limpa =remover_acentos (prioridade )
        for coluna in colunas :
            coluna_limpa =remover_acentos (coluna )
            if prioridade_limpa in coluna_limpa and not any (
            remover_acentos (item )in coluna_limpa for item in excluir 
            ):
                return coluna 
    return None 


@st .cache_data (show_spinner =False )
def ler_arquivo (nome ,conteudo ):
    buffer =io .BytesIO (conteudo )
    nome_minusculo =nome .lower ()

    if nome_minusculo .endswith ('.csv'):
        ultimo_erro =None 
        for encoding in ['utf-8-sig','latin-1']:
            for separador in [';',',','\t']:
                try :
                    buffer .seek (0 )
                    df =pd .read_csv (buffer ,header =None ,sep =separador ,encoding =encoding )
                    if len (df .columns )>2 :
                        return df 
                except Exception as erro :
                    ultimo_erro =erro 
        if ultimo_erro :
            raise ultimo_erro 

    buffer .seek (0 )
    return pd .read_excel (buffer ,header =None )


def preparar_resumo (df_mes ):
    colunas =list (df_mes .columns )

    valores_diretos =[
    coluna 
    for coluna in colunas 
    if remover_acentos (coluna ).strip ()in {'RECEBIDO','A RECEBER'}
    ]
    if len (valores_diretos )==2 :
        contagens ={
        coluna :df_mes [coluna ].map (extrair_valor ).gt (0 ).sum ()
        for coluna in valores_diretos 
        }
        col_valor =max (contagens ,key =contagens .get )
    elif len (valores_diretos )==1 :
        col_valor =valores_diretos [0 ]
    else :
        col_valor =encontrar_coluna (colunas ,['VALOR','PAGO','A PAGAR'])

    col_data =encontrar_coluna (
    colunas ,
    ['PREVIS\xc3O','PREVISAO','VENCIMENTO','DATA','PAGAMENTO','CR\xc9DITO','CREDITO'],
    )
    col_documento =encontrar_coluna (
    colunas ,
    ['FORMA DE PAGAMENTO','DOCUMENTO','DOC','TIPO','MODALIDADE'],
    )
    col_nf =encontrar_coluna (colunas ,['NOTA FISCAL','N.F','NF','NOTA'])
    col_parcela =encontrar_coluna (colunas ,['N\xba PARCELA','NUMERO PARCELA','PARCELA','PARC'])
    col_entidade =encontrar_coluna (
    colunas ,
    ['RAZ\xc3O SOCIAL','RAZAO SOCIAL','CLIENTE','FORNECEDOR','DEVEDOR'],
    excluir =['MINHA EMPRESA'],
    )
    col_descricao =encontrar_coluna (
    colunas ,
    ['DESCRI\xc7\xc3O','DESCRICAO','HIST\xd3RICO','HISTORICO','RAZ\xc3O SOCIAL','RAZAO SOCIAL','CLIENTE','FORNECEDOR','DEVEDOR'],
    excluir =['MINHA EMPRESA'],
    )

    if col_valor is None or col_data is None :
        return None 

    if col_descricao is None :
        col_descricao =colunas [1 ]if len (colunas )>1 else colunas [0 ]
    if col_entidade is None :
        col_entidade =col_descricao 

    df =df_mes .copy ()
    df ['VALOR_NORMALIZADO']=df [col_valor ].map (extrair_valor )
    df ['DATA_NORMALIZADA']=pd .to_datetime (df [col_data ],errors ='coerce',dayfirst =True ).dt .normalize ()
    df ['DESCRICAO_LIMPA']=(
    df [col_descricao ].astype (str ).str .upper ().str .strip ().replace ('\\s+',' ',regex =True )
    )
    df ['ENTIDADE_LIMPA']=(
    df [col_entidade ].astype (str ).str .upper ().str .strip ().replace ('\\s+',' ',regex =True )
    )
    df ['DESCRICAO_LIMPA']=df ['DESCRICAO_LIMPA'].map (normalizar_texto_exibicao )
    df ['ENTIDADE_LIMPA']=df ['ENTIDADE_LIMPA'].map (normalizar_texto_exibicao )

    df =df [~df ['DESCRICAO_LIMPA'].isin (['','NAN','NONE'])]
    df ['ENTIDADE_LIMPA']=df ['ENTIDADE_LIMPA'].replace (['','NAN','NONE'],pd .NA )
    df ['ENTIDADE_LIMPA']=df ['ENTIDADE_LIMPA'].fillna (df ['DESCRICAO_LIMPA'])

    def coluna_texto (coluna ):
        if coluna is None :
            return pd .Series ('-',index =df .index ,dtype ='object')
        serie =df [coluna ].astype (str ).str .upper ().str .strip ()
        return serie .replace (['NAN','NONE',''],'-')

    df ['DOCUMENTO']=coluna_texto (col_documento )
    df ['NOTA FISCAL']=coluna_texto (col_nf )
    df ['PARCELA']=coluna_texto (col_parcela )

    def extrair_despesa (linha ):
        texto =remover_acentos (' '.join (str (x )for x in linha .values if pd .notna (x )))
        for indice ,despesa in enumerate (DESPESAS_VALIDAS_LIMPAS ):
            if despesa in texto :
                return DESPESAS_VALIDAS [indice ]
        return ''

    df ['DESPESA']=df .apply (extrair_despesa ,axis =1 )

    return pd .DataFrame (
    {
    'ENTIDADE':df ['ENTIDADE_LIMPA'],
    'DESCRICAO':df ['DESCRICAO_LIMPA'],
    'DATA':df ['DATA_NORMALIZADA'],
    'DOCUMENTO':df ['DOCUMENTO'],
    'NOTA FISCAL':df ['NOTA FISCAL'],
    'PARCELA':df ['PARCELA'],
    'DESPESA':df ['DESPESA'],
    'VALOR':df ['VALOR_NORMALIZADO'],
    }
    )


def categorizar_pagamento (documento ):
    texto =remover_acentos (documento )
    if 'BOLETO'in texto :
        return 'Boleto'
    if 'CART'in texto :
        return 'Cart\xe3o'
    if any (item in texto for item in ['DEP','PIX','VISTA','TRANSF','TED','DOC']):
        return 'Dep\xf3sito/\xe0 vista/pix'
    if 'DIN'in texto or 'ESP'in texto :
        return 'Dinheiro'
    return 'Outros'


def entidade_para_grafico (linha ):
    entidade =normalizar_texto_exibicao (linha ['ENTIDADE'])
    if (
    entidade in {'','NAN','NONE'}
    or 'JNL IMPORTADORA'in entidade 
    or '01.718.395'in entidade 
    or 'MINHA EMPRESA'in entidade 
    ):
        return normalizar_texto_exibicao (linha ['DESCRICAO'])
    return entidade 


def obter_linhas_reais (pdf ,largura ,texto ):
    texto =limpar_texto_pdf (texto )
    if not texto :
        return 1 
    largura_util =max (largura -3 ,1 )
    total =0 
    for paragrafo in texto .split ('\n'):
        palavras =paragrafo .split ()
        if not palavras :
            total +=1 
            continue 
        linha =''
        linhas_paragrafo =1 
        for palavra in palavras :
            teste =palavra if not linha else f"{linha } {palavra }"
            if pdf .get_string_width (teste )>largura_util :
                if linha :
                    linhas_paragrafo +=1 
                else :
                    linhas_paragrafo +=max (1 ,math .ceil (pdf .get_string_width (palavra )/largura_util ))-1 
                linha =palavra 
            else :
                linha =teste 
        total +=linhas_paragrafo 
    return max (total ,1 )


if FPDF is not None :

    class PDFReport (FPDF ):
        def footer (self ):
            self .set_y (-15 )
            self .set_font ('Arial','I',8 )
            self .cell (0 ,10 ,f"Pagina {self .page_no ()}",border =0 ,align ='C')


    def desenhar_cabecalho_tabela (pdf ,colunas ,larguras ):
        pdf .set_fill_color (17 ,17 ,17 )
        pdf .set_text_color (255 ,255 ,255 )
        for indice ,coluna in enumerate (colunas ):
            texto =limpar_texto_pdf (coluna )
            tamanho =9.0 
            pdf .set_font ('Arial','B',tamanho )
            while pdf .get_string_width (texto )>larguras [indice ]-2 and tamanho >5 :
                tamanho -=0.5 
                pdf .set_font ('Arial','B',tamanho )
            pdf .cell (larguras [indice ],8 ,texto ,border =1 ,fill =True ,align ='C')
        pdf .ln ()


    def append_pdf_tabela (pdf ,df ,titulo ,colunas ,larguras ):
        pdf .add_page ()
        if titulo :
            pdf .set_font ('Arial','B',12 )
            pdf .cell (0 ,10 ,limpar_texto_pdf (titulo ),border =0 ,ln =1 ,align ='C')
            pdf .ln (4 )

        fator =190 /max (sum (larguras ),1 )
        larguras =[largura *fator for largura in larguras ]
        desenhar_cabecalho_tabela (pdf ,colunas ,larguras )

        altura_texto =5 
        for _ ,linha in df .iterrows ():
            valores =[]
            for coluna in colunas :
                valor =linha [coluna ]
                if 'VALOR'in remover_acentos (coluna )and str (valor ).strip ()not in {'','-'}:
                    valor =forcar_virgula_nos_centavos (formatar_contabil (valor ))
                valores .append (valor )
            total =any ('TOTAL'in str (valor ).upper ()for valor in valores )
            pdf .set_font ('Arial','B'if total else '',9 if total else 8 )

            quantidade_linhas =max (
            obter_linhas_reais (pdf ,larguras [indice ],valor )
            for indice ,valor in enumerate (valores )
            )
            altura_linha =quantidade_linhas *altura_texto +2 

            if pdf .get_y ()+altura_linha >275 :
                pdf .add_page ()
                desenhar_cabecalho_tabela (pdf ,colunas ,larguras )
                pdf .set_font ('Arial','B'if total else '',9 if total else 8 )

            inicio_x =pdf .get_x ()
            inicio_y =pdf .get_y ()
            deslocamento_x =0 

            for indice ,valor in enumerate (valores ):
                largura =larguras [indice ]
                x =inicio_x +deslocamento_x 
                texto =limpar_texto_pdf (valor )

                if total :
                    pdf .set_fill_color (230 ,230 ,230 )
                    pdf .set_text_color (17 ,17 ,17 )
                    pdf .rect (x ,inicio_y ,largura ,altura_linha ,style ='DF')
                else :
                    pdf .set_fill_color (255 ,255 ,255 )
                    pdf .set_text_color (26 ,28 ,30 )
                    pdf .rect (x ,inicio_y ,largura ,altura_linha ,style ='D')

                linhas_texto =obter_linhas_reais (pdf ,largura ,texto )
                y_texto =inicio_y +(altura_linha -linhas_texto *altura_texto )/2 
                pdf .set_xy (x ,y_texto )

                coluna =remover_acentos (colunas [indice ])
                if 'RAZAO'in coluna or 'DESCRI'in coluna :
                    alinhamento ='L'
                elif 'VALOR'in coluna :
                    alinhamento ='R'
                else :
                    alinhamento ='C'

                pdf .multi_cell (largura ,altura_texto ,texto ,border =0 ,align =alinhamento )
                deslocamento_x +=largura 

            pdf .set_xy (inicio_x ,inicio_y +altura_linha )


    def encurtar_texto_pdf (pdf ,texto ,largura ):
        texto =limpar_texto_pdf (texto )
        if pdf .get_string_width (texto )<=largura :
            return texto
        sufixo ='...'
        while texto and pdf .get_string_width (texto +sufixo )>largura :
            texto =texto [:-1 ]
        return texto .rstrip ()+sufixo


    def append_pdf_grafico (pdf ,df ,titulo ,coluna_nome ,coluna_valor ):
        df_plot =(
        df [[coluna_nome ,coluna_valor ]]
        .dropna ()
        .copy ()
        .sort_values (coluna_valor ,ascending =False )
        .reset_index (drop =True )
        )

        pdf .add_page ()
        if df_plot .empty :
            pdf .set_font ('Arial','B',14 )
            pdf .cell (0 ,10 ,limpar_texto_pdf (titulo ),border =0 ,ln =1 ,align ='C')
            pdf .set_font ('Arial','',10 )
            pdf .multi_cell (0 ,10 ,'Nenhum dado disponivel para o grafico.',align ='C')
            return

        valores =df_plot [coluna_valor ].astype (float ).tolist ()
        valor_maximo =max (max (valores ),1 )
        inicio_y =30
        limite_y =272
        espaco_vertical =limite_y -inicio_y
        minimo_altura_linha =4.0
        linhas_por_pagina =max (1 ,int (espaco_vertical /minimo_altura_linha ))

        for inicio in range (0 ,len (df_plot ),linhas_por_pagina ):
            if inicio >0 :
                pdf .add_page ()
            titulo_pagina =titulo if inicio ==0 else f"{titulo} - Continuacao"
            pdf .set_font ('Arial','B',14 )
            pdf .cell (0 ,10 ,limpar_texto_pdf (titulo_pagina ),border =0 ,ln =1 ,align ='C')

            trecho =df_plot .iloc [inicio :inicio +linhas_por_pagina ]
            altura_linha =min (8.0 ,max (minimo_altura_linha ,espaco_vertical /max (len (trecho ),1 )))
            tamanho_fonte =8.0 if len (trecho )<=20 else min (8.0 ,max (4.0 ,altura_linha *0.82 ))
            largura_rotulo =76
            x_rotulo =10
            x_barra =89
            largura_maxima_barra =72
            largura_valor =37
            y =inicio_y

            pdf .set_draw_color (210 ,213 ,217 )
            pdf .line (x_barra ,y ,x_barra ,y +altura_linha *len (trecho ))

            for _ ,linha in trecho .iterrows ():
                nome =linha [coluna_nome ]
                valor =float (linha [coluna_valor ])
                largura_barra =max (0.8 ,(valor /valor_maximo )*largura_maxima_barra )

                pdf .set_font ('Arial','',tamanho_fonte )
                pdf .set_text_color (26 ,28 ,30 )
                nome_curto =encurtar_texto_pdf (pdf ,nome ,largura_rotulo -2 )
                pdf .set_xy (x_rotulo ,y )
                pdf .cell (largura_rotulo ,altura_linha ,nome_curto ,border =0 ,align ='R')

                pdf .set_fill_color (17 ,17 ,17 )
                altura_barra =max (1.2 ,altura_linha *0.58 )
                y_barra =y +(altura_linha -altura_barra )/2
                pdf .rect (x_barra ,y_barra ,largura_barra ,altura_barra ,style ='F')

                pdf .set_font ('Arial','B',tamanho_fonte )
                pdf .set_xy (x_barra +largura_barra +1 ,y )
                rotulo_valor =formatar_contabil (valor )
                rotulo_valor =forcar_virgula_nos_centavos (rotulo_valor )
                rotulo_valor =validar_mascara_brl (rotulo_valor )
                pdf .cell (largura_valor ,altura_linha ,limpar_texto_pdf (rotulo_valor ),border =0 ,align ='L')
                y +=altura_linha

            pdf .set_text_color (0 ,0 ,0 )


    def finalizar_pdf (pdf ):
        resultado =pdf .output (dest ='S')
        if isinstance (resultado ,str ):
            return resultado .encode ('latin-1')
        return bytes (resultado )


def mostrar_grafico (titulo ,dataframe ,coluna_nome ,coluna_valor ,altura_por_item =50 ):
    dados =(
    dataframe [[coluna_nome ,coluna_valor ]]
    .dropna ()
    .copy ()
    .sort_values (coluna_valor ,ascending =False )
    )
    if dados .empty :
        st .info ('Nenhum dado disponível para o gráfico.')
        return

    altura =min (900 ,max (400 ,len (dados )*altura_por_item ))
    st .subheader (titulo )
    st .bar_chart (
    dados ,
    x =coluna_nome ,
    y =coluna_valor ,
    color ='#111111',
    horizontal =True ,
    height =altura ,
    use_container_width =True ,
    )
    st .caption ('Passe o cursor sobre as barras para consultar os valores exatos.')


def assinatura_dados (*partes ):
    texto ='|'.join (str (parte )for parte in partes )
    return str (abs (hash (texto )))


# -----------------------------------------------------------------------------
# Modo automático: um bloco completo por planilha, com a respectiva capa.
# A ordem abaixo reproduz o RELATÓRIO FINANCEIRO.pdf usado como modelo.
# -----------------------------------------------------------------------------

PASTA_APP =Path (__file__ ).resolve ().parent
PASTA_CAPAS =PASTA_APP /'assets'

ESPECIFICACOES_RELATORIOS ={
    'notas_em_atraso':{
        'nome_arquivo':'NOTAS EM ATRASO',
        'titulo':'NOTAS EM ATRASO',
        'capa':'INADIMPLÊNCIA.pdf',
        'segundo_grafico':'pagamentos',
        'situacao':True,
    },
    'notas_a_receber':{
        'nome_arquivo':'RELAÇÃO DE NOTAS À RECEBER',
        'titulo':'RELAÇÃO DE NOTAS À RECEBER',
        'capa':'FLUXO DE CAIXA PROJETADO.pdf',
        'segundo_grafico':'pagamentos',
        'situacao':False,
    },
    'notas_recebidas':{
        'nome_arquivo':'RELAÇÃO DE NOTAS RECEBIDAS',
        'titulo':'RELAÇÃO DE NOTAS RECEBIDAS',
        'capa':'FLUXO DE CAIXA REALIZADO.pdf',
        'segundo_grafico':'pagamentos',
        'situacao':False,
    },
    'fluxo_de_pagamento':{
        'nome_arquivo':'FLUXO DE PAGAMENTO',
        'titulo':'FLUXO DE PAGAMENTO',
        'capa':'FLUXO DE CAIXA REALIZADO.pdf',
        'segundo_grafico':'despesas',
        'situacao':False,
    },
    'contas_a_pagar':{
        'nome_arquivo':'RELAÇÃO DE CONTAS À PAGAR',
        'titulo':'RELAÇÃO DE CONTAS À PAGAR',
        'capa':'FLUXO DE CAIXA PROJETADO.pdf',
        'segundo_grafico':'despesas',
        'situacao':False,
    },
}

ORDEM_PADRAO_AUTOMATICA =[
    'notas_em_atraso',
    'notas_a_receber',
    'notas_recebidas',
    'fluxo_de_pagamento',
    'contas_a_pagar',
]


def normalizar_nome_entrada (nome ):
    base =Path (str (nome )).stem
    # Aceita cópias baixadas pelo navegador, como "ARQUIVO (1).xlsx".
    base =re .sub (r'\s*\(\d+\)\s*$','',base )
    base =remover_acentos (base )
    return re .sub (r'[^A-Z0-9]+',' ',base ).strip ()


MAPA_NOMES_AUTOMATICOS ={
    normalizar_nome_entrada (especificacao ['nome_arquivo']):chave
    for chave ,especificacao in ESPECIFICACOES_RELATORIOS .items ()
}

# Nomes oficiais dos três arquivos do novo fluxo. Os aliases abaixo também
# permitem que RECEBIDOS e CONTAS A PAGAR sejam usados enquanto ainda estiverem
# na estrutura antiga. Quando a estrutura nova for detectada, o conteúdo tem
# prioridade e CONTAS A PAGAR é separado automaticamente em pago e em aberto.
MAPA_NOMES_AUTOMATICOS .update ({
    normalizar_nome_entrada ('RECEBIDOS.xlsx'):'notas_recebidas',
    normalizar_nome_entrada ('CONTAS A PAGAR.xlsx'):'contas_a_pagar',
})


def reconhecer_tipo_relatorio (nome_arquivo ):
    return (
    MAPA_NOMES_AUTOMATICOS .get (normalizar_nome_entrada (nome_arquivo ))
    or tipo_legado_por_nome (nome_arquivo )
    )


@st .cache_data (show_spinner =False )
def preparar_arquivo_automatico (nome_arquivo ,conteudo ):
    bruto =ler_arquivo (nome_arquivo ,conteudo )
    resultado_novo =adaptar_exportacao_novo_erp (bruto )
    if resultado_novo .get ('reconhecido'):
        return resultado_novo

    chave =reconhecer_tipo_relatorio (nome_arquivo )
    if chave is None :
        raise ValueError ('Nome e estrutura de planilha não reconhecidos.')

    blocos_arquivo =processar_excel_hibrido (bruto )
    resumos_arquivo =[]
    for _ ,bloco in blocos_arquivo :
        resumo =preparar_resumo (bloco )
        if resumo is not None and not resumo .empty :
            resumos_arquivo .append (resumo )

    if not resumos_arquivo :
        raise ValueError ('Nenhuma tabela válida foi reconhecida dentro da planilha.')

    dados =pd .concat (resumos_arquivo ,ignore_index =True )
    dados =dados .dropna (subset =['DATA'])
    dados =dados [dados ['VALOR']>0 ].copy ()
    if dados .empty :
        raise ValueError ('A planilha não possui datas e valores válidos para o relatório.')
    return {
        'reconhecido':True,
        'tipo_fonte':'Modelo anterior',
        'dados_por_tipo':{chave:dados },
        'cancelados_qtd':0,
        'cancelados_valor':0.0,
    }


def componentes_do_relatorio (dados ,data_referencia =None ):
    df =dados .copy ()
    df ['ENTIDADE_GRAFICO']=df .apply (entidade_para_grafico ,axis =1 )

    entidades =(
        df .groupby ('ENTIDADE_GRAFICO',as_index =False )['VALOR']
        .sum ()
        .rename (columns ={'ENTIDADE_GRAFICO':'ENTIDADE'})
        .query ('VALOR > 0')
        .sort_values ('VALOR',ascending =False )
    )

    categorias =df .copy ()
    categorias ['CATEGORIA']=categorias ['DOCUMENTO'].map (categorizar_pagamento )
    pagamentos =(
        categorias .groupby ('CATEGORIA',as_index =False )['VALOR']
        .sum ()
        .query ('VALOR > 0')
        .sort_values ('VALOR',ascending =False )
    )

    com_despesa =df [df ['DESPESA']!='']
    despesas =(
        com_despesa .groupby ('DESPESA',as_index =False )['VALOR']
        .sum ()
        .query ('VALOR > 0')
        .sort_values ('VALOR',ascending =False )
        if not com_despesa .empty
        else pd .DataFrame (columns =['DESPESA','VALOR'])
    )

    detalhe =(
        df .groupby (
            ['DESCRICAO','DATA','DOCUMENTO','NOTA FISCAL','PARCELA','DESPESA'],
            as_index =False,
            dropna =False,
        )['VALOR']
        .sum ()
        .query ('VALOR > 0')
        .sort_values (['DATA','DESCRICAO'])
    )
    detalhe ['STATUS']=detalhe ['DATA'].map (
        lambda data:calcular_status_vencimento (data ,data_referencia )
    )
    detalhe ['DATA']=detalhe ['DATA'].dt .strftime ('%d/%m/%Y')
    return entidades ,pagamentos ,despesas ,detalhe


def tabela_automatica (detalhe ,especificacao ):
    total =formatar_contabil (detalhe ['VALOR'].sum ())
    valores =detalhe ['VALOR'].map (formatar_contabil ).tolist ()

    if especificacao ['segundo_grafico']=='despesas':
        colunas =['DATA','RAZÃO SOCIAL / DESCRIÇÃO','DESPESA','VALOR']
        larguras =[82 ,340 ,125 ,110 ]
        tabela =pd .DataFrame ({
            'DATA':detalhe ['DATA'].tolist ()+['-'],
            'RAZÃO SOCIAL / DESCRIÇÃO':detalhe ['DESCRICAO'].tolist ()+['TOTAL GERAL'],
            'DESPESA':detalhe ['DESPESA'].replace ('','-').tolist ()+[''],
            'VALOR':valores +[total ],
        })
        return tabela ,colunas ,larguras

    colunas =['DATA','RAZÃO SOCIAL / DESCRIÇÃO','DOCUMENTO','NOTA FISCAL','VALOR']
    larguras =[82 ,300 ,90 ,90 ,110 ]
    mapa ={
        'DATA':detalhe ['DATA'].tolist ()+['-'],
        'RAZÃO SOCIAL / DESCRIÇÃO':detalhe ['DESCRICAO'].tolist ()+['TOTAL GERAL'],
        'DOCUMENTO':detalhe ['DOCUMENTO'].tolist ()+['-'],
        'NOTA FISCAL':detalhe ['NOTA FISCAL'].tolist ()+['-'],
        'VALOR':valores +[total ],
    }
    if especificacao ['situacao']:
        colunas .append ('SITUAÇÃO')
        larguras .append (125 )
        mapa ['SITUAÇÃO']=detalhe ['STATUS'].tolist ()+['-']
    return pd .DataFrame ({coluna :mapa [coluna ]for coluna in colunas }),colunas ,larguras


def gerar_paginas_de_um_relatorio (chave_relatorio ,dados ,data_referencia =None ):
    especificacao =ESPECIFICACOES_RELATORIOS [chave_relatorio ]
    titulo =especificacao ['titulo']
    entidades ,pagamentos ,despesas ,detalhe =componentes_do_relatorio (dados ,data_referencia )
    tabela ,colunas ,larguras =tabela_automatica (detalhe ,especificacao )

    pdf =PDFReport ()
    if not entidades .empty :
        append_pdf_grafico (pdf ,entidades ,f"{titulo} - Entidades",'ENTIDADE','VALOR')

    if especificacao ['segundo_grafico']=='despesas':
        if not despesas .empty :
            append_pdf_grafico (pdf ,despesas ,f"{titulo} - Despesas",'DESPESA','VALOR')
    elif not pagamentos .empty :
        append_pdf_grafico (pdf ,pagamentos ,f"{titulo} - Pagamentos",'CATEGORIA','VALOR')

    append_pdf_tabela (pdf ,tabela ,f"{titulo} - Detalhado",colunas ,larguras )
    return finalizar_pdf (pdf )


def adicionar_pdf_ao_writer (writer ,origem ):
    leitor =PdfReader (origem )
    for pagina in leitor .pages :
        writer .add_page (pagina )


def gerar_resumo_executivo (ordem ,dados_por_tipo ,inicio ,fim ):
    pdf =PDFReport ()
    pdf .add_page ()
    pdf .set_fill_color (17 ,17 ,17 )
    pdf .rect (0 ,0 ,210 ,42 ,style ='F')
    pdf .set_text_color (255 ,255 ,255 )
    pdf .set_font ('Arial','B',20 )
    pdf .set_xy (14 ,12 )
    pdf .cell (182 ,10 ,'RELATORIO FINANCEIRO',border =0 ,ln =1 ,align ='L')
    pdf .set_font ('Arial','',10 )
    pdf .set_x (14 )
    periodo =f"Periodo: {inicio.strftime ('%d/%m/%Y')} a {fim.strftime ('%d/%m/%Y')}"
    pdf .cell (182 ,7 ,limpar_texto_pdf (periodo ),border =0 ,align ='L')

    pdf .set_text_color (17 ,17 ,17 )
    pdf .set_xy (14 ,52 )
    pdf .set_font ('Arial','B',14 )
    pdf .cell (182 ,8 ,'RESUMO EXECUTIVO',border =0 ,ln =1 )

    configuracoes =[
        ('notas_em_atraso','EM ATRASO',(178 ,44 ,44 )),
        ('notas_a_receber','A RECEBER',(48 ,112 ,90 )),
        ('notas_recebidas','RECEBIDO',(33 ,89 ,68 )),
        ('fluxo_de_pagamento','PAGO',(73 ,80 ,87 )),
        ('contas_a_pagar','A PAGAR',(169 ,102 ,21 )),
    ]
    disponiveis =[item for item in configuracoes if item [0 ]in ordem]
    largura =86
    altura =29
    for indice ,(chave ,rotulo ,cor )in enumerate (disponiveis ):
        coluna =indice %2
        linha =indice //2
        x =14 +coluna *94
        y =67 +linha *36
        dados =dados_por_tipo [chave ]
        total =formatar_contabil (dados ['VALOR'].sum ())
        pdf .set_fill_color (248 ,249 ,251 )
        pdf .set_draw_color (*cor )
        pdf .rect (x ,y ,largura ,altura ,style ='DF')
        pdf .set_xy (x +4 ,y +4 )
        pdf .set_text_color (*cor )
        pdf .set_font ('Arial','B',9 )
        pdf .cell (largura -8 ,5 ,rotulo ,border =0 ,ln =1 )
        pdf .set_x (x +4 )
        pdf .set_text_color (17 ,17 ,17 )
        pdf .set_font ('Arial','B',13 )
        pdf .cell (largura -8 ,8 ,limpar_texto_pdf (total ),border =0 ,ln =1 )
        pdf .set_x (x +4 )
        pdf .set_font ('Arial','',8 )
        pdf .set_text_color (73 ,80 ,87 )
        pdf .cell (largura -8 ,5 ,f"{len (dados )} lancamento(s)",border =0 )

    y_saldos =67 +math .ceil (len (disponiveis )/2 )*36 +4
    pdf .set_xy (14 ,y_saldos )
    pdf .set_font ('Arial','B',12 )
    pdf .set_text_color (17 ,17 ,17 )
    pdf .cell (182 ,7 ,'INDICADORES',border =0 ,ln =1 )

    indicadores =[]
    if {'notas_recebidas','fluxo_de_pagamento'}.issubset (dados_por_tipo ):
        recebidos =dados_por_tipo ['notas_recebidas']['VALOR'].sum ()
        pagos =dados_por_tipo ['fluxo_de_pagamento']['VALOR'].sum ()
        indicadores .append (('Saldo realizado (recebido - pago)',formatar_contabil (recebidos -pagos )))
    else :
        indicadores .append (('Saldo realizado','Indisponivel - falta RECEBIDO ou PAGO'))

    if {'notas_a_receber','contas_a_pagar'}.issubset (dados_por_tipo ):
        a_receber =dados_por_tipo ['notas_a_receber']['VALOR'].sum ()
        a_pagar =dados_por_tipo ['contas_a_pagar']['VALOR'].sum ()
        indicadores .append (('Saldo projetado (a receber - a pagar)',formatar_contabil (a_receber -a_pagar )))
    else :
        indicadores .append (('Saldo projetado','Indisponivel - falta A RECEBER ou A PAGAR'))

    for rotulo ,valor_texto in indicadores :
        pdf .set_x (14 )
        pdf .set_font ('Arial','',10 )
        pdf .cell (120 ,8 ,limpar_texto_pdf (rotulo ),border =0 )
        pdf .set_font ('Arial','B',8 if 'Indisponivel'in valor_texto else 10 )
        pdf .cell (62 ,8 ,limpar_texto_pdf (valor_texto ),border =0 ,ln =1 ,align ='R')

    pdf .set_xy (14 ,min (258 ,y_saldos +42 ))
    pdf .set_font ('Arial','',8 )
    pdf .set_text_color (92 ,99 ,106 )
    pdf .multi_cell (
        182 ,5 ,
        'O saldo projetado considera apenas os titulos a vencer do periodo selecionado. '
        'Os valores vencidos aparecem separadamente em EM ATRASO.',
        border =0 ,align ='L',
    )
    return finalizar_pdf (pdf )


def gerar_relatorio_financeiro_automatico (ordem ,dados_por_tipo ,inicio ,fim ):
    if FPDF is None :
        raise RuntimeError ('fpdf2 não está instalado.')
    if PdfReader is None or PdfWriter is None :
        raise RuntimeError ('pypdf não está instalado.')

    writer =PdfWriter ()
    resumo =gerar_resumo_executivo (ordem ,dados_por_tipo ,inicio ,fim )
    adicionar_pdf_ao_writer (writer ,io .BytesIO (resumo ))
    for chave in ordem :
        especificacao =ESPECIFICACOES_RELATORIOS [chave ]
        caminho_capa =PASTA_CAPAS /especificacao ['capa']
        if not caminho_capa .exists ():
            raise FileNotFoundError (f"Capa não encontrada: {caminho_capa.name}")

        adicionar_pdf_ao_writer (writer ,str (caminho_capa ))
        paginas =gerar_paginas_de_um_relatorio (chave ,dados_por_tipo [chave ],fim )
        adicionar_pdf_ao_writer (writer ,io .BytesIO (paginas ))

    saida =io .BytesIO ()
    writer .write (saida )
    return saida .getvalue ()


def executar_modo_automatico (arquivos ):
    st .markdown ('# Relatório financeiro automático')
    st .caption (
        'Aceita os arquivos do sistema anterior e os relatórios do novo ERP. '
        'O conteúdo e os status definem automaticamente cada bloco do PDF.'
    )

    dados_por_tipo ={}
    fontes_por_tipo ={}
    linhas_diagnostico =[]
    erros =[]

    arquivos_ordenados =sorted (
        arquivos,
        key =lambda arquivo:prioridade_arquivo (arquivo .name ),
        reverse =True,
    )
    for arquivo in arquivos_ordenados :
        try :
            resultado =preparar_arquivo_automatico (arquivo .name ,arquivo .getvalue ())
        except Exception as erro :
            erros .append (f"{arquivo.name}: {erro}")
            linhas_diagnostico .append ({
                'Arquivo':arquivo .name,
                'Resultado':'Não reconhecido',
                'Itens':0,
                'Total':'-',
                'Observação':str (erro ),
            })
            continue

        adicionados =[]
        ignorados =[]
        quantidade =0
        total =0.0
        for chave ,dados in resultado ['dados_por_tipo'].items ():
            titulo =ESPECIFICACOES_RELATORIOS [chave ]['titulo']
            if chave in dados_por_tipo :
                ignorados .append (titulo )
                continue
            dados_por_tipo [chave ]=dados
            fontes_por_tipo [chave ]=arquivo .name
            adicionados .append (titulo )
            quantidade +=len (dados )
            total +=float (dados ['VALOR'].sum ())

        observacoes =[]
        if ignorados :
            observacoes .append ('Redundante e ignorado: '+', '.join (ignorados ))
        cancelados_qtd =resultado .get ('cancelados_qtd',0 )
        if cancelados_qtd :
            observacoes .append (
                f"{cancelados_qtd} nota(s) cancelada(s) excluída(s), "
                f"total {formatar_contabil (resultado.get ('cancelados_valor',0 ))}"
            )
        linhas_diagnostico .append ({
            'Arquivo':arquivo .name,
            'Resultado':', '.join (adicionados )if adicionados else 'Arquivo redundante',
            'Itens':quantidade,
            'Total':formatar_contabil (total )if adicionados else '-',
            'Observação':'; '.join (observacoes )or resultado .get ('tipo_fonte','Reconhecido'),
        })

    st .dataframe (pd .DataFrame (linhas_diagnostico ),use_container_width =True ,hide_index =True )
    for erro in erros :
        st .error (erro )
    if not dados_por_tipo :
        st .error ('Nenhuma planilha compatível foi reconhecida.')
        return

    faltantes =[chave for chave in ORDEM_PADRAO_AUTOMATICA if chave not in dados_por_tipo]
    if 'contas_a_pagar'in faltantes :
        st .warning (
            'Falta a exportação das contas a pagar ainda em aberto. O arquivo recebido contém '
            'somente pagamentos realizados, por isso gera FLUXO DE PAGAMENTO, mas não A PAGAR.'
        )
    outros_faltantes =[
        ESPECIFICACOES_RELATORIOS [chave ]['titulo']
        for chave in faltantes
        if chave !='contas_a_pagar'
    ]
    if outros_faltantes :
        st .warning ('Blocos sem dados: '+', '.join (outros_faltantes ))
    if not faltantes :
        st .success ('Todos os cinco blocos financeiros foram reconhecidos.')

    data_minima =min (df ['DATA'].min ()for df in dados_por_tipo .values ()).date ()
    data_maxima =max (df ['DATA'].max ()for df in dados_por_tipo .values ()).date ()
    with st .sidebar :
        st .subheader ('📅 Filtro do relatório automático')
        periodo =st .date_input (
            'Selecione De / Até:',
            value =(data_minima ,data_maxima ),
            min_value =data_minima,
            max_value =data_maxima,
            format ='DD/MM/YYYY',
            key ='periodo_automatico',
        )
    if isinstance (periodo ,(tuple ,list ))and len (periodo )==2 :
        inicio ,fim =periodo
    elif isinstance (periodo ,(tuple ,list ))and len (periodo )==1 :
        inicio =fim =periodo [0 ]
    else :
        inicio ,fim =data_minima ,data_maxima

    dados_filtrados ={}
    for chave ,df in dados_por_tipo .items ():
        if chave =='notas_em_atraso':
            # Inadimplência é uma posição acumulada na data final, não apenas o movimento da semana.
            filtro =df ['DATA']<=pd .Timestamp (fim )
        else :
            filtro =(df ['DATA']>=pd .Timestamp (inicio ))&(df ['DATA']<=pd .Timestamp (fim ))
        recorte =df .loc [filtro ].copy ()
        if not recorte .empty :
            dados_filtrados [chave ]=recorte

    if not dados_filtrados :
        st .info ('Nenhum lançamento foi encontrado no período selecionado.')
        return

    ordem_disponivel =[chave for chave in ORDEM_PADRAO_AUTOMATICA if chave in dados_filtrados ]
    rotulo_para_chave ={
        ESPECIFICACOES_RELATORIOS [chave ]['titulo']:chave
        for chave in ordem_disponivel
    }
    rotulos_padrao =[ESPECIFICACOES_RELATORIOS [chave ]['titulo']for chave in ordem_disponivel ]

    st .subheader ('Ordem dos blocos no PDF')
    st .caption ('Cada bloco leva sua capa vinculada. Arraste para ordenar ou mova para a lixeira para excluir.')
    if sort_items is not None :
        assinatura_opcoes ='|'.join (rotulos_padrao )
        if st .session_state .get ('assinatura_blocos_auto')!=assinatura_opcoes :
            st .session_state ['estado_blocos_auto']=[
                {'header':'✅ INCLUIR NO PDF','items':rotulos_padrao },
                {'header':'❌ NÃO INCLUIR','items':[]},
            ]
            st .session_state ['assinatura_blocos_auto']=assinatura_opcoes
        estado =sort_items (
            st .session_state ['estado_blocos_auto'],
            multi_containers =True,
            direction ='vertical',
            key ='ordenador_blocos_auto',
        )
        if estado :
            st .session_state ['estado_blocos_auto']=estado
        rotulos_escolhidos =st .session_state ['estado_blocos_auto'][0 ]['items']
    else :
        st .info ('O arrastar e soltar está indisponível. Selecione os itens já na ordem desejada.')
        rotulos_escolhidos =st .multiselect (
            'Relatórios incluídos',
            options =rotulos_padrao,
            default =rotulos_padrao,
            key ='blocos_auto_fallback',
        )

    ordem =[rotulo_para_chave [rotulo ]for rotulo in rotulos_escolhidos if rotulo in rotulo_para_chave ]
    if not ordem :
        st .info ('Inclua pelo menos um bloco no PDF.')
        return

    resumo =[]
    for posicao ,chave in enumerate (ordem ,start =1 ):
        especificacao =ESPECIFICACOES_RELATORIOS [chave ]
        df =dados_filtrados [chave ]
        resumo .append ({
            'Ordem':posicao,
            'Relatório':especificacao ['titulo'],
            'Capa':especificacao ['capa'],
            'Itens':len (df ),
            'Total':formatar_contabil (df ['VALOR'].sum ()),
        })
    st .dataframe (pd .DataFrame (resumo ),use_container_width =True ,hide_index =True )

    assinatura =assinatura_dados (
        ordem,
        inicio,
        fim,
        [(chave ,len (dados_filtrados [chave ]),dados_filtrados [chave ]['VALOR'].sum ())for chave in ordem ],
    )
    if st .session_state .get ('assinatura_pdf_automatico')!=assinatura :
        st .session_state .pop ('pdf_automatico_pronto',None )

    if FPDF is None or PdfWriter is None :
        st .error ('PDF indisponível. Confirme fpdf2 e pypdf no requirements.txt.')
    elif st .button ('🚀 Preparar relatório financeiro completo',type ='primary',use_container_width =True ):
        with st .spinner ('Gerando capas, gráficos e tabelas na ordem escolhida...'):
            st .session_state ['pdf_automatico_pronto']=gerar_relatorio_financeiro_automatico (
                ordem,
                dados_filtrados,
                inicio,
                fim,
            )
            st .session_state ['assinatura_pdf_automatico']=assinatura

    if 'pdf_automatico_pronto'in st .session_state :
        st .download_button (
            '⬇️ Baixar RELATÓRIO FINANCEIRO.pdf',
            data =st .session_state ['pdf_automatico_pronto'],
            file_name ='RELATÓRIO FINANCEIRO.pdf',
            mime ='application/pdf',
            use_container_width =True,
        )


with st .sidebar :
    st .title ('\U0001f6e1\ufe0f RELATORIADOR')
    st .markdown ('---')
    st .subheader ('\U0001f4c1 GERADOR')
    modo =st .radio (
    'Modo de geração',
    ['Relatório completo automático','Individual / personalizado'],
    help ='O modo automático reconhece os arquivos antigos e os relatórios do novo ERP, separando os blocos pelo conteúdo e pelos status.',
    )
    arquivos =st .file_uploader (
    'Suba uma ou mais planilhas',
    type =['xlsx','xls','csv'],
    accept_multiple_files =True ,
    )

    with st .expander ('Arquivos necessários do novo ERP'):
        st .write ('1. AGUARDANDO RECEBIMENTO.xlsx — gera atrasados e a receber')
        st .write ('2. RECEBIDOS.xlsx — gera recebimentos realizados')
        st .write ('3. CONTAS A PAGAR.xlsx — gera pagamentos realizados e valores em aberto')
        st .caption ('CONTAS A PAGAR aceita temporariamente a estrutura antiga. Na estrutura nova, os lançamentos são separados automaticamente pela data e pelo valor pago.')
        st .caption ('ATRASADOS e NÃO VENCIDAS são dispensáveis quando o consolidado aguardando recebimento é enviado.')

    with st .expander ('Diagn\xf3stico das bibliotecas'):
        st .write ('Gráficos na tela: OK (Streamlit nativo)')
        st .write ('Tabelas na tela: OK (Streamlit nativo)')
        st .write (f"PDF: {'OK'if FPDF else 'indispon\xedvel'}")
        st .write (f"Mesclagem de capas: {'OK'if PdfWriter else 'indisponível'}")
        st .write (f"Ordenador: {'OK'if sort_items else 'indispon\xedvel'}")
        capas_ok =all ((PASTA_CAPAS /item ['capa']).exists ()for item in ESPECIFICACOES_RELATORIOS .values ())
        st .write (f"Capas: {'OK'if capas_ok else 'arquivo ausente'}")


if not arquivos :
    st .info ('Aguardando o envio da planilha...')
    st .stop ()


if modo =='Relatório completo automático':
    try :
        executar_modo_automatico (arquivos )
    except Exception as erro_automatico :
        st .error ('Não foi possível concluir o relatório automático.')
        st .error (str (erro_automatico ))
        with st .expander ('Detalhes técnicos para correção'):
            st .code (traceback .format_exc ())
    st .stop ()


try :
    blocos =[]
    for arquivo in arquivos :
        try :
            df_bruto =ler_arquivo (arquivo .name ,arquivo .getvalue ())
            resultados =processar_excel_hibrido (df_bruto )
            if not resultados :
                st .warning (f"N\u00e3o foi poss\u00edvel reconhecer o cabe\u00e7alho de: {arquivo .name }")
            blocos .extend (resultados )
        except ImportError as erro :
            st .error (
            f"N\u00e3o foi poss\u00edvel abrir {arquivo .name }. Verifique openpyxl/xlrd no requirements.txt. Detalhe: {erro }"
            )
        except Exception as erro :
            st .error (f"Erro ao ler {arquivo .name }: {erro }")

    resumos =[]
    for _ ,df_mes in blocos :
        resumo =preparar_resumo (df_mes )
        if resumo is not None and not resumo .empty :
            resumos .append (resumo )

    if not resumos :
        st .warning ('Nenhuma tabela v\xe1lida foi encontrada nos arquivos enviados.')
        st .stop ()

    df_master =pd .concat (resumos ,ignore_index =True ).dropna (subset =['DATA'])
    df_master =df_master [df_master ['VALOR']>0 ]
    if df_master .empty :
        st .warning ('Nenhuma data e nenhum valor v\xe1lido foram encontrados.')
        st .stop ()

    data_minima =df_master ['DATA'].min ().date ()
    data_maxima =df_master ['DATA'].max ().date ()

    with st .sidebar :
        st .subheader ('\U0001f4c5 Filtro de Per\xedodo')
        periodo =st .date_input (
        'Selecione De / At\xe9:',
        value =(data_minima ,data_maxima ),
        min_value =data_minima ,
        max_value =data_maxima ,
        format ='DD/MM/YYYY',
        )

    if isinstance (periodo ,(tuple ,list ))and len (periodo )==2 :
        inicio ,fim =periodo 
    elif isinstance (periodo ,(tuple ,list ))and len (periodo )==1 :
        inicio =fim =periodo [0 ]
    else :
        inicio ,fim =data_minima ,data_maxima 

    filtro_data =(df_master ['DATA']>=pd .Timestamp (inicio ))&(
    df_master ['DATA']<=pd .Timestamp (fim )
    )
    df_filtrado =df_master .loc [filtro_data ].copy ()

    st .markdown ('# Relat\xf3rio gerado')
    pesquisa =st .text_input (
    '\U0001f4ac Filtro de pesquisa...',
    placeholder ='Ex.: IMPORPECAS, KS MAQUINAS...',
    )
    if pesquisa :
        termo =pesquisa .strip ()
        filtro_texto =(
        df_filtrado ['ENTIDADE'].str .contains (termo ,case =False ,na =False ,regex =False )
        |df_filtrado ['DESCRICAO'].str .contains (termo ,case =False ,na =False ,regex =False )
        )
        df_filtrado =df_filtrado .loc [filtro_texto ].copy ()

    if df_filtrado .empty :
        st .info ('Nenhum item foi encontrado para os filtros selecionados.')
        st .stop ()

    df_filtrado ['ENTIDADE_GRAFICO']=df_filtrado .apply (entidade_para_grafico ,axis =1 )

    grafico_entidades =(
    df_filtrado .groupby ('ENTIDADE_GRAFICO',as_index =False )['VALOR']
    .sum ()
    .rename (columns ={'ENTIDADE_GRAFICO':'ENTIDADE'})
    .query ('VALOR > 0')
    .sort_values ('VALOR',ascending =False )
    )

    df_categorias =df_filtrado .copy ()
    df_categorias ['CATEGORIA']=df_categorias ['DOCUMENTO'].map (categorizar_pagamento )
    grafico_categorias =(
    df_categorias .groupby ('CATEGORIA',as_index =False )['VALOR']
    .sum ()
    .query ('VALOR > 0')
    .sort_values ('VALOR',ascending =False )
    )

    df_despesas =df_filtrado [df_filtrado ['DESPESA']!='']
    grafico_despesas =(
    df_despesas .groupby ('DESPESA',as_index =False )['VALOR']
    .sum ()
    .query ('VALOR > 0')
    .sort_values ('VALOR',ascending =False )
    if not df_despesas .empty 
    else pd .DataFrame (columns =['DESPESA','VALOR'])
    )

    tabela =(
    df_filtrado .groupby (
    ['DESCRICAO','DATA','DOCUMENTO','NOTA FISCAL','PARCELA','DESPESA'],
    as_index =False ,
    dropna =False ,
    )['VALOR']
    .sum ()
    .query ('VALOR > 0')
    .sort_values (['DATA','DESCRICAO'])
    )
    tabela ['STATUS']=tabela ['DATA'].map (calcular_status_vencimento )
    tabela ['DATA']=tabela ['DATA'].dt .strftime ('%d/%m/%Y')

    coluna_1 ,coluna_2 ,coluna_3 ,coluna_4 =st .columns (4 )
    coluna_1 .metric ('Volume Total (Filtrado)',formatar_contabil (df_filtrado ['VALOR'].sum ()))
    coluna_2 .metric (
    'Principal Entidade',
    grafico_entidades .iloc [0 ]['ENTIDADE']if not grafico_entidades .empty else '-',
    )
    coluna_3 .metric ('Per\xedodo Analisado',f"{(fim -inicio ).days +1 } Dia(s)")
    coluna_4 .metric ('Quantidade de itens',f"{len (tabela )} Linha(s)")

    st .markdown ('---')
    quantidade_entidades =max (len (grafico_entidades ),1 )
    limite =st .slider (
    '\U0001f39a\ufe0f N\xfamero de entidades exibidas:',
    min_value =1 ,
    max_value =quantidade_entidades ,
    value =min (30 ,quantidade_entidades ),
    )
    grafico_entidades_limitado =grafico_entidades .head (limite )

    aba_grafico ,aba_tabela ,aba_relatorio =st .tabs (
    ['\U0001f4ca Gr\xe1fico','\U0001f4cb Tabela Detalhada','\U0001f4d1 Relat\xf3rio Completo']
    )

    with aba_grafico :
        titulo =st .text_input (
        '\U0001f4dd T\xedtulo Customizado:',
        value =f"RELA\u00c7\u00c3O DE VALORES ({inicio .strftime ('%d/%m/%Y')} at\u00e9 {fim .strftime ('%d/%m/%Y')})",
        )
        tipo =st .radio (
        '\U0001f4ca Escolha o gr\xe1fico:',
        [
        'Por Entidade (Padr\xe3o)',
        'Categorizado (Por Tipo de Pagamento)',
        'Por Categoria de Despesa',
        ],
        horizontal =True ,
        )

        if tipo =='Por Entidade (Padr\xe3o)':
            mostrar_grafico (titulo ,grafico_entidades_limitado ,'ENTIDADE','VALOR',50 )
        elif tipo =='Categorizado (Por Tipo de Pagamento)':
            mostrar_grafico (f"{titulo } - Categorizado",grafico_categorias ,'CATEGORIA','VALOR',80 )
        elif grafico_despesas .empty :
            st .warning ('Nenhuma categoria de despesa foi reconhecida.')
        else :
            mostrar_grafico (f"{titulo } - Despesas",grafico_despesas ,'DESPESA','VALOR',60 )

    colunas_padrao =[
    'RAZ\xc3O SOCIAL / DESCRI\xc7\xc3O',
    'DATA',
    'DOCUMENTO',
    'NOTA FISCAL',
    'PARCELA',
    'VALOR',
    'SITUA\xc7\xc3O',
    ]
    colunas_ocultas =['DESPESA']

    with aba_tabela :
        titulo_tabela =st .text_input (
        '\U0001f4dd T\xedtulo Customizado (Tabela):',
        value =titulo ,
        key ='titulo_tabela',
        )

        if sort_items is not None :
            chave_estado ='estado_colunas_v2'
            if chave_estado not in st .session_state :
                st .session_state [chave_estado ]=[
                {'header':'\u2705 COLUNAS NA TELA E NO PDF','items':colunas_padrao },
                {'header':'\u274c LIXEIRA','items':colunas_ocultas },
                ]
            ordenado =sort_items (
            st .session_state [chave_estado ],
            multi_containers =True ,
            direction ='horizontal',
            key ='ordenador_colunas_v2',
            )
            if ordenado :
                st .session_state [chave_estado ]=ordenado 
            colunas_selecionadas =st .session_state [chave_estado ][0 ]['items']
        else :
            st .info ('O arrastar e soltar est\xe1 indispon\xedvel. A ordem padr\xe3o ser\xe1 usada.')
            colunas_selecionadas =colunas_padrao 

        colunas_selecionadas =colunas_selecionadas or ['RAZ\xc3O SOCIAL / DESCRI\xc7\xc3O','VALOR']
        tabela_final =tabela .copy ()
        tabela_final ['VALOR_STR']=tabela_final ['VALOR'].map (formatar_contabil )
        total =formatar_contabil (tabela_final ['VALOR'].sum ())

        mapa ={
        'RAZ\xc3O SOCIAL / DESCRI\xc7\xc3O':tabela_final ['DESCRICAO'].tolist ()+['TOTAL GERAL'],
        'DATA':tabela_final ['DATA'].tolist ()+['-'],
        'DOCUMENTO':tabela_final ['DOCUMENTO'].tolist ()+['-'],
        'NOTA FISCAL':tabela_final ['NOTA FISCAL'].tolist ()+['-'],
        'PARCELA':tabela_final ['PARCELA'].tolist ()+['-'],
        'DESPESA':tabela_final ['DESPESA'].tolist ()+[''],
        'VALOR':tabela_final ['VALOR_STR'].tolist ()+[total ],
        'SITUA\xc7\xc3O':tabela_final ['STATUS'].tolist ()+['-'],
        }
        larguras_mapa ={
        'RAZ\xc3O SOCIAL / DESCRI\xc7\xc3O':300 ,
        'DATA':90 ,
        'DOCUMENTO':90 ,
        'NOTA FISCAL':90 ,
        'PARCELA':80 ,
        'DESPESA':130 ,
        'VALOR':110 ,
        'SITUA\xc7\xc3O':120 ,
        }
        df_pdf =pd .DataFrame ({coluna :mapa [coluna ]for coluna in colunas_selecionadas })
        larguras =[larguras_mapa [coluna ]for coluna in colunas_selecionadas ]

        def estilo_linha_total (linha ):
            if linha .name ==df_pdf .index [-1 ]:
                return ['background-color: #D0D5DD; font-weight: 700']*len (linha )
            return ['background-color: #F8F9FB']*len (linha )

        st .subheader (titulo_tabela )
        altura_tabela =min (850 ,max (280 ,(len (df_pdf )+1 )*36 ))
        st .dataframe (
        df_pdf .style .apply (estilo_linha_total ,axis =1 ),
        use_container_width =True ,
        hide_index =True ,
        height =altura_tabela ,
        )

        assinatura_tabela =assinatura_dados (
        titulo_tabela ,
        colunas_selecionadas ,
        len (df_pdf ),
        tabela_final ['VALOR'].sum (),
        )
        if st .session_state .get ('assinatura_pdf_tabela')!=assinatura_tabela :
            st .session_state .pop ('pdf_tabela_pronto',None )

        if FPDF is None :
            st .error ('PDF indispon\xedvel. Confirme que fpdf2 est\xe1 no requirements.txt.')
        elif st .button ('\U0001f4c4 Preparar PDF da tabela',use_container_width =True ):
            with st .spinner ('Gerando PDF...'):
                pdf =PDFReport ()
                append_pdf_tabela (pdf ,df_pdf ,titulo_tabela ,colunas_selecionadas ,larguras )
                st .session_state ['pdf_tabela_pronto']=finalizar_pdf (pdf )
                st .session_state ['assinatura_pdf_tabela']=assinatura_tabela 

        if 'pdf_tabela_pronto'in st .session_state :
            st .download_button (
            '\u2b07\ufe0f Baixar Tabela em PDF',
            data =st .session_state ['pdf_tabela_pronto'],
            file_name =f"Tabela_JNL_{inicio .strftime ('%d%m%y')}.pdf",
            mime ='application/pdf',
            use_container_width =True ,
            )

    with aba_relatorio :
        st .write ('Monte o relat\xf3rio e s\xf3 depois clique em preparar. Isso evita estouro de mem\xf3ria no servidor.')
        opcoes =[
        'Gr\xe1fico: Por Entidade (Padr\xe3o)',
        'Gr\xe1fico: Categorizado (Por Tipo de Pagamento)',
        'Gr\xe1fico: Por Categoria de Despesa',
        'Tabela Detalhada',
        ]

        if sort_items is not None :
            chave_relatorio ='estado_relatorio_v2'
            if chave_relatorio not in st .session_state :
                st .session_state [chave_relatorio ]=[
                {'header':'\u2705 INCLUIR NO PDF','items':opcoes },
                {'header':'\u274c LIXEIRA','items':[]},
                ]
            ordem_atual =sort_items (
            st .session_state [chave_relatorio ],
            multi_containers =True ,
            direction ='vertical',
            key ='ordem_pdf_v2',
            )
            if ordem_atual :
                st .session_state [chave_relatorio ]=ordem_atual 
            ordem =st .session_state [chave_relatorio ][0 ]['items']
        else :
            ordem =opcoes 

        assinatura_relatorio =assinatura_dados (
        titulo ,
        ordem ,
        limite ,
        len (tabela ),
        df_filtrado ['VALOR'].sum (),
        )
        if st .session_state .get ('assinatura_pdf_completo')!=assinatura_relatorio :
            st .session_state .pop ('pdf_completo_pronto',None )

        if not ordem :
            st .info ('Inclua pelo menos um item no relat\xf3rio.')
        elif FPDF is None :
            st .error ('PDF indispon\xedvel. Confirme que fpdf2 est\xe1 no requirements.txt.')
        elif st .button ('\U0001f680 Preparar Relat\xf3rio Completo',use_container_width =True ):
            with st .spinner ('Montando o relat\xf3rio completo...'):
                pdf =PDFReport ()
                for item in ordem :
                    if item =='Gr\xe1fico: Por Entidade (Padr\xe3o)'and not grafico_entidades_limitado .empty :
                        append_pdf_grafico (pdf ,grafico_entidades_limitado ,f"{titulo } - Entidades",'ENTIDADE','VALOR')
                    elif item =='Gr\xe1fico: Categorizado (Por Tipo de Pagamento)'and not grafico_categorias .empty :
                        append_pdf_grafico (pdf ,grafico_categorias ,f"{titulo } - Pagamentos",'CATEGORIA','VALOR')
                    elif item =='Gr\xe1fico: Por Categoria de Despesa'and not grafico_despesas .empty :
                        append_pdf_grafico (pdf ,grafico_despesas ,f"{titulo } - Despesas",'DESPESA','VALOR')
                    elif item =='Tabela Detalhada'and not df_pdf .empty :
                        append_pdf_tabela (pdf ,df_pdf ,f"{titulo } - Detalhado",colunas_selecionadas ,larguras )

                st .session_state ['pdf_completo_pronto']=finalizar_pdf (pdf )
                st .session_state ['assinatura_pdf_completo']=assinatura_relatorio 

        if 'pdf_completo_pronto'in st .session_state :
            st .download_button (
            '\u2b07\ufe0f Baixar Relat\xf3rio Completo',
            data =st .session_state ['pdf_completo_pronto'],
            file_name =f"{limpar_nome_arquivo (titulo )}.pdf",
            mime ='application/pdf',
            use_container_width =True ,
            )

except Exception as erro_geral :
    st .error ('O processamento encontrou um erro inesperado, mas o aplicativo continua aberto.')
    st .error (str (erro_geral ))
    with st .expander ('Detalhes t\xe9cnicos para corre\xe7\xe3o'):
        st .code (traceback .format_exc ())
