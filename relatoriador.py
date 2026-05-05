with aba_visu:
                    titulo_customizado_grafico = st.text_input("📝 Título Customizado (Ranking):", value=f"RELAÇÃO DE VALORES ({dt_inicio.strftime('%d/%m/%Y')} até {dt_fim.strftime('%d/%m/%Y')})")
                    
                    col_g1, col_g2 = st.columns([2, 2])
                    with col_g1:
                        st.write("💡 *Use o ícone 📷 no canto direito do gráfico para baixar a foto das barras.*")
                    with col_g2:
                        if FPDF is not None:
                            pdf_ranking_bytes = gerar_pdf_ranking(dados_grafico, titulo_customizado_grafico)
                            # Alterado o nome e adicionada a chave "key" de segurança!
                            st.download_button(label="📄 Baixar Ranking em PDF", data=pdf_ranking_bytes, file_name=f"Ranking_JNL_{dt_inicio.strftime('%d%m%y')}.pdf", mime="application/pdf", use_container_width=True, key="btn_pdf_ranking")
                    
                    dados_completos = dados_grafico.sort_values(by='VALOR', ascending=True)
                    dados_barras_formatados = [{"value": row['VALOR'], "label": {"show": True, "position": "right", "formatter": f"R$ {row['VALOR']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "color": "#111111"}} for _, row in dados_completos.iterrows()]
                    
                    altura_dinamica = max(600, len(dados_completos) * 50) 
                    
                    bar_options = {
                        "backgroundColor": "transparent",
                        "title": {"text": titulo_customizado_grafico, "left": "center", "textStyle": {"color": "#111111", "fontSize": 18, "fontFamily": "Calibri"}},
                        # A FERRAMENTA DE BAIXAR A FOTO ESTÁ AQUI:
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
                    titulo_tabela = st.text_input("📝 Título Customizado (Tabela):", value=titulo_customizado_grafico, key="titulo_tabela_input")
                    
                    st.write("💡 *Controle as colunas visíveis e baixe em PDF.*")
                    c_t1, c_t2, c_t3, c_t4 = st.columns(4)
                    with c_t1: mostrar_documento = st.toggle("Mostrar 'Documento'", value=True)
                    with c_t2: mostrar_nf = st.toggle("Mostrar 'Nota Fiscal'", value=True)
                    with c_t3: mostrar_parc = st.toggle("Mostrar 'Parcela'", value=True)
                    with c_t4: mostrar_situacao = st.toggle("Mostrar 'Situação'", value=True)

                    tabela_final = dados_tabela.copy()
                    tabela_final['VALOR_STR'] = tabela_final['VALOR'].apply(formatar_contabil)
                    
                    soma_total = tabela_final['VALOR'].sum()
                    soma_total_str = formatar_contabil(soma_total)
                    
                    lista_entidades = tabela_final['ENTIDADE'].tolist() + ["TOTAL GERAL"]
                    lista_datas = tabela_final['DATA'].tolist() + ["-"]
                    lista_documentos = tabela_final['DOCUMENTO'].tolist() + ["-"]
                    lista_nfs = tabela_final['NOTA FISCAL'].tolist() + ["-"]
                    lista_parcs = tabela_final['PARCELA'].tolist() + ["-"]
                    lista_valores = tabela_final['VALOR_STR'].tolist() + [soma_total_str]
                    lista_status = tabela_final['STATUS'].tolist() + ["-"]

                    lista_entidades_visual = tabela_final['ENTIDADE'].tolist() + ["<b>TOTAL GERAL</b>"]
                    lista_datas_visual = tabela_final['DATA'].tolist() + ["<b>-</b>"]
                    lista_documentos_visual = tabela_final['DOCUMENTO'].tolist() + ["<b>-</b>"]
                    lista_nfs_visual = tabela_final['NOTA FISCAL'].tolist() + ["<b>-</b>"]
                    lista_parcs_visual = tabela_final['PARCELA'].tolist() + ["<b>-</b>"]
                    lista_valores_visual = tabela_final['VALOR_STR'].tolist() + [f"<b>{soma_total_str}</b>"]
                    lista_status_visual = tabela_final['STATUS'].tolist() + ["<b>-</b>"]
                    
                    cols_pdf = {"RAZÃO SOCIAL / DESCRIÇÃO": lista_entidades, "DATA": lista_datas}
                    cabecalhos = ["<b>RAZÃO SOCIAL / DESCRIÇÃO</b>", "<b>DATA</b>"]
                    celulas = [lista_entidades_visual, lista_datas_visual]
                    larguras_colunas = [300, 90]
                    
                    if mostrar_documento:
                        cols_pdf["DOCUMENTO"] = lista_documentos
                        cabecalhos.append("<b>DOCUMENTO</b>")
                        celulas.append(lista_documentos_visual)
                        larguras_colunas.append(90)
                        
                    if mostrar_nf:
                        cols_pdf["NOTA FISCAL"] = lista_nfs
                        cabecalhos.append("<b>NOTA FISCAL</b>")
                        celulas.append(lista_nfs_visual)
                        larguras_colunas.append(90)
                        
                    if mostrar_parc:
                        cols_pdf["PARCELA"] = lista_parcs
                        cabecalhos.append("<b>PARCELA</b>")
                        celulas.append(lista_parcs_visual)
                        larguras_colunas.append(80)
                        
                    cols_pdf["VALOR"] = lista_valores
                    cabecalhos.append("<b>VALOR</b>")
                    celulas.append(lista_valores_visual)
                    larguras_colunas.append(110)
                    
                    if mostrar_situacao:
                        cols_pdf["SITUAÇÃO"] = lista_status
                        cabecalhos.append("<b>SITUAÇÃO</b>")
                        celulas.append(lista_status_visual)
                        larguras_colunas.append(120)
                        
                    df_pdf = pd.DataFrame(cols_pdf)

                    if FPDF is not None:
                        pdf_bytes = gerar_pdf_tabela(df_pdf, titulo_tabela)
                        # Adicionada a chave "key" de segurança!
                        st.download_button(label="📄 Baixar Tabela em PDF", data=pdf_bytes, file_name=f"Detalhado_JNL_{dt_inicio.strftime('%d%m%y')}.pdf", mime="application/pdf", use_container_width=True, key="btn_pdf_tabela")
                    else:
                        st.error("⚠️ Biblioteca 'fpdf' não instalada. Atualize o ficheiro requirements.txt.")