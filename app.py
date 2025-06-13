import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import io
import os

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="Sistema Comex",
    page_icon="📊",
    layout="wide"
)

# Database connection with thread safety
def get_db_connection():
    return sqlite3.connect('cnpj.db', check_same_thread=False)

# Helper functions
def format_cnpj(cnpj):
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj

def format_currency(value):
    return f"R$ {value:,.2f}"

def get_table_columns(table_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    conn.close()
    return columns

def get_available_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [table[0] for table in cursor.fetchall()]
    conn.close()
    return tables

def execute_query(query, params=None):
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn, params=params or ())
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

def download_csv(df):
    return df.to_csv(index=False)

# Main app
def main():
    # Debug: show working directory and files
    st.write("Diretório atual:", os.getcwd())
    st.write("Arquivos aqui:", os.listdir())

    st.title("📊 Sistema de Análise Comex")
    
    # Sidebar
    st.sidebar.title("Menu")
    page = st.sidebar.radio(
        "Selecione uma opção:",
        ["Busca por CNPJ", "Análise de Importações", "Dashboard", "Consulta Personalizada", "Exportação de Dados"]
    )
    
    if page == "Busca por CNPJ":
        show_cnpj_search()
    elif page == "Análise de Importações":
        show_import_analysis()
    elif page == "Dashboard":
        show_dashboard()
    elif page == "Consulta Personalizada":
        show_custom_query()
    else:
        show_export()

# 1. Busca por CNPJ
def show_cnpj_search():
    st.header("🔍 Busca por CNPJ")
    cnpj = st.text_input("Digite o CNPJ (apenas números):")
    if cnpj:
        conn = get_db_connection()
        query = (
            "SELECT e.*, est.* "
            "FROM Empresas e "
            "LEFT JOIN Estabelecimentos est ON e.cnpj_basico = est.cnpj_basico "
            "WHERE e.cnpj_basico = ?"
        )
        df = pd.read_sql_query(query, conn, params=(cnpj[:8],))
        conn.close()
        if not df.empty:
            st.success(f"Empresa encontrada: {df['razao_social'].iloc[0]}")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Informações Básicas")
                st.write(f"**Razão Social:** {df['razao_social'].iloc[0]}")
                st.write(f"**CNPJ:** {format_cnpj(cnpj)}")
                st.write(f"**Capital Social:** {format_currency(df['capital_social'].iloc[0])}")
            with col2:
                st.subheader("Endereço")
                st.write(f"**Logradouro:** {df['logradouro'].iloc[0]}, {df['numero'].iloc[0]}")
                st.write(f"**Bairro:** {df['bairro'].iloc[0]}")
                st.write(f"**Cidade/UF:** {df['municipio'].iloc[0]}/{df['uf'].iloc[0]}")
                st.write(f"**CEP:** {df['cep'].iloc[0]}")
            csv = download_csv(df)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"empresa_{cnpj}.csv",
                mime="text/csv"
            )
        else:
            st.error("CNPJ não encontrado na base de dados.")

# 2. Análise de Importações
def show_import_analysis():
    st.header("📈 Análise de Importações")
    conn = get_db_connection()
    # Show available tables for debug
    # st.write("Tabelas disponíveis:", get_available_tables())
    col1, col2 = st.columns(2)
    with col1:
        anos = pd.read_sql_query("SELECT DISTINCT CO_ANO FROM Importacao", conn)
        ano = st.selectbox("Selecione o ano:", sorted(anos['CO_ANO'].tolist()))
    with col2:
        ufs = pd.read_sql_query("SELECT DISTINCT SG_UF FROM Importacao", conn)
        uf = st.selectbox("Selecione a UF:", sorted(ufs['SG_UF'].tolist()))
    available_columns = get_table_columns('Importacao')
    selected_columns = st.multiselect(
        "Selecione as colunas para análise:",
        available_columns,
        default=['VL_FOB', 'KG_LIQUIDO', 'QT_ESTAT']
    )
    if selected_columns:
        cols_str = ", ".join(selected_columns)
        query = (
            f"SELECT CO_ANO, CO_MES, {cols_str} "
            "FROM Importacao "
            "WHERE CO_ANO = ? AND SG_UF = ?"
        )
        df = pd.read_sql_query(query, conn, params=(ano, uf))
        conn.close()
        if not df.empty:
            for col in selected_columns:
                fig = px.line(
                    df,
                    x='CO_MES',
                    y=col,
                    title=f'{col} por Mês - {uf} ({ano})',
                    labels={'CO_MES': 'Mês', col: col}
                )
                st.plotly_chart(fig, use_container_width=True)
            csv = download_csv(df)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"importacoes_{uf}_{ano}.csv",
                mime="text/csv"
            )

