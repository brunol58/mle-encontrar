import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

BASE_URL = "https://esaj.tjsp.jus.br"

# Título e aviso do app
st.title("📄 Relatório de Juízes - Mandados de Levantamento (TJSP)")
st.markdown("⚠️ Esta aplicação está em **fase de testes** e foi desenvolvida por **Bruno Ferreira da Silva**.")

uploaded_file = st.file_uploader("Selecione o arquivo CSV com os processos", type="csv")

# Função para criar o link do processo
def gerar_link(numero_mod):
    return f"{BASE_URL}/cpopg/show.do?processo.numero={numero_mod}&uuidCaptcha=sajcaptcha_123"

# Função robusta de requisição
def requisitar(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }
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
            time.sleep(2)
        except Exception as e:
            time.sleep(2)
    return None, "Falha após múltiplas tentativas"

# Função para extrair nome do juiz
def extrair_juiz(numero_mod):
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

# Função para gerar PDF
def gerar_pdf(dados, nome_arquivo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph("Relatório de Juízes", styles["Heading1"]))
    elements.append(Spacer(1, 12))
    for index, row in dados.iterrows():
        elements.append(Paragraph(f"<b>Processo:</b> {row['Número do Processo Mod']}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Juiz:</b> {row['Juiz']}", styles["Normal"]))
        elements.append(Spacer(1, 12))
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Processamento
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    if "Número do Processo Mod" not in df.columns:
        st.error("O arquivo CSV deve conter a coluna 'Número do Processo Mod'")
    else:
        status_extracao = st.empty()
        progress_bar = st.progress(0)
        juizes = []
        total = len(df)
        for i, row in enumerate(df.itertuples(), 1):
            status_extracao.info(f"⏳ Extraindo juiz ({i}/{total}) - Processo: {row._asdict()['Número do Processo Mod']}")
            juiz = extrair_juiz(row._asdict()["Número do Processo Mod"])
            juizes.append(juiz)
            progress_bar.progress(i / total)
        df["Juiz"] = juizes

        # Download do PDF
        pdf_buffer = gerar_pdf(df, "relatorio_juizes.pdf")
        st.download_button("📥 Baixar Relatório PDF", data=pdf_buffer, file_name="relatorio_juizes.pdf", mime="application/pdf")
        
        # Mostrar tabela
        st.dataframe(df)
