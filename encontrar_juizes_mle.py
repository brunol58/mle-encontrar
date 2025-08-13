import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import unicodedata

# Título do app
st.title("Relatório de Juízes - Mandados de Levantamento (TJSP)")
st.markdown("**Esta aplicação está em fase de testes e foi desenvolvida por Bruno Ferreira da Silva.**")

# Upload do CSV
uploaded_file = st.file_uploader("Envie o arquivo CSV", type=["csv"])

if uploaded_file is not None:
    # Leitura do CSV
    df = pd.read_csv(uploaded_file)

    # Padroniza nomes das colunas
    df.columns = [
        unicodedata.normalize("NFKD", col)
        .encode("ASCII", "ignore")
        .decode("utf-8")
        .strip()
        .lower()
        .replace(" ", "_")
        for col in df.columns
    ]

    if "numero_do_processo_mod" not in df.columns:
        st.error("O arquivo CSV deve conter a coluna 'Número do Processo Mod'")
    else:
        processos = df["numero_do_processo_mod"].dropna().unique().tolist()

        resultados = []

        # Função para buscar juiz no TJSP com retry
        def buscar_juiz(numero_processo):
            url = f"https://esaj.tjsp.jus.br/cpopg/open.do?gateway=true&cdProcesso={numero_processo}"
            tentativas = 3
            for _ in range(tentativas):
                try:
                    resposta = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    if resposta.status_code == 200:
                        soup = BeautifulSoup(resposta.text, "html.parser")
                        juiz_tag = soup.find("span", id="juiz")
                        if juiz_tag:
                            return juiz_tag.get_text(strip=True)
                        else:
                            return "Juiz não encontrado"
                except requests.RequestException:
                    time.sleep(2)
            return "Erro na busca"

        st.write(f"Total de processos para verificar: {len(processos)}")

        for idx, numero in enumerate(processos, 1):
            juiz = buscar_juiz(numero)
            resultados.append({"Número do Processo": numero, "Juiz": juiz})
            st.write(f"[{idx}/{len(processos)}] Processo {numero} → {juiz}")
            time.sleep(0.5)

        df_resultados = pd.DataFrame(resultados)

        # Geração de PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer)
        styles = getSampleStyleSheet()
        elementos = [Paragraph("Relatório de Juízes", styles["Title"]), Spacer(1, 12)]
        for _, row in df_resultados.iterrows():
            elementos.append(Paragraph(f"{row['Número do Processo']} — {row['Juiz']}", styles["Normal"]))
        doc.build(elementos)

        st.download_button(
            label="📄 Baixar Relatório em PDF",
            data=buffer.getvalue(),
            file_name=f"relatorio_juizes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )

        # Geração de Excel
        excel_buffer = BytesIO()
        df_resultados.to_excel(excel_buffer, index=False)
        st.download_button(
            label="📊 Baixar Relatório em Excel",
            data=excel_buffer.getvalue(),
            file_name=f"relatorio_juizes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
