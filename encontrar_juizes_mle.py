#!/usr/bin/env python
# coding: utf-8

# In[19]:


import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

get_ipython().system('pip install reportlab')


# In[21]:


df = pd.read_csv('relatorio.csv', sep=';', encoding='utf-8', dtype={'Número do Processo': str})
df["Número do Processo"] = df["Número do Processo"].str.strip("\t")
df["Número do Mandado"] = df["Número do Mandado"].str.strip("\t")
df['Número do Processo Mod'] = df['Número do Processo'].str.replace('826', '', regex=False)
df


# In[35]:


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

# Loop substituindo o Selenium
resultados_juiz = []

for processo in df["Número do Processo Mod"]:
    try:
        juiz = extrair_juiz(processo)
        print(f"Processo {processo}: Juiz = {juiz}")
        resultados_juiz.append(juiz)
        time.sleep(2)  # evitar bloqueio
    except Exception as e:
        resultados_juiz.append("Erro ou não encontrado")
        print(f"Erro no processo {processo}: {e}")

# Adiciona a nova coluna ao DataFrame
df["Juiz"] = resultados_juiz


# In[37]:


for i, row in df[df["Juiz"] == "Juiz não encontrado"].iterrows():
    print(f"\nNúmero do processo: {row['Número do Processo']}")
    juiz_manual = input("Digite o nome do juiz (ou pressione Enter para pular): ").strip()
    if juiz_manual:
        df.at[i, "Juiz"] = juiz_manual


# In[53]:


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os

# Cria a pasta
os.makedirs("relatorios_juizes_pdf", exist_ok=True)

# Estilos para PDF
styles = getSampleStyleSheet()
style_normal = styles["Normal"]
style_heading = styles["Heading1"]
style_subheading = styles["Heading2"]

# Gera um PDF para cada juiz
for juiz, grupo in df.groupby("Juiz"):
    if juiz == "Erro ou não encontrado":
        continue

    filename = f"relatorios_juizes_pdf/{juiz.replace('/', '_').replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(filename)

    story = [Paragraph(f"Relatório - MLEs Aguardando Assinatura - Magistrado(a): {juiz}", style_heading), Spacer(1, 12)]

    # Agrupa por Órgão/Vara dentro de cada juiz
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

    print(f"Relatório PDF gerado para: {juiz}")

