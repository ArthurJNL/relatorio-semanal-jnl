# -*- coding: utf-8 -*-

import io 
import math 
import os 
import re 
import tempfile 
import traceback 
import unicodedata 
import uuid 

import pandas as pd 
import streamlit as st 


# Componentes opcionais. A aus\xeancia de um deles n\xe3o impede o site de abrir.
try :
    from streamlit_echarts import st_echarts 
except Exception :
    st_echarts =None 

try :
    import plotly .graph_objects as go 
except Exception :
    go =None 

try :
    from fpdf import FPDF 
except Exception :
    FPDF =None 

try :
    from streamlit_sortables import sort_items 
except Exception :
    sort_items =None 


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


def formatar_contabil (valor ):
    try :
        numero =float (valor )
    except (TypeError ,ValueError ):
        numero =0.0 
    return f"R$ {numero :,.2f}".replace (',','X').replace ('.',',').replace ('X','.')


def extrair_valor (valor ):
    if pd .isna (valor ):
        return 0.0 
    if isinstance (valor ,(int ,float )):
        return float (valor )

    texto =str (valor ).upper ().replace ('R$','').replace (' ','')
    texto =re .sub ('[^0-9,.-]','',texto )
    if ','in texto and '.'in texto :
        texto =texto .replace ('.','').replace (',','.')
    elif ','in texto :
        texto =texto .replace (',','.')

    try :
        return float (texto )
    except (TypeError ,ValueError ):
        return 0.0 


def converter_para_data (valor ):
    return pd .to_datetime (valor ,errors ='coerce',dayfirst =True )


def calcular_status_vencimento (data_alvo ):
    if pd .isna (data_alvo ):
        return '-'
    hoje =pd .Timestamp .today ().normalize ()
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
    entidade =str (linha ['ENTIDADE']).strip ().upper ()
    if (
    entidade in {'','NAN','NONE'}
    or 'JNL IMPORTADORA'in entidade 
    or '01.718.395'in entidade 
    or 'MINHA EMPRESA'in entidade 
    ):
        return str (linha ['DESCRICAO']).strip ().upper ()
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
            valores =[linha [coluna ]for coluna in colunas ]
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


    def append_pdf_grafico (pdf ,df ,titulo ,coluna_nome ,coluna_valor ):
        pdf .add_page ()
        pdf .set_font ('Arial','B',14 )
        pdf .cell (0 ,10 ,limpar_texto_pdf (titulo ),border =0 ,ln =1 ,align ='C')

        try :
            import matplotlib 

            matplotlib .use ('Agg')
            import matplotlib .pyplot as plt 
        except Exception :
            pdf .set_font ('Arial','',10 )
            pdf .multi_cell (0 ,10 ,'Biblioteca matplotlib nao disponivel.',align ='C')
            return 

        df_plot =(
        df [[coluna_nome ,coluna_valor ]]
        .dropna ()
        .copy ()
        .sort_values (coluna_valor ,ascending =False )
        .reset_index (drop =True )
        )
        if df_plot .empty :
            pdf .set_font ('Arial','',10 )
            pdf .multi_cell (0 ,10 ,'Nenhum dado disponivel para o grafico.',align ='C')
            return 

        nomes =df_plot [coluna_nome ].astype (str ).map (
        lambda nome :f"{nome [:48 ]}..."if len (nome )>48 else nome 
        )
        valores =df_plot [coluna_valor ].astype (float ).tolist ()
        posicoes =list (range (len (df_plot )))
        altura_figura =min (max (4.8 ,len (df_plot )*0.38 ),9.2 )

        figura ,eixo =plt .subplots (figsize =(11.2 ,altura_figura ))
        eixo .barh (posicoes ,valores ,color ='#111111',height =0.62 )
        eixo .set_yticks (posicoes )
        eixo .set_yticklabels (nomes .tolist (),fontsize =8.5 )
        eixo .invert_yaxis ()
        eixo .xaxis .set_visible (False )
        eixo .tick_params (axis ='y',length =0 ,pad =5 )
        for borda in ['top','right','bottom','left']:
            eixo .spines [borda ].set_visible (False )

        maximo =max (max (valores ),1 )
        eixo .set_xlim (0 ,maximo *1.34 )
        for posicao ,valor in zip (posicoes ,valores ):
            eixo .text (
            valor +maximo *0.018 ,
            posicao ,
            formatar_contabil (valor ),
            va ='center',
            ha ='left',
            fontsize =8.5 ,
            fontweight ='bold',
            color ='#111111',
            )

        figura .subplots_adjust (left =0.40 ,right =0.94 ,top =0.97 ,bottom =0.04 )
        caminho =os .path .join (tempfile .gettempdir (),f"relatoriador_{uuid .uuid4 ().hex }.png")
        figura .savefig (caminho ,dpi =160 ,bbox_inches ='tight',pad_inches =0.12 ,facecolor ='white')
        plt .close (figura )

        try :
            y =max (pdf .get_y ()+5 ,25 )
            pdf .image (caminho ,x =10 ,y =y ,w =190 )
        finally :
            try :
                os .remove (caminho )
            except OSError :
                pass 


    def finalizar_pdf (pdf ):
        resultado =pdf .output (dest ='S')
        if isinstance (resultado ,str ):
            return resultado .encode ('latin-1')
        return bytes (resultado )


