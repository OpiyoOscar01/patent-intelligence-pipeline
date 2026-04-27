#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================

"""
analyze.py
ULTRA-FAST: Pre-computed patent analytics using materialized views.
Runs in seconds instead of minutes.
"""

import sqlite3
import time
from pathlib import Path

import pandas as pd
from tabulate import tabulate

DB_PATH = Path("patents.db")


def run_query(conn, sql, description):
    """Run query with timing."""
    print(f"   ⏳ {description}...", end='', flush=True)
    start = time.time()
    df = pd.read_sql_query(sql, conn)
    elapsed = time.time() - start
    print(f" Done in {elapsed:.2f}s ({len(df):,} rows)")
    return df


def main():
    print("\n" + "="*60)
    print("🔍 PATENT INTELLIGENCE ANALYZER (ULTRA-FAST)")
    print("="*60)
    print("   Author: Opiyo Oscar (2300701330)")
    print("   Using pre-computed aggregations")
    
    conn = sqlite3.connect(str(DB_PATH))
    
    # Create temporary materialized views for fast queries
    print("\n📊 Creating temporary aggregation tables (one-time setup)...")
    
    # View 1: Inventor patent counts (pre-computed)
    conn.execute("""
        DROP TABLE IF EXISTS temp_inventor_counts
    """)
    conn.execute("""
        CREATE TEMP TABLE temp_inventor_counts AS
        SELECT 
            inventor_id,
            COUNT(patent_id) as patent_count
        FROM patent_relationships
        GROUP BY inventor_id
    """)
    print("   ✓ Created inventor counts table")
    
    # View 2: Company patent counts (pre-computed)
    conn.execute("""
        DROP TABLE IF EXISTS temp_company_counts
    """)
    conn.execute("""
        CREATE TEMP TABLE temp_company_counts AS
        SELECT 
            company_id,
            COUNT(patent_id) as patent_count
        FROM patent_relationships
        WHERE company_id IS NOT NULL
        GROUP BY company_id
    """)
    print("   ✓ Created company counts table")
    
    # View 3: Country patent counts (pre-computed)
    conn.execute("""
        DROP TABLE IF EXISTS temp_country_counts
    """)
    conn.execute("""
        CREATE TEMP TABLE temp_country_counts AS
        SELECT 
            i.country,
            COUNT(DISTINCT r.patent_id) as patent_count
        FROM inventors i
        JOIN patent_relationships r ON i.inventor_id = r.inventor_id
        WHERE i.country IS NOT NULL AND i.country != '' AND i.country != 'Unknown'
        GROUP BY i.country
    """)
    print("   ✓ Created country counts table")
    
    results = {}
    
    # ============================================================
    # Q1: Top Inventors (ULTRA FAST - uses pre-computed table)
    # ============================================================
    print("\n" + "─"*60)
    print("🚀 Q1: Top Inventors")
    print("─"*60)
    
    q1_sql = """
        SELECT 
            i.name,
            i.country,
            c.patent_count
        FROM temp_inventor_counts c
        JOIN inventors i ON c.inventor_id = i.inventor_id
        ORDER BY c.patent_count DESC
        LIMIT 20
    """
    results['q1'] = run_query(conn, q1_sql, "Retrieving top inventors")
    if not results['q1'].empty:
        print(tabulate(results['q1'].head(10), headers='keys', tablefmt='simple', showindex=False))
    
    # ============================================================
    # Q2: Top Companies (ULTRA FAST)
    # ============================================================
    print("\n" + "─"*60)
    print("🚀 Q2: Top Companies")
    print("─"*60)
    
    q2_sql = """
        SELECT 
            c.name,
            cc.patent_count
        FROM temp_company_counts cc
        JOIN companies c ON cc.company_id = c.company_id
        ORDER BY cc.patent_count DESC
        LIMIT 20
    """
    results['q2'] = run_query(conn, q2_sql, "Retrieving top companies")
    if not results['q2'].empty:
        print(tabulate(results['q2'].head(10), headers='keys', tablefmt='simple', showindex=False))
    
    # ============================================================
    # Q3: Top Countries (ULTRA FAST)
    # ============================================================
    print("\n" + "─"*60)
    print("🚀 Q3: Top Countries")
    print("─"*60)
    
    total_patents = pd.read_sql_query("SELECT COUNT(*) as cnt FROM patents", conn)['cnt'][0]
    
    q3_sql = f"""
        SELECT 
            country,
            patent_count,
            ROUND(100.0 * patent_count / {total_patents}, 2) as share_pct
        FROM temp_country_counts
        ORDER BY patent_count DESC
        LIMIT 20
    """
    results['q3'] = run_query(conn, q3_sql, "Retrieving country stats")
    if not results['q3'].empty:
        print(tabulate(results['q3'].head(10), headers='keys', tablefmt='simple', showindex=False))
    
    # ============================================================
    # Q4: Yearly Trends (direct query - uses index)
    # ============================================================
    print("\n" + "─"*60)
    print("🚀 Q4: Yearly Patent Trends")
    print("─"*60)
    
    q4_sql = """
        SELECT 
            year,
            COUNT(*) as patent_count
        FROM patents
        WHERE year IS NOT NULL AND year > 1975
        GROUP BY year
        ORDER BY year
    """
    results['q4'] = run_query(conn, q4_sql, "Calculating yearly trends")
    if not results['q4'].empty:
        print(tabulate(results['q4'].head(15), headers='keys', tablefmt='simple', showindex=False))
    
    # ============================================================
    # Q5: JOIN Query (limited rows)
    # ============================================================
    print("\n" + "─"*60)
    print("🚀 Q5: Sample Patent Data (JOIN)")
    print("─"*60)
    
    q5_sql = """
        SELECT 
            p.patent_id,
            SUBSTR(p.title, 1, 50) as title,
            p.year,
            i.name as inventor_name,
            c.name as company_name
        FROM patents p
        JOIN patent_relationships r ON p.patent_id = r.patent_id
        JOIN inventors i ON r.inventor_id = i.inventor_id
        LEFT JOIN companies c ON r.company_id = c.company_id
        LIMIT 20
    """
    results['q5'] = run_query(conn, q5_sql, "Sample patent data")
    if not results['q5'].empty:
        print(tabulate(results['q5'].head(10), headers='keys', tablefmt='simple', showindex=False))
    
    # ============================================================
    # Q6: CTE Query (uses pre-computed)
    # ============================================================
    print("\n" + "─"*60)
    print("🚀 Q6: Prolific Inventors (CTE)")
    print("─"*60)
    
    q6_sql = """
        WITH prolific AS (
            SELECT 
                i.name,
                i.country,
                c.patent_count
            FROM temp_inventor_counts c
            JOIN inventors i ON c.inventor_id = i.inventor_id
            WHERE c.patent_count >= 100
        )
        SELECT * FROM prolific
        ORDER BY patent_count DESC
        LIMIT 20
    """
    results['q6'] = run_query(conn, q6_sql, "Finding prolific inventors")
    if not results['q6'].empty:
        print(tabulate(results['q6'].head(10), headers='keys', tablefmt='simple', showindex=False))
    
    # ============================================================
    # Q7: Ranking Query
    # ============================================================
    print("\n" + "─"*60)
    print("🚀 Q7: Ranked Inventors by Country")
    print("─"*60)
    
    q7_sql = """
        WITH inventor_ranks AS (
            SELECT 
                i.country,
                i.name,
                c.patent_count,
                RANK() OVER (PARTITION BY i.country ORDER BY c.patent_count DESC) as rank_num
            FROM temp_inventor_counts c
            JOIN inventors i ON c.inventor_id = i.inventor_id
            WHERE i.country IS NOT NULL AND i.country != '' AND i.country != 'Unknown'
        )
        SELECT 
            country,
            name,
            patent_count,
            rank_num
        FROM inventor_ranks
        WHERE rank_num <= 5
        ORDER BY country, rank_num
        LIMIT 50
    """
    results['q7'] = run_query(conn, q7_sql, "Ranking inventors by country")
    if not results['q7'].empty:
        print(tabulate(results['q7'].head(15), headers='keys', tablefmt='simple', showindex=False))
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*60)
    print("✅ EXECUTION SUMMARY")
    print("="*60)
    for key, df in results.items():
        status = "✓" if not df.empty else "✗"
        print(f"   {status} {key.upper()}: {len(df):,} rows")
    
    # Save results
    import pickle
    with open("query_results.pkl", "wb") as f:
        pickle.dump(results, f)
    print(f"\n💾 Results saved to: query_results.pkl")
    
    # Export CSVs
    if not results.get('q1', pd.DataFrame()).empty:
        results['q1'].to_csv("top_inventors.csv", index=False)
    if not results.get('q2', pd.DataFrame()).empty:
        results['q2'].to_csv("top_companies.csv", index=False)
    if not results.get('q4', pd.DataFrame()).empty:
        results['q4'].to_csv("yearly_trends.csv", index=False)
    
    print(f"\n💾 Exports saved: top_inventors.csv, top_companies.csv, yearly_trends.csv")
    
    conn.close()
    
    print("\n" + "="*60)
    print("🎯 NEXT: python report.py")
    print("="*60)


if __name__ == "__main__":
    main()