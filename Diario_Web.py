# Diario_Web.py (Código FINAL com Lógica Premium e Login)

import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import datetime
import os 
# --- NOVAS IMPORTAÇÕES PARA POSTGRESQL ---
from sqlalchemy import create_engine
import psycopg2

# =========================================================================
# 1. CONFIGURAÇÃO DE CONEXÃO E CONSTANTES
# =========================================================================

# URL EXTERNA COMPLETA DO SEU BANCO DE DADOS RENDER (USADA NO Streamlit)
RENDER_DB_URL = "postgresql://diario_db_render_user:JVoTQlm0QaJC3l75fja0s7tLdxwQw5Zr@dpg-d4srpc63jp1c73eovq50-a.virginia-postgres.render.com/diario_db_render"

# Link do Checkout do Mercado Pago (USADO NO BOTÃO DE UPGRADE)
MP_CHECKOUT_LINK = "https://mpago.la/19wM16s" 

CORTE_FREQUENCIA = 75
NOTA_APROVACAO_DIRETA = 7.0
NOTA_MINIMA_P3 = 4.0
NOTA_MINIMA_FINAL = 5.0
DB_NAME = 'diario_de_classe.db'

diario_de_classe = {
    "Alice": {},  
    "Bruno": {},
    "Carol": {},
}

# =========================================================================
# 2. FUNÇÕES DE CONEXÃO COM O RENDER (POSTGRESQL)
# =========================================================================

@st.cache_resource
def get_db_engine():
    """Cria e armazena o motor de conexão do Render (PostgreSQL) para reutilização."""
    return create_engine(RENDER_DB_URL)

def verificar_acesso_premium(email_usuario):
    """Consulta o banco de dados do Render para verificar o status premium do usuário."""
    engine = get_db_engine()
    select_query = f"SELECT acesso_premium FROM professores WHERE email = '{email_usuario}'"
    
    try:
        df = pd.read_sql_query(select_query, engine)
        
        if not df.empty:
            return df['acesso_premium'].iloc[0] 
        else:
            return False 
            
    except Exception as e:
        st.sidebar.error(f"⚠️ Erro no BD. Status Básico Ativo.")
        return False

# =========================================================================
# 3. FUNÇÕES DE LÓGICA E BD (SQLite) - SUAS FUNÇÕES ORIGINAIS
# =========================================================================

@st.cache_resource
def criar_e_popular_sqlite():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS Frequencia")
    cursor.execute("DROP TABLE IF EXISTS Notas")
    cursor.execute("DROP TABLE IF EXISTS Aulas")
    cursor.execute("DROP TABLE IF EXISTS Alunos")
    cursor.execute("DROP TABLE IF EXISTS Disciplinas")
    cursor.execute("DROP TABLE IF EXISTS Turmas")
    conn.commit()
     
    cursor.execute('''CREATE TABLE Alunos (id_aluno INTEGER PRIMARY KEY, nome TEXT NOT NULL, matricula TEXT UNIQUE NOT NULL);''')
    cursor.execute('''CREATE TABLE Disciplinas (id_disciplina INTEGER PRIMARY KEY, nome_disciplina TEXT UNIQUE NOT NULL);''')
    cursor.execute('''CREATE TABLE Turmas (id_turma INTEGER PRIMARY KEY, nome_turma TEXT NOT NULL, ano_letivo INTEGER NOT NULL);''')
    cursor.execute('''CREATE TABLE Aulas (id_aula INTEGER PRIMARY KEY, id_turma INTEGER, id_disciplina INTEGER, data_aula DATE NOT NULL, conteudo_lecionado TEXT, FOREIGN KEY (id_turma) REFERENCES Turmas(id_turma), FOREIGN KEY (id_disciplina) REFERENCES Disciplinas(id_disciplina));''')
    cursor.execute('''CREATE TABLE Notas (id_nota INTEGER PRIMARY KEY, id_aluno INTEGER, id_disciplina INTEGER, tipo_avaliacao TEXT NOT NULL, valor_nota REAL NOT NULL, UNIQUE(id_aluno, id_disciplina, tipo_avaliacao), FOREIGN KEY (id_aluno) REFERENCES Alunos(id_aluno), FOREIGN KEY (id_disciplina) REFERENCES Disciplinas(id_disciplina));''')
    cursor.execute('''CREATE TABLE Frequencia (id_frequencia INTEGER PRIMARY KEY, id_aula INTEGER, id_aluno INTEGER, presente BOOLEAN NOT NULL, UNIQUE(id_aula, id_aluno), FOREIGN KEY (id_aula) REFERENCES Aulas(id_aula), FOREIGN KEY (id_aluno) REFERENCES Alunos(id_aluno));''')
    conn.commit()

    aluno_map = {}; disciplina_map = {}; id_turma_padrao = 1
    cursor.execute("REPLACE INTO Turmas (id_turma, nome_turma, ano_letivo) VALUES (?, ?, ?)", (id_turma_padrao, "Exemplo 2025/1", 2025))
    
    disciplinas_list = ["Língua Portuguesa", "Matemática", "Ciências", "História", "Geografia", "Artes"]
    for i, disc in enumerate(disciplinas_list): 
        cursor.execute("REPLACE INTO Disciplinas (id_disciplina, nome_disciplina) VALUES (?, ?)", (i+1, disc))
    cursor.execute("SELECT id_disciplina, nome_disciplina FROM Disciplinas")
    for id_disc, nome_disc in cursor.fetchall(): 
        disciplina_map[nome_disc] = id_disc
    
    alunos_list = list(diario_de_classe.keys())
    for i, aluno in enumerate(alunos_list): 
        cursor.execute("REPLACE INTO Alunos (id_aluno, nome, matricula) VALUES (?, ?, ?)", (i+1, aluno, f"MAT{2025000 + i + 1}"))
    cursor.execute("SELECT id_aluno, nome FROM Alunos")
    for id_aluno, nome_aluno in cursor.fetchall(): 
        aluno_map[nome_aluno] = id_aluno

    conn.commit()
    conn.close()
    return aluno_map, disciplina_map

