# RELATORIADOR — atualização 12/08/2026

Esta versão mantém o gerador individual/personalizado e adiciona o modo **Relatório completo automático**.

Os gráficos e as tabelas exibidos no site usam componentes nativos do Streamlit. Os gráficos dos PDFs são vetoriais e desenhados diretamente pelo `fpdf2`, sem ECharts, Plotly ou Matplotlib. Isso reduz o tempo de instalação e de inicialização no Streamlit Community Cloud.

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
streamlit run relatoriador.py
```

Mantenha a pasta `assets` ao lado do `relatoriador.py`, pois ela contém as três capas usadas no relatório automático.

## Atualização no GitHub

Substitua, na raiz do repositório, os arquivos `relatoriador.py`, `requirements.txt` e `README.md` pelos arquivos deste pacote. Faça um único commit com os três arquivos. A pasta `assets` não deve ser alterada.
