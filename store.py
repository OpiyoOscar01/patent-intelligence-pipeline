#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
Load cleaned CSV files into SQLite database in chunks.
Handles both test and full datasets without row limits.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

CLEAN_DIR = Path("clean_data")
DB_PATH = Path("patents.db")
SCHEMA_SQL = Path("schema.sql")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def init_db(conn: sqlite3.Connection):
    """Create tables and indexes from schema.sql (drops existing)."""
    with open(SCHEMA_SQL, "r", encoding='utf-8') as f:
        schema = f.read()
    conn.executescript(schema)
    logger.info("Database schema created.")


def load_table_in_chunks(conn: sqlite3.Connection, csv_path: Path, table_name: str, id_column: str = None, chunksize=50000):
    """
    Load CSV into SQLite table in chunks - handles any file size.
    Works for both test and full datasets.
    """
    if not csv_path.exists():
        logger.warning(f"{csv_path} not found, skipping {table_name}")
        return False

    # Get total rows for progress
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            total_rows = sum(1 for _ in f) - 1
    except:
        with open(csv_path, 'r', encoding='latin-1') as f:
            total_rows = sum(1 for _ in f) - 1
    
    logger.info(f"Loading {total_rows:,} rows into {table_name} (chunk size: {chunksize})...")
    
    loaded = 0
    chunk_num = 0
    
    try:
        for chunk in pd.read_csv(
            csv_path, 
            chunksize=chunksize,
            encoding='utf-8',
            encoding_errors='ignore',
            low_memory=False
        ):
            # Drop rows with null ID if id_column is specified
            if id_column and id_column in chunk.columns:
                chunk = chunk.dropna(subset=[id_column])
            
            # Replace NaN with None for SQLite
            chunk = chunk.where(pd.notnull(chunk), None)
            
            # Append to database
            if chunk_num == 0:
                chunk.to_sql(table_name, conn, if_exists='replace', index=False)
            else:
                chunk.to_sql(table_name, conn, if_exists='append', index=False)
            
            loaded += len(chunk)
            chunk_num += 1
            
            if chunk_num % 10 == 0:
                logger.info(f"  Progress: {loaded:,}/{total_rows:,} rows ({loaded/total_rows*100:.1f}%)")
            
            import gc
            gc.collect()
            
    except UnicodeError:
        logger.warning(f"UTF-8 failed, trying latin-1 encoding for {table_name}...")
        try:
            for chunk in pd.read_csv(
                csv_path, 
                chunksize=chunksize, 
                encoding='latin-1',
                low_memory=False
            ):
                if id_column and id_column in chunk.columns:
                    chunk = chunk.dropna(subset=[id_column])
                chunk = chunk.where(pd.notnull(chunk), None)
                
                if chunk_num == 0:
                    chunk.to_sql(table_name, conn, if_exists='replace', index=False)
                else:
                    chunk.to_sql(table_name, conn, if_exists='append', index=False)
                
                loaded += len(chunk)
                chunk_num += 1
                
                if chunk_num % 10 == 0:
                    logger.info(f"  Progress: {loaded:,}/{total_rows:,} rows ({loaded/total_rows*100:.1f}%)")
                
                import gc
                gc.collect()
        except Exception as e2:
            logger.error(f"Error loading {table_name} with latin-1: {e2}")
            return False
    except Exception as e:
        logger.error(f"Error loading {table_name} at chunk {chunk_num}: {e}")
        return False
    
    logger.info(f"✓ Loaded {loaded:,} rows into {table_name}")
    return True


def main():
    """Orchestrate database creation and data loading."""
    required_files = {
        "patents": CLEAN_DIR / "clean_patents.csv",
        "inventors": CLEAN_DIR / "clean_inventors.csv",
        "companies": CLEAN_DIR / "clean_companies.csv",
        "patent_relationships": CLEAN_DIR / "clean_relationships.csv"
    }
    
    # ID columns for each table (for dropping nulls)
    id_columns = {
        "patents": "patent_id",
        "inventors": "inventor_id",
        "companies": "company_id",
        "patent_relationships": None  # Relationships might handle nulls differently
    }
    
    existing_files = {}
    for table_name, file_path in required_files.items():
        if file_path.exists():
            file_size_mb = file_path.stat().st_size / 1024 / 1024
            existing_files[table_name] = file_path
            logger.info(f"Found {table_name}: {file_size_mb:.1f} MB")
        else:
            logger.warning(f"Missing {table_name}: {file_path}")
    
    if not existing_files:
        logger.error("No clean data files found. Please run clean.py first")
        return
    
    # Remove existing database to start fresh
    if DB_PATH.exists():
        DB_PATH.unlink()
        logger.info("Removed existing database.")
    
    # Connect with optimized settings
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA cache_size = -200000")  # 200MB cache
    
    try:
        # Create schema
        init_db(conn)
        
        # Load tables in order (smallest to largest for memory efficiency)
        # Order: relationships (smallest) -> companies -> inventors -> patents (largest)
        
        table_order = ["patent_relationships", "companies", "inventors", "patents"]
        chunk_sizes = {
            "patent_relationships": 10000,
            "companies": 50000,
            "inventors": 50000,
            "patents": 50000
        }
        
        for table_name in table_order:
            if table_name in existing_files:
                logger.info("\n" + "=" * 60)
                logger.info(f"Loading {table_name}...")
                load_table_in_chunks(
                    conn, 
                    existing_files[table_name], 
                    table_name, 
                    id_column=id_columns.get(table_name),
                    chunksize=chunk_sizes.get(table_name, 50000)
                )
        
        # Verify row counts
        logger.info("\n" + "=" * 60)
        logger.info("VERIFYING ROW COUNTS")
        logger.info("=" * 60)
        cur = conn.cursor()
        for table in ["patents", "inventors", "companies", "patent_relationships"]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                cnt = cur.fetchone()[0]
                logger.info(f"  {table}: {cnt:,} rows")
            except:
                logger.info(f"  {table}: table not found or empty")
        
        # Create indexes
        logger.info("\n" + "=" * 60)
        logger.info("CREATING INDEXES...")
        logger.info("=" * 60)
        
        indexes = [
            ("idx_patents_year", "CREATE INDEX IF NOT EXISTS idx_patents_year ON patents(year)"),
            ("idx_inventors_country", "CREATE INDEX IF NOT EXISTS idx_inventors_country ON inventors(country)"),
            ("idx_rel_patent", "CREATE INDEX IF NOT EXISTS idx_rel_patent ON patent_relationships(patent_id)"),
            ("idx_rel_inventor", "CREATE INDEX IF NOT EXISTS idx_rel_inventor ON patent_relationships(inventor_id)"),
            ("idx_rel_company", "CREATE INDEX IF NOT EXISTS idx_rel_company ON patent_relationships(company_id)"),
        ]
        
        for idx_name, idx_sql in indexes:
            try:
                logger.info(f"  Creating {idx_name}...")
                cur.execute(idx_sql)
            except Exception as e:
                logger.warning(f"  Could not create {idx_name}: {e}")
        
        logger.info("✓ Index creation complete")
        
    except Exception as e:
        logger.error(f"Error during database loading: {e}")
        import traceback
        traceback.print_exc()
        return
    finally:
        conn.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ DATABASE READY: patents.db")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("  1. python analyze.py  - Run SQL queries")
    logger.info("  2. python report.py   - Generate reports")
    logger.info("  3. streamlit run dashboard.py - Launch dashboard")


if __name__ == "__main__":
    main()