def calcular_media_final(avaliacoes):
    p1_val = avaliacoes.get("P1"); p2_val = avaliacoes.get("P2"); p3_val = avaliacoes.get("P3")
    
    p1 = float(p1_val) if pd.notna(p1_val) and p1_val is not None else 0.0
    p2 = float(p2_val) if pd.notna(p2_val) and p2_val is not None else 0.0
    
    p3 = None
    if p3_val is not None and pd.notna(p3_val): p3 = float(p3_val)
    
    media_parcial = (p1 + p2) / 2
    nota_final = media_parcial
    situacao_nota = ""
    
    if media_parcial >= NOTA_APROVACAO_DIRETA:
        situacao_nota = "APROVADO POR MÉDIA"
    elif media_parcial >= NOTA_MINIMA_P3:
        if p3 is None: situacao_nota = "PENDENTE (AGUARDANDO P3)"
        else:
            media_final_com_p3 = (media_parcial + p3) / 2
            nota_final = media_final_com_p3
            if nota_final >= NOTA_MINIMA_FINAL: situacao_nota = "APROVADO APÓS P3"
            else: situacao_nota = "REPROVADO POR NOTA"
    else: situacao_nota = "REPROVADO DIRETO"
    
    return nota_final, situacao_nota, media_parcial

def lancar_aula_e_frequencia(id_disciplina, data_aula, conteudo):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    id_turma_padrao = 1
    try:
        cursor.execute("""INSERT INTO Aulas (id_turma, id_disciplina, data_aula, conteudo_lecionado) VALUES (?, ?, ?, ?)""", (id_turma_padrao, id_disciplina, data_aula, conteudo))
        conn.commit()
        id_aula = cursor.lastrowid
        
        cursor.execute("SELECT id_aluno FROM Alunos")
        alunos_ids = [row[0] for row in cursor.fetchall()]
        
        if not alunos_ids:
            st.warning("⚠️ Alunos não encontrados no DB. Por favor, recarregue a página.")
            return

        registros_frequencia = [(id_aula, id_aluno, 1) for id_aluno in alunos_ids]
        cursor.executemany("""INSERT INTO Frequencia (id_aula, id_aluno, presente) VALUES (?, ?, ?)""", registros_frequencia)
        conn.commit()
        st.success(f"✅ Aula de {conteudo} em {data_aula} lançada (ID: {id_aula}). Todos marcados como Presentes.")
    except Exception as e:
        st.error(f"❌ Erro ao lançar aula: {e}")
    finally:
        conn.close()

