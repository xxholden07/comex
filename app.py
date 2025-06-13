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

# DB helpers
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def available_tables():
    try:
        with get_conn() as conn:
            return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")]
    except:
        return []

def get_df(table, query=None, params=()):
    with get_conn() as conn:
        if query:
            return pd.read_sql_query(query, conn, params=params)
        return pd.read_sql_query(f"SELECT * FROM {table};", conn)

# Main application
def main():
    st.title("📊 Indovinya Comex Dashboard")
    menu = ["Visão Geral", "Métricas Dinâmicas", "Consulta", "Exportar"]
    choice = st.sidebar.radio("Menu", menu)
    tables = available_tables()

    if choice != "Visão Geral" and not tables:
        st.error("Nenhuma tabela carregada. Vá em Visão Geral para importar dados.")
        return

    if choice == "Visão Geral":
        overview(tables)
    elif choice == "Métricas Dinâmicas":
        dynamic_metrics(tables)
    elif choice == "Consulta":
        custom_query()
    else:
        export_data(tables)

# 1. Visão Geral

def overview(tables):
    st.header("🗄️ Visão Geral")
    st.write("Banco:", os.path.abspath(DB_PATH))
    if tables:
        st.write(f"Tabelas ({len(tables)}): {tables}")
        for t in tables:
            with st.expander(t):
                cols = [r[1] for r in get_conn().execute(f"PRAGMA table_info({t});")]
                st.write(cols)
    else:
        st.info("Nenhuma tabela. Envie CSV/JSON/HTML abaixo:")
        uploaded = st.file_uploader("Arquivos (.csv .json .html)", type=['csv','json','html'], accept_multiple_files=True)
        if uploaded:
            conn = get_conn()
            for f in uploaded:
                name, ext = os.path.splitext(f.name)
                try:
                    if ext == '.csv': df = pd.read_csv(f, engine='python', on_bad_lines='skip')
                    elif ext == '.json': df = pd.read_json(f, orient='records')
                    else: df = pd.read_html(f)[0]
                    df.to_sql(name, conn, if_exists='replace', index=False)
                    st.write(f"Tabela '{name}' carregada ({len(df)} linhas)")
                except Exception as e:
                    st.error(f"Erro em {f.name}: {e}")
            conn.close()
            st.success("Dados importados. Recarregue para visualizar.")

# 2. Métricas Dinâmicas (ambas tabelas)

def dynamic_metrics(tables):
    st.header("📈 Métricas Dinâmicas")
    table = st.selectbox("Selecione a tabela", tables)
    if not table:
        return
    df = get_df(table)
    # Select numeric columns
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    cols = st.multiselect("Selecione métricas", numeric, default=numeric[:3])
    if cols:
        # Group by selection dimension
        dim = st.selectbox("Agrupar por", [None] + [c for c in df.columns if df[c].dtype == object])
        if st.button("Atualizar gráficos"):
            if dim:
                for metric in cols:
                    grouped = df.groupby(dim)[metric].sum().reset_index()
                    fig = px.bar(grouped, x=dim, y=metric, title=f"{metric} por {dim}")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                # Time series if exists a date or month column
                time_cols = [c for c in df.columns if 'MES' in c or 'MONTH' in c or 'DATA' in c.upper()]
                if time_cols:
                    time = st.selectbox("Eixo tempo (opcional)", [None] + time_cols)
                    if time:
                        for metric in cols:
                            ts = df.groupby(time)[metric].sum().reset_index()
                            fig = px.line(ts, x=time, y=metric, title=f"{metric} ao longo de {time}")
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Não há coluna temporal para séries.")

# 3. Consulta SQL

def custom_query():
    st.header("🔧 Consulta Personalizada")
    q = st.text_area("Digite SQL:")
    if st.button("Executar") and q.strip():
        try:
            df = execute_query(q)
            st.dataframe(df)
        except Exception as e:
            st.error(f"Erro na consulta: {e}")

# 4. Exportar

def export_data(tables):
    st.header("📤 Exportar Dados")
    tbl = st.selectbox("Tabela", tables)
    if tbl:
        df = get_df(tbl)
        st.download_button("Download CSV", df.to_csv(index=False), file_name=f"{tbl}.csv")

if __name__ == '__main__':
    main()
