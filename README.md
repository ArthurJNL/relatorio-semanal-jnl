# RELATORIADOR — atualização 12/08/2026

Esta versão mantém o gerador individual/personalizado e adiciona o modo **Relatório completo automático**.

## Como usar o modo automático

1. Envie uma ou mais planilhas.
2. Mantenha os nomes abaixo (maiúsculas/minúsculas não fazem diferença; cópias com `(1)` também são aceitas):
   - `NOTAS EM ATRASO.xlsx`
   - `RELAÇÃO DE NOTAS À RECEBER.xlsx`
   - `RELAÇÃO DE NOTAS RECEBIDAS.xlsx`
   - `FLUXO DE PAGAMENTO.xlsx`
   - `RELAÇÃO DE CONTAS À PAGAR.xlsx`
3. Confira o reconhecimento e a capa vinculada.
4. Ajuste o período.
5. Arraste os blocos para escolher a ordem ou mova um item para **NÃO INCLUIR**.
6. Clique em **Preparar relatório financeiro completo** e baixe o PDF.

Cada planilha gera um bloco independente: capa, gráfico por entidades, gráfico por pagamentos/despesas e tabela detalhada. A ordem inicial reproduz o `RELATÓRIO FINANCEIRO.pdf` fornecido como modelo.

## Modo anterior

Selecione **Individual / personalizado** para continuar usando títulos, gráficos, colunas, filtros e ordem de componentes de forma livre, como antes.

## Execução local

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Mantenha a pasta `assets` ao lado do `app.py`, pois ela contém as três capas usadas no relatório automático.