def opcoes_echarts (titulo ,nomes ,valores ,largura_rotulo =220 ):
    dados =[]
    for valor in valores :
        numero =float (valor )
        dados .append (
        {
        'value':numero ,
        'label':{
        'show':True ,
        'position':'right',
        'formatter':formatar_contabil (numero ),
        'color':'#111111',
        },
        }
        )

    return {
    'backgroundColor':'transparent',
    'title':{
    'text':titulo ,
    'left':'center',
    'textStyle':{'color':'#111111','fontSize':18 ,'fontFamily':'Calibri'},
    },
    'toolbox':{
    'feature':{
    'saveAsImage':{
    'show':True ,
    'title':'Baixar JPG',
    'type':'jpeg',
    'backgroundColor':'#FFFFFF',
    'pixelRatio':2 ,
    }
    }
    },
    'tooltip':{'trigger':'axis','axisPointer':{'type':'shadow'}},
    'grid':{'top':80 ,'left':'1%','right':'17%','bottom':'2%','containLabel':True },
    'xAxis':{
    'type':'value',
    'splitLine':{'lineStyle':{'type':'dashed','color':'#E0E4E8'}},
    },
    'yAxis':{
    'type':'category',
    'data':nomes ,
    'axisLabel':{
    'interval':0 ,
    'width':largura_rotulo ,
    'overflow':'break',
    'lineHeight':14 ,
    'color':'#1A1C1E',
    },
    },
    'series':[
    {
    'type':'bar',
    'data':dados ,
    'itemStyle':{'color':'#111111','borderRadius':[0 ,8 ,8 ,0 ]},
    }
    ],
    }


def mostrar_grafico (titulo ,dataframe ,coluna_nome ,coluna_valor ,altura_por_item =50 ):
    dados =dataframe .sort_values (coluna_valor ,ascending =True )
    altura =max (400 ,len (dados )*altura_por_item )
    if st_echarts is not None :
        opcoes =opcoes_echarts (
        titulo ,
        dados [coluna_nome ].astype (str ).tolist (),
        dados [coluna_valor ].astype (float ).tolist (),
        )
        st_echarts (options =opcoes ,height =f"{altura }px")
    else :
        st .warning ('O gr\xe1fico ECharts est\xe1 indispon\xedvel, mas os dados continuam acess\xedveis.')
        st .bar_chart (dados .set_index (coluna_nome )[coluna_valor ],horizontal =True )


def assinatura_dados (*partes ):
    texto ='|'.join (str (parte )for parte in partes )
    return str (abs (hash (texto )))


with st .sidebar :
    st .title ('\U0001f6e1\ufe0f RELATORIADOR')
    st .markdown ('---')
    st .subheader ('\U0001f4c1 GERADOR')
    arquivos =st .file_uploader (
    'Suba as planilhas que deseja transformar',
    type =['xlsx','xls','csv'],
    accept_multiple_files =True ,
    )

    with st .expander ('Diagn\xf3stico das bibliotecas'):
        st .write (f"ECharts: {'OK'if st_echarts else 'indispon\xedvel'}")
        st .write (f"Plotly: {'OK'if go else 'indispon\xedvel'}")
        st .write (f"PDF: {'OK'if FPDF else 'indispon\xedvel'}")
        st .write (f"Ordenador: {'OK'if sort_items else 'indispon\xedvel'}")


if not arquivos :
    st .info ('Aguardando o envio da planilha...')
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

        if go is not None :
            alinhamentos =[]
            for coluna in colunas_selecionadas :
                coluna_limpa =remover_acentos (coluna )
                if 'RAZAO'in coluna_limpa or 'DESCRI'in coluna_limpa :
                    alinhamentos .append ('left')
                elif 'VALOR'in coluna_limpa :
                    alinhamentos .append ('right')
                else :
                    alinhamentos .append ('center')

            valores_visuais =[mapa [coluna ][:-1 ]+[f"<b>{mapa [coluna ][-1 ]}</b>"]for coluna in colunas_selecionadas ]
            cores_linha =['#F8F9FB']*len (tabela_final )+['#D0D5DD']
            figura =go .Figure (
            data =[
            go .Table (
            columnwidth =larguras ,
            header ={
            'values':[f"<b>{coluna }</b>"for coluna in colunas_selecionadas ],
            'fill_color':'#111111',
            'align':alinhamentos ,
            'font':{'family':'Calibri','color':'white','size':13 },
            },
            cells ={
            'values':valores_visuais ,
            'fill_color':[cores_linha ]*len (colunas_selecionadas ),
            'align':alinhamentos ,
            'font':{'family':'Calibri','color':'#1A1C1E','size':12 },
            'height':48 ,
            },
            )
            ]
            )
            figura .update_layout (
            title ={'text':f"<b>{titulo_tabela }</b>"},
            margin ={'l':0 ,'r':0 ,'b':0 ,'t':40 },
            height =550 ,
            )
            st .plotly_chart (figura ,use_container_width =True )
        else :
            st .dataframe (df_pdf ,use_container_width =True ,hide_index =True )

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