def inserir_nota_no_db(id_aluno, id_disciplina, tipo_avaliacao, valor_nota):
    if valor_nota is None or valor_nota < 0 or valor_nota > 10.0:
        st.warning("⚠️ Erro: Insira um valor de nota válido (0.0 a 10.0).")
        return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""REPLACE INTO Notas (id_aluno, id_disciplina, tipo_avaliacao, valor_nota) VALUES (?, ?, ?, ?)""", (id_aluno, id_disciplina, tipo_avaliacao, valor_nota))
        conn.commit()
        st.success(f"✅ Nota {tipo_avaliacao} ({valor_nota:.1f}) inserida/atualizada.")
    except Exception as e:
        st.error(f"❌ Erro ao inserir nota: {e}")
    finally: conn.close()

def obter_frequencia_por_aula(id_disciplina, data_aula):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    id_turma_padrao = 1
    cursor.execute("""
        SELECT id_aula FROM Aulas WHERE id_turma = ? AND id_disciplina = ? AND data_aula = ?
    """, (id_turma_padrao, id_disciplina, data_aula)) 
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return None, "Aula não encontrada para essa data/disciplina."
        
    id_aula = result[0]
    df = pd.read_sql_query(f"""
        SELECT 
            A.nome AS "Aluno", 
            F.id_frequencia,
            F.presente 
        FROM Frequencia F
        JOIN Alunos A ON F.id_aluno = A.id_aluno
        WHERE F.id_aula = {id_aula}
        ORDER BY A.nome;
    """, conn)
    conn.close()
    
    if df.empty:
        return None, f"Nenhum registro de frequência encontrado para a Aula ID: {id_aula}."
        
    df['Status Atual'] = df['presente'].apply(lambda x: 'PRESENTE ✅' if x == 1 else 'FALTA 🚫')
    df['Opção'] = df['id_frequencia'].astype(str) + ' - ' + df['Aluno']
    return df, id_aula


def atualizar_status_frequencia(id_frequencia, novo_status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Frequencia SET presente = ? WHERE id_frequencia = ?
        """, (novo_status, id_frequencia))
        conn.commit()
        st.success(f"✅ Status de Presença Atualizado! (ID Frequência: {id_frequencia})")
    except Exception as e:
        st.error(f"❌ Erro ao atualizar frequência: {e}")
    finally:
        conn.close()

