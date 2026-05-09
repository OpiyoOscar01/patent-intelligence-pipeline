#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
dashboard.py
Streamlit dashboard for interactive patent analytics.
Run: streamlit run dashboard.py
"""

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

DB_PATH = Path("patents.db")

st.set_page_config(page_title="Patent Intelligence Dashboard", layout="wide")
st.title("📊 Global Patent Intelligence Dashboard")
st.markdown("**Author:** Opiyo Oscar (2300701330) – Makerere University | Cloud Computing & Big Data Analytics")


def chunked_query(conn, query, ids, id_column_name, chunk_size=500):
    """
    Execute a query with an IN clause by splitting IDs into chunks.
    
    Args:
        conn: SQLite connection
        query: SQL query with {placeholders} placeholder
        ids: List/tuple of IDs to filter on
        id_column_name: Name of the ID column (unused but kept for clarity)
        chunk_size: Number of IDs per chunk
    
    Returns:
        DataFrame with combined results from all chunks
    """
    if not ids:
        return pd.DataFrame()
    
    ids_list = list(ids)
    chunks = [ids_list[i:i + chunk_size] for i in range(0, len(ids_list), chunk_size)]
    
    all_dfs = []
    for chunk in chunks:
        placeholders = ','.join(['?'] * len(chunk))
        chunk_query = query.format(placeholders=placeholders)
        chunk_df = pd.read_sql_query(chunk_query, conn, params=chunk)
        all_dfs.append(chunk_df)
    
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()


@st.cache_resource
def load_data(limit_records):
    """Load minimal data from SQLite with configurable record limit."""
    conn = sqlite3.connect(DB_PATH)
    
    # Limit to configurable number of patents
    patents = pd.read_sql_query(
        f"SELECT patent_id, year FROM patents WHERE year IS NOT NULL LIMIT {limit_records}", 
        conn
    )
    
    # Get the patent IDs from the limited patents
    patent_ids = patents["patent_id"].tolist()
    
    # If there are no patents, return empty dataframes
    if not patent_ids:
        conn.close()
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Use chunked queries to avoid parameter limit issues
    # Inventor counts per patent (only for limited patents)
    inv_rel = chunked_query(
        conn,
        "SELECT patent_id, inventor_id FROM patent_relationships WHERE patent_id IN ({placeholders})",
        patent_ids,
        "patent_id",
        chunk_size=500
    )
    
    # Assignee links (only for limited patents)
    ass_rel = chunked_query(
        conn,
        "SELECT patent_id, company_id FROM patent_relationships WHERE patent_id IN ({placeholders}) AND company_id IS NOT NULL",
        patent_ids,
        "patent_id",
        chunk_size=500
    )
    
    # Get inventor IDs from filtered relationships
    inventor_ids = inv_rel["inventor_id"].unique().tolist() if not inv_rel.empty else []
    
    if inventor_ids:
        inventors = chunked_query(
            conn,
            "SELECT inventor_id, name, country FROM inventors WHERE inventor_id IN ({placeholders})",
            inventor_ids,
            "inventor_id",
            chunk_size=500
        )
    else:
        inventors = pd.DataFrame()
    
    # Get company IDs from filtered relationships
    company_ids = ass_rel["company_id"].unique().tolist() if not ass_rel.empty else []
    
    if company_ids:
        companies = chunked_query(
            conn,
            "SELECT company_id, name FROM companies WHERE company_id IN ({placeholders})",
            company_ids,
            "company_id",
            chunk_size=500
        )
    else:
        companies = pd.DataFrame()
    
    conn.close()
    return patents, inv_rel, ass_rel, inventors, companies


def get_total_patent_count():
    """Get total number of patents in the database."""
    conn = sqlite3.connect(DB_PATH)
    count = pd.read_sql_query("SELECT COUNT(*) as count FROM patents WHERE year IS NOT NULL", conn)
    conn.close()
    return count.iloc[0]['count']


def main():
    if not DB_PATH.exists():
        st.error("Database not found. Please run `python store.py` first.")
        return

    # Sidebar filters
    st.sidebar.header("Data Loading Configuration")
    
    # Get total available patents
    total_patents = get_total_patent_count()
    
    # Configurable record limit - reduced options for better performance
    record_options = [100, 500, 1000, 2000, 5000, 10000]
    # Filter options to not exceed total patents
    record_options = [x for x in record_options if x <= total_patents]
    
    # Add total patents as an option if it's not already included
    if total_patents not in record_options and total_patents > 10000:
        record_options.append(total_patents)
    
    # Remove duplicates and sort
    record_options = sorted(set(record_options))
    
    default_limit = 100 if 100 in record_options else record_options[0] if record_options else 100
    
    limit_records = st.sidebar.selectbox(
        "📦 Number of records to load from database",
        options=record_options,
        index=record_options.index(default_limit) if default_limit in record_options else 0,
        help=f"Total patents available in database: {total_patents:,}\nNote: Loading more than 10,000 records may impact performance"
    )
    
    # Show database info
    st.sidebar.info(f"📊 Database contains {total_patents:,} total patents")
    
    # Warning for large loads
    if limit_records > 10000:
        st.sidebar.warning("⚠️ Loading many records may cause slow performance. Consider using a smaller limit for faster interaction.")
    
    # Load data with selected limit
    with st.spinner(f"Loading {limit_records:,} patents from database..."):
        patents, inv_rel, ass_rel, inventors, companies = load_data(limit_records)
    
    # Check if data was loaded
    if patents.empty:
        st.warning("No patents found in the database. Please run `python store.py` first.")
        return

    st.success(f"✅ Successfully loaded {len(patents):,} patents with related data")
    
    # Sidebar filters for analysis
    st.sidebar.header("Analysis Filters")
    
    # Fixed year range slider with proper handling for single year
    min_year = int(patents["year"].min())
    max_year = int(patents["year"].max())
    
    # Handle case where min_year equals max_year
    if min_year == max_year:
        st.sidebar.info(f"ℹ️ Data only available for year {min_year}")
        year_range = (min_year, max_year)
        # Don't show slider, just show the year as text
        st.sidebar.markdown(f"**Year:** {min_year}")
    else:
        year_range = st.sidebar.slider(
            "📅 Year range", 
            min_value=min_year, 
            max_value=max_year, 
            value=(min_year, max_year)
        )
    
    # Top N configuration for different categories
    st.sidebar.subheader("📊 Display Configuration")
    
    top_n_inventors = st.sidebar.selectbox(
        "👥 Top N Inventors to display",
        options=[5, 10, 15, 20, 25, 30, 50],
        index=1,
        help="Number of top inventors to show in chart"
    )
    
    top_n_companies = st.sidebar.selectbox(
        "🏢 Top N Companies to display",
        options=[5, 10, 15, 20, 25, 30, 50],
        index=1,
        help="Number of top companies to show in chart"
    )
    
    top_n_countries = st.sidebar.selectbox(
        "🌍 Top N Countries to display",
        options=[5, 10, 15, 20, 25, 30, 50],
        index=1,
        help="Number of top countries to show in chart"
    )

    # Filter patents by year
    if min_year == max_year:
        filtered_patents = patents
    else:
        mask = (patents["year"] >= year_range[0]) & (patents["year"] <= year_range[1])
        filtered_patents = patents[mask]
    
    filtered_patent_ids = set(filtered_patents["patent_id"])

    # Prepare inventor counts within filtered patents
    inv_filtered = inv_rel[inv_rel["patent_id"].isin(filtered_patent_ids)]
    if not inv_filtered.empty and not inventors.empty:
        inv_counts = inv_filtered.groupby("inventor_id").size().reset_index(name="patent_count")
        inv_counts = inv_counts.merge(inventors, on="inventor_id")
        inv_counts = inv_counts.sort_values("patent_count", ascending=False).head(top_n_inventors)
    else:
        inv_counts = pd.DataFrame()

    # Prepare company counts
    ass_filtered = ass_rel[ass_rel["patent_id"].isin(filtered_patent_ids)]
    if not ass_filtered.empty and not companies.empty:
        company_counts = ass_filtered.groupby("company_id").size().reset_index(name="patent_count")
        company_counts = company_counts.merge(companies, on="company_id")
        company_counts = company_counts.sort_values("patent_count", ascending=False).head(top_n_companies)
    else:
        company_counts = pd.DataFrame()

    # Yearly trend for filtered range
    yearly = filtered_patents.groupby("year").size().reset_index(name="patent_count")

    # Country trends
    if not inv_filtered.empty and not inventors.empty:
        inv_with_country = inv_filtered.merge(inventors[["inventor_id", "country"]], on="inventor_id")
        country_counts = inv_with_country.groupby("country").size().reset_index(name="patent_count")
        country_counts = country_counts.sort_values("patent_count", ascending=False).head(top_n_countries)
    else:
        country_counts = pd.DataFrame()

    # Row 1: Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Loaded Patents", f"{len(patents):,}")
    with col2:
        st.metric("🔍 Filtered Patents", f"{len(filtered_patents):,}")
    with col3:
        st.metric("👨‍🔬 Unique Inventors", f"{inv_filtered['inventor_id'].nunique() if not inv_filtered.empty else 0:,}")
    with col4:
        st.metric("🏭 Unique Companies", f"{ass_filtered['company_id'].nunique() if not ass_filtered.empty else 0:,}")

    # Progress information
    if min_year == max_year:
        st.info(f"📈 Showing data for {len(filtered_patents):,} patents from year {min_year}")
    else:
        st.info(f"📈 Showing data for {len(filtered_patents):,} patents in year range {year_range[0]}–{year_range[1]}")

    # Create two columns for charts
    col_left, col_right = st.columns(2)

    # Row 2: Top Inventors (left column)
    with col_left:
        if not inv_counts.empty:
            st.subheader(f"🏆 Top {top_n_inventors} Inventors")
            fig1, ax1 = plt.subplots(figsize=(10, 6))
            bars = ax1.barh(inv_counts["name"], inv_counts["patent_count"], color="skyblue")
            ax1.set_xlabel("Patent Count", fontsize=12)
            ax1.set_title(f"Top {top_n_inventors} Inventors (Based on {len(patents):,} loaded patents)", fontsize=14)
            ax1.invert_yaxis()
            
            # Add value labels
            for bar, val in zip(bars, inv_counts["patent_count"]):
                ax1.text(val, bar.get_y() + bar.get_height()/2, f' {val}', 
                        va='center', fontweight='bold', fontsize=10)
            
            plt.tight_layout()
            st.pyplot(fig1)
        else:
            st.info("No inventor data available for the selected filters.")

    # Row 3: Top Companies (right column)
    with col_right:
        if not company_counts.empty:
            st.subheader(f"🏢 Top {top_n_companies} Companies")
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            bars = ax2.barh(company_counts["name"], company_counts["patent_count"], color="lightgreen")
            ax2.set_xlabel("Patent Count", fontsize=12)
            ax2.set_title(f"Top {top_n_companies} Companies (Based on {len(patents):,} loaded patents)", fontsize=14)
            ax2.invert_yaxis()
            
            # Add value labels
            for bar, val in zip(bars, company_counts["patent_count"]):
                ax2.text(val, bar.get_y() + bar.get_height()/2, f' {val}', 
                        va='center', fontweight='bold', fontsize=10)
            
            plt.tight_layout()
            st.pyplot(fig2)
        else:
            st.info("No company data available for the selected filters.")

    # Row 4: Yearly trend
    st.subheader("📈 Patent Trends Over Time")
    
    if not yearly.empty and len(yearly) > 1:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # Line chart
            st.line_chart(yearly.set_index("year"))
        
        with col_chart2:
            # Bar chart
            fig3, ax3 = plt.subplots(figsize=(10, 6))
            ax3.bar(yearly["year"], yearly["patent_count"], color="steelblue", alpha=0.7, edgecolor='black')
            ax3.set_xlabel("Year", fontsize=12)
            ax3.set_ylabel("Number of Patents", fontsize=12)
            
            if min_year == max_year:
                ax3.set_title(f"Patent Distribution for {min_year}", fontsize=14)
            else:
                ax3.set_title(f"Patent Trends ({year_range[0]}–{year_range[1]})", fontsize=14)
            
            ax3.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig3)
    elif not yearly.empty and len(yearly) == 1:
        st.info(f"Data only available for a single year: {yearly['year'].iloc[0]} with {yearly['patent_count'].iloc[0]:,} patents")
        
        # Show single year as a simple metric
        fig3, ax3 = plt.subplots(figsize=(10, 6))
        ax3.bar(yearly["year"], yearly["patent_count"], color="steelblue", alpha=0.7, edgecolor='black')
        ax3.set_xlabel("Year", fontsize=12)
        ax3.set_ylabel("Number of Patents", fontsize=12)
        ax3.set_title(f"Patent Distribution for {yearly['year'].iloc[0]}", fontsize=14)
        
        # Add value label on top of bar
        ax3.text(yearly['year'].iloc[0], yearly['patent_count'].iloc[0], 
                f' {yearly["patent_count"].iloc[0]:,}', 
                ha='center', va='bottom', fontweight='bold')
        
        ax3.grid(True, alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig3)
    else:
        st.info("No patent trend data available for the selected filters.")

    # Row 5: Top countries
    st.subheader(f"🌍 Global Innovation Landscape")
    
    if not country_counts.empty:
        fig4, ax4 = plt.subplots(figsize=(12, 8))
        bars = ax4.barh(country_counts["country"], country_counts["patent_count"], 
                       color="orange", alpha=0.8, edgecolor='darkorange')
        ax4.set_xlabel("Patent Count", fontsize=12)
        ax4.set_title(f"Top {top_n_countries} Countries by Patent Share (Based on {len(patents):,} loaded patents)", fontsize=14)
        ax4.invert_yaxis()
        
        # Add value labels
        for bar, val in zip(bars, country_counts["patent_count"]):
            ax4.text(val, bar.get_y() + bar.get_height()/2, f' {val:,}', 
                    va='center', fontweight='bold', fontsize=10)
        
        plt.tight_layout()
        st.pyplot(fig4)
        
        # Show percentages
        total_patents_country = country_counts['patent_count'].sum()
        st.caption(f"📊 Total patents represented in top {top_n_countries} countries: {total_patents_country:,}")
    else:
        st.info("No country data available for the selected filters.")
    
    # Data quality information
    with st.expander("ℹ️ Data Quality & Configuration Information"):
        st.markdown(f"""
        ### Current Configuration
        - **Loaded Records**: {len(patents):,} of {total_patents:,} total patents
        - **Load Percentage**: {(len(patents)/total_patents*100):.1f}% of database
        - **Top N Settings**: 
          - Inventors: {top_n_inventors}
          - Companies: {top_n_companies}
          - Countries: {top_n_countries}
        
        ### Data Coverage
        - **Patents with Inventors**: {len(inv_rel['patent_id'].unique()):,} ({len(inv_rel['patent_id'].unique())/len(patents)*100:.1f}% of loaded)
        - **Patents with Companies**: {len(ass_rel['patent_id'].unique()):,} ({len(ass_rel['patent_id'].unique())/len(patents)*100:.1f}% of loaded)
        - **Year Range in Loaded Data**: {min_year}–{max_year}
        
        ### Performance Tips
        - For faster loading, use fewer records (100-1000)
        - For comprehensive analysis, use more records (5000+)
        - Adjust Top N values to control chart readability
        """)

if __name__ == "__main__":
    main()