import re
import os
import json
import base64
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic
from playwright.sync_api import Playwright, sync_playwright, expect

load_dotenv()  # lê o arquivo .env e carrega as variáveis
chave = os.getenv("ANTHROPIC_API_KEY")


usuarios = {
    "impulsionar": {
    "chapa": os.getenv("IMPULSIONAR_CHAPA"),
    "senha_magalu": os.getenv("IMPULSIONAR_SENHA"),
    "filial": os.getenv("IMPULSIONAR_FILIAL")
},
    "douglas": {
        "chapa": os.getenv("DOUGLAS_CHAPA"),
        "senha_magalu": os.getenv("DOUGLAS_SENHA"),
        "filial": os.getenv("DOUGLAS_FILIAL")
    }
}
nomes_usuarios = ", ".join(usuarios.keys())

usuario_entrada = input(f"De qual usuário é essa cota? Digite um dos nomes abaixo:\n {nomes_usuarios} \n").lower().strip()

if usuario_entrada in usuarios:
    chapa = usuarios[usuario_entrada]["chapa"]
    senha_magalu = usuarios[usuario_entrada]["senha_magalu"]
    filial = usuarios[usuario_entrada]["filial"]

else:
    raise ValueError("Esse usuário não existe ou não foi cadastrado")

caminho_pasta = os.getenv("PASTA_TRABALHO")

if caminho_pasta:
    pasta = Path(caminho_pasta) # o caminho real da sua pasta
else:
    raise ValueError("Não existe um caminho da pasta no .env")

MODO_TESTE = False

cpf_teste = os.getenv("CPF_TESTE")
if MODO_TESTE:
    grupo = os.getenv("GRUPO_TESTE")
    cota = os.getenv("COTA_TESTE")
else:
    grupo = input("Digite o Grupo para esse processo: ").strip()
    cota = input("Digite a cota para esse processo: ").strip()

if not grupo or not cota:
    raise ValueError("Grupo ou cota não informados.")

pasta_processo = pasta / f"{grupo}_{cota}"
pasta_documentos = pasta_processo / "Documentos"

if not pasta_documentos.exists():
    os.makedirs(pasta_documentos)
    (pasta_documentos / "texto_whats.txt").touch()
    os.startfile(pasta_documentos)
    input("A pasta do processo foi criada. Salve os documentos, coloque as informações no texto_whats.txt e aperte Enter para continuar: ")
else:
    os.startfile(pasta_documentos)

# Bloco de verificação se os documentos necessáriso estão na pasta
arquivos_endereco = list(pasta_documentos.glob("endereco.*"))

if not arquivos_endereco:
    raise FileNotFoundError("Não encontrei o arquivo com nome endereco na pasta")
else:
    caminho_arquivo_endereco = arquivos_endereco[0]

arquivos_cnh = list(pasta_documentos.glob("cnh.*"))

if not arquivos_cnh:
    raise FileNotFoundError("Não encontrei o arquivo com nome cnh na pasta")
else:
    caminho_arquivo_cnh = arquivos_cnh[0]

arquivos_certidao = list(pasta_documentos.glob("*certidao*"))

if not arquivos_certidao:
    raise FileNotFoundError("Não encontrei nenhum arquivo com certidao no nome na pasta")

if MODO_TESTE:
    print("⚠️ RODANDO EM MODO TESTE")

client = anthropic.Anthropic(api_key=chave)

# Lista de profissões cadastradas no sistema da Magalu (gerada uma única vez
# pelo gerar_lista_profissoes.py). Usada no prompt pra IA padronizar o texto
# extraído do WhatsApp com uma opção que realmente existe no sistema.
with open("profissoes_magalu.json", "r", encoding="utf-8") as arquivo_profissoes:
    lista_profissoes_magalu = json.load(arquivo_profissoes)

lista_profissoes_texto = ", ".join(lista_profissoes_magalu)

# Chaves já normalizadas (minúsculas, sem acento, sem "(a)").
# Masculino e feminino apontam para o mesmo código do combo do Magalu.
mapa_estado_civil = {
    "casado": "1", "casada": "1",
    "desquitado": "2", "desquitada": "2",
    "separado judicialmente": "3", "separada judicialmente": "3",
    "outro": "4",
    "divorciado": "5", "divorciada": "5",
    "solteiro": "6", "solteira": "6",
    "uniao estavel": "8",
    "viuvo": "9", "viuva": "9",
}


