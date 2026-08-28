from dotenv import load_dotenv
import os

load_dotenv()  # lê o arquivo .env e carrega as variáveis
chave = os.getenv("ANTHROPIC_API_KEY")  # pega o valor de dentro do código

from pathlib import Path

from pathlib import Path
pasta = Path(r"C:\Users\bruno\Desktop\CadastroMagalu")  # o caminho real da sua pasta
caminho_arquivo = pasta / "texto_whats.txt"

with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
    texto_whats = arquivo.read()

import anthropic

client = anthropic.Anthropic(api_key=chave)  # a variável que você já carregou do .env

prompt = f"""Preciso que me dê um JSON. Somente JSON de resposta! No seguinte formato abaixo:

{{
"cliente": {{ "renda": "aqui vai o valor", "profissao": "aqui vai o valor", "email": "aqui vai o valor", "telefone": "aqui vai o valor", "estado_civil": "aqui vai o valor" }},
"conjuge": null ou {{ "nome": "aqui vai o valor", "cpf": "aqui vai o valor", "profissao": "aqui vai o valor", "renda": "aqui vai o valor" }}
}}

Preencha os campos com os valores encontrados no texto abaixo. Caso não encontre o valor de algum campo, preencha com null. Não invente ou estime valores — só preencha um campo se ele aparecer claramente no texto.

Não use blocos de código markdown, nem texto antes ou depois — sua resposta deve começar direto com {{ e terminar com }}.

O texto pode trazer uma seção "Dados do cliente" e outra "Dados do cônjuge" — use essas marcações para separar quem é quem.

Texto do WhatsApp:
{texto_whats}
"""

resposta = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=500,
    messages=[{"role": "user", "content": prompt}]
)

def tratar_resposta(resposta_IA):

    texto_resposta = resposta.content[0].text

    inicio = texto_resposta.find("{")
    fim = texto_resposta.rfind("}")

    json_limpo = texto_resposta[inicio:fim + 1]  # +1 porque o slice não inclui o índice final
    return  json_limpo

import json

def verificar_json(texto_json):
    try:
        dados = json.loads(texto_json)
        return dados
    except json.JSONDecodeError:
        try:
            resposta2 = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            texto_json2 = tratar_resposta(resposta2)
            dados = json.loads(texto_json2)
            return dados
        except json.JSONDecodeError:
            return {
                "cliente": {
                    "renda": None,
                    "profissao": None,
                    "email": None,
                    "telefone": None,
                    "estado_civil": None
                },
                "conjuge": None
            }

json_decodificado = verificar_json(tratar_resposta(resposta))





