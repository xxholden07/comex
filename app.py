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

# Database helpers
def get_db_connection(path=DB_PATH):
    return sqlite3.connect(path, check_same_thread=False)

def get_available_tables(path=DB_PATH):
    try:
        conn = get_db_connection(path)
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")]
        conn.close()
        return tables
    except Exception:
        return []

def get_table_columns(table, path=DB_PATH):
    conn = get_db_connection(path)
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table});")]
    conn.close()
    return cols

def execute_query(query, conn, params=()):
    df = pd.read_sql_query(query, conn, params=params)
    return df

# Main application

def main():
    st.title("📊 Indovinya Comex Dashboard")
    choice = st.sidebar.radio("Menu", ["Visão Geral", "Busca CNPJ", "Análise", "Dashboard", "Consulta", "Exportar"])
    tables = get_available_tables()
    if choice != "Visão Geral" and not tables:
        st.error("Nenhuma tabela no banco. Carregue arquivos em Visão Geral.")
        return

    if choice == "Visão Geral":
        show_db_overview()
    elif choice == "Busca CNPJ":
        show_cnpj_search()
    elif choice == "Análise":
        show_import_analysis()
    elif choice == "Dashboard":
        show_dashboard()
    elif choice == "Consulta":
        show_custom_query()
    elif choice == "Exportar":
        show_export()

# 1. Visão Geral with continuous uploader

def show_db_overview():
    st.header("🗄️ Visão Geral do Banco")
    st.write("Arquivo:", os.path.abspath(DB_PATH))
    tables = get_available_tables()
    if tables:
        st.success(f"Tabelas ({len(tables)}): {tables}")
        for tbl in tables:
            with st.expander(f"Tabela: {tbl}"):
                st.write(get_table_columns(tbl))
        st.markdown("---")
        st.info("Envie mais arquivos para adicionar tabelas:")
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
                    try:
                        df = pd.read_csv(file, sep=';', engine='python', on_bad_lines='skip')
                    except Exception:
                        df = pd.read_csv(file, sep=',', engine='python', on_bad_lines='skip')
                elif ext.lower() == '.json':
                    df = pd.read_json(file, orient='records')
                elif ext.lower() == '.html':
                    df = pd.read_html(file)[0]
                else:
                    continue
                df.to_sql(name, conn, if_exists='replace', index=False)
                st.write(f"Tabela '{name}' criada/atualizada: {len(df)} linhas")
            except Exception as e:
                st.error(f"Erro ao processar {file.name}: {e}")
        conn.close()
        st.success("Reconstrução concluída. Recarregue a página para visualizar as tabelas.")

# 2. Busca por CNPJ

def show_cnpj_search():
    st.header("🔍 Busca por CNPJ")
    cnpj = st.text_input("Digite o CNPJ (apenas números):")
    if not cnpj:
        return
    conn = get_db_connection()
    query = (
        "SELECT e.*, est.* FROM Empresas e "
        "LEFT JOIN Estabelecimentos est ON e.cnpj_basico = est.cnpj_basico "
        "WHERE e.cnpj_basico = ?"
    )
    df = execute_query(query, conn, params=(cnpj[:8],))
    conn.close()
    if df.empty:
        st.error("CNPJ não encontrado.")
    else:
        st.success(f"Empresa: {df['razao_social'].iloc[0]}")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**CNPJ:** {cnpj}")
            st.write(f"**Capital Social:** R$ {df['capital_social'].iloc[0]:,.2f}")
        with col2:
            st.write(f"**Endereço:** {df['logradouro'].iloc[0]}, {df['numero'].iloc[0]}")
            st.write(f"**Cidade/UF:** {df['municipio'].iloc[0]}/{df['uf'].iloc[0]}")

# 3. Análise de Importações

def show_import_analysis():
    st.header("📈 Análise de Importações")
    conn = get_db_connection()
    anos = pd.read_sql_query("SELECT DISTINCT CO_ANO FROM Importacao;", conn)['CO_ANO']
    ufs = pd.read_sql_query("SELECT DISTINCT SG_UF FROM Importacao;", conn)['SG_UF']
    conn.close()
    ano = st.selectbox("Ano", sorted(anos))
    uf = st.selectbox("UF", sorted(ufs))
    cols = get_table_columns('Importacao')
    default = [c for c in ['VL_FOB','KG_LIQUIDO','QT_ESTAT'] if c in cols]
    sel = st.multiselect("Colunas", cols, default=default)
    if sel:
        conn = get_db_connection()
        df = pd.read_sql_query(
            f"SELECT CO_MES, {', '.join(sel)} FROM Importacao WHERE CO_ANO=? AND SG_UF=?;", conn,
            params=(ano, uf)
        )
        conn.close()
        if df.empty:
            st.warning("Sem dados para esses filtros.")
        else:
            for c in sel:
                st.plotly_chart(px.line(df, x='CO_MES', y=c, title=f"{c} por mês"))

# 4. Dashboard Geral

def show_dashboard():
    st.header("📊 Dashboard")
    conn = get_db_connection()
    cols = get_table_columns('Importacao')
    conn.close()
    default = [c for c in ['VL_FOB','KG_LIQUIDO'] if c in cols]
    sel = st.multiselect("Colunas", cols, default=default)
    if sel:
        conn = get_db_connection()
        expr = ", ".join([f"SUM({c}) as {c}" for c in sel])
        df_est = pd.read_sql_query(f"SELECT SG_UF, {expr} FROM Importacao GROUP BY SG_UF ORDER BY {sel[0]} DESC LIMIT 5;", conn)
        df_mes = pd.read_sql_query(f"SELECT CO_MES, {expr} FROM Importacao GROUP BY CO_MES ORDER BY CO_MES;", conn)
        conn.close()
        for c in sel:
            st.plotly_chart(px.bar(df_est, x='SG_UF', y=c, title=f"Top 5 Estados por {c}"))
            st.plotly_chart(px.line(df_mes, x='CO_MES', y=c, title=f"{c} por mês"))

# 5. Consulta Personalizada

def show_custom_query():
    st.header("🔍 Consulta Personalizada")
    q = st.text_area("Digite SQL:")
    if st.button("Executar") and q.strip():
        conn = get_db_connection()
        df = pd.read_sql_query(q, conn)
        conn.close()
        st.dataframe(df)

# 6. Exportar Dados

def show_export():
    st.header("📤 Exportar Dados")
    tables = get_available_tables()
    tbl = st.selectbox("Tabela", tables)
    if tbl:
        conn = get_db_connection()
        cols = get_table_columns(tbl)
        df = pd.read_sql_query(f"SELECT * FROM {tbl};", conn)
        conn.close()
        st.dataframe(df)

if __name__ == '__main__':
    main()