# =====================================================================
# Funções de extração / validação de dados (vindas do main.py)
# =====================================================================

def tratar_resposta(resposta_IA):
    for bloco in resposta_IA.content:
        if bloco.type == "text":
            texto_resposta = bloco.text

    inicio = texto_resposta.find("{")
    fim = texto_resposta.rfind("}")

    json_limpo = texto_resposta[inicio:fim + 1]  # +1 porque o slice não inclui o índice final
    return json_limpo


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
    else:
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


# =====================================================================
# Extração via IA (mensagem do WhatsApp + documentos)
# =====================================================================

caminho_arquivo = pasta_documentos / "texto_whats.txt"

with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
    texto_whats = arquivo.read()

prompt = f"""Preciso que me dê um JSON. Somente JSON de resposta! No seguinte formato abaixo:

{{
"cliente": {{ "renda": "renda": "aqui vai o valor (formato numérico, ex: 2500,00 - sem R$, sem ponto de milhar, use vírgula para os centavos; se o valor não tiver centavos, acrescente ,00 no final)"", "profissao": "aqui vai o valor", "email": "aqui vai o valor", "telefone": "aqui vai o valor sem DDD e sem +55 o resto você devolve do jeito que vier) tome cuidado pra não duplicar numeros principalemnte "9" em sequencia, "estado_civil": "aqui vai o valor !sempre devolver no masculino Ex: casada devolver casado(solteiro, casado, divorciado, desquitado, separado judicialmente, uniao estavel, viuvo ou outro)", "sexo": "aqui vai o valor"  }},
"conjuge": null ou {{ "nome": "aqui vai o valor", "data_de_nascimento: "aqui vai o valor", "cpf": "aqui vai o valor", "profissao": "aqui vai o valor", "renda": "renda": "aqui vai o valor (formato numérico, ex: 2500,00 - sem R$, sem ponto de milhar, use vírgula para os centavos; se o valor não tiver centavos, acrescente ,00 no final)", "sexo": "aqui vai o valor" }}
}}

Preencha os campos com os valores encontrados no texto abaixo. Caso não encontre o valor de algum campo, preencha com null. Não invente ou estime valores — só preencha um campo se ele aparecer claramente no texto.

Não use blocos de código markdown, nem texto antes ou depois — sua resposta deve começar direto com {{ e terminar com }}.

O texto pode trazer uma seção "Dados do cliente" e outra "Dados do cônjuge" — use essas marcações para separar quem é quem.

Tanto cliente quanto conjuge devem ter sexo/genero e ele verá dessa forma Sexo: (m/f) - "m" para masculino e F para feminino. No JSON você deve colocar dessa forma sem ser por extenso

Para o campo "profissao" (tanto do cliente quanto do cônjuge, se houver), escolha a opção mais parecida/equivalente dentre a lista abaixo — essas são as únicas profissões cadastradas no sistema onde esse dado vai ser usado (ex: "PEDREIRO" no texto e "PEDREIRO" na lista bate direto; "MOTORISTA DE APP" no texto pode corresponder a "MOTORISTA" na lista). Alguns itens da lista têm sufixos de gênero como "(A)" ou "(O)" com formatação inconsistente (às vezes com espaço antes, às vezes sem) — não se preocupe em reproduzir esse sufixo nem sua formatação exata, priorize acertar a palavra principal da profissão. Se não tiver na lista voce deve colocar "OUTROS" como profissao.
Lista de profissões válidas: {lista_profissoes_texto}

Texto do WhatsApp:
{texto_whats}
"""

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
"numero": "aqui vai o valor, apenas o numero sem complemento",
"bairro": "aqui vai o valor",
"cep": "aqui vai o valor",
"cidade": "aqui vai o valor",
"uf": "aqui vai a sigla de 2 letras do estado em questão, maiúscula (ex: PR, não Paraná)"
}}

Preencha os campos com os valores encontrados no arquivo anexado. Caso não encontre o valor de algum campo, preencha com null. Não invente ou estime valores — só preencha um campo se ele aparecer claramente no arquivo.

Não use blocos de código markdown, nem texto antes ou depois — sua resposta deve começar direto com {{ e terminar com }}.

