import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Título do app
st.title("Relatório de Juízes - Mandados (TJSP)")

# Inicializar variáveis de sessão
if 'df_final' not in st.session_state:
    st.session_state.df_final = None
if 'extracao_concluida' not in st.session_state:
    st.session_state.extracao_concluida = False

# Upload do CSV
arquivo = st.file_uploader("📄 Faça upload do arquivo relatorio.csv", type=["csv"])

if arquivo:
    if not st.session_state.extracao_concluida:
        df = pd.read_csv(arquivo, sep=';', encoding='utf-8', dtype={'Número do Processo': str})
        df["Número do Processo"] = df["Número do Processo"].str.strip("\t")
        df["Número do Mandado"] = df["Número do Mandado"].str.strip("\t")
        df['Número do Processo Mod'] = df['Número do Processo'].str.replace('826', '', regex=False)

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
            headers = {"User-Agent": "Mozilla/5.0"}
            def requisitar(url):
                resp = requests.get(url, headers=headers)
                if resp.status_code != 200:
                    return None, f"Erro HTTP {resp.status_code}"
                return BeautifulSoup(resp.text, "html.parser"), None

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
                if juiz_princ:
                    return juiz_princ.get_text(strip=True)
                else:
                    return "Juiz não encontrado"
            else:
                juiz = soup.find("span", id="juizProcesso")
                if juiz:
                    return juiz.get_text(strip=True)
                else:
                    return "Juiz não encontrado"

        st.info("⏳ Iniciando extração de juízes...")
        
        # Cria placeholders para os elementos dinâmicos
        progress_bar = st.progress(0)
        status_text = st.empty()
        table_placeholder = st.empty()
        
        # DataFrame para exibição em tempo real
        display_df = df[["Número do Processo", "Órgão/Vara"]].copy()
        display_df["Juiz"] = ["⏳ Extraindo..." for _ in range(len(df))]
        
        # Exibe a tabela inicial
        table_placeholder.dataframe(display_df)
        
        resultados_juiz = []
        
        for i, (index, row) in enumerate(df.iterrows()):
            try:
                juiz = extrair_juiz(row["Número do Processo Mod"])
                resultados_juiz.append(juiz)
            except Exception:
                juiz = "Erro ou não encontrado"
                resultados_juiz.append(juiz)
            
            # Atualiza o DataFrame de exibição
            display_df.at[index, "Juiz"] = juiz
            
            # Atualiza a interface
            progress = (i + 1) / len(df)
            progress_bar.progress(progress)
            status_text.text(f"Processando {i + 1} de {len(df)} | Último juiz: {juiz}")
            
            # Atualiza a tabela a cada 5 registros ou no último
            if i % 5 == 0 or i == len(df) - 1:
                table_placeholder.dataframe(display_df)
                time.sleep(0.1)  # Pequena pausa para a interface atualizar
            
            time.sleep(1.5)  # evitar bloqueios

        df["Juiz"] = resultados_juiz
        st.session_state.df_final = df.copy()
        st.session_state.extracao_concluida = True
        
        # Atualiza a tabela final
        table_placeholder.dataframe(display_df)
        st.success("✅ Extração finalizada!")
    else:
        df = st.session_state.df_final.copy()
        st.success("✅ Extração já concluída anteriormente!")
        st.dataframe(df[["Número do Processo", "Órgão/Vara", "Juiz"]])

    # Permite edição manual
    st.write("### Corrija juízes não encontrados (se desejar):")
    
    # Criar um formulário para as edições
    with st.form(key='edicao_juizes'):
        juizes_editados = {}
        for i, row in df[df["Juiz"] == "Juiz não encontrado"].iterrows():
            juiz_manual = st.text_input(
                f"Informe o juiz para o processo {row['Número do Processo Mod']}:", 
                key=f"juiz_edit_{i}"
            )
            juizes_editados[i] = juiz_manual.strip() if juiz_manual.strip() else None
        
        submit_button = st.form_submit_button("Aplicar Correções")

    # Aplicar as correções quando o formulário for submetido
    if submit_button:
        for i, juiz in juizes_editados.items():
            if juiz:
                df.at[i, "Juiz"] = juiz
                st.session_state.df_final.at[i, "Juiz"] = juiz
        st.success("Correções aplicadas com sucesso!")
        # Atualiza a exibição do DataFrame
        st.dataframe(df[["Número do Processo", "Órgão/Vara", "Juiz"]])

    # Gerar e disponibilizar PDFs individualmente
    st.write("### 📄 Baixar relatórios individuais por juiz")

    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_heading = styles["Heading1"]
    style_subheading = styles["Heading2"]

    for juiz, grupo in df.groupby("Juiz"):
        if juiz in ["Erro ou não encontrado", "Juiz não encontrado"]:
            continue

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer)
        story = [Paragraph(f"Relatório - MLEs Aguardando Assinatura - Magistrado(a): {juiz}", style_heading), Spacer(1, 12)]

        for orgao, subgrupo in grupo.sort_values("Órgão/Vara").groupby("Órgão/Vara"):
            story.append(Paragraph(f"Vara: {orgao}", style_subheading))
            story.append(Spacer(1, 6))

            for _, row in subgrupo.iterrows():
                story.append(Paragraph(f"Processo: {row['Número do Processo Mod']}", style_normal))
                story.append(Paragraph(f"Jurisdicao: {row['Jurisdição']}", style_normal))
                story.append(Paragraph(f"Situação do Mandado: {row['Situação do Mandado']}", style_normal))
                story.append(Paragraph(f"Valor do Mandado: R$ {row['Valor do Mandado']}", style_normal))
                story.append(Paragraph(f"Usuário da Ação: {row['Usuário da Ação']}", style_normal))
                story.append(Paragraph(f"Data da Ação: {row['Data da Ação']}", style_normal))
                story.append(Spacer(1, 12))
                story.append(Paragraph("-" * 50, style_normal))
                story.append(Spacer(1, 12))

        doc.build(story)
        buffer.seek(0)
        nome_arquivo = f"{juiz.replace('/', '_').replace(' ', '_')}.pdf"
        st.download_button(
            label=f"📥 Baixar relatório de {juiz}",
            data=buffer,
            file_name=nome_arquivo,
            mime="application/pdf"
        )

