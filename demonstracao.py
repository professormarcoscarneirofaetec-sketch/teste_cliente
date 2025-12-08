import sqlite3
import pandas as pd
import os
from datetime import date
# Nota: IPython.display é aceitável aqui, mas será substituído por st.write no código Streamlit
from IPython.display import display, clear_output, Markdown 
import numpy as np

print("--- Setup Inicial Completo e Bibliotecas Importadas ---")

# =========================================================================
# CONSTANTES E DADOS DE EXEMPLO
# =========================================================================
CORTE_FREQUENCIA = 75
NOTA_APROVACAO_DIRETA = 7.0
NOTA_MINIMA_P3 = 4.0
NOTA_MINIMA_FINAL = 5.0
DB_NAME = 'diario_de_classe.db'
# Dados usados APENAS para popular as tabelas Alunos e Disciplinas
diario_de_classe = {
    "Alice": {
        "Português Instrumental": {
            "presencas": [{"data": "2025-09-01", "conteudo": "Revisão Gramatical", "status": 1}],
            "avaliacoes": {"P1": 9.0, "P2": 9.0, "P3": None}
        },
    },
    "Bruno": {
        "Português Instrumental": {
            "presencas": [{"data": "2025-09-01", "conteudo": "Revisão Gramatical", "status": 1}],
            "avaliacoes": {"P1": 6.0, "P2": 6.0, "P3": 8.0}
        },
    },
    "Carol": {
        "Português Instrumental": {
            "presencas": [{"data": "2025-09-01", "conteudo": "Revisão Gramatical", "status": 1}],
            "avaliacoes": {"P1": 5.0, "P2": 5.0, "P3": None}
        },
    },
}

# =========================================================================
# FUNÇÕES DE SETUP DO BANCO DE DADOS (CRIAÇÃO DE TABELAS)
# =========================================================================

