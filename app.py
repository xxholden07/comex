import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import os

# Page config
st.set_page_config(
    page_title="Indovinya Comex Dashboard",
    page_icon="🌐",
    layout="wide"
)

# Branding CSS
st.markdown(
    """
    <style>
    .reportview-container, .main { background-color: #f8f9fa; }
    .sidebar .sidebar-content { background-image: linear-gradient(180deg, #004990 0%, #61be64 100%); color: white; }
    .stButton>button { background-color: #61be64; color: white; border-radius: .25em; }
    #MainMenu, footer { visibility: hidden; }
    """,
    unsafe_allow_html=True
)

# Configure DB path
DB_PATH = st.sidebar.text_input("Caminho para o SQLite DB", value="cnpj.db")
IMPORT_TABLE = 'IMPORTACOES_TEST_FULL_202506131448'
ENRICH_TABLE = 'Consulta_enriquecida'

# DB helpers
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def available_tables():
    try:
        with get_conn() as conn:
            return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")]
    except:
        return []

def cols_for(table):
    with get_conn() as conn:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table});")]

def execute_query(query, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)

# Main application
def main():
    st.title("📊 Indovinya Comex Dashboard")
    menu = ["Visão Geral", "Importações", "Enriquecida", "Busca CNPJ", "Dashboard", "Consulta", "Exportar"]
    choice = st.sidebar.radio("Menu", menu)
    tables = available_tables()
    if choice != "Visão Geral" and not tables:
        st.error("Nenhuma tabela carregada. Vá em Visão Geral para importar dados.")
        return

    if choice == "Visão Geral":
        overview()
    elif choice == "Importações":
        analyze_import()
    elif choice == "Enriquecida":
        show_enriched()
    elif choice == "Busca CNPJ":
        search_cnpj()
    elif choice == "Dashboard":
        show_dashboard()
    elif choice == "Consulta":
        custom_query()
    else:
        export_data()

# 1. Visão Geral

def overview():
    st.header("🗄️ Visão Geral")
    st.write("Banco:", os.path.abspath(DB_PATH))
    tables = available_tables()
    if tables:
        st.write(f"Tabelas ({len(tables)}): {tables}")
        for t in tables:
            with st.expander(t):
                st.write(cols_for(t))
    else:
        st.info("Nenhuma tabela. Envie CSV/JSON/HTML abaixo:")
    uploaded = st.file_uploader("Arquivos (.csv .json .html)", type=['csv','json','html'], accept_multiple_files=True)
    if uploaded:
        conn = get_conn()
        for f in uploaded:
            name, ext = os.path.splitext(f.name)
            try:
                if ext == '.csv':
                    df = pd.read_csv(f, engine='python', on_bad_lines='skip')
                elif ext == '.json':
                    df = pd.read_json(f, orient='records')
                else:
                    df = pd.read_html(f)[0]
                df.to_sql(name, conn, if_exists='replace', index=False)
                st.write(f"Tabela '{name}' carregada ({len(df)} linhas)")
            except Exception as e:
                st.error(f"Erro ao processar {f.name}: {e}")
        conn.close()
        st.success("Dados importados. Recarregue para visualizar.")

# 2. Importações

def analyze_import():
    st.header("📈 Análise de Importações")
    if IMPORT_TABLE not in available_tables():
        st.error(f"Tabela '{IMPORT_TABLE}' não encontrada.")
        return
    # filtros
    df = execute_query(f"SELECT DISTINCT ANO_MES FROM {IMPORT_TABLE};")
    ano = st.selectbox("ANO_MES", sorted(df['ANO_MES']))
    df_year = execute_query(f"SELECT * FROM {IMPORT_TABLE} WHERE ANO_MES = ?;", params=(ano,))
    numeric = [c for c in df_year.columns if pd.api.types.is_numeric_dtype(df_year[c])]
    sel = st.multiselect("Métricas", numeric, default=numeric[:3])
    if sel:
        for c in sel:
            fig = px.line(df_year, x='MES', y=c, title=f"{c} por mês ({ano})")
            st.plotly_chart(fig, use_container_width=True)

# 3. Enriquecida

def show_enriched():
    st.header("🔍 Dados Enriquecidos")
    if ENRICH_TABLE not in available_tables():
        st.error(f"Tabela '{ENRICH_TABLE}' não encontrada.")
        return
    df = execute_query(f"SELECT * FROM {ENRICH_TABLE} LIMIT 100;")
    st.dataframe(df)
    if st.checkbox("Mostrar estatísticas", False):
        st.write(df.describe(include='all'))

# 4. Busca por CNPJ

def search_cnpj():
    st.header("🔎 Busca por CNPJ")
    cnpj = st.text_input("CNPJ (8 dígitos):")
    if not cnpj:
        return
    if ENRICH_TABLE in available_tables():
        df = execute_query(f"SELECT * FROM {ENRICH_TABLE} WHERE PROVAVEL_IMPORTADOR_CNPJ LIKE ?;", params=(f"%{cnpj}%",))
        if df.empty:
            st.error("CNPJ não encontrado na tabela enriquecida.")
        else:
            st.dataframe(df)
    else:
        st.error("Tabela enriquecida não disponível.")

# 5. Dashboard

def show_dashboard():
    st.header("📊 Dashboard Geral")
    if IMPORT_TABLE not in available_tables():
        st.error(f"Tabela '{IMPORT_TABLE}' não disponível.")
        return
    df = execute_query(f"SELECT SG_UF AS UF, SUM(VALOR_FOB_ESTIMADO_TOTAL) AS TotalFOB FROM {IMPORT_TABLE} GROUP BY SG_UF;")
    st.bar_chart(df.set_index('UF'))

# 6. Consulta SQL

def custom_query():
    st.header("🔧 Consulta Personalizada")
    q = st.text_area("Digite SQL:")
    if st.button("Executar") and q.strip():
        try:
            df = execute_query(q)
            st.dataframe(df)
        except Exception as e:
            st.error(f"Erro na consulta: {e}")

# 7. Exportar

def export_data():
    st.header("📤 Exportar Dados")
    tables = available_tables()
    tbl = st.selectbox("Tabela", tables)
    if tbl:
        df = execute_query(f"SELECT * FROM {tbl};")
        st.download_button("Download CSV", df.to_csv(index=False), file_name=f"{tbl}.csv")

if __name__ == '__main__':
    main()
