#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
reports.py
Generate three report types:
- Console report (terminal)
- CSV exports (top_inventors, top_companies, country_trends, yearly_trends)
- JSON report (patent_report.json)
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path("patents.db")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_summary_stats(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM patents")
    total_patents = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM inventors")
    total_inventors = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM companies")
    total_companies = cur.fetchone()[0]
    cur.execute("SELECT MIN(year), MAX(year) FROM patents WHERE year IS NOT NULL")
    min_year, max_year = cur.fetchone()
    return {
        "total_patents": total_patents,
        "total_inventors": total_inventors,
        "total_companies": total_companies,
        "year_range": f"{min_year}–{max_year}",
    }


def console_report(conn):
    """Print formatted report to terminal."""
    stats = get_summary_stats(conn)

    top_inventors = pd.read_sql_query("""
        SELECT i.name, i.country, COUNT(DISTINCT r.patent_id) AS patents
        FROM inventors i
        JOIN patent_relationships r ON i.inventor_id = r.inventor_id
        GROUP BY i.inventor_id
        ORDER BY patents DESC
        LIMIT 10
    """, conn)

    top_companies = pd.read_sql_query("""
        SELECT c.name, COUNT(DISTINCT r.patent_id) AS patents
        FROM companies c
        JOIN patent_relationships r ON c.company_id = r.company_id
        GROUP BY c.company_id
        ORDER BY patents DESC
        LIMIT 10
    """, conn)

    top_countries = pd.read_sql_query("""
        SELECT i.country, COUNT(DISTINCT r.patent_id) AS patents,
               ROUND(100.0 * COUNT(DISTINCT r.patent_id) / (SELECT COUNT(*) FROM patents), 2) AS share
        FROM inventors i
        JOIN patent_relationships r ON i.inventor_id = r.inventor_id
        WHERE i.country IS NOT NULL AND i.country != ''
        GROUP BY i.country
        ORDER BY patents DESC
        LIMIT 10
    """, conn)

    print("\n" + "=" * 80)
    print("GLOBAL PATENT INTELLIGENCE REPORT")
    print(f"Author: Opiyo Oscar  |  Student No: 2300701330")
    print(f"Makerere University — Cloud Computing & Big Data Analytics")
    print("=" * 80)
    print(f"Total Patents Analysed:    {stats['total_patents']:,}")
    print(f"Total Unique Inventors:    {stats['total_inventors']:,}")
    print(f"Total Companies (Assignees): {stats['total_companies']:,}")
    print(f"Years Covered:             {stats['year_range']}")
    print("-" * 80)
    print("TOP 10 INVENTORS:")
    for i, row in top_inventors.iterrows():
        print(f"  {i+1:2d}. {row['name']} ({row['country']}) — {row['patents']:,} patents")
    print("-" * 80)
    print("TOP 10 COMPANIES:")
    for i, row in top_companies.iterrows():
        print(f"  {i+1:2d}. {row['name']} — {row['patents']:,} patents")
    print("-" * 80)
    print("TOP 10 COUNTRIES:")
    for i, row in top_countries.iterrows():
        print(f"  {i+1:2d}. {row['country']:15s} — {row['patents']:>10,}  ({row['share']:5.2f}%)")
    print("=" * 80 + "\n")


def export_csvs(conn):
    """Export required CSV files."""
    logger.info("Exporting CSV reports...")
    top_inventors = pd.read_sql_query("""
        SELECT i.name, i.country, COUNT(DISTINCT r.patent_id) AS patent_count
        FROM inventors i
        JOIN patent_relationships r ON i.inventor_id = r.inventor_id
        GROUP BY i.inventor_id
        ORDER BY patent_count DESC
        LIMIT 100
    """, conn)
    top_inventors.insert(0, "rank", range(1, len(top_inventors)+1))
    top_inventors.to_csv(OUTPUT_DIR / "top_inventors.csv", index=False)

    top_companies = pd.read_sql_query("""
        SELECT c.name, COUNT(DISTINCT r.patent_id) AS patent_count
        FROM companies c
        JOIN patent_relationships r ON c.company_id = r.company_id
        GROUP BY c.company_id
        ORDER BY patent_count DESC
        LIMIT 50
    """, conn)
    top_companies.insert(0, "rank", range(1, len(top_companies)+1))
    top_companies.to_csv(OUTPUT_DIR / "top_companies.csv", index=False)

    country_trends = pd.read_sql_query("""
        SELECT i.country, COUNT(DISTINCT r.patent_id) AS patent_count,
               ROUND(100.0 * COUNT(DISTINCT r.patent_id) / (SELECT COUNT(*) FROM patents), 2) AS share_pct
        FROM inventors i
        JOIN patent_relationships r ON i.inventor_id = r.inventor_id
        WHERE i.country IS NOT NULL AND i.country != ''
        GROUP BY i.country
        ORDER BY patent_count DESC
    """, conn)
    country_trends.to_csv(OUTPUT_DIR / "country_trends.csv", index=False)

    yearly = pd.read_sql_query("SELECT year, COUNT(*) AS patent_count FROM patents WHERE year IS NOT NULL GROUP BY year ORDER BY year", conn)
    yearly.to_csv(OUTPUT_DIR / "yearly_trends.csv", index=False)
    logger.info("CSV exports saved in outputs/")


def json_report(conn):
    """Create JSON report."""
    stats = get_summary_stats(conn)

    top_inventors = pd.read_sql_query("""
        SELECT i.name, i.country, COUNT(DISTINCT r.patent_id) AS patents
        FROM inventors i
        JOIN patent_relationships r ON i.inventor_id = r.inventor_id
        GROUP BY i.inventor_id
        ORDER BY patents DESC
        LIMIT 20
    """, conn)

    top_companies = pd.read_sql_query("""
        SELECT c.name, COUNT(DISTINCT r.patent_id) AS patents
        FROM companies c
        JOIN patent_relationships r ON c.company_id = r.company_id
        GROUP BY c.company_id
        ORDER BY patents DESC
        LIMIT 20
    """, conn)

    top_countries = pd.read_sql_query("""
        SELECT i.country, COUNT(DISTINCT r.patent_id) AS patents,
               ROUND(100.0 * COUNT(DISTINCT r.patent_id) / (SELECT COUNT(*) FROM patents), 2) AS share
        FROM inventors i
        JOIN patent_relationships r ON i.inventor_id = r.inventor_id
        WHERE i.country IS NOT NULL AND i.country != ''
        GROUP BY i.country
        ORDER BY patents DESC
        LIMIT 20
    """, conn)

    yearly = pd.read_sql_query("SELECT year, COUNT(*) AS patents FROM patents WHERE year IS NOT NULL GROUP BY year ORDER BY year", conn)

    report = {
        "author": "Opiyo Oscar",
        "student_number": "2300701330",
        "university": "Makerere University",
        "course": "Cloud Computing and Big Data Analytics",
        "generated_at": datetime.now().isoformat(),
        "summary": stats,
        "top_inventors": [{"rank": i+1, "name": row["name"], "country": row["country"], "patents": int(row["patents"])}
                          for i, row in top_inventors.iterrows()],
        "top_companies": [{"rank": i+1, "name": row["name"], "patents": int(row["patents"])}
                          for i, row in top_companies.iterrows()],
        "top_countries": [{"rank": i+1, "country": row["country"], "patents": int(row["patents"]), "share_pct": float(row["share"])}
                          for i, row in top_countries.iterrows()],
        "yearly_trends": [{"year": int(row["year"]), "patents": int(row["patents"])}
                          for _, row in yearly.iterrows()]
    }

    with open(OUTPUT_DIR / "patent_report.json", "w") as f:
        json.dump(report, f, indent=2)
    logger.info("JSON report saved.")


def main():
    if not DB_PATH.exists():
        logger.error("Database not found. Run store.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        console_report(conn)
        export_csvs(conn)
        json_report(conn)
        logger.info("All reports generated successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()