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
FIXED: Disk I/O error by using in-memory database for temp tables
"""

import sqlite3
import time
import os
import sys
from pathlib import Path

import pandas as pd
from tabulate import tabulate

DB_PATH = Path("patents.db")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def check_disk_space(path="."):
    """Check available disk space."""
    try:
        if sys.platform == 'win32':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                str(path), None, None, ctypes.pointer(free_bytes)
            )
            free_gb = free_bytes.value / (1024**3)
        else:
            import shutil
            stat = shutil.disk_usage(path)
            free_gb = stat.free / (1024**3)
        
        print(f"   💾 Available disk space: {free_gb:.2f} GB")
        return free_gb > 0.5  # Need at least 500MB free
    except:
        return True  # Assume OK if can't check


def run_query(conn, sql, description):
    """Run query with timing."""
    print(f"   ⏳ {description}...", end='', flush=True)
    start = time.time()
    try:
        df = pd.read_sql_query(sql, conn)
        elapsed = time.time() - start
        print(f" Done in {elapsed:.2f}s ({len(df):,} rows)")
        return df
    except sqlite3.OperationalError as e:
        print(f" Failed: {e}")
        return pd.DataFrame()


def create_connection():
    """Create database connection with optimized settings."""
    # Check if database exists
    if not DB_PATH.exists():
        print(f"\n❌ Database not found: {DB_PATH}")
        print("   Please run 'python etl.py' first to create the database.")
        sys.exit(1)
    
    # Check disk space
    if not check_disk_space(DB_PATH.parent):
        print("\n⚠️  WARNING: Low disk space! Consider freeing up space.")
    
    # Connect with optimized settings to reduce I/O
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    
    # Optimize SQLite for better I/O performance
    conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
    conn.execute("PRAGMA synchronous = NORMAL")  # Faster writes
    conn.execute("PRAGMA cache_size = 10000")  # Larger cache
    conn.execute("PRAGMA temp_store = MEMORY")  # Store temp tables in memory (KEY FIX!)
    conn.execute("PRAGMA mmap_size = 30000000000")  # 30GB memory mapping
    
    return conn


def create_temp_tables_alternative(conn):
    """
    Alternative: Create regular tables instead of TEMP tables.
    This avoids disk I/O if TEMP tables are problematic.
    """
    print("\n📊 Creating aggregation tables (one-time setup)...")
    
    try:
        # Try with TEMP tables first (faster but might fail)
        conn.execute("PRAGMA temp_store = MEMORY")  # Force memory storage
        
        # View 1: Inventor patent counts
        conn.execute("DROP TABLE IF EXISTS temp_inventor_counts")
        conn.execute("""
            CREATE TEMP TABLE temp_inventor_counts AS
            SELECT 
                inventor_id,
                COUNT(patent_id) as patent_count
            FROM patent_relationships
            GROUP BY inventor_id
        """)
        print("   ✓ Created inventor counts table (in-memory)")
        
        # View 2: Company patent counts
        conn.execute("DROP TABLE IF EXISTS temp_company_counts")
        conn.execute("""
            CREATE TEMP TABLE temp_company_counts AS
            SELECT 
                company_id,
                COUNT(patent_id) as patent_count
            FROM patent_relationships
            WHERE company_id IS NOT NULL
            GROUP BY company_id
        """)
        print("   ✓ Created company counts table (in-memory)")
        
        # View 3: Country patent counts
        conn.execute("DROP TABLE IF EXISTS temp_country_counts")
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
        print("   ✓ Created country counts table (in-memory)")
        
        return True
        
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  TEMP table failed: {e}")
        print("   🔄 Falling back to persistent tables...")
        
        # Fallback: Use regular tables instead of TEMP (slower but works)
        try:
            conn.execute("DROP TABLE IF EXISTS persistent_inventor_counts")
            conn.execute("""
                CREATE TABLE persistent_inventor_counts AS
                SELECT inventor_id, COUNT(patent_id) as patent_count
                FROM patent_relationships
                GROUP BY inventor_id
            """)
            
            conn.execute("DROP TABLE IF EXISTS persistent_company_counts")
            conn.execute("""
                CREATE TABLE persistent_company_counts AS
                SELECT company_id, COUNT(patent_id) as patent_count
                FROM patent_relationships
                WHERE company_id IS NOT NULL
                GROUP BY company_id
            """)
            
            conn.execute("DROP TABLE IF EXISTS persistent_country_counts")
            conn.execute("""
                CREATE TABLE persistent_country_counts AS
                SELECT i.country, COUNT(DISTINCT r.patent_id) as patent_count
                FROM inventors i
                JOIN patent_relationships r ON i.inventor_id = r.inventor_id
                WHERE i.country IS NOT NULL AND i.country != '' AND i.country != 'Unknown'
                GROUP BY i.country
            """)
            
            print("   ✓ Created persistent tables (fallback mode)")
            return True
            
        except sqlite3.OperationalError as e2:
            print(f"   ❌ Failed even with persistent tables: {e2}")
            return False


def main():
    print("\n" + "="*60)
    print("🔍 PATENT INTELLIGENCE ANALYZER (ULTRA-FAST)")
    print("="*60)
    print("   Author: Opiyo Oscar (2300701330)")
    print("   Using pre-computed aggregations")
    
    # Create connection with optimizations
    conn = create_connection()
    
    # Create aggregation tables (automatically handles I/O errors)
    if not create_temp_tables_alternative(conn):
        print("\n❌ Failed to create aggregation tables.")
        print("   Possible solutions:")
        print("   1. Check available disk space")
        print("   2. Run as administrator")
        print("   3. Move patents.db to local drive (C:)")
        print("   4. Disable anti-virus temporarily")
        conn.close()
        sys.exit(1)
    
    results = {}
    
    # ============================================================
    # Q1: Top Inventors
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
    # Q2: Top Companies
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
    # Q3: Top Countries
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
    # Q4: Yearly Trends
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
    # Q5: JOIN Query
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
    # Q6: CTE Query
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
            WHERE c.patent_count >= 50
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
    
    # Clean up temp tables (optional)
    try:
        conn.execute("DROP TABLE IF EXISTS temp_inventor_counts")
        conn.execute("DROP TABLE IF EXISTS temp_company_counts")
        conn.execute("DROP TABLE IF EXISTS temp_country_counts")
    except:
        pass
    
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
    if any(not df.empty for df in results.values()):
        import pickle
        with open("query_results.pkl", "wb") as f:
            pickle.dump(results, f)
        print(f"\n💾 Results saved to: query_results.pkl")
    
    # Export CSVs
    if not results.get('q1', pd.DataFrame()).empty:
        results['q1'].to_csv(OUTPUT_DIR / "analyze_top_inventors_sample.csv", index=False)
    if not results.get('q2', pd.DataFrame()).empty:
        results['q2'].to_csv(OUTPUT_DIR / "analyze_top_companies_sample.csv", index=False)
    if not results.get('q4', pd.DataFrame()).empty:
        results['q4'].to_csv(OUTPUT_DIR / "analyze_yearly_trends_sample.csv", index=False)
    
    print(f"\n💾 Sample exports saved under {OUTPUT_DIR}/")
    
    conn.close()
    
    print("\n" + "="*60)
    print("🎯 NEXT: python report.py")
    print("="*60)


if __name__ == "__main__":
    main()