def gerar_relatorio_final_completo(): 
    try:
        conn = sqlite3.connect(DB_NAME)
        query_sql_completa = """
        SELECT A.nome AS "Aluno", D.nome_disciplina AS "Disciplina", 
            MAX(CASE WHEN N.tipo_avaliacao = 'P1' THEN N.valor_nota ELSE NULL END) AS "P1",
            MAX(CASE WHEN N.tipo_avaliacao = 'P2' THEN N.valor_nota ELSE NULL END) AS "P2",
            MAX(CASE WHEN N.tipo_avaliacao = 'P3' THEN N.valor_nota ELSE NULL END) AS "P3",
            COUNT(CASE WHEN F.presente = 1 THEN 1 ELSE NULL END) AS "Total_Presencas",
            COUNT(AU.id_aula) AS "Total_Aulas"
        FROM Alunos A CROSS JOIN Disciplinas D 
        LEFT JOIN Notas N ON A.id_aluno = N.id_aluno AND D.id_disciplina = N.id_disciplina
        LEFT JOIN Aulas AU ON D.id_disciplina = AU.id_disciplina
        LEFT JOIN Frequencia F ON A.id_aluno = F.id_aluno AND AU.id_aula = F.id_aula
        GROUP BY A.nome, D.nome_disciplina;
        """
        df_relatorio = pd.read_sql_query(query_sql_completa, conn)

    except Exception as e:
        st.error(f"❌ ERRO FATAL na consulta SQL/Pandas. Verifique a estrutura do DB. Mensagem: {e}")
        return

    if df_relatorio.empty:
        st.info("Nenhum dado de aluno/disciplina encontrado no DB para o relatório. Verifique a inicialização.")
        return None

    resultados_finais = []
    for index, row in df_relatorio.iterrows():
        total_aulas = row['Total_Aulas'] or 0; total_presencas = row['Total_Presencas'] or 0
        frequencia_percentual = (total_presencas / total_aulas * 100) if total_aulas > 0 else 0
        
        avaliacoes = {"P1": row.get('P1'), "P2": row.get('P2'), "P3": row.get('P3')}
        
        nota_final, situacao_nota, media_parcial = calcular_media_final(avaliacoes)
        situacao_frequencia = "REPROVADO POR FALTA" if frequencia_percentual < CORTE_FREQUENCIA else "APROVADO POR FREQUÊNCIA"

        if situacao_frequencia.startswith("REPROVADO") or situacao_nota.startswith("REPROVADO"):
            situacao_final = "REPROVADO GERAL 🔴"
        elif situacao_nota.startswith("PENDENTE"):
            situacao_final = "PENDENTE ⚠️"
        else:
            situacao_final = "APROVADO GERAL 🟢"

        resultados_finais.append({
            "Aluno": row['Aluno'], "Disciplina": row['Disciplina'],
            "P1": f"{row['P1']:.1f}" if pd.notna(row['P1']) else '-',
            "P2": f"{row['P2']:.1f}" if pd.notna(row['P2']) else '-',
            "P3": f"{row['P3']:.1f}" if pd.notna(row['P3']) else '-',
            "Frequência (%)": f"{frequencia_percentual:.1f}",
            "Nota Final": f"{nota_final:.1f}",
            "Situação Final": situacao_final
        })

    if not resultados_finais: st.info("Nenhum dado encontrado para o relatório.")
    
    st.markdown("### Relatório Final Consolidado")
    df_final = pd.DataFrame(resultados_finais)
    st.dataframe(df_final.set_index(["Aluno", "Disciplina"]), use_container_width=True)
    
    return df_final


# =========================================================================
# 4. FUNÇÃO PRINCIPAL DO STREAMLIT (Interface)
# =========================================================================

