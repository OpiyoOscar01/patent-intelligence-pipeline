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
def load_data(year_start=None, year_end=None, limit_records=None):
    """
    Load data from SQLite with year filtering and optional record limit.
    
    Args:
        year_start: Starting year (optional)
        year_end: Ending year (optional)
        limit_records: Maximum number of records to load (optional)
    """
    conn = sqlite3.connect(DB_PATH)
    
    # Build WHERE clause based on year filter
    where_clauses = []
    params = []
    
    if year_start is not None and year_end is not None:
        where_clauses.append("year BETWEEN ? AND ?")
        params.extend([year_start, year_end])
    elif year_start is not None:
        where_clauses.append("year >= ?")
        params.append(year_start)
    elif year_end is not None:
        where_clauses.append("year <= ?")
        params.append(year_end)
    
    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Add LIMIT clause if specified
    limit_clause = f"LIMIT {limit_records}" if limit_records else ""
    
    # Load patents with filters
    query = f"SELECT patent_id, year FROM patents {where_clause} ORDER BY year {limit_clause}".strip()
    patents = pd.read_sql_query(query, conn, params=params)
    
    # Get the patent IDs from the loaded patents
    patent_ids = patents["patent_id"].tolist()
    
    # If there are no patents, return empty dataframes
    if not patent_ids:
        conn.close()
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Use chunked queries to avoid parameter limit issues
    # Inventor counts per patent (only for loaded patents)
    inv_rel = chunked_query(
        conn,
        "SELECT patent_id, inventor_id FROM patent_relationships WHERE patent_id IN ({placeholders})",
        patent_ids,
        "patent_id",
        chunk_size=500
    )
    
    # Assignee links (only for loaded patents)
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


def get_year_range():
    """Get the minimum and maximum years available in the database."""
    conn = sqlite3.connect(DB_PATH)
    result = pd.read_sql_query("SELECT MIN(year) as min_year, MAX(year) as max_year FROM patents WHERE year IS NOT NULL", conn)
    conn.close()
    return int(result.iloc[0]['min_year']), int(result.iloc[0]['max_year'])


def get_total_patent_count(year_start=None, year_end=None):
    """Get total number of patents in the database with optional year filter."""
    conn = sqlite3.connect(DB_PATH)
    
    if year_start is not None and year_end is not None:
        count = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM patents WHERE year BETWEEN ? AND ?", 
            conn, 
            params=[year_start, year_end]
        )
    elif year_start is not None:
        count = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM patents WHERE year >= ?", 
            conn, 
            params=[year_start]
        )
    elif year_end is not None:
        count = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM patents WHERE year <= ?", 
            conn, 
            params=[year_end]
        )
    else:
        count = pd.read_sql_query("SELECT COUNT(*) as count FROM patents WHERE year IS NOT NULL", conn)
    
    conn.close()
    return count.iloc[0]['count']


