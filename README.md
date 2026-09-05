# RELATORIADOR — atualização 05/09/2026

Esta versão mantém o gerador individual/personalizado e adiciona o modo **Relatório completo automático**.

Os gráficos e as tabelas exibidos no site usam componentes nativos do Streamlit. Os gráficos dos PDFs são vetoriais e desenhados diretamente pelo `fpdf2`, sem ECharts, Plotly ou Matplotlib. Isso reduz o tempo de instalação e de inicialização no Streamlit Community Cloud.

Principais melhorias desta versão:

- Compatibilidade automática com os relatórios exportados pelo novo ERP.
- O arquivo consolidado `aguardando recebimento.xlsx` é separado automaticamente em **Notas em atraso** e **Notas a receber**.
- Notas com status cancelado são excluídas dos totais e informadas no diagnóstico.
- Relatórios de pagamentos são separados entre **realizados** e **a pagar**, de acordo com a data e o valor pago.
- Inclusão de uma página inicial de resumo executivo com totais, quantidades, saldo realizado e saldo projetado.
- Para recebimentos realizados, o período utiliza a data de crédito/pagamento; para pagamentos, utiliza a data de pagamento; para títulos em aberto, utiliza o vencimento.
- A inadimplência considera todos os títulos vencidos até a data final selecionada, inclusive os anteriores ao início da semana.
- Os arquivos do modelo anterior continuam aceitos.
- Normalização de `LOCACAO` e `LOCACÃO` para `LOCAÇÃO` (e das respectivas formas no plural).
- Máscara monetária brasileira centralizada e independente de configuração regional, sempre no formato `R$ 2.560,00`.
- Validação obrigatória antes de escrever qualquer moeda: uma saída como `R$ 2.560.00` interrompe a geração em vez de produzir um PDF incorreto.
- Valores monetários recebidos como `2.560,00`, `2560.00` ou até `2.560.00` são normalizados para o mesmo padrão brasileiro.
- Imediatamente antes da impressão no PDF, o último separador seguido por dois centavos é forçado para vírgula; o ponto dos milhares permanece intacto.

## Como usar o modo automático

1. Envie uma ou mais planilhas.
2. Para o novo ERP, use preferencialmente:
   - `aguardando recebimento.xlsx` — gera **Notas em atraso** e **Notas a receber**;
   - `recebidos.xlsx` — gera **Notas recebidas**;
   - exportação de pagamentos realizados — gera **Fluxo de pagamento**;
   - exportação de contas a pagar em aberto — gera **Contas a pagar**.
3. Não é necessário baixar `ATRASADOS.xlsx` nem `NÃO VENCIDAS.xlsx` quando `aguardando recebimento.xlsx` for enviado, pois são subconjuntos idênticos do consolidado.
4. Os nomes antigos continuam aceitos (maiúsculas/minúsculas e sufixos como `(1)` não fazem diferença):
   - `NOTAS EM ATRASO.xlsx`
   - `RELAÇÃO DE NOTAS À RECEBER.xlsx`
   - `RELAÇÃO DE NOTAS RECEBIDAS.xlsx`
   - `FLUXO DE PAGAMENTO.xlsx`
   - `RELAÇÃO DE CONTAS À PAGAR.xlsx`
5. Confira o diagnóstico: arquivos redundantes, notas canceladas e blocos faltantes são informados antes da geração.
6. Ajuste o período.
7. Arraste os blocos para escolher a ordem ou mova um item para **NÃO INCLUIR**.
8. Clique em **Preparar relatório financeiro completo** e baixe o PDF.

O PDF começa com um resumo executivo. Depois, cada conjunto de dados gera um bloco independente: capa, gráfico por entidades, gráfico por pagamentos/despesas e tabela detalhada. A ordem inicial reproduz o `RELATÓRIO FINANCEIRO.pdf` fornecido como modelo.

## Modo anterior

Selecione **Individual / personalizado** para continuar usando títulos, gráficos, colunas, filtros e ordem de componentes de forma livre, como antes.

## Execução local

```bash
python -m pip install -r requirements.txt
streamlit run relatoriador.py
```

Mantenha a pasta `assets` ao lado do `relatoriador.py`, pois ela contém as três capas usadas no relatório automático.

## Testes

```bash
python -m unittest discover -s tests -v
python -m py_compile relatoriador.py erp_adapter.py
```
