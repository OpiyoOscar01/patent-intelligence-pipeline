#!/usr/bin/env python3
# load_inventors_companies.py - FULL DATASET VERSION

import sqlite3
import pandas as pd
from pathlib import Path

CLEAN_DIR = Path("clean_data")
DB_PATH = Path("patents.db")

def load_table_in_chunks(csv_path, table_name, conn, chunksize=50000):
    """Load any CSV fully using chunking - handles any file size."""
    if not csv_path.exists():
        print(f"❌ {csv_path} not found")
        return False
    
    # Get total rows for progress
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        total_rows = sum(1 for _ in f) - 1
    
    print(f"Loading {table_name} ({total_rows:,} rows) in chunks of {chunksize}...")
    
    loaded = 0
    chunk_num = 0
    
    for chunk in pd.read_csv(
        csv_path, 
        chunksize=chunksize,
        encoding='utf-8',
        encoding_errors='ignore',
        low_memory=False
    ):
        # Clean the chunk
        chunk = chunk.dropna(subset=[f'{table_name[:-1]}_id'])  # e.g., inventor_id, company_id
        chunk = chunk.where(pd.notnull(chunk), None)
        
        # Append to database
        if chunk_num == 0:
            chunk.to_sql(table_name, conn, if_exists='replace', index=False)
        else:
            chunk.to_sql(table_name, conn, if_exists='append', index=False)
        
        loaded += len(chunk)
        chunk_num += 1
        
        if chunk_num % 10 == 0:
            print(f"  Progress: {loaded:,}/{total_rows:,} rows ({loaded/total_rows*100:.1f}%)")
        
        import gc
        gc.collect()
    
    print(f"✓ Loaded {loaded:,} rows into {table_name}")
    return True

def main():
    conn = sqlite3.connect(str(DB_PATH))
    
    # Optimize SQLite for large inserts
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA cache_size = -200000")  # 200MB cache
    
    # Load inventors (full dataset)
    print("\n" + "="*50)
    load_table_in_chunks(CLEAN_DIR / "clean_inventors.csv", "inventors", conn, chunksize=50000)
    
    # Load companies (full dataset)
    print("\n" + "="*50)
    load_table_in_chunks(CLEAN_DIR / "clean_companies.csv", "companies", conn, chunksize=50000)
    
    # Verify counts
    print("\n" + "="*50)
    print("VERIFICATION:")
    cur = conn.cursor()
    for table in ["inventors", "companies"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table}: {count:,} rows")
    
    conn.close()
    print("\n✅ Full dataset loaded successfully!")

if __name__ == "__main__":
    main()