import unittest

import pandas as pd

from erp_adapter import adaptar_exportacao_novo_erp, prioridade_arquivo


class ErpAdapterTest(unittest.TestCase):
    def test_recebimentos_sao_separados_por_status_e_cancelados_sao_excluidos(self):
        bruto = pd.DataFrame(
            [
                [
                    "NF-e",
                    "Código",
                    "Número do documento",
                    "Cliente",
                    "Valor",
                    "Vencimento",
                    "Valor recebido",
                    "Data de crédito",
                    "Forma de pagamento",
                    "Status da Nota",
                    "Status do Recebimento",
                ],
                ["001/000000101", "NF-e 00000101 - Parcela 001/001", "00000101-001/001", "A", 100, "2026-09-01", None, None, "boleto", "NF-e aceita", "Vencido"],
                ["001/000000102", "NF-e 00000102 - Parcela 001/001", "00000102-001/001", "B", 200, "2026-09-10", None, None, "pix", "NF-e aceita", "Iminente"],
                ["001/000000103", "NF-e 00000103 - Parcela 001/001", "00000103-001/001", "C", 300, "2026-09-02", 300, "2026-09-03", "boleto", "NF-e aceita", "Recebido"],
                ["001/000000104", "NF-e 00000104 - Parcela 001/001", "00000104-001/001", "D", 400, "2026-09-01", None, None, "boleto", "NF-e cancelada", "Vencido"],
            ]
        )

        resultado = adaptar_exportacao_novo_erp(bruto)

        self.assertTrue(resultado["reconhecido"])
        self.assertEqual(resultado["cancelados_qtd"], 1)
        self.assertEqual(resultado["cancelados_valor"], 400)
        self.assertEqual(resultado["dados_por_tipo"]["notas_em_atraso"]["VALOR"].sum(), 100)
        self.assertEqual(resultado["dados_por_tipo"]["notas_a_receber"]["VALOR"].sum(), 200)
        self.assertEqual(resultado["dados_por_tipo"]["notas_recebidas"]["VALOR"].sum(), 300)

    def test_pagamentos_sao_separados_em_realizados_e_abertos(self):
        bruto = pd.DataFrame(
            [
                ["Descrição", "Fornecedor", "Valor", "Valor pago", "Vencimento", "Data de pagamento", "Forma de pagamento", "Plano de contas"],
                ["SERVIÇO NF-S 20", "FORNECEDOR A", 150, 150, "2026-09-01", "2026-09-01", "Boleto", "2.2.7 - Telefone"],
                ["MATERIAL NF 21", "FORNECEDOR B", 250, None, "2026-09-10", None, "PIX", "2.4.1 - Fornecedores"],
            ]
        )

        resultado = adaptar_exportacao_novo_erp(bruto)

        self.assertEqual(resultado["dados_por_tipo"]["fluxo_de_pagamento"]["VALOR"].sum(), 150)
        self.assertEqual(resultado["dados_por_tipo"]["contas_a_pagar"]["VALOR"].sum(), 250)
        self.assertEqual(resultado["dados_por_tipo"]["contas_a_pagar"].iloc[0]["DESPESA"], "FORNECEDORES")

    def test_consolidado_tem_prioridade_sobre_recortes(self):
        self.assertGreater(
            prioridade_arquivo("aguardando recebimento.xlsx"),
            prioridade_arquivo("ATRASADOS.xlsx"),
        )
        self.assertGreater(
            prioridade_arquivo("aguardando recebimento.xlsx"),
            prioridade_arquivo("NÃO VENCIDAS.xlsx"),
        )


if __name__ == "__main__":
    unittest.main()