def setup_inicial_db(force_recreate=False):
    """Cria o banco de dados e todas as tabelas se elas não existirem."""
    if os.path.exists(DB_NAME) and force_recreate:
        os.remove(DB_NAME)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Criação das Tabelas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Alunos (
            id_aluno INTEGER PRIMARY KEY,
            nome TEXT NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Disciplinas (
            id_disciplina INTEGER PRIMARY KEY,
            nome_disciplina TEXT NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Turmas (
            id_turma INTEGER PRIMARY KEY,
            nome_turma TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Aulas (
            id_aula INTEGER PRIMARY KEY,
            id_turma INTEGER,
            id_disciplina INTEGER,
            data_aula TEXT NOT NULL,
            conteudo_lecionado TEXT,
            FOREIGN KEY (id_turma) REFERENCES Turmas(id_turma),
            FOREIGN KEY (id_disciplina) REFERENCES Disciplinas(id_disciplina),
            UNIQUE (id_disciplina, data_aula)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Frequencia (
            id_frequencia INTEGER PRIMARY KEY,
            id_aula INTEGER,
            id_aluno INTEGER,
            presente INTEGER NOT NULL, -- 1 para presente, 0 para falta
            FOREIGN KEY (id_aula) REFERENCES Aulas(id_aula),
            FOREIGN KEY (id_aluno) REFERENCES Alunos(id_aluno),
            UNIQUE (id_aula, id_aluno)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Notas (
            id_aluno INTEGER,
            id_disciplina INTEGER,
            tipo_avaliacao TEXT NOT NULL, -- Ex: 'P1', 'P2', 'P3'
            valor_nota REAL NOT NULL,
            PRIMARY KEY (id_aluno, id_disciplina, tipo_avaliacao),
            FOREIGN KEY (id_aluno) REFERENCES Alunos(id_aluno),
            FOREIGN KEY (id_disciplina) REFERENCES Disciplinas(id_disciplina)
        )
    """)
    conn.commit()

    # População Inicial de Dados de Exemplo
    # 1. Turma Padrão
    cursor.execute("INSERT OR IGNORE INTO Turmas (id_turma, nome_turma) VALUES (1, 'Turma Padrão 2026')")
    # 2. Alunos
    alunos_nomes = list(diario_de_classe.keys())
    for nome in alunos_nomes:
        cursor.execute("INSERT OR IGNORE INTO Alunos (nome) VALUES (?)", (nome,))
    
    # 3. Disciplinas (coletando todas as disciplinas únicas do dict)
    disciplinas_nomes = set(d for dados_aluno in diario_de_classe.values() for d in dados_aluno.keys())
    for nome in disciplinas_nomes:
        cursor.execute("INSERT OR IGNORE INTO Disciplinas (nome_disciplina) VALUES (?)", (nome,))

    conn.commit()
    conn.close()
    
    print("✅ Setup do Banco de Dados Completo e Dados Iniciais Inseridos.")

# Garante que o BD exista antes de qualquer outra operação
setup_inicial_db()

# =========================================================================
# FUNÇÕES PRINCIPAIS DE LÓGICA E BD
# =========================================================================

def calcular_media_final(avaliacoes):
    """Calcula a média final do aluno baseado nas notas P1, P2, e P3 (se aplicável)."""
    p1_val = avaliacoes.get("P1")
    p2_val = avaliacoes.get("P2")
    p3_val = avaliacoes.get("P3")
    
    # Trata None/NaN como 0.0 para cálculo parcial
    p1 = np.nan_to_num(p1_val, nan=0.0)
    p2 = np.nan_to_num(p2_val, nan=0.0)
    
    p3 = None
    if p3_val is not None and not np.isnan(p3_val):
        p3 = p3_val
    
    media_parcial = (p1 + p2) / 2
    nota_final = media_parcial
    situacao_nota = ""
    
    if media_parcial >= NOTA_APROVACAO_DIRETA:
        situacao_nota = "APROVADO POR MÉDIA"
    elif media_parcial >= NOTA_MINIMA_P3:
        if p3 is None:
            situacao_nota = "PENDENTE (AGUARDANDO P3)"
        else:
            media_final_com_p3 = (media_parcial + p3) / 2
            nota_final = media_final_com_p3
            if nota_final >= NOTA_MINIMA_FINAL:
                situacao_nota = "APROVADO APÓS P3"
            else:
                situacao_nota = "REPROVADO POR NOTA"
    else: 
        situacao_nota = "REPROVADO DIRETO"
        
    return nota_final, situacao_nota, media_parcial

def lancar_aula_e_frequencia(id_disciplina, data_aula, conteudo):
    """Lança uma nova aula e marca todos os alunos como presentes por padrão."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    id_turma_padrao = 1
    try:
        # 1. Lançar a Aula
        cursor.execute("""INSERT INTO Aulas (id_turma, id_disciplina, data_aula, conteudo_lecionado) VALUES (?, ?, ?, ?)""", (id_turma_padrao, id_disciplina, data_aula, conteudo))
        conn.commit()
        id_aula = cursor.lastrowid
        
        # 2. Lançar Frequência para todos os alunos (Padrão: Presente = 1)
        cursor.execute("SELECT id_aluno FROM Alunos")
        alunos_ids = [row[0] for row in cursor.fetchall()]
        registros_frequencia = [(id_aula, id_aluno, 1) for id_aluno in alunos_ids]
        cursor.executemany("""INSERT INTO Frequencia (id_aula, id_aluno, presente) VALUES (?, ?, ?)""", registros_frequencia)
        conn.commit()
        print(f"✅ Aula de {conteudo} em {data_aula} lançada (ID: {id_aula}). Todos marcados como Presentes.")
    except Exception as e:
        print(f"❌ Erro ao lançar aula: {e}")
    finally:
        conn.close()

def inserir_nota_no_db(id_aluno, id_disciplina, tipo_avaliacao, valor_nota):
    """Insere ou atualiza (REPLACE INTO) a nota de um aluno no BD."""
    if valor_nota is None or valor_nota < 0 or valor_nota > 10.0:
        print("⚠️ Erro: Insira um valor de nota válido (0.0 a 10.0).")
        return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""REPLACE INTO Notas (id_aluno, id_disciplina, tipo_avaliacao, valor_nota) VALUES (?, ?, ?, ?)""", (id_aluno, id_disciplina, tipo_avaliacao, valor_nota))
        conn.commit()
        print(f"✅ Nota {tipo_avaliacao} ({valor_nota:.1f}) inserida/atualizada para o Aluno {id_aluno} na Disciplina {id_disciplina}.")
    except Exception as e:
        print(f"❌ Erro ao inserir nota: {e}")
    finally: conn.close()

def carregar_ids():
    """Carrega Dicionários de mapeamento Nome -> ID de Alunos e Disciplinas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    alunos_db = {nome: id_a for id_a, nome in cursor.execute("SELECT id_aluno, nome FROM Alunos").fetchall()}
    disciplinas_db = {nome: id_d for id_d, nome in cursor.execute("SELECT id_disciplina, nome_disciplina FROM Disciplinas").fetchall()}
    conn.close()
    return alunos_db, disciplinas_db
    
def obter_frequencia_por_aula(id_disciplina, data_aula):
    """Busca o ID da aula e a lista de alunos com status de presença para aquela aula."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    id_turma_padrao = 1
    
    # 1. Encontrar o ID da Aula
    cursor.execute("""
        SELECT id_aula FROM Aulas WHERE id_turma = ? AND id_disciplina = ? AND data_aula = ?
    """, (id_turma_padrao, id_disciplina, data_aula))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return None, "❌ Aula não encontrada para essa data/disciplina."
        
    id_aula = result[0]
    
    # 2. Montar o DataFrame com a frequência
    df = pd.read_sql_query(f"""
        SELECT 
            A.nome AS Aluno, 
            F.id_frequencia,
            F.presente 
        FROM Frequencia F
        JOIN Alunos A ON F.id_aluno = A.id_aluno
        WHERE F.id_aula = {id_aula}
        ORDER BY A.nome;
    """, conn)
    conn.close()
    
    df['Status Atual'] = df['presente'].apply(lambda x: 'PRESENTE ✅' if x == 1 else 'FALTA 🚫')
    df['Opção'] = df['id_frequencia'].astype(str) + ' - ' + df['Aluno']
    
    return df, id_aula
    
def atualizar_status_frequencia(id_frequencia, novo_status):
    """Atualiza o status de presente/falta (0 ou 1) de um aluno em uma aula."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Frequencia SET presente = ? WHERE id_frequencia = ?
        """, (novo_status, id_frequencia))
        conn.commit()
        return f"✅ Status de Presença Atualizado! (ID Frequência: {id_frequencia})"
    except Exception as e:
        return f"❌ Erro ao atualizar frequência: {e}"
    finally:
        conn.close()