# Cadastro Magalu
Script em Python que organiza documentos de clientes e sobe processos de transferência de consórcio no sistema da Magalu.
Mas o que é esse processo de transferência? A resposta mais curta para isso seria: um cliente compra a cota de outra pessoa, e a administradora precisa do cadastro do novo titular, com documentos, para analisar a troca.
## O problema
No fluxo do meu trabalho (subir processos no sistema da Magalu), tenho um problema: esse fluxo é repetitivo, manual e tem risco de erro humano. Subir um processo no sistema da Magalu significa extrair os dados do cliente por meio dos documentos pessoais, escrevê-los nos formulários do sistema e anexar os arquivos para o processo ir para análise. Antes, todo esse processo era feito manualmente e demorava cerca de 20 a 30 minutos:
- Salvar os documentos recebidos em uma pasta na área de trabalho
- Abrir o sistema da Magalu e os documentos salvos
- Preencher os formulários de acordo com os documentos
- Baixar os documentos do processo
- Anexar os documentos
- Conferir se o processo foi para análise de fato

Hoje a história muda: leva cerca de 5 minutos, somando iniciar o script, salvar e renomear os documentos na pasta e toda a parte necessária no sistema da Magalu.
- O script cria a pasta do cliente
- Manda os documentos pessoais pela API da Anthropic: a IA lê os documentos e o texto do WhatsApp, com as informações que não constam nos documentos, como profissão, renda, telefone e e-mail
- Retorna todos os dados necessários para preencher o formulário
- Antes de entrar no sistema da Magalu, o script tem alguns cuidados:
  - Função que verifica se o CPF extraído é matematicamente válido; caso contrário, avisa o usuário
  - Portão: verifica se foram extraídos todos os dados necessários para iniciar o processo no sistema; caso contrário, para e avisa o usuário do que está faltando
- Abre sozinho o sistema, preenche o formulário e anexa os documentos, avisando o usuário do que está acontecendo nos momentos necessários
- Baixa o termo de transferência (contrato), o extrato da cota e o boleto da taxa do processo, e salva tudo na pasta do cliente que o script criou
- Envia o processo para análise, anexando o termo que foi salvo
- Verifica se o processo realmente foi para análise e avisa o usuário




## Como rodar

## Decisões
## Uso de IA