O arquivo será um documento de comprovante de residência, conta de luz/água e afins, sendo em PNG, JPEG ou PDF.
"""

resposta = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=500,
    messages=[{"role": "user", "content": prompt}]
)

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

json_dados_por_escrito = verificar_json(
    tratar_resposta(resposta),
    prompt,
    {"cliente": {"renda": None, "profissao": None, "email": None, "telefone": None, "estado_civil": None}, "conjuge": None, "sexo": None}
)

json_dados_cnh = verificar_json(
    tratar_resposta(resposta_documento_cnh),
    [montar_bloco_arquivo(caminho_arquivo_cnh), {"type": "text", "text": prompt_documento}],
    {"nome": None, "cpf": None, "data_de_nascimento": None}
)

json_dados_endereco = verificar_json(
    tratar_resposta(resposta_docuemnto_endeco),
    [montar_bloco_arquivo(caminho_arquivo_endereco), {"type": "text", "text": prompt_endereco}],
    {"logradouro": None, "numero": None, "bairro": None, "cep": None, "cidade": None, "uf": None}
)

if json_dados_endereco["bairro"] is None:
    json_dados_endereco["bairro"] = "Centro"

if not verificador_cpf(json_dados_cnh["cpf"]):
    json_dados_cnh["cpf"] = None

if json_dados_por_escrito["conjuge"] is not None and not verificador_cpf(json_dados_por_escrito["conjuge"]["cpf"]):
    json_dados_por_escrito["conjuge"]["cpf"] = None

dados_cliente = {}
dados_cliente.update(json_dados_cnh)
dados_cliente.update(json_dados_endereco)
dados_cliente.update(json_dados_por_escrito["cliente"])

ficha_final = {
    "cliente": dados_cliente,
    "conjuge": json_dados_por_escrito["conjuge"]
}

cliente_ok = portao(ficha_final["cliente"], "Cliente")

conjuge_ok = True
if ficha_final["conjuge"] is not None:
    conjuge_ok = portao(ficha_final["conjuge"], "Cônjuge")

if not cliente_ok or not conjuge_ok:
    raise ValueError("Ficha incompleta — corrija os dados faltantes antes de continuar.")

# Normaliza o sexo pra maiúsculo aqui (ponto único), pois os <option> do Magalu
# usam value="M"/"F" e a IA pode devolver em qualquer caixa.
ficha_final["cliente"]["sexo"] = ficha_final["cliente"]["sexo"].upper()

if ficha_final["conjuge"] is not None:
    ficha_final["conjuge"]["sexo"] = ficha_final["conjuge"]["sexo"].upper()

# Telefone: a IA só copia o número do texto, sem transformar.
# A normalização fica aqui no código, que faz sempre a mesma coisa.
# O Magalu preenche o DDD pela cidade, então o campo recebe só o número local (8 ou 9 dígitos).

telefone_limpo = ""
for caractere in ficha_final["cliente"]["telefone"]:
    if caractere.isnumeric():
        telefone_limpo += caractere

ficha_final["cliente"]["telefone"] = telefone_limpo

# 11 dígitos = DDD + celular; 10 dígitos = DDD + número de 8 dígitos
if len(ficha_final["cliente"]["telefone"]) in (10, 11):
    ficha_final["cliente"]["telefone"] = ficha_final["cliente"]["telefone"][2:]

if len(ficha_final["cliente"]["telefone"]) not in (8, 9):
    raise ValueError(f"Telefone com tamanho inválido: {ficha_final['cliente']['telefone']}. Confira o texto_whats.txt")

# Normaliza o numero caso a I.A devolve com complemento
ficha_final["cliente"]["numero"] = ficha_final["cliente"]["numero"].split()[0]

# Estado civil: calculado uma única vez aqui, reaproveitado tanto no portão
# quanto dentro do Playwright (adicionar_dados_cliente) para decidir o combo
# e se a aba de cônjuge deve abrir.
estado_civil_extraido = ficha_final["cliente"]["estado_civil"].lower().replace("(a)", "").strip().replace("ã", "a").replace("á", "a").replace("ú", "u")
codigo_estado_civil = mapa_estado_civil[estado_civil_extraido]

# "1" = casado, "8" = união estável — os dois casos em que a aba de cônjuge abre no Magalu.
if codigo_estado_civil in ("1", "8") and ficha_final["conjuge"] is None:
    raise ValueError("O cliente é casado ou está em união estável, mas não temos dados do cônjuge")

#funcao utilziada para imprimir taxa de trasnferencia
def eh_relatorio(pagina):
    return "frmConCmImpressao" in pagina.url

if MODO_TESTE:
    ficha_final["cliente"]["cpf"] = cpf_teste
# =====================================================================
# Automação Playwright (preenchimento no Magalu)
# =====================================================================

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    context.set_default_timeout(120000)  # todas as páginas do contexto, inclusive popups
    page = context.new_page()
    page.goto("https://portal.consorciomagalu.com.br/portal-consorcio/login")
    page.wait_for_load_state("networkidle")
    page.get_by_role("textbox", name="Chapa").fill(chapa)
    page.get_by_role("textbox", name="Senha").fill(senha_magalu)
    page.get_by_role("textbox", name="Filial").fill(filial)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Acessar portal").click()
    page.wait_for_load_state("networkidle")

    with page.expect_popup() as page1_info:
        page.get_by_role("link", name="Registro de Vendas").click()
    page1 = page1_info.value
    page1.locator("a").filter(has_text="Atendimento").first.click()
    page1.get_by_role("link", name="Atendimento a Clientes").click()
    page1.get_by_role("link", name="Posição do Consorciado").click()
    page1.locator("#ctl00_Conteudo_edtGrupo").fill(grupo)
    page1.locator("#ctl00_Conteudo_edtCota").fill(cota)
    page1.get_by_role("button", name="Localizar").click()
    titular = page1.locator("#ctl00_Conteudo_lblCD_Cota").text_content()

    partes = titular.split()
    titular_tratado = " ".join(partes[2:])
    print(f"\nNome do Consorciado {titular_tratado}")

    page1.wait_for_load_state("networkidle")
    page1.locator("a").filter(has_text="Crédito").click()
    with page1.expect_popup() as page2_info:
        page1.get_by_role("link", name="Workflow").click()
        page1.wait_for_load_state("networkidle")
    page2 = page2_info.value
    page2.wait_for_load_state("networkidle")
    page2.goto("https://newconsq.consorciomagalu.tec.br/workflow")
    page2.wait_for_load_state("networkidle")
    page2.get_by_role("button", name="Solicitações").click()
    with page2.expect_popup() as page3_info:
        page2.locator("div").filter(has_text=re.compile(r"^TransferênciaRealizar solicitação de transferência$")).nth(
            1).click()
    page3 = page3_info.value
    page3.locator("#ctl00_Conteudo_edtGrupo").fill(grupo)
    page3.locator("#ctl00_Conteudo_edtCota").fill(cota)
    page3.get_by_role("button", name="Localizar").click()
    linha_titular = page3.locator("tr", has_text=titular_tratado)
    linha_titular.locator("a").click()

    mensagem_solicitacao = page3.locator(".mensagem-solicitacao-andamento")
    if mensagem_solicitacao.is_visible():
        page3.get_by_role("button", name="Cancelar Solicitação").click()

    linha_cota = page3.locator("#tableCotas tr").filter(has_text=grupo).filter(has_text=cota)
    linha_cota.locator("input").check()
    page3.get_by_role("button", name="Continuar").click()

# =====================================================================
    # Preenchimento dos dados do cessionário
# =====================================================================
    def adicionar_dados_conjuge():
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_txtCPF").fill(
            ficha_final["conjuge"]["cpf"])
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_txtCPF").press("Tab")

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_txtNascimento").fill(
            ficha_final["conjuge"]["data_de_nascimento"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_txtNome").fill(
            ficha_final["conjuge"]["nome"])

        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_cmbSexo").select_option(
            ficha_final["conjuge"]["sexo"])
        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_cmbPoliticamenteExposto").select_option(
            "N")
        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_cmbTipoDocumento").select_option(
            "1006")

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_txtDocumento").fill(
            ficha_final["conjuge"]["cpf"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_txtValorRenda").fill(
            ficha_final["conjuge"]["renda"])
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_txtValorRenda").press(
            "Tab")
        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_cmbAcessibilidade").select_option(
            "1")
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_btnProfissao").click()

        page3.get_by_role("textbox", name="Faça a busca pela descrição").fill(
            ficha_final["conjuge"]["profissao"])
        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_btnBuscarProfissao").click()
        tabela_profissoes = page3.locator("#tablePais tbody tr")
        qtde_profissoes = tabela_profissoes.count()
        if qtde_profissoes == 0:
            print("\n⏸ Nenhuma profissão encontrada — selecione manualmente e confirme...")
            page3.locator(
                "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_btnBuscarProfissao").wait_for(
                state="hidden", timeout=120000)
            page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_btnContinuar").click()
        else:
            # count() > 1 acontece quando o sistema da Magalu tem a mesma profissão
            # cadastrada duas vezes com códigos diferentes (bug já mapeado) — como o
            # texto é idêntico, tanto faz qual delas escolher, então pega a primeira.
            page3.get_by_title("selecionar").first.click()
            page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaConjuge_btnContinuar").click()

    def adicionar_dados_cliente():
        page3.wait_for_selector("text=ADICIONAR", timeout=120000)
        page3.get_by_role("button", name="Adicionar ").click()
        page3.get_by_role("link", name="Pessoa Física").click()

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_txtCPF").fill(
            ficha_final["cliente"]["cpf"])
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_txtCPF").press("Tab")

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_txtNascimento").fill(
            ficha_final["cliente"]["data_de_nascimento"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_txtNome").fill(
            ficha_final["cliente"]["nome"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_cmbSexo").select_option(
            ficha_final["cliente"]["sexo"])
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_cmbPoliticamenteExposto").select_option("N")
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_cmbTipoDocumento").select_option("1006")

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_txtDocumento").fill(
            ficha_final["cliente"]["cpf"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_txtValorRenda").fill(
            ficha_final["cliente"]["renda"])
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_txtValorRenda").press("Tab")
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_cmbAcessibilidade").select_option("1")
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_btnProfissao").click()

        page3.get_by_role("textbox", name="Faça a busca pela descrição").fill(ficha_final["cliente"]["profissao"])
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_btnBuscarProfissao").click()

        tabela_profissoes = page3.locator("#tablePais tbody tr")
        qtde_profissoes = tabela_profissoes.count()
        if qtde_profissoes == 0:
            print("\n⏸ Nenhuma profissão encontrada — selecione manualmente e confirme...")
            page3.locator(
                "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_divBuscaProfissao").wait_for(
                state="hidden", timeout=120000)
        else:
            # count() > 1 acontece quando o sistema da Magalu tem a mesma profissão
            # cadastrada duas vezes com códigos diferentes (bug já mapeado) — como o
            # texto é idêntico, tanto faz qual delas escolher, então pega a primeira.
            page3.get_by_title("selecionar").first.click()

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_cmbEstadoCivil").select_option(codigo_estado_civil)

        if codigo_estado_civil in ("1", "8"):
            page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_btnContinuar").click()
            adicionar_dados_conjuge()
        else:
            page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowPessoaFisica_btnContinuar").click()

    adicionar_dados_cliente()

    page2.wait_for_load_state("networkidle")

    cidade_autocomplete = f"{ficha_final['cliente']['cidade']} - {ficha_final['cliente']['uf']}"

# =====================================================================
    # Parte do endereço
# =====================================================================
    tabela_de_enderecos = page3.locator("#tableEndereco tr")

    def adicionar_novo_endereco():
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_btAddEndereco").click()
        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_cmbTipoEndereco").select_option("1")

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtCEP").fill(
            ficha_final["cliente"]["cep"])

        page3.wait_for_load_state("networkidle")

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtEndereco").fill(
            ficha_final["cliente"]["logradouro"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtNumero").fill(
            ficha_final["cliente"]["numero"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtBairro").fill(
            ficha_final["cliente"]["bairro"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtNM_Cidade").fill(
            ficha_final["cliente"]["cidade"])

        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtNM_Cidade").fill(ficha_final["cliente"]["cidade"])
        page3.locator(".ui-autocomplete").get_by_text(cidade_autocomplete.upper()).click()

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtEndereco").fill(
            ficha_final["cliente"]["logradouro"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtNumero").fill(
            ficha_final["cliente"]["numero"])

        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEndereco_txtBairro").fill(
            ficha_final["cliente"]["bairro"])

        page3.get_by_role("button", name="Salvar").click()
        page3.wait_for_load_state("networkidle")


        linha_recem_criada = page3.locator("#tableEndereco tr").filter(has_text=ficha_final["cliente"]["logradouro"]).filter(
            has_text=ficha_final["cliente"]["numero"]).filter(has_text=ficha_final["cliente"]["cidade"])
        linha_recem_criada.locator("a[id*='lnkDefinirPrincipal']").click()
        page3.get_by_role("button", name="Continuar", description="continuar").click()
        page3.wait_for_load_state("networkidle")

    if tabela_de_enderecos.count() > 0:
        linha_igual = tabela_de_enderecos.filter(
            has_text=ficha_final["cliente"]["logradouro"].upper()).filter(
            has_text=ficha_final["cliente"]["numero"]).filter(
            has_text=ficha_final["cliente"]["cidade"].upper())

        if linha_igual.count() > 0:
            linha_igual.locator("a[id*='lnkDefinirPrincipal']").click()
            page3.get_by_role("button", name="Continuar", description="continuar").click()
            page3.wait_for_load_state("networkidle")
        else:
            adicionar_novo_endereco()
    else:
        adicionar_novo_endereco()

# =====================================================================
    # Adicionar Telefone
# =====================================================================
    tabela_de_telefones = page3.locator("#tableEndereco tr")

    def adicionar_novo_telefone():
        page3.get_by_role("button", name=" Adicionar").click()
        page3.locator(
            "#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowTelefone_cmbTipoTelefone").select_option("1")
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowTelefone_txtNM_Cidade").fill(
            ficha_final["cliente"]["cidade"])
        page3.locator(".ui-autocomplete").get_by_text(cidade_autocomplete.upper()).click()
        page3.wait_for_load_state("networkidle")
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowTelefone_txtTelefone").fill(
            ficha_final["cliente"]["telefone"])
        page3.get_by_role("button", name="Salvar").click()

        linha_recem_criada_telefone = page3.locator("#tableEndereco tr").filter(has_text=ficha_final["cliente"]["telefone"])
        linha_recem_criada_telefone.locator("a[id*='lnkDefinirPrincipal']").click()
        page3.get_by_role("button", name="Continuar", description="continuar").click()
        page3.wait_for_load_state("networkidle")

    if tabela_de_telefones.count() > 0:
        linha_igual = tabela_de_telefones.filter(
            has_text=ficha_final["cliente"]["telefone"].upper())

        if linha_igual.count() > 0:
            linha_igual.locator("a[id*='lnkDefinirPrincipal']").click()
            page3.get_by_role("button", name="Continuar", description="continuar").click()
            page3.wait_for_load_state("networkidle")
        else:
            adicionar_novo_telefone()
    else:
        adicionar_novo_telefone()

# =====================================================================
    # Adicionar email
# =====================================================================
    tabela_de_email = page3.locator("#tableEndereco tr")

    def adicionar_novo_email():
        page3.get_by_role("button", name=" Adicionar").click()
        page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowEmail_txtEmail").fill(
            ficha_final["cliente"]["email"])
        page3.get_by_role("button", name="Salvar").click()

        linha_recem_criada_email = page3.locator("#tableEndereco tr").filter(has_text=ficha_final["cliente"]["email"])
        linha_recem_criada_email.locator("a[id*='lnkDefinirPrincipal']").click()
        page3.get_by_role("button", name="Continuar", description="continuar").click()
        page3.wait_for_load_state("networkidle")

    if tabela_de_email.count() > 0:
        linha_igual = tabela_de_email.filter(
            has_text=ficha_final["cliente"]["email"].upper())

        if linha_igual.count() > 0:
            linha_igual.locator("a[id*='lnkDefinirPrincipal']").click()
            page3.wait_for_load_state("networkidle")
            page3.get_by_role("button", name="Continuar", description="continuar").click()
            page3.wait_for_load_state("networkidle")
        else:
            adicionar_novo_email()
    else:
        adicionar_novo_email()

    page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowFatca_btnConfirmar").click()
    page3.wait_for_load_state("networkidle")
    page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowDadosLaborais_btnContinuar").click()
    page3.wait_for_load_state("networkidle")
    page3.locator("#ctl00_Conteudo_fichaCadastralWorkflow_fichaCadastralWorkflowInformacaoBancaria_btnContinuar").click()
    page3.wait_for_load_state("networkidle")
    page3.locator("#ctl00_Conteudo_btnAvancar").click(timeout=60000)
    page3.wait_for_load_state("networkidle")
    page3.locator("#ctl00_Conteudo_btnAvancar").click(timeout=60000)
    page3.wait_for_load_state("networkidle")

    # Bloco para anexar documentos (lê da `pasta_documentos` definida no topo do arquivo)
    lista_todos_arquivos = os.listdir(pasta_documentos)
    arquivos_cnh_upload = []
    arquivos_endereco_upload = []
    arquivos_certidao_upload = []
    arquivos_renda_upload = []

    for arquivo in lista_todos_arquivos:
        if "cnh" in arquivo:
            arquivos_cnh_upload.append(arquivo)
        elif "endereco" in arquivo:
            arquivos_endereco_upload.append(arquivo)
        elif "certidao" in arquivo:
            arquivos_certidao_upload.append(arquivo)
        else:
            arquivos_renda_upload.append(arquivo)

    arquivos_renda_upload = [arquivo for arquivo in arquivos_renda_upload if not arquivo.endswith(".txt")]

    # Bloco para anexar documentos de endereco
    linha_endereco = page3.locator(".documentos-lista-items").filter(has_text="COMPROVANTE DE RESIDÊNCIA")
    linha_endereco.locator("a[id*='lbkUpload']").click()
    for arquivo_endereco in arquivos_endereco_upload:
        page3.locator("#ctl00_Conteudo_rptCessionarios_ctl00_wucDocumentosWorkflow_fileUploadEdicao").set_input_files(f"{pasta_documentos}/{arquivo_endereco}")
    page3.get_by_role("button", name="Confirmar").click()

    # Bloco para anexar documentos de certidao/ comprovacao estado civil
    linha_certidao = page3.locator(".documentos-lista-items").filter(has_text="CERTIDÃO DE ESTADO CIVIL")
    linha_certidao.locator("a[id*='lbkUpload']").click()
    for arquivo_certidao in arquivos_certidao_upload:
        page3.locator("#ctl00_Conteudo_rptCessionarios_ctl00_wucDocumentosWorkflow_fileUploadEdicao").set_input_files(
            f"{pasta_documentos}/{arquivo_certidao}")
    page3.get_by_role("button", name="Confirmar").click()

    # Bloco para anexar documentos pessoais CNH / ETC
    linha_cnh = page3.locator(".documentos-lista-items").filter(has_text="DOCUMENTO PESSOAL C/ FOTO - CNH/ RG E CPF")
    linha_cnh.locator("a[id*='lbkUpload']").click()
    for arquivo_cnh in arquivos_cnh_upload:
        page3.locator("#ctl00_Conteudo_rptCessionarios_ctl00_wucDocumentosWorkflow_fileUploadEdicao").set_input_files(
            f"{pasta_documentos}/{arquivo_cnh}")
    page3.get_by_role("button", name="Confirmar").click()

    # Bloco para anexar documentos comprovacao de Renda
    linha_renda = page3.locator(".documentos-lista-items").filter(has_text="COMPROVANTE DE RENDA - PF")
    linha_renda.locator("a[id*='lbkUpload']").click()
    for arquivo_renda in arquivos_renda_upload:
        page3.locator("#ctl00_Conteudo_rptCessionarios_ctl00_wucDocumentosWorkflow_fileUploadEdicao").set_input_files(
            f"{pasta_documentos}/{arquivo_renda}")
    page3.get_by_role("button", name="Confirmar").click()

    page3.get_by_role("button", name="Continuar").click()
    page3.get_by_role("link", name=" Boleto Definir para Boleto").click()
    page3.wait_for_load_state("networkidle")
    page3.get_by_role("button", name="Continuar").click()
    page3.get_by_role("checkbox", name="Declaro, para os devidos fins").check()  # sempre marcar
    page3.get_by_role("checkbox", name="Comprometo-me a manter as").check()  # sempre marcar
    page3.locator("#ctl00_Conteudo_cbxPropositoAquisicao").select_option("3")  # Sempre essa opção independente
    page3.get_by_role("button", name="Continuar").click()
    page3.get_by_role("button", name="Confirmar").click()
    page3.close()


    # Gerar e baixar o termo de cessão (bloco já testado e validado)
    caminho_termo = str(pasta_processo / f"termo_{grupo}_{cota}.pdf")
    page2.get_by_role("button", name="Processos").click()
    page2.wait_for_timeout(60500)
    page2.reload()
    page2.wait_for_load_state("networkidle")
    page2.get_by_role("button", name="Processos").click()
    page2.get_by_role("combobox", name="Pesquisar por Nome").click()
    page2.get_by_role("option", name="Grupo/Cota").click()
    page2.get_by_role("textbox", name="Descrição").fill(f"{grupo}/{cota}")
    page2.locator("[data-testid='FilterAltIcon'].MuiSvgIcon-fontSizeMedium").click()
    linha_termo = page2.locator("p").get_by_text(f"{titular_tratado}")
    linha_termo.click()
    page2.locator(".MuiBox-root > div:nth-child(2) > .MuiButtonBase-root").click()
    linha_cessonario = page2.locator(".MuiDataGrid-row").filter(has_text="CESSONÁRIO(A) - PF")
    linha_cessonario.get_by_test_id("ArrowForwardIcon").click()
    page2.get_by_role("tab", name="Termo de Cessão Transferência").click()
    page2.get_by_role("tab", name="Termo de Cessão Transferência").click()
    with page2.expect_popup() as page6_info:
        page2.get_by_role("button", name="Baixar Termo").click()
    page6 = page6_info.value
    page6.wait_for_load_state("networkidle")
    frame_pdf = page6.frame(url=re.compile(r"^chrome-extension://"))

    with page6.expect_download() as download_info:
        frame_pdf.get_by_role("button", name="Baixar").click()
    download = download_info.value
    download.save_as(caminho_termo)

    # Emitir extrato da cota
    page1.get_by_role("link", name="Imprimir Extrato").click()
    page1.locator("#ctl00_Conteudo_btnImprimir").click()

    with page1.expect_popup() as page_extrato_info:
        page1.get_by_role("button", name="Imprimir").click()
    page_extrato = page_extrato_info.value
    page_extrato.wait_for_load_state("networkidle")

    resposta = context.request.get(page_extrato.url)
    with open(pasta_processo / f"extrato_{grupo}_{cota}.pdf", "wb") as arquivo:
        arquivo.write(resposta.body())

    page_extrato.close()

    # Emitir taxa de transferencia
    page1.get_by_role("link", name="Emissão de Cobrança").click()
    linha_taxa = page1.locator("#ctl00_Conteudo_grdBoleto_Avulso tr").filter(has_text="RECBTO. TAXA TRANSF")
    linha_taxa.locator("[id*='imgEmite_Boleto']").click()
    page1.wait_for_load_state("networkidle")

    with page1.expect_popup(predicate=eh_relatorio) as page_taxa_info:
        page1.get_by_role("button", name="Emitir Cobrança", exact=True).click()
    page_taxa = page_taxa_info.value
    page_taxa.wait_for_load_state("networkidle")

    resposta = context.request.get(page_taxa.url)
    with open(pasta_processo / f"taxa_{grupo}_{cota}.pdf", "wb") as arquivo:
        arquivo.write(resposta.body())

    page_taxa.close()

    page2.get_by_role("tab", name="Documentos").click()
    linha_comprovante_envio = page2.locator(".MuiDataGrid-row").filter(has_text="COMPROVANTE DE ENVIO DO TERMO ORIGINAL")
    linha_comprovante_envio.get_by_test_id("FileUploadIcon").click()
    page2.get_by_label("", exact=True).set_input_files(caminho_termo)
    page2.get_by_role("button", name="Confirmar").click()

    linha_termo_cessao = page2.locator(".MuiDataGrid-row").filter(
        has_text="TERMO DE CESSÃO - TRANSFERÊNCIA")
    linha_termo_cessao.get_by_test_id("FileUploadIcon").click()
    page2.get_by_label("", exact=True).set_input_files(caminho_termo)
    page2.get_by_role("button", name="Confirmar").click()

    page2.get_by_test_id("ArrowBackIcon").click()
    if MODO_TESTE:
        print("Não podemos mandar o termo em MODO TESTE!")
        sys.exit()
    else:
        page2.get_by_role("button", name="Concluir").click()
        page2.get_by_role("button", name="Salvar").click()

    page2.get_by_role("button", name="Processos").click()
    page2.wait_for_timeout(60500)
    page2.reload()
    page2.get_by_role("combobox", name="Pesquisar por Nome").click()
    page2.get_by_role("option", name="Grupo/Cota").click()
    page2.get_by_role("textbox", name="Descrição").fill(f"{grupo}/{cota}")
    page2.locator("[data-testid='FilterAltIcon'].MuiSvgIcon-fontSizeMedium").click()
    page2.wait_for_timeout(2500)
    verificar_qnt_processos = page2.get_by_role("button", name="Todos").text_content().strip()
    if verificar_qnt_processos != "Todos (0)":
        print("Esse processo não foi para análise, verificar se a taxa foi paga")
    else:
        print("Processo foi para análise")


    input("\nEsperando Enter pra finalizar")
    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)