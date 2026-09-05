# -*- coding: utf-8 -*-
"""Adaptadores dos arquivos exportados pelo ERP atual da JNL.

Este módulo não conhece Streamlit nem PDF. Ele transforma os relatórios brutos do
ERP em uma estrutura canônica que o ``relatoriador.py`` já sabe apresentar.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd


COLUNAS_CANONICAS = [
    "ENTIDADE",
    "DESCRICAO",
    "DATA",
    "DOCUMENTO",
    "NOTA FISCAL",
    "PARCELA",
    "DESPESA",
    "VALOR",
]


def _sem_acentos(valor):
    return (
        unicodedata.normalize("NFKD", str(valor))
        .encode("ASCII", "ignore")
        .decode("ASCII")
        .upper()
        .strip()
    )


def _texto(valor, padrao="-"):
    if pd.isna(valor):
        return padrao
    resultado = re.sub(r"\s+", " ", str(valor)).strip().upper()
    return resultado if resultado and resultado not in {"NAN", "NONE"} else padrao


def _dinheiro(valor):
    if pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = re.sub(r"[^0-9,.-]", "", str(valor)).strip()
    if not texto:
        return 0.0
    negativo = texto.startswith("-")
    texto = texto.lstrip("-")
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        partes = texto.split(".")
        texto = "".join(partes[:-1]) + "." + partes[-1]
    try:
        numero = float(texto)
    except ValueError:
        return 0.0
    return -abs(numero) if negativo else numero


def _cabecalhos_unicos(valores):
    usados = {}
    resultado = []
    for indice, valor in enumerate(valores):
        nome = str(valor).strip() if pd.notna(valor) else f"COL_{indice}"
        nome = nome or f"COL_{indice}"
        quantidade = usados.get(nome, 0)
        usados[nome] = quantidade + 1
        resultado.append(nome if quantidade == 0 else f"{nome}_{quantidade + 1}")
    return resultado


def _promover_cabecalho(bruto):
    termos = {
        "CLIENTE",
        "FORNECEDOR",
        "VALOR",
        "VENCIMENTO",
        "STATUS DO RECEBIMENTO",
        "DATA DE PAGAMENTO",
        "FORMA DE PAGAMENTO",
    }
    melhor_indice = None
    melhor_pontuacao = -1
    for indice in range(min(len(bruto), 15)):
        linha = {_sem_acentos(valor) for valor in bruto.iloc[indice].dropna().tolist()}
        pontuacao = len(linha & termos) * 10 + len(linha)
        if pontuacao > melhor_pontuacao:
            melhor_indice = indice
            melhor_pontuacao = pontuacao
    if melhor_indice is None:
        return pd.DataFrame()
    dados = bruto.iloc[melhor_indice + 1 :].copy()
    dados.columns = _cabecalhos_unicos(bruto.iloc[melhor_indice].tolist())
    return dados.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)


def _mapa_colunas(df):
    return {_sem_acentos(coluna): coluna for coluna in df.columns}


def _coluna(df, *nomes):
    mapa = _mapa_colunas(df)
    for nome in nomes:
        normalizado = _sem_acentos(nome)
        if normalizado in mapa:
            return mapa[normalizado]
    return None


def _serie_texto(df, coluna, padrao="-"):
    if coluna is None:
        return pd.Series(padrao, index=df.index, dtype="object")
    return df[coluna].map(lambda valor: _texto(valor, padrao))


def _serie_valor(df, coluna):
    if coluna is None:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return df[coluna].map(_dinheiro).astype(float)


def _serie_data(df, coluna):
    if coluna is None:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    # ``format='mixed'`` evita que uma data ISO numa linha faça o pandas inferir
    # um único formato e descarte outras datas válidas da mesma coluna.
    return pd.to_datetime(
        df[coluna], errors="coerce", dayfirst=True, format="mixed"
    ).dt.normalize()


def _nota_fiscal(linha, col_codigo, col_nfe, col_documento, col_descricao=None):
    candidatos = []
    for coluna in [col_codigo, col_nfe, col_documento, col_descricao]:
        if coluna is not None and pd.notna(linha.get(coluna)):
            candidatos.append(str(linha.get(coluna)))

    padroes = [
        r"NF\s*[- ]?E\s*[:Nº.]*\s*0*(\d+)",
        r"NF\s*[- ]?S\s*[:Nº.]*\s*0*(\d+)",
        r"\bNF\s*[:Nº.]*\s*0*(\d+)",
    ]
    for candidato in candidatos:
        texto = _sem_acentos(candidato)
        for padrao in padroes:
            encontrado = re.search(padrao, texto)
            if encontrado:
                return encontrado.group(1).zfill(8)

    for candidato in candidatos:
        trecho = str(candidato).split("-")[0]
        grupos = re.findall(r"\d+", trecho)
        if grupos:
            numero = grupos[-1].lstrip("0") or "0"
            if len(numero) <= 8:
                return numero.zfill(8)
    return "-"


def _parcela(linha, col_codigo, col_documento, col_descricao=None):
    for coluna in [col_codigo, col_documento, col_descricao]:
        if coluna is None or pd.isna(linha.get(coluna)):
            continue
        texto = _sem_acentos(linha.get(coluna))
        encontrado = re.search(r"(?:PARCELA\s*)?(\d{1,3}/\d{1,3})", texto)
        if encontrado:
            return encontrado.group(1)
    return "-"


def _categoria_despesa(valor):
    texto = _texto(valor, "")
    texto = re.sub(r"^\d+(?:\.\d+)*\s*-\s*", "", texto)
    return texto


def _deduplicar(df):
    if df.empty:
        return df.reindex(columns=COLUNAS_CANONICAS)
    # Não eliminamos linhas apenas por terem os mesmos campos visíveis: duas parcelas
    # ou dois lançamentos legítimos podem coincidir em cliente, data e valor.
    return df.reset_index(drop=True)


def _base_recebimentos(df, recebidos=False):
    col_cliente = _coluna(df, "Cliente")
    col_descricao = _coluna(df, "Descrição")
    col_forma = _coluna(df, "Forma de pagamento")
    col_codigo = _coluna(df, "Código")
    col_nfe = _coluna(df, "NF-e")
    col_documento = _coluna(df, "Número do documento")
    col_vencimento = _coluna(df, "Vencimento")
    col_pagamento = _coluna(df, "Data de pagamento")
    col_credito = _coluna(df, "Data de crédito")
    col_valor = _coluna(df, "Valor")
    col_recebido = _coluna(df, "Valor recebido")
    col_liquido = _coluna(df, "Valor líquido")

    entidade = _serie_texto(df, col_cliente)
    descricao = entidade.where(entidade != "-", _serie_texto(df, col_descricao))
    documento = _serie_texto(df, col_forma)
    vencimento = _serie_data(df, col_vencimento)

    if recebidos:
        data = _serie_data(df, col_credito)
        data = data.fillna(_serie_data(df, col_pagamento)).fillna(vencimento)
        valor_recebido = _serie_valor(df, col_recebido)
        valor_liquido = _serie_valor(df, col_liquido)
        valor_original = _serie_valor(df, col_valor)
        valor = valor_recebido.where(valor_recebido > 0, valor_liquido)
        valor = valor.where(valor > 0, valor_original)
    else:
        data = vencimento
        valor = _serie_valor(df, col_valor)

    resultado = pd.DataFrame(
        {
            "ENTIDADE": entidade,
            "DESCRICAO": descricao,
            "DATA": data,
            "DOCUMENTO": documento,
            "NOTA FISCAL": df.apply(
                _nota_fiscal,
                axis=1,
                args=(col_codigo, col_nfe, col_documento, col_descricao),
            ),
            "PARCELA": df.apply(
                _parcela,
                axis=1,
                args=(col_codigo, col_documento, col_descricao),
            ),
            "DESPESA": "",
            "VALOR": valor,
        }
    )
    resultado = resultado[(resultado["VALOR"] > 0) & resultado["DATA"].notna()]
    return _deduplicar(resultado)


def _adaptar_recebimentos(df):
    col_status = _coluna(df, "Status do Recebimento")
    col_status_nota = _coluna(df, "Status da Nota")
    col_valor = _coluna(df, "Valor")

    status = _serie_texto(df, col_status, "")
    status_norm = status.map(_sem_acentos)
    status_nota = _serie_texto(df, col_status_nota, "")
    cancelada = status_nota.map(_sem_acentos).str.contains("CANCEL", na=False)
    valor_cancelado = float(_serie_valor(df, col_valor)[cancelada].sum())
    dados = df.loc[~cancelada].copy()
    status_dados = status_norm.loc[~cancelada]

    mask_recebido = status_dados.str.contains("RECEBID", na=False)
    mask_vencido = status_dados.str.contains("VENCID", na=False) & ~status_dados.str.contains("NAO", na=False)
    mask_futuro = status_dados.str.contains("IMINENTE|A VENCER|NAO VENCID", regex=True, na=False)

    # Se o ERP mudar o rótulo, a data continua sendo um fallback seguro.
    sem_status = ~(mask_recebido | mask_vencido | mask_futuro)
    vencimentos = _serie_data(dados, _coluna(dados, "Vencimento"))
    hoje = pd.Timestamp.today().normalize()
    mask_vencido = mask_vencido | (sem_status & vencimentos.lt(hoje))
    mask_futuro = mask_futuro | (sem_status & vencimentos.ge(hoje))

    saidas = {}
    if mask_vencido.any():
        saidas["notas_em_atraso"] = _base_recebimentos(dados.loc[mask_vencido], recebidos=False)
    if mask_futuro.any():
        saidas["notas_a_receber"] = _base_recebimentos(dados.loc[mask_futuro], recebidos=False)
    if mask_recebido.any():
        saidas["notas_recebidas"] = _base_recebimentos(dados.loc[mask_recebido], recebidos=True)

    return {
        "reconhecido": True,
        "tipo_fonte": "Recebimentos do novo ERP",
        "dados_por_tipo": saidas,
        "cancelados_qtd": int(cancelada.sum()),
        "cancelados_valor": valor_cancelado,
    }


def _adaptar_pagamentos(df):
    col_descricao = _coluna(df, "Descrição")
    col_fornecedor = _coluna(df, "Fornecedor")
    col_forma = _coluna(df, "Forma de pagamento")
    col_vencimento = _coluna(df, "Vencimento")
    col_pagamento = _coluna(df, "Data de pagamento")
    col_valor = _coluna(df, "Valor")
    col_valor_brl = _coluna(df, "Valor em R$")
    col_valor_pago = _coluna(df, "Valor pago")
    col_plano = _coluna(df, "Plano de contas")
    col_centro = _coluna(df, "Centro de custo")
    col_tipo_custo = _coluna(df, "Tipo de custo")
    col_documento = _coluna(df, "Número do documento")

    descricao = _serie_texto(df, col_descricao, "")
    validas = descricao.ne("") & ~descricao.map(_sem_acentos).str.contains("TOTAL", na=False)
    dados = df.loc[validas].copy()
    descricao = descricao.loc[validas]

    fornecedor = _serie_texto(dados, col_fornecedor, "")
    prefixo = descricao.str.split(" - ", n=1).str[0]
    entidade = fornecedor.where(fornecedor.ne(""), prefixo)
    forma = _serie_texto(dados, col_forma)
    vencimento = _serie_data(dados, col_vencimento)
    pagamento = _serie_data(dados, col_pagamento)
    valor_original = _serie_valor(dados, col_valor)
    valor_brl = _serie_valor(dados, col_valor_brl)
    valor_pago = _serie_valor(dados, col_valor_pago)
    valor_projetado = valor_brl.where(valor_brl > 0, valor_original)
    valor_realizado = valor_pago.where(valor_pago > 0, valor_projetado)
    pago = pagamento.notna() | valor_pago.gt(0)

    plano = _serie_texto(dados, col_plano, "")
    centro = _serie_texto(dados, col_centro, "")
    tipo_custo = _serie_texto(dados, col_tipo_custo, "")
    despesa = plano.where(plano.ne(""), centro).where(lambda serie: serie.ne(""), tipo_custo)
    despesa = despesa.map(_categoria_despesa)

    def montar(mask, data, valor):
        recorte = dados.loc[mask]
        resultado = pd.DataFrame(
            {
                "ENTIDADE": entidade.loc[mask],
                "DESCRICAO": descricao.loc[mask],
                "DATA": data.loc[mask],
                "DOCUMENTO": forma.loc[mask],
                "NOTA FISCAL": recorte.apply(
                    _nota_fiscal,
                    axis=1,
                    args=(None, None, col_documento, col_descricao),
                ),
                "PARCELA": recorte.apply(
                    _parcela,
                    axis=1,
                    args=(None, col_documento, col_descricao),
                ),
                "DESPESA": despesa.loc[mask],
                "VALOR": valor.loc[mask],
            }
        )
        resultado = resultado[(resultado["VALOR"] > 0) & resultado["DATA"].notna()]
        return _deduplicar(resultado)

    saidas = {}
    realizado = montar(pago, pagamento.fillna(vencimento), valor_realizado)
    projetado = montar(~pago, vencimento, valor_projetado)
    if not realizado.empty:
        saidas["fluxo_de_pagamento"] = realizado
    if not projetado.empty:
        saidas["contas_a_pagar"] = projetado

    return {
        "reconhecido": True,
        "tipo_fonte": "Pagamentos do novo ERP",
        "dados_por_tipo": saidas,
        "cancelados_qtd": 0,
        "cancelados_valor": 0.0,
    }


def adaptar_exportacao_novo_erp(bruto):
    """Retorna relatórios canônicos ou ``reconhecido=False`` para arquivos legados."""
    df = _promover_cabecalho(bruto)
    if df.empty:
        return {"reconhecido": False}
    colunas = set(_mapa_colunas(df))
    if {"CLIENTE", "VALOR", "STATUS DO RECEBIMENTO"}.issubset(colunas):
        return _adaptar_recebimentos(df)
    if {"DESCRICAO", "VALOR", "FORMA DE PAGAMENTO"}.issubset(colunas) and (
        "DATA DE PAGAMENTO" in colunas or "FORNECEDOR" in colunas
    ):
        return _adaptar_pagamentos(df)
    return {"reconhecido": False}


def prioridade_arquivo(nome):
    """Faz o consolidado prevalecer sobre recortes redundantes."""
    normalizado = _sem_acentos(re.sub(r"\s*\(\d+\)\s*(?=\.[^.]+$)", "", str(nome)))
    if "AGUARDANDO RECEBIMENTO" in normalizado:
        return 100
    if "CONTAS_A_PAGAR" in normalizado or "CONTAS A PAGAR" in normalizado:
        return 90
    if "RECEBIDOS" in normalizado:
        return 85
    if "ATRASADOS" in normalizado or "NAO VENCIDAS" in normalizado:
        return 70
    return 50


def tipo_legado_por_nome(nome):
    """Reconhece os novos nomes oficiais quando o conteúdo ainda é legado."""
    base = re.sub(r"\.[^.]+$", "", str(nome))
    base = re.sub(r"\s*\(\d+\)\s*$", "", base)
    normalizado = re.sub(r"[^A-Z0-9]+", " ", _sem_acentos(base)).strip()
    return {
        "RECEBIDOS": "notas_recebidas",
        "CONTAS A PAGAR": "contas_a_pagar",
    }.get(normalizado)
