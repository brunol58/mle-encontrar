import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="Juízes MLE - TJSP", layout="wide")

st.title("📄 Analisador de Juízes - Mandados (TJSP)")

# Estado inicial
if "df" not in st.session_state:
    st.session_state.df = None
if "index" not in st.session_state:
    st.session_state.index = 0
if "juizes" not in st.session_state:
    st.session_state.juizes = []
if "executando" not in st.session_state:
    st.session_state.executando = False

# Upload
uploaded_file = st.file_uploader("Faça upload do arquivo `relatorio.csv`", type="csv")
if uploaded_file and st.session_state.df is None:
    df = pd.read_csv(uploaded_file, sep=";", encoding="utf-8", dtype={"Número do Processo": str})
    df["Número do Processo"] = df["Número do Processo"].str.strip("\t")
    df["Número do Mandado"] = df["Número do Mandado"].str.strip("\t")
    df["Número do Processo Mod"] = df["Número do Processo"].str.replace('826', '', regex=False)
    df["Juiz"] = ""
    st.session_state.df = df
    st.session_state.index = 0
    st.session_state.juizes = []

# Funções auxiliares
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

# Controles
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("▶️ Iniciar/Continuar Extração"):
        st.session_state.executando = True

with col2:
    if st.button("⏸ Pausar"):
        st.session_state.executando = False

with col3:
    if st.button("🔄 Resetar"):
        st.session_state.df = None
        st.session_state.index = 0
        st.session_state.juizes = []
        st.session_state.executando = False
        st.experimental_rerun()

# Extração
df = st.session_state.df
if df is not None:
    progress = st.progress(st.session_state.index / len(df))
    status_text = st.empty()

    while st.session_state.executando and st.session_state.index < len(df):
        i = st.session_state.index
        numero_mod = df.at[i, "Número do Processo Mod"]
        try:
            juiz = extrair_juiz(numero_mod)
        except Exception:
            juiz = "Erro ou não encontrado"

        df.at[i, "Juiz"] = juiz
        st.session_state.index += 1
        status_text.text(f"Processo {i + 1}/{len(df)} — {numero_mod}: {juiz}")
        progress.progress(st.session_state.index / len(df))
        time.sleep(1.5)
        st.experimental_rerun()

    # Mostrar tabela de progresso
    st.subheader("✅ Processos já executados")
    st.dataframe(df[df["Juiz"] != ""])

    # Correção manual
    st.subheader("📝 Corrigir juízes manualmente (opcional)")
    for i, row in df[df["Juiz"] == "Juiz não encontrado"].iterrows():
        juiz_manual = st.text_input(f"Processo {row['Número do Processo Mod']}", key=f"juiz_{i}")
        if juiz_manual.strip():
            df.at[i, "Juiz"] = juiz_manual.strip()

    # Geração individual de PDF
    st.subheader("📥 Baixar relatórios individuais")
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_heading = styles["Heading1"]
    style_subheading = styles["Heading2"]

    for juiz, grupo in df.groupby("Juiz"):
        if juiz in ["Erro ou não encontrado", "Juiz não encontrado", ""]:
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

        st.download_button(
            label=f"📄 Baixar PDF do juiz: {juiz}",
            data=buffer,
            file_name=f"{juiz.replace('/', '_').replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
