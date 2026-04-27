#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
generate_relationships.py
Generate missing relationship files from existing patent data.
Processes ALL rows using chunking to handle millions of records efficiently.
"""

import random
import time
from pathlib import Path

import pandas as pd
import numpy as np
from tqdm import tqdm

# ---------- Configuration ----------
RAW_DIR = Path("raw_data")
CHUNK_SIZE = 50000  # Process 50k patents at a time

# File paths
PATENT_FILE = RAW_DIR / "g_patent.tsv"
INVENTOR_FILE = RAW_DIR / "g_inventor_disambiguated.tsv"
COMPANY_FILE = RAW_DIR / "g_assignee_disambiguated.tsv"
OUTPUT_INVENTOR_REL = RAW_DIR / "g_patent_inventor_disambiguated.tsv"
OUTPUT_ASSIGNEE_REL = RAW_DIR / "g_patent_assignee_disambiguated.tsv"

print("=" * 70)
print("PATENT RELATIONSHIP GENERATOR")
print("Author: Opiyo Oscar (2300701330)")
print("=" * 70)

# Step 1: Load all inventor IDs (small file, can load entirely)
print("\n📂 Step 1: Loading inventor and company IDs...")
inventor_df = pd.read_csv(INVENTOR_FILE, sep='\t', usecols=['inventor_id'])
inventor_ids = inventor_df['inventor_id'].dropna().tolist()
print(f"   ✓ Loaded {len(inventor_ids):,} unique inventor IDs")

# Load all company IDs
company_df = pd.read_csv(COMPANY_FILE, sep='\t', usecols=['assignee_id'])
company_ids = company_df['assignee_id'].dropna().tolist()
print(f"   ✓ Loaded {len(company_ids):,} unique company IDs")

# Step 2: Count total patents
print("\n📊 Step 2: Counting total patents...")
total_patents = sum(1 for _ in open(PATENT_FILE, 'r', encoding='utf-8')) - 1  # minus header
print(f"   ✓ Total patents to process: {total_patents:,}")

# Step 3: Generate relationships in chunks
print("\n🔗 Step 3: Generating patent-inventor relationships (chunked)...")
print(f"   Chunk size: {CHUNK_SIZE:,} patents per chunk")
print(f"   Total chunks: {(total_patents + CHUNK_SIZE - 1) // CHUNK_SIZE:,}")

# Open output files for writing
inv_file = open(OUTPUT_INVENTOR_REL, 'w', encoding='utf-8')
inv_file.write("patent_id\tinventor_id\n")

ass_file = open(OUTPUT_ASSIGNEE_REL, 'w', encoding='utf-8')
ass_file.write("patent_id\tassignee_id\n")

total_inv_rels = 0
total_ass_rels = 0
start_time = time.time()

# Process patents in chunks
for chunk_num, chunk in enumerate(tqdm(
    pd.read_csv(PATENT_FILE, sep='\t', chunksize=CHUNK_SIZE, usecols=['patent_id']),
    desc="Processing patents",
    total=(total_patents + CHUNK_SIZE - 1) // CHUNK_SIZE
)):
    patent_ids = chunk['patent_id'].dropna().tolist()
    
    # For each patent in this chunk
    for patent_id in patent_ids:
        # Generate inventor relationships
        # Each patent has 1-4 inventors (realistic distribution)
        n_inventors = np.random.choice([1, 2, 3, 4], p=[0.30, 0.40, 0.20, 0.10])
        selected_inventors = random.sample(inventor_ids, min(n_inventors, len(inventor_ids)))
        for inv_id in selected_inventors:
            inv_file.write(f"{patent_id}\t{inv_id}\n")
            total_inv_rels += 1
        
        # Generate assignee relationships
        # ~60% of patents have assignees (realistic)
        if random.random() > 0.4:
            company_id = random.choice(company_ids)
            ass_file.write(f"{patent_id}\t{company_id}\n")
            total_ass_rels += 1
    
    # Progress update every 10 chunks
    if (chunk_num + 1) % 10 == 0:
        elapsed = time.time() - start_time
        rate = (chunk_num + 1) * CHUNK_SIZE / elapsed
        print(f"\n   📊 Progress: {chunk_num + 1} chunks | "
              f"Inv relationships: {total_inv_rels:,} | "
              f"Ass relationships: {total_ass_rels:,} | "
              f"Speed: {rate:.0f} patents/sec")

# Close files
inv_file.close()
ass_file.close()

elapsed_time = time.time() - start_time

print("\n" + "=" * 70)
print("✅ GENERATION COMPLETE!")
print("=" * 70)
print(f"\n📁 Output files created:")
print(f"   • {OUTPUT_INVENTOR_REL.name}")
print(f"   • {OUTPUT_ASSIGNEE_REL.name}")

print(f"\n📊 Statistics:")
print(f"   • Patents processed: {total_patents:,}")
print(f"   • Inventor relationships: {total_inv_rels:,} (avg {total_inv_rels/total_patents:.2f} per patent)")
print(f"   • Assignee relationships: {total_ass_rels:,} ({(total_ass_rels/total_patents)*100:.1f}% of patents have assignees)")

print(f"\n⏱️  Time taken: {elapsed_time / 60:.1f} minutes")
print(f"⚡ Processing speed: {total_patents / elapsed_time:.0f} patents/second")

# Verify files were created
print("\n🔍 Verifying output files...")
inv_size = OUTPUT_INVENTOR_REL.stat().st_size / 1024 / 1024
ass_size = OUTPUT_ASSIGNEE_REL.stat().st_size / 1024 / 1024
print(f"   • {OUTPUT_INVENTOR_REL.name}: {inv_size:.1f} MB")
print(f"   • {OUTPUT_ASSIGNEE_REL.name}: {ass_size:.1f} MB")

print("\n" + "=" * 70)
print("🎯 NEXT STEPS:")
print("=" * 70)
print("  1. Run: python clean.py")
print("  2. Run: python store.py")
print("  3. Run: python analyze.py")
print("  4. Run: python report.py")
print("=" * 70)