# 3. Dashboard Geral
def show_dashboard():
    st.header("📊 Dashboard Geral")
    conn = get_db_connection()
    available_columns = get_table_columns('Importacao')
    selected_columns = st.multiselect(
        "Selecione as colunas para análise:",
        available_columns,
        default=['VL_FOB', 'KG_LIQUIDO']
    )
    if selected_columns:
        cols_sum = ", ".join([f"SUM({col}) as {col}" for col in selected_columns])
        query_est = (
            f"SELECT SG_UF, {cols_sum} "
            "FROM Importacao "
            f"GROUP BY SG_UF ORDER BY SUM({selected_columns[0]}) DESC LIMIT 5"
        )
        df_est = pd.read_sql_query(query_est, conn)
        for col in selected_columns:
            fig_e = px.bar(
                df_est,
                x='SG_UF',
                y=col,
                title=f'Top 5 Estados por {col}',
                labels={'SG_UF': 'Estado', col: col}
            )
            st.plotly_chart(fig_e, use_container_width=True)
        cols_mes = cols_sum
        query_mes = (
            f"SELECT CO_MES, {cols_sum} "
            "FROM Importacao GROUP BY CO_MES ORDER BY CO_MES"
        )
        df_mes = pd.read_sql_query(query_mes, conn)
        conn.close()
        for col in selected_columns:
            fig_m = px.line(
                df_mes,
                x='CO_MES',
                y=col,
                title=f'Distribuição de {col} por Mês',
                labels={'CO_MES': 'Mês', col: col}
            )
            st.plotly_chart(fig_m, use_container_width=True)
        # Downloads
        st.download_button("📥 Download Top 5 Estados", download_csv(df_est), file_name="top5_estados.csv")
        st.download_button("📥 Download Distribuição Mensal", download_csv(df_mes), file_name="distribuicao_mensal.csv")

# 4. Consulta Personalizada
def show_custom_query():
    st.header("🔍 Consulta Personalizada")
    query = st.text_area("Digite sua consulta SQL:", height=150)
    if st.button("Executar Consulta"):
        if query:
            df, error = execute_query(query)
            if error:
                st.error(f"Erro na consulta: {error}")
            else:
                st.success(f"Consulta executada com sucesso! {len(df)} linhas encontradas.")
                st.dataframe(df)
                if not df.empty:
                    st.download_button("📥 Download CSV", download_csv(df), file_name="consulta_resultado.csv")

# 5. Exportação de Dados
def show_export():
    st.header("📤 Exportação de Dados")
    tables = get_available_tables()
    selected_table = st.selectbox("Selecione a tabela:", tables)
    if selected_table:
        columns = get_table_columns(selected_table)
        selected_columns = st.multiselect("Selecione as colunas:", columns, default=columns[:5])
        if selected_columns:
            cols_str = ", ".join(selected_columns)
            query = f"SELECT {cols_str} FROM {selected_table}"
            st.subheader("Filtros")
            filters = []
            for col in st.multiselect("Selecione colunas para filtrar:", selected_columns):
                val = st.text_input(f"Valor para {col}:")
                if val:
                    filters.append(f"{col} LIKE '%{val}%'" )
            if filters:
                query += " WHERE " + " AND ".join(filters)
            if st.button("Exportar Dados"):
                df, error = execute_query(query)
                if error:
                    st.error(f"Erro na consulta: {error}")
                else:
                    st.success(f"Dados exportados com sucesso! {len(df)} linhas encontradas.")
                    st.dataframe(df)
                    st.download_button("📥 Download CSV", download_csv(df), file_name=f"{selected_table}_export.csv")

if __name__ == "__main__":
    main()