def main():
    if not DB_PATH.exists():
        st.error("Database not found. Please run `python store.py` first.")
        return

    # Get available year range from database
    db_min_year, db_max_year = get_year_range()
    
    # Sidebar filters
    st.sidebar.header("📊 Data Loading Configuration")
    
    # Data loading mode selection
    load_mode = st.sidebar.radio(
        "Data Loading Mode",
        options=["By Year Range", "By Record Count", "Combined (Year + Limit)"],
        help="Choose how to filter data from the database"
    )
    
    # Initialize variables
    start_year = db_min_year
    end_year = db_max_year
    limit_records = None
    total_patents_in_range = get_total_patent_count()
    
    if load_mode == "By Year Range":
        st.sidebar.subheader("📅 Year Range Selection")
        col_year1, col_year2 = st.sidebar.columns(2)
        with col_year1:
            start_year = st.number_input(
                "Start Year",
                min_value=db_min_year,
                max_value=db_max_year,
                value=db_min_year,
                step=1
            )
        with col_year2:
            end_year = st.number_input(
                "End Year",
                min_value=db_min_year,
                max_value=db_max_year,
                value=db_max_year,
                step=1
            )
        
        # Validate year range
        if start_year > end_year:
            st.sidebar.error("⚠️ Start year must be less than or equal to end year")
            start_year, end_year = end_year, start_year
        
        total_patents_in_range = get_total_patent_count(start_year, end_year)
        st.sidebar.metric("📄 Total patents in range", f"{total_patents_in_range:,}")
        
        # Performance warning
        if total_patents_in_range > 50000:
            st.sidebar.warning(f"⚠️ Loading {total_patents_in_range:,} patents may be slow. Consider using record limit.")
        
        limit_records = None  # Load all in range
        
    elif load_mode == "By Record Count":
        st.sidebar.subheader("🔢 Record Limit Selection")
        
        # Get total available patents
        total_available = get_total_patent_count()
        
        # Configurable record limit options
        record_options = [100, 500, 1000, 2000, 5000, 10000, 25000, 50000, 100000]
        # Filter options to not exceed total available
        record_options = [x for x in record_options if x <= total_available]
        
        # Add total available as an option if not already included
        if total_available not in record_options:
            record_options.append(total_available)
        
        record_options = sorted(set(record_options))
        
        default_limit = 1000 if 1000 in record_options else record_options[0]
        
        limit_records = st.sidebar.selectbox(
            "Number of records to load",
            options=record_options,
            index=record_options.index(default_limit),
            help=f"Total patents available: {total_available:,}"
        )
        
        st.sidebar.info(f"📊 Loading most recent {limit_records:,} patents")
        start_year = db_min_year
        end_year = db_max_year
        total_patents_in_range = limit_records
        
    else:  # Combined mode
        st.sidebar.subheader("📅 Year Range Selection")
        col_year1, col_year2 = st.sidebar.columns(2)
        with col_year1:
            start_year = st.number_input(
                "Start Year",
                min_value=db_min_year,
                max_value=db_max_year,
                value=db_min_year,
                step=1
            )
        with col_year2:
            end_year = st.number_input(
                "End Year",
                min_value=db_min_year,
                max_value=db_max_year,
                value=db_max_year,
                step=1
            )
        
        if start_year > end_year:
            st.sidebar.error("⚠️ Start year must be less than or equal to end year")
            start_year, end_year = end_year, start_year
        
        total_in_range = get_total_patent_count(start_year, end_year)
        st.sidebar.metric("📄 Total patents in range", f"{total_in_range:,}")
        
        st.sidebar.subheader("🔢 Record Limit (Optional)")
        use_limit = st.sidebar.checkbox("Apply record limit", value=False)
        
        if use_limit:
            # Record limit options
            record_options = [100, 500, 1000, 2000, 5000, 10000, 25000, 50000]
            record_options = [x for x in record_options if x <= total_in_range]
            
            if total_in_range not in record_options and total_in_range > 50000:
                record_options.append(total_in_range)
            
            record_options = sorted(set(record_options))
            
            limit_records = st.sidebar.selectbox(
                "Maximum records to load",
                options=record_options,
                index=min(2, len(record_options)-1),
                help=f"Total available in range: {total_in_range:,}"
            )
            total_patents_in_range = limit_records
            st.sidebar.info(f"📊 Loading {limit_records:,} of {total_in_range:,} patents from {start_year}–{end_year}")
        else:
            limit_records = None
            total_patents_in_range = total_in_range
            st.sidebar.success(f"📊 Loading ALL {total_in_range:,} patents from {start_year}–{end_year}")
    
    # Display current configuration
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Current Configuration")
    st.sidebar.info(f"""
    **Mode:** {load_mode}
    **Year Range:** {start_year}–{end_year}
    **Record Limit:** {limit_records if limit_records else 'No limit'}
    **Patents to load:** {total_patents_in_range:,}
    """)
    
    # Performance warning for large loads
    if total_patents_in_range > 50000:
        st.sidebar.error(
            f"⚠️⚠️⚠️ WARNING: Loading {total_patents_in_range:,} patents!\n\n"
            "This may cause:\n"
            "• Slow loading (30+ seconds)\n"
            "• High memory usage\n"
            "• Possible timeout errors\n\n"
            "Consider using a smaller year range or record limit."
        )
    elif total_patents_in_range > 20000:
        st.sidebar.warning(
            f"⚠️ Loading {total_patents_in_range:,} patents.\n"
            "This may take 10-20 seconds. Consider a smaller limit for faster interaction."
        )
    
    # Load data with selected filters
    with st.spinner(f"Loading patents{' from ' + str(start_year) + '–' + str(end_year) if load_mode != 'By Record Count' else ''}..."):
        patents, inv_rel, ass_rel, inventors, companies = load_data(start_year, end_year, limit_records)
    
    # Check if data was loaded
    if patents.empty:
        st.warning(f"No patents found for the selected criteria.")
        return

    st.success(f"✅ Successfully loaded {len(patents):,} patents")
    
    # Sidebar filters for analysis within loaded data
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 Analysis Filters (Within Loaded Data)")
    
    min_year = int(patents["year"].min())
    max_year = int(patents["year"].max())
    
    if min_year == max_year:
        st.sidebar.info(f"Data only available for year {min_year}")
        filter_year_range = (min_year, max_year)
    else:
        filter_year_range = st.sidebar.slider(
            "Focus on specific years",
            min_value=min_year,
            max_value=max_year,
            value=(min_year, max_year),
            help="Zoom in on a specific period within the loaded data"
        )
    
    # Top N configuration
    st.sidebar.subheader("📊 Display Configuration")
    
    top_n_inventors = st.sidebar.selectbox(
        "👥 Top Inventors",
        options=[5, 10, 15, 20, 25, 30, 50, 100],
        index=1,
        help="Number of top inventors to show"
    )
    
    top_n_companies = st.sidebar.selectbox(
        "🏢 Top Companies",
        options=[5, 10, 15, 20, 25, 30, 50, 100],
        index=1,
        help="Number of top companies to show"
    )
    
    top_n_countries = st.sidebar.selectbox(
        "🌍 Top Countries",
        options=[5, 10, 15, 20, 25, 30, 50, 100],
        index=1,
        help="Number of top countries to show"
    )
    
    # Filter patents by year focus range
    if min_year == max_year:
        filtered_patents = patents
    else:
        mask = (patents["year"] >= filter_year_range[0]) & (patents["year"] <= filter_year_range[1])
        filtered_patents = patents[mask]
    
    filtered_patent_ids = set(filtered_patents["patent_id"])

    # Prepare inventor counts
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

    # Yearly trend
    yearly = filtered_patents.groupby("year").size().reset_index(name="patent_count")

    # Country trends
    if not inv_filtered.empty and not inventors.empty:
        inv_with_country = inv_filtered.merge(inventors[["inventor_id", "country"]], on="inventor_id")
        country_counts = inv_with_country.groupby("country").size().reset_index(name="patent_count")
        country_counts = country_counts.sort_values("patent_count", ascending=False).head(top_n_countries)
    else:
        country_counts = pd.DataFrame()

    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Loaded Patents", f"{len(patents):,}")
    with col2:
        st.metric("🔍 Currently Showing", f"{len(filtered_patents):,}")
    with col3:
        st.metric("👨‍🔬 Unique Inventors", f"{inv_filtered['inventor_id'].nunique() if not inv_filtered.empty else 0:,}")
    with col4:
        st.metric("🏭 Unique Companies", f"{ass_filtered['company_id'].nunique() if not ass_filtered.empty else 0:,}")

    # Info about current view
    if filter_year_range[0] == filter_year_range[1]:
        st.info(f"📈 Showing data for {len(filtered_patents):,} patents from year {filter_year_range[0]}")
    else:
        st.info(f"📈 Showing data for {len(filtered_patents):,} patents in year range {filter_year_range[0]}–{filter_year_range[1]}")

    # Charts Row 1
    col_left, col_right = st.columns(2)

    with col_left:
        if not inv_counts.empty:
            st.subheader(f"🏆 Top {top_n_inventors} Inventors")
            fig1, ax1 = plt.subplots(figsize=(10, 6))
            bars = ax1.barh(inv_counts["name"], inv_counts["patent_count"], color="skyblue")
            ax1.set_xlabel("Patent Count", fontsize=12)
            ax1.set_title(f"Top {top_n_inventors} Inventors", fontsize=14)
            ax1.invert_yaxis()
            
            for bar, val in zip(bars, inv_counts["patent_count"]):
                ax1.text(val, bar.get_y() + bar.get_height()/2, f' {val}', 
                        va='center', fontweight='bold', fontsize=10)
            
            plt.tight_layout()
            st.pyplot(fig1)
        else:
            st.info("No inventor data available")

    with col_right:
        if not company_counts.empty:
            st.subheader(f"🏢 Top {top_n_companies} Companies")
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            bars = ax2.barh(company_counts["name"], company_counts["patent_count"], color="lightgreen")
            ax2.set_xlabel("Patent Count", fontsize=12)
            ax2.set_title(f"Top {top_n_companies} Companies", fontsize=14)
            ax2.invert_yaxis()
            
            for bar, val in zip(bars, company_counts["patent_count"]):
                ax2.text(val, bar.get_y() + bar.get_height()/2, f' {val}', 
                        va='center', fontweight='bold', fontsize=10)
            
            plt.tight_layout()
            st.pyplot(fig2)
        else:
            st.info("No company data available")

    # Yearly Trends
    st.subheader("📈 Patent Trends Over Time")
    
    if not yearly.empty and len(yearly) > 1:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.line_chart(yearly.set_index("year"))
        
        with col_chart2:
            fig3, ax3 = plt.subplots(figsize=(10, 6))
            bars = ax3.bar(yearly["year"], yearly["patent_count"], color="steelblue", alpha=0.7, edgecolor='black')
            ax3.set_xlabel("Year", fontsize=12)
            ax3.set_ylabel("Number of Patents", fontsize=12)
            ax3.set_title(f"Patent Trends ({filter_year_range[0]}–{filter_year_range[1]})", fontsize=14)
            
            # Add labels on tallest bars to avoid clutter
            max_height = yearly["patent_count"].max()
            for bar, val in zip(bars, yearly["patent_count"]):
                if val > max_height * 0.1:  # Only label bars with significant height
                    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height(), 
                            f'{val:,}', ha='center', va='bottom', fontweight='bold', fontsize=8, rotation=45)
            
            ax3.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig3)
    elif not yearly.empty and len(yearly) == 1:
        fig3, ax3 = plt.subplots(figsize=(10, 6))
        ax3.bar(yearly["year"], yearly["patent_count"], color="steelblue", alpha=0.7, edgecolor='black')
        ax3.set_xlabel("Year", fontsize=12)
        ax3.set_ylabel("Number of Patents", fontsize=12)
        ax3.set_title(f"Patent Distribution for {yearly['year'].iloc[0]}", fontsize=14)
        ax3.text(yearly['year'].iloc[0], yearly['patent_count'].iloc[0], 
                f' {yearly["patent_count"].iloc[0]:,}', ha='center', va='bottom', fontweight='bold')
        ax3.grid(True, alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig3)
    else:
        st.info("No patent trend data available")

    # Top Countries
    st.subheader(f"🌍 Global Innovation Landscape")
    
    if not country_counts.empty:
        fig4, ax4 = plt.subplots(figsize=(12, 8))
        bars = ax4.barh(country_counts["country"], country_counts["patent_count"], 
                       color="orange", alpha=0.8, edgecolor='darkorange')
        ax4.set_xlabel("Patent Count", fontsize=12)
        ax4.set_title(f"Top {top_n_countries} Countries by Patent Share", fontsize=14)
        ax4.invert_yaxis()
        
        for bar, val in zip(bars, country_counts["patent_count"]):
            ax4.text(val, bar.get_y() + bar.get_height()/2, f' {val:,}', 
                    va='center', fontweight='bold', fontsize=10)
        
        plt.tight_layout()
        st.pyplot(fig4)
        
        total_shown = country_counts['patent_count'].sum()
        st.caption(f"📊 Total patents represented in top {top_n_countries} countries: {total_shown:,}")
    else:
        st.info("No country data available")
    
    # Data Quality Information
    with st.expander("ℹ️ Data Quality & Configuration Information"):
        st.markdown(f"""
        ### Current Configuration
        - **Load Mode:** {load_mode}
        - **Database Year Range:** {db_min_year}–{db_max_year}
        - **Loaded Year Range:** {start_year}–{end_year}
        - **Record Limit:** {limit_records if limit_records else 'No limit'}
        - **Total Patents Loaded:** {len(patents):,}
        - **Display Focus Range:** {filter_year_range[0]}–{filter_year_range[1]}
        
        ### Display Settings
        - **Top N Inventors:** {top_n_inventors}
        - **Top N Companies:** {top_n_companies}
        - **Top N Countries:** {top_n_countries}
        
        ### Data Coverage
        - **Patents with Inventors:** {len(inv_rel['patent_id'].unique()):,} ({len(inv_rel['patent_id'].unique())/len(patents)*100:.1f}% of loaded)
        - **Patents with Companies:** {len(ass_rel['patent_id'].unique()):,} ({len(ass_rel['patent_id'].unique())/len(patents)*100:.1f}% of loaded)
        
        ### Recommendations
        - **For quick loading:** Use "By Record Count" with 100-1000 records
        - **For full analysis:** Use "By Year Range" with a narrow range
        - **For overview:** Use "Combined" mode with moderate limits
        - **For complete data:** Use "By Year Range" with full range (may be slow)
        """)

if __name__ == "__main__":
    main()