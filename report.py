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
        SELECT i.name, i.country, c.patent_count AS patents
        FROM temp_inventor_counts c
        JOIN inventors i ON c.inventor_id = i.inventor_id
        ORDER BY c.patent_count DESC
        LIMIT 10
    """, conn)

    top_companies = pd.read_sql_query("""
        SELECT co.name, cc.patent_count AS patents
        FROM temp_company_counts cc
        JOIN companies co ON cc.company_id = co.company_id
        ORDER BY cc.patent_count DESC
        LIMIT 10
    """, conn)

    top_countries = pd.read_sql_query("""
        SELECT country, patent_count AS patents,
               ROUND(100.0 * patent_count / (SELECT COUNT(*) FROM patents), 2) AS share
        FROM temp_country_counts
        ORDER BY patent_count DESC
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


def _ensure_temp_counts(conn):
    """Speed up large-db exports (same pattern as analyze.py)."""
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS temp_inventor_counts")
    cur.execute("DROP TABLE IF EXISTS temp_company_counts")
    cur.execute(
        """
        CREATE TEMP TABLE temp_inventor_counts AS
        SELECT inventor_id, COUNT(patent_id) AS patent_count
        FROM patent_relationships
        GROUP BY inventor_id
        """
    )
    cur.execute(
        """
        CREATE TEMP TABLE temp_company_counts AS
        SELECT company_id, COUNT(patent_id) AS patent_count
        FROM patent_relationships
        WHERE company_id IS NOT NULL
        GROUP BY company_id
        """
    )
    cur.execute("DROP TABLE IF EXISTS patent_country_pairs")
    cur.execute("DROP TABLE IF EXISTS temp_country_counts")
    cur.execute(
        """
        CREATE TEMP TABLE patent_country_pairs AS
        SELECT DISTINCT r.patent_id, TRIM(i.country) AS country
        FROM patent_relationships r
        JOIN inventors i ON r.inventor_id = i.inventor_id
        WHERE i.country IS NOT NULL AND TRIM(i.country) != '' AND TRIM(i.country) != 'Unknown'
        """
    )
    cur.execute(
        """
        CREATE TEMP TABLE temp_country_counts AS
        SELECT country, COUNT(*) AS patent_count
        FROM patent_country_pairs
        GROUP BY country
        """
    )


def export_csvs(conn):
    """Export required CSV files (run after _ensure_temp_counts)."""
    logger.info("Exporting CSV reports...")
    top_inventors = pd.read_sql_query("""
        SELECT i.name, i.country, c.patent_count
        FROM temp_inventor_counts c
        JOIN inventors i ON c.inventor_id = i.inventor_id
        ORDER BY c.patent_count DESC
        LIMIT 100
    """, conn)
    top_inventors.insert(0, "rank", range(1, len(top_inventors)+1))
    top_inventors.to_csv(OUTPUT_DIR / "top_inventors.csv", index=False)

    top_companies = pd.read_sql_query("""
        SELECT co.name, cc.patent_count
        FROM temp_company_counts cc
        JOIN companies co ON cc.company_id = co.company_id
        ORDER BY cc.patent_count DESC
        LIMIT 50
    """, conn)
    top_companies.insert(0, "rank", range(1, len(top_companies)+1))
    top_companies.to_csv(OUTPUT_DIR / "top_companies.csv", index=False)

    country_trends = pd.read_sql_query("""
        SELECT country, patent_count,
               ROUND(100.0 * patent_count / (SELECT COUNT(*) FROM patents), 2) AS share_pct
        FROM temp_country_counts
        ORDER BY patent_count DESC
    """, conn)
    country_trends.to_csv(OUTPUT_DIR / "country_trends.csv", index=False)

    yearly = pd.read_sql_query("SELECT year, COUNT(*) AS patent_count FROM patents WHERE year IS NOT NULL GROUP BY year ORDER BY year", conn)
    yearly.to_csv(OUTPUT_DIR / "yearly_trends.csv", index=False)

    join_sample = pd.read_sql_query("""
        SELECT p.patent_id,
               SUBSTR(p.title, 1, 120) AS title,
               p.year,
               i.name AS inventor_name,
               i.country AS inventor_country,
               c.name AS company_name
        FROM patents p
        JOIN patent_relationships r ON p.patent_id = r.patent_id
        JOIN inventors i ON r.inventor_id = i.inventor_id
        LEFT JOIN companies c ON r.company_id = c.company_id
        LIMIT 500
    """, conn)
    join_sample.to_csv(OUTPUT_DIR / "join_sample.csv", index=False)

    prolific = pd.read_sql_query("""
        SELECT i.name, c.patent_count, i.country
        FROM temp_inventor_counts c
        JOIN inventors i ON c.inventor_id = i.inventor_id
        WHERE c.patent_count >= 50
        ORDER BY c.patent_count DESC
    """, conn)
    prolific.to_csv(OUTPUT_DIR / "prolific_inventors.csv", index=False)

    ranked = pd.read_sql_query("""
        WITH inventor_stats AS (
            SELECT i.country, i.name, c.patent_count
            FROM temp_inventor_counts c
            JOIN inventors i ON c.inventor_id = i.inventor_id
            WHERE i.country IS NOT NULL AND TRIM(i.country) != '' AND i.country != 'Unknown'
        ),
        inventor_ranks AS (
            SELECT country, name, patent_count,
                   RANK() OVER (PARTITION BY country ORDER BY patent_count DESC) AS rank_num
            FROM inventor_stats
        )
        SELECT country, name AS inventor_name, rank_num AS rank, patent_count
        FROM inventor_ranks
        WHERE rank_num <= 5
        ORDER BY country, rank_num
    """, conn)
    ranked.to_csv(OUTPUT_DIR / "ranked_inventors_by_country.csv", index=False)

    logger.info("CSV exports saved in outputs/")


def json_report(conn):
    """Create JSON report (run after _ensure_temp_counts)."""
    stats = get_summary_stats(conn)

    top_inventors = pd.read_sql_query("""
        SELECT i.name, i.country, c.patent_count AS patents
        FROM temp_inventor_counts c
        JOIN inventors i ON c.inventor_id = i.inventor_id
        ORDER BY c.patent_count DESC
        LIMIT 20
    """, conn)

    top_companies = pd.read_sql_query("""
        SELECT co.name, cc.patent_count AS patents
        FROM temp_company_counts cc
        JOIN companies co ON cc.company_id = co.company_id
        ORDER BY cc.patent_count DESC
        LIMIT 20
    """, conn)

    top_countries = pd.read_sql_query("""
        SELECT country, patent_count AS patents,
               ROUND(100.0 * patent_count / (SELECT COUNT(*) FROM patents), 2) AS share
        FROM temp_country_counts
        ORDER BY patent_count DESC
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
        logger.info("Building aggregation tables (one-time per run; may take several minutes on full data)…")
        _ensure_temp_counts(conn)
        console_report(conn)
        export_csvs(conn)
        json_report(conn)
        logger.info("All reports generated successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()