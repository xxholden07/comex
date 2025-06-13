import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import os

# Page config must be first
st.set_page_config(
    page_title="Indovinya Comex Dashboard",
    page_icon="🌐",
    layout="wide"
)

# Custom CSS for branding
st.markdown(
    """
    <style>
    .reportview-container, .main { background-color: #f8f9fa; }
    .sidebar .sidebar-content { background-image: linear-gradient(180deg, #004990 0%, #61be64 100%); color: white; }
    .css-12oz5g7 h1 { color: #004990; }
    .stButton>button { background-color: #61be64; color: white; border-radius: .25em; }
    #MainMenu, footer { visibility: hidden; }
    """,
    unsafe_allow_html=True
)

# Sidebar for DB path
DB_PATH = st.sidebar.text_input("Caminho para o SQLite DB", value="cnpj.db")

# DB helpers
def get_db_connection(path=DB_PATH): return sqlite3.connect(path, check_same_thread=False)
def get_available_tables(path=DB_PATH):
    try:
        conn = get_db_connection(path)
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")]
        conn.close()
        return tables
    except:
        return []
def get_table_columns(table, path=DB_PATH):
    conn = get_db_connection(path)
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table});")]
    conn.close()
    return cols

# Main
def main():
    st.title("📊 Indovinya Comex Dashboard")
    choice = st.sidebar.radio("Menu", ["Visão Geral", "Busca CNPJ", "Análise", "Dashboard", "Consulta", "Exportar"])
    tables = get_available_tables()
    if choice != "Visão Geral" and not tables:
        st.error("Nenhuma tabela: vá em Visão Geral para carregar arquivos.")
        return
    if choice == "Visão Geral": show_db_overview()
    # ... restante das páginas permanece igual ...

# 1. Visão Geral com uploader contínuo
def show_db_overview():
    st.header("🗄️ Visão Geral do Banco")
    st.write("Arquivo:", os.path.abspath(DB_PATH))
    tables = get_available_tables()
    if tables:
        st.success(f"Tabelas ({len(tables)}): {tables}")
        for tbl in tables:
            with st.expander(tbl):
                st.write(get_table_columns(tbl))
        # Offer additional uploads
        st.markdown("---")
        st.info("Envie mais arquivos para adicionar novas tabelas:")
    else:
        st.info("Nenhuma tabela encontrada. Envie arquivos abaixo:")
    uploaded = st.file_uploader(
        "Arquivos CSV/JSON/HTML", type=['csv','json','html'], accept_multiple_files=True
    )
    if uploaded:
        conn = sqlite3.connect(DB_PATH)
        for file in uploaded:
            name, ext = os.path.splitext(file.name)
            try:
                if ext.lower() == '.csv':
                        # Tenta ler CSV com diferentes delimitadores e ignora linhas ruins
                        try:
                            df = pd.read_csv(file, sep=';', engine='python', on_bad_lines='skip')
                        except Exception:
                            df = pd.read_csv(file, sep=',', engine='python', on_bad_lines='skip')
                elif ext.lower() == '.json': df = pd.read_json(file)
                elif ext.lower() == '.html': df = pd.read_html(file)[0]
                else: continue
                df.to_sql(name, conn, if_exists='replace', index=False)
                st.write(f"Criou/atualizou tabela '{name}' ({len(df)} linhas)")
            except Exception as e:
                st.error(f"Erro {file.name}: {e}")
        conn.close()
        st.success("Operação concluída! Recarregue para ver tabelas.")

if __name__ == '__main__':
    main()
