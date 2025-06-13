import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import os

# Git LFS Setup Instructions:
# 1. Inicialize o repositório Git (se ainda não estiver):
#    git init
#    git remote add origin https://github.com/xxholden07/comex.git
# 2. Instale e habilite o Git LFS:
#    git lfs install
# 3. Adicione o arquivo cnpj.db ao LFS:
#    git lfs track "cnpj.db"
#    git add .gitattributes cnpj.db
#    git commit -m "Track cnpj.db with Git LFS"
# 4. Verifique o remote:
#    git remote -v
#    (Se precisar alterar: git remote set-url origin https://github.com/xxholden07/comex.git)
# 5. Faça push para a branch principal:
#    git push -u origin master  # ou main, conforme sua branch padrão

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

# Sidebar input for DB path (when running locally)
db_path = st.sidebar.text_input("Caminho para o arquivo SQLite DB (se aplicável)", value="cnpj.db")
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
    
    # For non-overview pages, ensure DB loaded
    tables = get_available_tables()
    if choice != "Visão Geral do Banco" and not tables:
        st.error("Nenhuma tabela encontrada. Carregue o banco na visão geral, via upload em múltiplos arquivos se necessário.")
        return

    if choice == "Visão Geral do Banco":
        show_db_overview()
    elif choice == "Busca por CNPJ":
        show_cnpj_search()
    elif choice == "Análise de Importações":
        show_import_analysis()
    elif choice == "Dashboard":
        show_dashboard()
    elif choice == "Consulta Personalizada":
        show_custom_query()
    else:
        show_export()

# 1. DB Overview with multi-file uploader or CSV uploader

def show_db_overview():
    st.header("🗄️ Visão Geral do Banco de Dados")
    st.write("Arquivo atual de DB:", os.path.abspath(DB_PATH))
    tables = get_available_tables()
    if tables:
        st.success(f"Tabelas disponíveis ({len(tables)}):")
        st.write(tables)
        for tbl in tables:
            with st.expander(f"Colunas de {tbl}"):
                st.write(get_table_columns(tbl))
    else:
        st.info(f"Nenhuma tabela encontrada em '{DB_PATH}'.")
        st.markdown("**Reconstrua o banco a partir de seus arquivos de exportação:**")
        # JSON and HTML uploader
        uploaded_files = st.file_uploader(
            "Envie arquivos JSON, HTML ou CSV para reconstruir o banco SQLite", 
            type=['csv','json','html'], accept_multiple_files=True
        )
        if uploaded_files:
            conn = sqlite3.connect(DB_PATH)
            for file in uploaded_files:
                name, ext = os.path.splitext(file.name)
                try:
                    if ext.lower() == '.csv':
                        df = pd.read_csv(file, sep=';') if ';' in file.getvalue().decode('utf-8', errors='ignore') else pd.read_csv(file)
                    elif ext.lower() == '.json':
                        df = pd.read_json(file, orient='records')
                    elif ext.lower() == '.html':
                        tables_html = pd.read_html(file)
                        df = tables_html[0] if tables_html else pd.DataFrame()
                    else:
                        st.warning(f"Formato não suportado: {file.name}")
                        continue
                    df.to_sql(name, conn, if_exists='replace', index=False)
                    st.write(f"Tabela '{name}' criada com {len(df)} linhas.")
                except Exception as e:
                    st.error(f"Erro ao processar {file.name}: {e}")
            conn.close()
            st.success("Banco reconstruído com sucesso! Recarregue a página para visualizar as tabelas.")
        else:
            st.warning("Envie pelo menos um arquivo JSON ou HTML de exportação para reconstruir.")
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
        # Build query
        q = f"SELECT {', '.join(sel)} FROM {tbl}"
        # Filters
        filter_cols = st.multiselect("Filtros", sel)
        clauses = []
        for f in filter_cols:
            v = st.text_input(f"Valor para {f}")
            if v:
                clauses.append(f"{f} LIKE '%{v}%'")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        # Execute
        conn = get_db_connection()
        df = pd.read_sql_query(q, conn)
        conn.close()
        # Show and downloads
        st.dataframe(df)
        csv_data = df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv_data, file_name=f"{tbl}.csv", mime="text/csv")
        # JSON export
        json_data = df.to_json(orient='records')
        st.download_button("📥 Download JSON", json_data, file_name=f"{tbl}.json", mime="application/json")
        # HTML export
        html_data = df.to_html(index=False)
        st.download_button("📥 Download HTML", html_data, file_name=f"{tbl}.html", mime="text/html")

if __name__ == "__main__":
    main()
