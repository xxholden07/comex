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

# Allow user to specify the DB path (for large local files)
db_path = st.sidebar.text_input("Caminho para o arquivo SQLite DB", value="cnpj.db")
DB_PATH = db_path

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

# Main application
def main():
    st.title("📊 Sistema de Análise Comex - Indovinya")
    st.sidebar.title("Menu")
    pages = ["Visão Geral do Banco", "Busca por CNPJ", "Análise de Importações", "Dashboard", "Consulta Personalizada", "Exportação de Dados"]
    choice = st.sidebar.radio("Selecione uma opção:", pages)

    # Load available tables once
    tables = get_available_tables()

    if choice == "Visão Geral do Banco":
        show_db_overview()
    else:
        if not tables:
            st.error("Nenhuma tabela encontrada. Verifique se o caminho está correto e se o arquivo existe.")
            return
        if choice == "Busca por CNPJ":
            show_cnpj_search()
        elif choice == "Análise de Importações":
            show_import_analysis()
        elif choice == "Dashboard":
            show_dashboard()
        elif choice == "Consulta Personalizada":
            show_custom_query()
        elif choice == "Exportação de Dados":
            show_export()

# 1. DB Overview

def show_db_overview():
    st.header("🗄️ Visão Geral do Banco de Dados")
    st.write("Arquivo atual de DB:", os.path.abspath(DB_PATH))
    tables = get_available_tables()
    if not tables:
        st.error("Nenhuma tabela encontrada em '" + DB_PATH + "'.")
        return
    st.write(f"Tabelas disponíveis ({len(tables)}):", tables)
    for tbl in tables:
        with st.expander(f"Colunas de {tbl}"):
            st.write(get_table_columns(tbl))

# 2. Busca por CNPJ

def show_cnpj_search():
    st.header("🔍 Busca por CNPJ")
    cnpj = st.text_input("Digite o CNPJ (apenas números):")
    if not cnpj:
        return
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT e.*, est.* FROM Empresas e LEFT JOIN Estabelecimentos est ON e.cnpj_basico = est.cnpj_basico WHERE e.cnpj_basico = ?;",
        conn, params=(cnpj[:8],)
    )
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
        st.download_button("📥 Download CSV", df.to_csv(index=False), file_name=f"empresa_{cnpj}.csv")

# 3. Análise de Importações

def show_import_analysis():
    st.header("📈 Análise de Importações")
    if 'Importacao' not in get_available_tables():
        st.error("Tabela 'Importacao' não encontrada.")
        return
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
            st.download_button("📥 CSV", df.to_csv(index=False), file_name=f"imp_{uf}_{ano}.csv")

# 4. Dashboard

def show_dashboard():
    st.header("📊 Dashboard Geral")
    if 'Importacao' not in get_available_tables():
        st.error("Tabela 'Importacao' não encontrada.")
        return
    conn = get_db_connection()
    cols = get_table_columns('Importacao')
    conn.close()
    default = [c for c in ['VL_FOB','KG_LIQUIDO'] if c in cols]
    sel = st.multiselect("Colunas", cols, default=default)
    if sel:
        conn = get_db_connection()
        sum_expr = ", ".join([f"SUM({c}) as {c}" for c in sel])
        df_e = pd.read_sql_query(f"SELECT SG_UF, {sum_expr} FROM Importacao GROUP BY SG_UF ORDER BY {sel[0]} DESC LIMIT 5;", conn)
        df_m = pd.read_sql_query(f"SELECT CO_MES, {sum_expr} FROM Importacao GROUP BY CO_MES ORDER BY CO_MES;", conn)
        conn.close()
        for c in sel:
            st.plotly_chart(px.bar(df_e, x='SG_UF', y=c, title=f"Top 5 Estados por {c}"))
            st.plotly_chart(px.line(df_m, x='CO_MES', y=c, title=f"Distribuição mensal de {c}"))
        st.download_button("📥 Estados", df_e.to_csv(index=False), file_name="top5.csv")
        st.download_button("📥 Mes", df_m.to_csv(index=False), file_name="mes.csv")

# 5. Consulta Personalizada

def show_custom_query():
    st.header("🔍 Consulta Personalizada")
    q = st.text_area("SQL:")
    if st.button("Executar"):
        if q.strip():
            conn = get_db_connection()
            df = pd.read_sql_query(q, conn)
            conn.close()
            st.dataframe(df)
            st.download_button("CSV", df.to_csv(index=False), file_name="query.csv")

# 6. Exportação
def show_export():
    st.header("📤 Exportação de Dados")
    tables = get_available_tables()
    tbl = st.selectbox("Tabela", tables)
    if tbl:
        cols = get_table_columns(tbl)
        sel = st.multiselect("Colunas", cols, default=cols[:5])
        q = f"SELECT {', '.join(sel)} FROM {tbl}"
        if filters := st.multiselect("Filtros", sel):
            clauses=[]
            for f in filters:
                v=st.text_input(f"Valor para {f}")
                if v: clauses.append(f"{f} LIKE '%{v}%'" )
            if clauses: q+= " WHERE " + " AND ".join(clauses)
        conn = get_db_connection()
        df = pd.read_sql_query(q, conn)
        conn.close()
        st.dataframe(df)
        st.download_button("CSV", df.to_csv(index=False), file_name=f"{tbl}.csv")

if __name__ == "__main__":
    main()
