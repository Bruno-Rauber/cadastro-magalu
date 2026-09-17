import base64

from dotenv import load_dotenv
import os

load_dotenv()  # lê o arquivo .env e carrega as variáveis
chave = os.getenv("ANTHROPIC_API_KEY")  # pega o valor de dentro do código


from pathlib import Path
pasta = Path(r"C:\Users\bruno\Desktop\CadastroMagalu\SubirCadastro")  # o caminho real da sua pasta
caminho_arquivo = pasta / "texto_whats.txt"

with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
    texto_whats = arquivo.read()

import anthropic

client = anthropic.Anthropic(api_key=chave)  # a variável que você já carregou do .env

prompt = f"""Preciso que me dê um JSON. Somente JSON de resposta! No seguinte formato abaixo:

{{
"cliente": {{ "renda": "renda": "aqui vai o valor (formato numérico, ex: 2500,00 - sem R$, sem ponto de milhar, use vírgula para os centavos; se o valor não tiver centavos, acrescente ,00 no final)"", "profissao": "aqui vai o valor", "email": "aqui vai o valor", "telefone": "aqui vai o valor", "estado_civil": "aqui vai o valor (solteiro, casado, divorciado, desquitado, separado judicialmente ou outro)", "sexo": "aqui vai o valor"  }},
"conjuge": null ou {{ "nome": "aqui vai o valor", "data_de_nascimento: "aqui vai o valor", "cpf": "aqui vai o valor", "profissao": "aqui vai o valor", "renda": "renda": "aqui vai o valor (formato numérico, ex: 2500,00 - sem R$, sem ponto de milhar, use vírgula para os centavos; se o valor não tiver centavos, acrescente ,00 no final)", "sexo": "aqui vai o valor" }}
}}

Preencha os campos com os valores encontrados no texto abaixo. Caso não encontre o valor de algum campo, preencha com null. Não invente ou estime valores — só preencha um campo se ele aparecer claramente no texto.

Não use blocos de código markdown, nem texto antes ou depois — sua resposta deve começar direto com {{ e terminar com }}.

O texto pode trazer uma seção "Dados do cliente" e outra "Dados do cônjuge" — use essas marcações para separar quem é quem.

Tanto cliente quanto conjuge devem ter sexo/genero e ele verá dessa forma Sexo: (m/f) - "m" para masculino e F para feminino. No JSON você deve colocar dessa forma sem ser por extenso
Texto do WhatsApp:
{texto_whats}
"""

resposta = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=500,
    messages=[{"role": "user", "content": prompt}]
)

def tratar_resposta(resposta_IA):

    texto_resposta = resposta_IA.content[0].text

    inicio = texto_resposta.find("{")
    fim = texto_resposta.rfind("}")

    json_limpo = texto_resposta[inicio:fim + 1]  # +1 porque o slice não inclui o índice final
    return  json_limpo

import json

def verificar_json(texto_json, content_retry, fallback):
    try:
        dados = json.loads(texto_json)
        return dados
    except json.JSONDecodeError:
        try:
            resposta2 = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=500,
                messages=[{"role": "user", "content": content_retry}]
            )
            texto_json2 = tratar_resposta(resposta2)
            dados = json.loads(texto_json2)
            return dados
        except json.JSONDecodeError:
            return fallback

def montar_bloco_arquivo(caminho_arquivo):
    with open(caminho_arquivo, "rb") as arquivo:
        arquivo_binario = arquivo.read()

    arquivo_base64 = base64.b64encode(arquivo_binario).decode("utf-8")

    caminho_arquivo = str(caminho_arquivo)

    if caminho_arquivo.endswith((".png", ".jpg", ".jpeg")):
        if caminho_arquivo.endswith(".png"):
            extensao = "image"
            media_type = "image/png"

        else:
            extensao = "image"
            media_type = "image/jpeg"

    elif caminho_arquivo.endswith(".pdf"):
        extensao = "document"
        media_type = "application/pdf"

    else:
        raise ValueError("esse arquivo não é nem um PDF nem uma imagem, verifique sua extensão e convertao")

    return {
        "type": extensao,
        "source": {
        "type": "base64",
        "media_type": media_type,
        "data": arquivo_base64
            }
        }

prompt_documento = f"""Preciso que me dê um JSON. Somente JSON de resposta! No seguinte formato abaixo:

{{
"nome": "aqui vai o valor",
"cpf": "aqui vai o valor",
"data_de_nascimento": "aqui vai o valor"
}}

Preencha os campos com os valores encontrados no arquivo anexado. Caso não encontre o valor de algum campo, preencha com null. Não invente ou estime valores — só preencha um campo se ele aparecer claramente no arquivo.

Não use blocos de código markdown, nem texto antes ou depois — sua resposta deve começar direto com {{ e terminar com }}.

O arquivo será um documento pessoal da pessoa, CNH/RG, sendo em PNG, JPEG ou PDF.
"""

