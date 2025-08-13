import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from docx import Document

# Título do app
st.title("Relatório de Juízes - Mandados de Levantamento(TJSP)")
st.warning("🚧 Esta aplicação está em fase de testes. Desenvolvida por Bruno Ferreira da Silva.")

# Inicializar variáveis de sessão
if 'df_final' not in st.session_state:
    st.session_state.df_final = None
if 'extracao_concluida' not in st.session_state:
    st.session_state.extracao_concluida = False
if 'data_relatorio' not in st.session_state:
    st.session_state.data_relatorio = datetime.now().strftime('%d/%m/%Y')

# Upload do CSV
arquivo = st.file_uploader("📄 Faça upload do relatório gerado diretamente no Portal de Custas", type=["csv"])

if arquivo:
    if not st.session_state.extracao_concluida:
        df = pd.read_csv(arquivo, sep=';', encoding='utf-8', dtype={'Número do Processo': str})
        df["Número do Processo"] = df["Número do Processo"].str.strip("\t")
        df["Número do Mandado"] = df["Número do Mandado"].str.strip("\t")
        df['Número do Processo Mod'] = df['Número do Processo'].str.replace('826', '', regex=False)

        # Data mais recente
        try:
            df['Data da Ação'] = pd.to_datetime(df['Data da Ação'], format='%d/%m/%Y')
            data_mais_recente = df['Data da Ação'].max()
            st.session_state.data_relatorio = data_mais_recente.strftime('%d/%m/%Y')
        except:
            st.session_state.data_relatorio = datetime.now().strftime('%d/%m/%Y')

        BASE_URL = "https://esaj.tjsp.jus.br"

        def formatar_numero_cnj(numero):
            return f"{numero[:7]}-{numero[7:9]}.{numero[9:13]}.8.26.{numero[13:]}"

        def gerar_link(numero_mod):
            numero_formatado = formatar_numero_cnj(numero_mod)
            foro = numero_mod[-4:]
            return (
                f"{BASE_URL}/cpopg/search.do?"
                f"conversationId=&cbPesquisa=NUMPROC"
                f"&numeroDigitoAnoUnificado={numero_mod}"
                f"&foroNumeroUnificado={foro}"
                f"&dadosConsulta.valorConsultaNuUnificado={numero_formatado}"
                f"&dadosConsulta.valorConsultaNuUnificado=UNIFICADO"
                f"&dadosConsulta.valorConsulta="
                f"&dadosConsulta.tipoNuProcesso=UNIFICADO"
            )

        def extrair_juiz(numero_mod):
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/115.0.0.0 Safari/537.36"
                )
            }

            def requisitar(url):
                for tentativa in range(3):
                    try:
                        resp = requests.get(url, headers=headers, timeout=10)
                        if resp.status_code != 200:
                            time.sleep(2)
                            continue
                        if "captcha" in resp.text.lower():
                            return None, "Página bloqueada por captcha"
                        return BeautifulSoup(resp.text, "html.parser"), None
                    except requests.Timeout:
                        print(f"⏳ Timeout {tentativa+1} para {url}")
                        time.sleep(2)
                    except Exception as e:
                        print(f"⚠️ Erro {tentativa+1} para {url}: {e}")
                        time.sleep(2)
                return None, "Falha após múltiplas tentativas"

            url = gerar_link(numero_mod)
            soup, erro = requisitar(url)
            if erro:
                return erro

            proc_princ = soup.find("a", class_="processoPrinc")
            if proc_princ:
                href_princ = proc_princ.get("href")
                if not href_princ:
                    return "Link do processo principal não encontrado"
                url_princ = BASE_URL + href_princ
                soup_princ, erro_princ = requisitar(url_princ)
                if erro_princ:
                    return erro_princ
                juiz_princ = soup_princ.find("span", id="juizProcesso")
                return juiz_princ.get_text(strip=True) if juiz_princ else "Juiz não encontrado"
            else:
                juiz = soup.find("span", id="juizProcesso")
                return juiz.get_text(strip=True) if juiz else "Juiz não encontrado"

        status_extracao = st.empty()
        status_extracao.info("⏳ Extração de nomes dos juízes em andamento...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        table_placeholder = st.empty()

        display_df = df[["Número do Processo", "Órgão/Vara"]].copy()
        display_df["Juiz"] = ["⏳ Extraindo..." for _ in range(len(df))]
        table_placeholder.dataframe(display_df)

        resultados_juiz = []

        for i, (index, row) in enumerate(df.iterrows()):
            try:
                juiz = extrair_juiz(row["Número do Processo Mod"])
                resultados_juiz.append(juiz)
            except Exception:
                juiz = "Erro ou não encontrado"
                resultados_juiz.append(juiz)

            display_df.at[index, "Juiz"] = juiz
            progress = (i + 1) / len(df)
            progress_bar.progress(progress)
            status_text.text(f"Processando {i + 1} de {len(df)} | Último juiz: {juiz}")

            if i % 5 == 0 or i == len(df) - 1:
                table_placeholder.dataframe(display_df)
                st.session_state.df_final = df.copy()
                st.session_state.df_final["Juiz"] = resultados_juiz
                time.sleep(0.1)

            time.sleep(1.5)

        df["Juiz"] = resultados_juiz
        st.session_state.df_final = df.copy()
        st.session_state.extracao_concluida = True
        table_placeholder.dataframe(display_df)
        status_extracao.success("✅ Extração concluída!")

    else:
        df = st.session_state.df_final.copy()
        st.success("✅ Extração já concluída anteriormente!")
        st.dataframe(df[["Número do Processo", "Órgão/Vara", "Juiz"]])

    # Edição manual
    st.write("### Insira manualmente os juízes não encontrados:")
    with st.form(key='edicao_juizes'):
        juizes_editados = {}
        for i, row in df[df["Juiz"] == "Juiz não encontrado"].iterrows():
            juiz_manual = st.text_input(
                f"Informe o juiz para o processo {row['Número do Processo']}:",
                key=f"juiz_edit_{i}"
            )
            juizes_editados[i] = juiz_manual.strip() if juiz_manual.strip() else None
        submit_button = st.form_submit_button("Aplicar Correções")

    if submit_button:
        for i, juiz in juizes_editados.items():
            if juiz:
                df.at[i, "Juiz"] = juiz
                st.session_state.df_final.at[i, "Juiz"] = juiz
        st.success("Correções aplicadas com sucesso!")
        st.dataframe(df[["Número do Processo", "Órgão/Vara", "Juiz"]])

    # Configuração do relatório
    st.write("### ⚙️ Configuração do Relatório")
    campos_disponiveis = {
        "Número do Processo": "Número do Processo",
        "Jurisdição": "Jurisdição",
        "Situação do Mandado": "Situação do Mandado",
        "Valor do Mandado": "Valor do Mandado",
        "Usuário da Ação": "Usuário da Ação",
        "Data da Ação": "Data da Ação"
    }

    selecao_campos = {}
    col1, col2, col3 = st.columns(3)
    with col1:
        selecao_campos["Número do Processo"] = st.checkbox("Número do Processo", value=True)
        selecao_campos["Jurisdição"] = st.checkbox("Jurisdição", value=False)
    with col2:
        selecao_campos["Situação do Mandado"] = st.checkbox("Situação do Mandado", value=False)
        selecao_campos["Valor do Mandado"] = st.checkbox("Valor do Mandado", value=False)
    with col3:
        selecao_campos["Usuário da Ação"] = st.checkbox("Usuário da Ação", value=False)
        selecao_campos["Data da Ação"] = st.checkbox("Data da Ação", value=False)

    mostrar_separadores = sum(selecao_campos.values()) > 1

    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_heading = styles["Heading1"]
    style_subheading = styles["Heading2"]

    st.write(f"### 📄 Baixar relatórios até {st.session_state.data_relatorio} (PDF e Word)")
    for juiz, grupo in df.groupby("Juiz"):
        if juiz in ["Erro ou não encontrado", "Juiz não encontrado"]:
            continue

        # PDF
        pdf_buffer = BytesIO()
        doc_pdf = SimpleDocTemplate(pdf_buffer)
        story = [Paragraph(f"Relatório até {st.session_state.data_relatorio} - Magistrado(a): {juiz}", style_heading), Spacer(1, 12)]

        # Word
        docx_doc = Document()
        docx_doc.add_heading(f"Relatório até {st.session_state.data_relatorio}", level=1)
        docx_doc.add_heading(f"Magistrado(a): {juiz}", level=2)

        for orgao, subgrupo in grupo.sort_values("Órgão/Vara").groupby("Órgão/Vara"):
            story.append(Paragraph(f"Vara: {orgao}", style_subheading))
            story.append(Spacer(1, 6))
            docx_doc.add_heading(f"Vara: {orgao}", level=3)

            for _, row in subgrupo.iterrows():
                if selecao_campos["Número do Processo"]:
                    story.append(Paragraph(f"{row['Número do Processo']}", style_normal))
                    docx_doc.add_paragraph(f"{row['Número do Processo']}")
                if selecao_campos["Jurisdição"]:
                    story.append(Paragraph(f"Jurisdição: {row['Jurisdição']}", style_normal))
                    docx_doc.add_paragraph(f"Jurisdição: {row['Jurisdição']}")
                if selecao_campos["Situação do Mandado"]:
                    story.append(Paragraph(f"Situação do Mandado: {row['Situação do Mandado']}", style_normal))
                    docx_doc.add_paragraph(f"Situação do Mandado: {row['Situação do Mandado']}")
                if selecao_campos["Valor do Mandado"]:
                    story.append(Paragraph(f"Valor do Mandado: R$ {row['Valor do Mandado']}", style_normal))
                    docx_doc.add_paragraph(f"Valor do Mandado: R$ {row['Valor do Mandado']}")
                if selecao_campos["Usuário da Ação"]:
                    story.append(Paragraph(f"Usuário da Ação: {row['Usuário da Ação']}", style_normal))
                    docx_doc.add_paragraph(f"Usuário da Ação: {row['Usuário da Ação']}")
                if selecao_campos["Data da Ação"]:
                    story.append(Paragraph(f"Data da Ação: {row['Data da Ação']}", style_normal))
                    docx_doc.add_paragraph(f"Data da Ação: {row['Data da Ação']}")

                if mostrar_separadores:
                    story.append(Spacer(1, 12))
                    story.append(Paragraph("-" * 50, style_normal))
                    story.append(Spacer(1, 12))
                    docx_doc.add_paragraph("-" * 50)

        doc_pdf.build(story)
        pdf_buffer.seek(0)
        nome_base = f"Relatorio_MLEs_{juiz.replace('/', '_').replace(' ', '_')}_{st.session_state.data_relatorio.replace('/', '-')}"
        st.download_button(f"📥 Baixar PDF - {juiz}", data=pdf_buffer, file_name=f"{nome_base}.pdf", mime="application/pdf")

        docx_buffer = BytesIO()
        docx_doc.save(docx_buffer)
        docx_buffer.seek(0)
        st.download_button(f"📥 Baixar Word - {juiz}", data=docx_buffer, file_name=f"{nome_base}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
