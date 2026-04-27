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


@st.cache_resource
def load_data():
    """Load minimal data from SQLite (filtered by year later)."""
    conn = sqlite3.connect(DB_PATH)
    # patents with year
    patents = pd.read_sql_query("SELECT patent_id, year FROM patents WHERE year IS NOT NULL", conn)
    # inventor counts per patent
    inv_rel = pd.read_sql_query("SELECT patent_id, inventor_id FROM patent_relationships", conn)
    # assignee links
    ass_rel = pd.read_sql_query("SELECT patent_id, company_id FROM patent_relationships WHERE company_id IS NOT NULL", conn)
    # inventor names & countries
    inventors = pd.read_sql_query("SELECT inventor_id, name, country FROM inventors", conn)
    # company names
    companies = pd.read_sql_query("SELECT company_id, name FROM companies", conn)
    conn.close()
    return patents, inv_rel, ass_rel, inventors, companies


def main():
    if not DB_PATH.exists():
        st.error("Database not found. Please run `python store.py` first.")
        return

    patents, inv_rel, ass_rel, inventors, companies = load_data()

    # Sidebar filters
    st.sidebar.header("Filters")
    min_year = int(patents["year"].min())
    max_year = int(patents["year"].max())
    year_range = st.sidebar.slider("Year range", min_year, max_year, (min_year, max_year))
    top_n = st.sidebar.selectbox("Top N to display", [10, 20, 50], index=0)

    # Filter patents by year
    mask = (patents["year"] >= year_range[0]) & (patents["year"] <= year_range[1])
    filtered_patents = patents[mask]
    filtered_patent_ids = set(filtered_patents["patent_id"])

    # Prepare inventor counts within filtered patents
    inv_filtered = inv_rel[inv_rel["patent_id"].isin(filtered_patent_ids)]
    inv_counts = inv_filtered.groupby("inventor_id").size().reset_index(name="patent_count")
    inv_counts = inv_counts.merge(inventors, on="inventor_id")
    inv_counts = inv_counts.sort_values("patent_count", ascending=False).head(top_n)

    # Prepare company counts
    ass_filtered = ass_rel[ass_rel["patent_id"].isin(filtered_patent_ids)]
    company_counts = ass_filtered.groupby("company_id").size().reset_index(name="patent_count")
    company_counts = company_counts.merge(companies, on="company_id")
    company_counts = company_counts.sort_values("patent_count", ascending=False).head(top_n)

    # Yearly trend for filtered range
    yearly = filtered_patents.groupby("year").size().reset_index(name="patent_count")

    # Country trends
    inv_with_country = inv_filtered.merge(inventors[["inventor_id", "country"]], on="inventor_id")
    country_counts = inv_with_country.groupby("country").size().reset_index(name="patent_count")
    country_counts = country_counts.sort_values("patent_count", ascending=False).head(top_n)

    # Row 1: Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Patents", f"{len(filtered_patents):,}")
    col2.metric("Unique Inventors", f"{inv_filtered['inventor_id'].nunique():,}")
    col3.metric("Unique Companies", f"{ass_filtered['company_id'].nunique():,}")
    col4.metric("Year Range", f"{year_range[0]} – {year_range[1]}")

    # Row 2: Top Inventors (horizontal bar chart)
    st.subheader(f"🏆 Top {top_n} Inventors by Patent Count")
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    ax1.barh(inv_counts["name"], inv_counts["patent_count"], color="skyblue")
    ax1.set_xlabel("Patent Count")
    ax1.invert_yaxis()
    st.pyplot(fig1)

    # Row 3: Top Companies
    st.subheader(f"🏢 Top {top_n} Companies (Assignees)")
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    ax2.barh(company_counts["name"], company_counts["patent_count"], color="lightgreen")
    ax2.set_xlabel("Patent Count")
    ax2.invert_yaxis()
    st.pyplot(fig2)

    # Row 4: Yearly trend line chart
    st.subheader("📈 Patents Granted Per Year")
    st.line_chart(yearly.set_index("year"))

    # Row 5: Top countries
    st.subheader(f"🌍 Top {top_n} Countries by Patent Share")
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    ax3.barh(country_counts["country"], country_counts["patent_count"], color="orange")
    ax3.set_xlabel("Patent Count")
    ax3.invert_yaxis()
    st.pyplot(fig3)


if __name__ == "__main__":
    main()