prompt_endereco = f"""Preciso que me dê um JSON. Somente JSON de resposta! No seguinte formato abaixo:

{{
"logradouro": "aqui vai o valor",
"numero": "aqui vai o valor",
"bairro": "aqui vai o valor",
"cep": "aqui vai o valor",
"cidade": "aqui vai o valor"
}}

Preencha os campos com os valores encontrados no arquivo anexado. Caso não encontre o valor de algum campo, preencha com null. Não invente ou estime valores — só preencha um campo se ele aparecer claramente no arquivo.

Não use blocos de código markdown, nem texto antes ou depois — sua resposta deve começar direto com {{ e terminar com }}.

O arquivo será um documento de comprovante de residência, conta de luz/água e afins, sendo em PNG, JPEG ou PDF.
"""

arquivos_endereco = list(pasta.glob("endereco.*"))

if not arquivos_endereco:
    raise FileNotFoundError("Não encontrei o arquivo com nome endereco na pasta")
else:
    caminho_arquivo_endereco = arquivos_endereco[0]

arquivos_cnh = list(pasta.glob("cnh.*"))

if not arquivos_cnh:
    raise FileNotFoundError("Não encontrei o arquivo com nome cnh na pasta")
else:
    caminho_arquivo_cnh = arquivos_cnh[0]


resposta_documento_cnh = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=500,
    messages=[{"role": "user", "content": [montar_bloco_arquivo(caminho_arquivo_cnh), {"type": "text", "text": prompt_documento}]}],
)

resposta_docuemnto_endeco = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=500,
    messages=[{"role": "user", "content": [montar_bloco_arquivo(caminho_arquivo_endereco), {"type": "text", "text": prompt_endereco}]}],
)

json_dados_por_escrito = verificar_json(tratar_resposta(resposta),
    prompt,
    {"cliente": {"renda": None, "profissao": None, "email": None, "telefone": None, "estado_civil": None}, "conjuge": None, "sexo": None})

json_dados_cnh = verificar_json(tratar_resposta(resposta_documento_cnh),
[montar_bloco_arquivo(caminho_arquivo_cnh), {"type": "text", "text": prompt_documento}],
{"nome": None, "cpf": None, "data_de_nascimento": None})

json_dados_endereco = verificar_json(tratar_resposta(resposta_docuemnto_endeco),
[montar_bloco_arquivo(caminho_arquivo_endereco), {"type": "text", "text": prompt_endereco}],
{"logradouro": None, "numero": None, "bairro": None, "cep": None, "cidade": None})

if json_dados_endereco["bairro"] is None:
    json_dados_endereco["bairro"] = "Centro"

def verificador_cpf(cpf) -> bool:
    if cpf is None:
        return False
    cpf_limpo = cpf.replace(".", "").replace("-", "")

    if len(cpf_limpo) != 11:
        return False

    primeiros_nove_digitos = cpf_limpo[:9]
    digito_varificador1 = 0
    digito_varificador2 = 0
    soma = 0

    for indice, digito in enumerate(primeiros_nove_digitos):
        peso = 10 - indice
        soma += int(digito) * peso

    soma = soma % 11

    if soma < 2:
        digito_varificador1 = 0
    else :
        digito_varificador1 = 11 - soma

    soma = 0

    for indice, digito in enumerate(primeiros_nove_digitos + str(digito_varificador1)):
        peso = 11 - indice
        soma += int(digito) * peso

    soma = soma % 11

    if soma < 2:
        digito_varificador2 = 0
    else:
        digito_varificador2 = 11 - soma


    if digito_varificador1 != int(cpf_limpo[9]) or digito_varificador2 != int(cpf_limpo[10]):
        return False
    else:
        return True

if not verificador_cpf(json_dados_cnh["cpf"]):
    json_dados_cnh["cpf"] = None


if  not json_dados_por_escrito["conjuge"] is None and not verificador_cpf(json_dados_por_escrito["conjuge"]["cpf"]):
    json_dados_por_escrito["conjuge"]["cpf"] = None


dados_cliente = {}
dados_cliente.update(json_dados_cnh)
dados_cliente.update(json_dados_endereco)
dados_cliente.update(json_dados_por_escrito["cliente"])

ficha_final = {
    "cliente": dados_cliente,
    "conjuge":  json_dados_por_escrito["conjuge"]
}

def imprimir_pessoa(dicionario_pessoa, titulo):
    result = f"=== {titulo} ===\n"

    for chave, valor in dicionario_pessoa.items():
        result = result + f"{chave}: {valor}\n"

    print(result)
    return result

def portao(dados_pessoa, pessoa):
    dados_none = []

    for chave, valor in dados_pessoa.items():
        if valor is None:
            dados_none.append(f"{pessoa}: {chave}")

    if not dados_none:
        imprimir_pessoa(dados_pessoa, pessoa)
        return True
    else:
        print(f"Não podemos prosseguir devido a falta do(s) seguinte(s) dado(s): {dados_none}")
        return False

cliente_ok = portao(ficha_final["cliente"], "Cliente")

conjuge_ok = True
if ficha_final["conjuge"] is not None:
    conjuge_ok = portao(ficha_final["conjuge"], "Cônjuge")

if not cliente_ok or not conjuge_ok:
    raise ValueError("Ficha incompleta — corrija os dados faltantes antes de continuar.")

if ficha_final["cliente"]["estado_civil"].lower() == "casado" and ficha_final["conjuge"] is None:
    raise ValueError("O Cliente é casado, mas não temos dados do conjuge")





