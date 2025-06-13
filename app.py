import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import io
import os
st.write("Diretório atual:", os.getcwd())
st.write("Arquivos aqui:", os.listdir())


# Page config
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

def execute_query(query):
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

def download_csv(df):
    csv = df.to_csv(index=False)
    return csv

# Main app
def main():
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

def show_custom_query():
    st.header("🔍 Consulta Personalizada")
    
    # Query input
    query = st.text_area("Digite sua consulta SQL:", height=150)
    
    if st.button("Executar Consulta"):
        if query:
            df, error = execute_query(query)
            if error:
                st.error(f"Erro na consulta: {error}")
            else:
                st.success(f"Consulta executada com sucesso! {len(df)} linhas encontradas.")
                st.dataframe(df)
                
                # Export options
                if not df.empty:
                    csv = download_csv(df)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name="consulta_resultado.csv",
                        mime="text/csv"
                    )

def show_export():
    st.header("📤 Exportação de Dados")
    
    # Table selection
    tables = get_available_tables()
    selected_table = st.selectbox("Selecione a tabela:", tables)
    
    if selected_table:
        # Column selection
        columns = get_table_columns(selected_table)
        selected_columns = st.multiselect(
            "Selecione as colunas:",
            columns,
            default=columns[:5] if len(columns) > 5 else columns
        )
        
        if selected_columns:
            # Build query
            columns_str = ", ".join(selected_columns)
            query = f"SELECT {columns_str} FROM {selected_table}"
            
            # Add filters
            st.subheader("Filtros")
            filter_cols = st.multiselect("Selecione colunas para filtrar:", selected_columns)
            
            where_clauses = []
            for col in filter_cols:
                filter_value = st.text_input(f"Valor para {col}:")
                if filter_value:
                    where_clauses.append(f"{col} LIKE '%{filter_value}%'")
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            # Execute query
            if st.button("Exportar Dados"):
                df, error = execute_query(query)
                if error:
                    st.error(f"Erro na consulta: {error}")
                else:
                    st.success(f"Dados exportados com sucesso! {len(df)} linhas encontradas.")
                    st.dataframe(df)
                    
                    # Download button
                    csv = download_csv(df)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"{selected_table}_export.csv",
                        mime="text/csv"
                    )

def show_cnpj_search():
    st.header("🔍 Busca por CNPJ")
    
    cnpj = st.text_input("Digite o CNPJ (apenas números):")
    
    if cnpj:
        conn = get_db_connection()
        
        # Busca empresa
        query = """
        SELECT e.*, est.* 
        FROM Empresas e 
        LEFT JOIN Estabelecimentos est ON e.cnpj_basico = est.cnpj_basico 
        WHERE e.cnpj_basico = ?
        """
        
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
            
            # Export option
            csv = download_csv(df)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"empresa_{cnpj}.csv",
                mime="text/csv"
            )
        else:
            st.error("CNPJ não encontrado na base de dados.")

def show_import_analysis():
    st.header("📈 Análise de Importações")
    
    conn = get_db_connection()
    
    # Filtros
    col1, col2 = st.columns(2)
    
    with col1:
        ano = st.selectbox(
            "Selecione o ano:",
            options=sorted(pd.read_sql_query("SELECT DISTINCT CO_ANO FROM Importacao", conn)['CO_ANO'].tolist())
        )
    
    with col2:
        uf = st.selectbox(
            "Selecione a UF:",
            options=sorted(pd.read_sql_query("SELECT DISTINCT SG_UF FROM Importacao", conn)['SG_UF'].tolist())
        )
    
    # Column selection for visualization
    available_columns = get_table_columns('Importacao')
    selected_columns = st.multiselect(
        "Selecione as colunas para análise:",
        available_columns,
        default=['VL_FOB', 'KG_LIQUIDO', 'QT_ESTAT']
    )
    
    if selected_columns:
        # Query para dados filtrados
        columns_str = ", ".join(selected_columns)
        query = f"""
        SELECT 
            CO_ANO,
            CO_MES,
            {columns_str}
        FROM Importacao
        WHERE CO_ANO = ? AND SG_UF = ?
        """
        
        df = pd.read_sql_query(query, conn, params=(ano, uf))
        conn.close()
        
        if not df.empty:
            # Gráficos para cada coluna selecionada
            for col in selected_columns:
                fig = px.line(
                    df,
                    x='CO_MES',
                    y=col,
                    title=f'{col} por Mês - {uf} ({ano})',
                    labels={'CO_MES': 'Mês', col: col}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Export option
            csv = download_csv(df)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"importacoes_{uf}_{ano}.csv",
                mime="text/csv"
            )

def show_dashboard():
    st.header("📊 Dashboard Geral")
    
    conn = get_db_connection()
    
    # Column selection for visualization
    available_columns = get_table_columns('Importacao')
    selected_columns = st.multiselect(
        "Selecione as colunas para análise:",
        available_columns,
        default=['VL_FOB', 'KG_LIQUIDO']
    )
    
    if selected_columns:
        # Top 5 estados por valor de importação
        columns_str = ", ".join([f"SUM({col}) as {col}" for col in selected_columns])
        query = f"""
        SELECT 
            SG_UF,
            {columns_str}
        FROM Importacao
        GROUP BY SG_UF
        ORDER BY SUM({selected_columns[0]}) DESC
        LIMIT 5
        """
        
        df_estados = pd.read_sql_query(query, conn)
        
        # Gráfico de barras para top 5 estados
        for col in selected_columns:
            fig_estados = px.bar(
                df_estados,
                x='SG_UF',
                y=col,
                title=f'Top 5 Estados por {col}',
                labels={'SG_UF': 'Estado', col: col}
            )
            st.plotly_chart(fig_estados, use_container_width=True)
        
        # Distribuição por mês
        query_mes = f"""
        SELECT 
            CO_MES,
            {columns_str}
        FROM Importacao
        GROUP BY CO_MES
        ORDER BY CO_MES
        """
        
        df_mes = pd.read_sql_query(query_mes, conn)
        conn.close()
        
        for col in selected_columns:
            fig_mes = px.line(
                df_mes,
                x='CO_MES',
                y=col,
                title=f'Distribuição de {col} por Mês',
                labels={'CO_MES': 'Mês', col: col}
            )
            st.plotly_chart(fig_mes, use_container_width=True)
        
        # Export options
        csv_estados = download_csv(df_estados)
        st.download_button(
            label="📥 Download Top 5 Estados",
            data=csv_estados,
            file_name="top5_estados.csv",
            mime="text/csv"
        )
        
        csv_mes = download_csv(df_mes)
        st.download_button(
            label="📥 Download Distribuição Mensal",
            data=csv_mes,
            file_name="distribuicao_mensal.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main() 