def main():
    # 1. CONFIGURAÇÃO DA PÁGINA
    st.set_page_config(layout="wide") 
    st.title("👨‍🏫 Diário de Classe Interativo") 
    st.markdown("---") 

    # ----------------------------------------
    # CONTAS COM ACESSO TOTAL (ILIMITADO - O SEU AMBIENTE)
    ADMIN_USER = "demonstracao" 
    ADMIN_PASS = "Teste2026"
    
    # CONTAS COM ACESSO RESTRITO (LIMITADO - AMBIENTE DO CLIENTE DE VENDAS)
    USUARIOS_RESTRITOS = {
        "demo_aluno_a": "Senha123", 
        "demo_coord_b": "Senha123",
        "cliente_teste": "Senha1234" 
    }
    # ----------------------------------------

    st.sidebar.title("Login")
    username = st.sidebar.text_input("Usuário")
    password = st.sidebar.text_input("Senha", type="password") 

    # Inicializa o estado de login e o novo flag de restrição
    if 'user_login_name' not in st.session_state:
        st.session_state['user_login_name'] = None 
    if 'is_restricted' not in st.session_state:
        st.session_state['is_restricted'] = None 

    # =========================================================================
    # 5. PORTÃO DE LOGIN MÚLTIPLO E ARMAZENAMENTO DA SESSÃO 
    # =========================================================================
    
    login_successful = False
    
    # 1. TENTA LOGIN ILIMITADO (DONO/ADMIN)
    if username == ADMIN_USER and password == ADMIN_PASS:
        st.session_state.user_login_name = username
        st.session_state.is_restricted = False # ILIMITADO
        login_successful = True
    
    # 2. TENTA LOGIN RESTRITO (DEMO)
    elif username in USUARIOS_RESTRITOS and password == USUARIOS_RESTRITOS[username]:
        st.session_state.user_login_name = username
        st.session_state.is_restricted = True # LIMITADO
        login_successful = True
    
    # 3. LÓGICA DE LOGIN BEM-SUCEDIDO
    if login_successful:
        usuario_logado = st.session_state.user_login_name 
        st.sidebar.success(f"Login bem-sucedido! Bem-vindo, {usuario_logado}.")
        
        # ** LÓGICA DE PREMIUM (INJETADA AQUI) **
        if st.session_state.user_login_name == ADMIN_USER: # APENAS PARA O ADMIN
            st.session_state['email_admin'] = 'professormarcoscarneirofaetec@gmail.com' 
            
            email_logado = st.session_state['email_admin']
            is_premium = verificar_acesso_premium(email_logado)
            
            st.sidebar.markdown("---")
            st.sidebar.header("Status da Conta Premium")
            
            if is_premium:
                st.sidebar.success("✅ Você é Premium! Todos os recursos liberados.")
            else:
                st.sidebar.warning("🔒 Acesso Básico. Faça Upgrade para liberar tudo.")
                
                # Botão de Upgrade (HTML formatado)
                st.sidebar.markdown(
                    f"""
                    <a href="{MP_CHECKOUT_LINK}" target="_blank">
                        <button style="background-color: #009ee3; color: white; padding: 10px 20px; border-radius: 5px; border: none; font-weight: bold;">
                            Fazer Upgrade para Premium!
                        </button>
                    </a>
                    """,
                    unsafe_allow_html=True
                )
        # ------------------------------------------

        # APLICAÇÃO DA LIMITAÇÃO DE USO (AVISO LATERAL) 
        if st.session_state.is_restricted:
            st.sidebar.warning("⚠️ **Aviso Demo:** A modificação de dados existentes está bloqueada.")
            st.sidebar.info("Apenas a criação e visualização são permitidas.")
            
        # 1. INICIALIZAÇÃO DO DB e Persistência
        aluno_map_nome, disciplina_map_nome = criar_e_popular_sqlite()
        
        aluno_map_id = {v: k for k, v in aluno_map_nome.items()}
        disciplina_map_id = {v: k for k, v in disciplina_map_nome.items()}

        # -------------------------------------------------------------------------
        # 1. Lançamento de Aulas e Frequência (CRIAÇÃO LIBERADA PARA TODOS)
        # -------------------------------------------------------------------------
        st.header("🗓️ 1. Lançamento de Aulas (Liberado)")
        with st.form("form_aulas"):
            col1, col2, col3 = st.columns(3)
            
            disciplina_aula_nome = col1.selectbox('Disciplina', options=list(disciplina_map_nome.keys()))
            data_input = col2.date_input('Data', value=datetime.date.today())
            conteudo = col3.text_input('Conteúdo da Aula')
            
            id_disciplina = disciplina_map_nome.get(disciplina_aula_nome)

            submitted_aula = st.form_submit_button("Lançar Aula e Marcar Todos Presentes")
            
            if submitted_aula:
                lancar_aula_e_frequencia(id_disciplina, data_input.strftime("%Y-%m-%d"), conteudo)
                st.rerun() 

        # -------------------------------------------------------------------------
        # 2. Painel de Chamada (Ajuste de Faltas - BLOQUEIO CONDICIONAL)
        # -------------------------------------------------------------------------
        st.header("📋 2. Ajuste de Faltas Pontuais")
        
        col1, col2 = st.columns(2)
        disciplina_chamada_nome = col1.selectbox('Disciplina (Ajuste)', options=list(disciplina_map_nome.keys()), key="sel_disc_chamada")
        data_consulta = col2.date_input('Data da Aula (Ajuste)', value=datetime.date.today(), key="data_chamada")
        
        id_disciplina_chamada = disciplina_map_nome.get(disciplina_chamada_nome)
        
        if st.button("Carregar Chamada da Aula"):
            df_frequencia_atual, id_aula_ou_erro = obter_frequencia_por_aula(id_disciplina_chamada, data_consulta.strftime("%Y-%m-%d"))
            
            if isinstance(df_frequencia_atual, pd.DataFrame):
                st.session_state['df_chamada'] = df_frequencia_atual
                st.session_state['id_aula'] = id_aula_ou_erro
                st.session_state['msg_chamada'] = f"✅ Chamada Carregada (Aula ID: {id_aula_ou_erro})"
            else:
                st.session_state['df_chamada'] = None
                st.session_state['msg_chamada'] = f"❌ ERRO: {id_aula_ou_erro}" 

        if 'msg_chamada' in st.session_state:
            st.markdown(st.session_state['msg_chamada'])
            if st.session_state['df_chamada'] is not None and not st.session_state['df_chamada'].empty:
                st.dataframe(st.session_state['df_chamada'][['Aluno', 'Status Atual']], hide_index=True)
                st.markdown("---")

                st.subheader("Alterar Status (Falta/Presença)")
                
                df_chamada = st.session_state['df_chamada']
                opcoes_ajuste = {row['Aluno']: row['id_frequencia'] for index, row in df_chamada.iterrows()}
                col_aluno, col_status = st.columns([2, 1])

                aluno_ajuste = col_aluno.selectbox('Aluno para Ajuste', options=list(opcoes_ajuste.keys()))
                novo_status_label = col_status.selectbox('Novo Status', options=['PRESENTE', 'FALTA'])

                # --- BLOQUEIO CONDICIONAL (AGORA SÓ VERIFICA SE ESTÁ RESTRITO) ---
                if st.button("Salvar Alteração de Frequência"):
                    
                    if st.session_state.is_restricted: # VERIFICA O NOVO FLAG DE RESTRIÇÃO
                        st.error("❌ A alteração de frequência está bloqueada nesta conta de demonstração (modifica dados existentes).")
                        
                    else:
                        # Código de execução para a conta ADMIN (ILIMITADA)
                        id_frequencia_registro = opcoes_ajuste[aluno_ajuste]
                        novo_status = 1 if novo_status_label == 'PRESENTE' else 0
                        
                        atualizar_status_frequencia(id_frequencia_registro, novo_status)
                        st.info("✅ Atualização salva. Recarregue a chamada para confirmar.")
                        st.rerun()

                if st.session_state.is_restricted:
                    st.markdown("⚠️ **Aviso:** Este botão está desabilitado para contas de demonstração.")
        
        # -------------------------------------------------------------------------
        # 3. Lançamento de Notas (CRIAÇÃO LIBERADA PARA TODOS)
        # -------------------------------------------------------------------------
        st.header("🖊️ 3. Lançamento de Notas (Liberado)")
        with st.form("form_notas"):
            col1, col2, col3, col4 = st.columns(4)
            
            aluno_nome = col1.selectbox('Aluno(a)', options=list(aluno_map_nome.keys()))
            disciplina_nome = col2.selectbox('Disciplina (Nota)', options=list(disciplina_map_nome.keys()), key="disc_nota")
            tipo_avaliacao = col3.selectbox('Avaliação', options=['P1', 'P2', 'P3'])
            valor_nota = col4.number_input('Nota (0-10)', min_value=0.0, max_value=10.0, step=0.5, value=7.0)
            
            id_aluno = aluno_map_nome.get(aluno_nome)
            id_disciplina = disciplina_map_nome.get(disciplina_nome)

            submitted_nota = st.form_submit_button("Inserir/Atualizar Nota")

            if submitted_nota:
                inserir_nota_no_db(id_aluno, id_disciplina, tipo_avaliacao, valor_nota)
                st.rerun()

        st.markdown("---")

        # -------------------------------------------------------------------------
        # 4. Relatório Consolidado (VISUALIZAÇÃO LIBERADA PARA TODOS)
        # -------------------------------------------------------------------------
        st.header("📊 Relatório Consolidado")
        
        df_relatorio_final = gerar_relatorio_final_completo()
        
        if df_relatorio_final is not None and not df_relatorio_final.empty:
            st.markdown("---")
            col_csv, col_spacer = st.columns([1, 4]) 
            
            csv_data = df_relatorio_final.to_csv(index=False).encode('utf-8')
            col_csv.download_button(
                label="⬇️ Gerar Conteúdo (CSV)",
                data=csv_data,
                file_name=f'Relatorio_Diario_Classe_{datetime.date.today()}.csv',
                mime='text/csv',
                key='download_csv'
            )
            
    # -------------------------------------------------------------------------
    # 6. LÓGICA DE FALHA DE LOGIN
    # -------------------------------------------------------------------------
    else:
        if username or password: 
            st.sidebar.error("Usuário ou senha incorretos.")
        
        st.info("Insira seu nome de usuário e senha na barra lateral para acessar o Diário de Classe.")
        return 
        
    st.markdown("---") 

if __name__ == "__main__":
    main()