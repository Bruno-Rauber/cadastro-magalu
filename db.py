import sqlite3

def conectar(caminho_banco):
    conexao = sqlite3.connect(caminho_banco)
    conexao.execute("PRAGMA foreign_keys = ON")

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS execucoes (
            id INTEGER PRIMARY KEY,
            iniciado_em TEXT NOT NULL,
            finalizado_em TEXT,
            conta TEXT NOT NULL,
            grupo TEXT NOT NULL,
            cota TEXT NOT NULL,
            modo_teste INTEGER NOT NULL,
            estado TEXT NOT NULL
        )
    """)

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS pessoas (
            id INTEGER PRIMARY KEY,
            papel TEXT NOT NULL,
            execucao_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            cpf TEXT NOT NULL,
            data_de_nascimento TEXT NOT NULL,
            sexo TEXT NOT NULL,
            estado_civil TEXT,
            profissao TEXT NOT NULL,
            renda TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            cep TEXT,
            logradouro TEXT,
            numero TEXT,
            bairro TEXT,
            cidade  TEXT,
            uf TEXT,
            FOREIGN KEY (execucao_id) REFERENCES execucoes(id)
        )
    """)

    return conexao