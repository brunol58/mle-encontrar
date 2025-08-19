import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import streamlit as st
from io import BytesIO
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==============================
# Funções auxiliares
# ==============================

BASE_URL = "https://esaj.tjsp.jus.br"

def formatar_numero_cnj(numero):
    return f"{numero[:7]}-{numero[7:9]}.{numero[9:13]}.8.26.{numero[13:]}"

def gerar_link(numero_mod):
    numero_formatado = formatar_numero_cnj(numero_mod)
    foro = numero_mod[-4:]
    return (
        f"https://esaj.tjsp.jus.br/cpopg/search.do?"
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

# ==============================
# Aplicativo Streamlit
# ==============================

st.title("📑 Relatório de Juízes - MLE (TJSP)")
st.warning("⚠️ Esta aplicação está em fase de testes e foi implementada por **Bruno Ferreira da Silva**.")

uploaded_file = st.file_uploader("Carregue o arquivo CSV com os processos", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file, sep=";", encoding="utf-8", dtype={'Número do Processo': str})
    df["Número do Processo"] = df["Número do Processo"].str.strip("\t")
    df["Número do Mandado"] = df["Número do Mandado"].str.strip("\t")
    df['Número do Processo Mod'] = df['Número do Processo'].str.replace('826', '', regex=False)

    st.subheader("📋 Pré-visualização dos dados")
    st.dataframe(df.head())

    if st.button("🔍 Extrair Juízes"):
        resultados_juiz = []
        progress = st.progress(0)
        for i, processo in enumerate(df["Número do Processo Mod"]):
            try:
                juiz = extrair_juiz(processo)
                resultados_juiz.append(juiz)
            except Exception:
                juiz = "Erro ou não encontrado"
                resultados_juiz.append(juiz)
            progress.progress((i+1)/len(df))
            time.sleep(2)  # evita bloqueio
        
        df["Juiz"] = resultados_juiz
        st.success("✅ Extração concluída!")
        st.dataframe(df)

        # Corrigir manualmente juízes não encontrados
        st.subheader("✏️ Correção Manual dos Juízes")
        for i, row in df[df["Juiz"] == "Juiz não encontrado"].iterrows():
            juiz_manual = st.text_input(f"Digite o juiz para o processo {row['Número do Processo']}", "")
            if juiz_manual:
                df.at[i, "Juiz"] = juiz_manual

        # Geração dos relatórios
        st.subheader("📂 Gerar Relatórios")
        os.makedirs("relatorios_juizes_word", exist_ok=True)

        buffer_word = BytesIO()

        # Gera relatórios Word agrupados por juiz e vara
        for juiz, grupo in df.groupby("Juiz"):
            if juiz in ["Erro ou não encontrado", None]:
                continue

            doc = Document()
            
            # Estilo
            style = doc.styles['Normal']
            font = style.font
            font.name = 'Arial'
            font.size = Pt(12)
            
            # Título
            title = doc.add_paragraph(f"MLEs para assinatura - {juiz}")
            title.style = doc.styles['Heading 1']
            title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            doc.add_paragraph()

            # Agrupar por Vara
            for vara, processos in grupo.sort_values("Órgão/Vara").groupby("Órgão/Vara"):
                subtitle = doc.add_paragraph(f"Vara: {vara}")
                subtitle.style = doc.styles['Heading 2']
                for _, row in processos.iterrows():
                    doc.add_paragraph(row['Número do Processo'].strip())
                doc.add_paragraph()
            
            doc.save(buffer_word)

        buffer_word.seek(0)
        st.download_button(
            label="📥 Baixar Relatório em Word",
            data=buffer_word,
            file_name="relatorio_juizes.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
