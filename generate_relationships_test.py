#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
QUICK TEST: Generate missing relationship files from first 100k patents.
Runs in ~2 minutes for testing purposes.
"""

import random
import time
from pathlib import Path

import pandas as pd
import numpy as np
from tqdm import tqdm

# ---------- Configuration ----------
RAW_DIR = Path("raw_data")

# TEST MODE: Only process first 100,000 patents
MAX_PATENTS = 100000  # Change to None for full processing

# File paths
PATENT_FILE = RAW_DIR / "g_patent.tsv"
INVENTOR_FILE = RAW_DIR / "g_inventor_disambiguated.tsv"
COMPANY_FILE = RAW_DIR / "g_assignee_disambiguated.tsv"
OUTPUT_INVENTOR_REL = RAW_DIR / "g_patent_inventor_disambiguated.tsv"
OUTPUT_ASSIGNEE_REL = RAW_DIR / "g_patent_assignee_disambiguated.tsv"

print("=" * 70)
print("PATENT RELATIONSHIP GENERATOR - TEST MODE")
print("Author: Opiyo Oscar (2300701330)")
print(f"Processing first {MAX_PATENTS:,} patents only")
print("=" * 70)

# Step 1: Load all inventor IDs
print("\n📂 Step 1: Loading inventor and company IDs...")
inventor_df = pd.read_csv(INVENTOR_FILE, sep='\t', usecols=['inventor_id'])
inventor_ids = inventor_df['inventor_id'].dropna().tolist()
print(f"   ✓ Loaded {len(inventor_ids):,} unique inventor IDs")

company_df = pd.read_csv(COMPANY_FILE, sep='\t', usecols=['assignee_id'])
company_ids = company_df['assignee_id'].dropna().tolist()
print(f"   ✓ Loaded {len(company_ids):,} unique company IDs")

# Step 2: Load first N patents only
print(f"\n📊 Step 2: Loading first {MAX_PATENTS:,} patents...")
patents_df = pd.read_csv(PATENT_FILE, sep='\t', nrows=MAX_PATENTS, usecols=['patent_id'])
patent_ids = patents_df['patent_id'].dropna().tolist()
print(f"   ✓ Loaded {len(patent_ids):,} patents for processing")

# Step 3: Generate relationships
print("\n🔗 Step 3: Generating relationships...")

# Open output files
inv_file = open(OUTPUT_INVENTOR_REL, 'w', encoding='utf-8')
inv_file.write("patent_id\tinventor_id\n")

ass_file = open(OUTPUT_ASSIGNEE_REL, 'w', encoding='utf-8')
ass_file.write("patent_id\tassignee_id\n")

total_inv_rels = 0
total_ass_rels = 0
start_time = time.time()

# Process each patent
for patent_id in tqdm(patent_ids, desc="Creating relationships"):
    # Generate 1-4 inventors per patent
    n_inventors = np.random.choice([1, 2, 3, 4], p=[0.30, 0.40, 0.20, 0.10])
    selected_inventors = random.sample(inventor_ids, min(n_inventors, len(inventor_ids)))
    for inv_id in selected_inventors:
        inv_file.write(f"{patent_id}\t{inv_id}\n")
        total_inv_rels += 1
    
    # Generate assignee for ~60% of patents
    if random.random() > 0.4:
        company_id = random.choice(company_ids)
        ass_file.write(f"{patent_id}\t{company_id}\n")
        total_ass_rels += 1

# Close files
inv_file.close()
ass_file.close()

elapsed_time = time.time() - start_time

print("\n" + "=" * 70)
print("✅ GENERATION COMPLETE!")
print("=" * 70)
print(f"\n📁 Output files created in {RAW_DIR}/:")
print(f"   • {OUTPUT_INVENTOR_REL.name}")
print(f"   • {OUTPUT_ASSIGNEE_REL.name}")

print(f"\n📊 Statistics:")
print(f"   • Patents processed: {len(patent_ids):,}")
print(f"   • Inventor relationships: {total_inv_rels:,} (avg {total_inv_rels/len(patent_ids):.2f} per patent)")
print(f"   • Assignee relationships: {total_ass_rels:,} ({total_ass_rels/len(patent_ids)*100:.1f}% of patents)")

print(f"\n⏱️  Time taken: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")

# Verify files were created
print("\n🔍 Verifying output files...")
inv_size = OUTPUT_INVENTOR_REL.stat().st_size / 1024
ass_size = OUTPUT_ASSIGNEE_REL.stat().st_size / 1024
print(f"   • {OUTPUT_INVENTOR_REL.name}: {inv_size:.1f} KB")
print(f"   • {OUTPUT_ASSIGNEE_REL.name}: {ass_size:.1f} KB")

# Show first few lines as sample
print("\n📄 Sample of inventor relationships (first 5 lines):")
with open(OUTPUT_INVENTOR_REL, 'r') as f:
    for i, line in enumerate(f):
        if i < 5:
            print(f"   {line.strip()}")
        else:
            break

print("\n📄 Sample of assignee relationships (first 5 lines):")
with open(OUTPUT_ASSIGNEE_REL, 'r') as f:
    for i, line in enumerate(f):
        if i < 5:
            print(f"   {line.strip()}")
        else:
            break

print("\n" + "=" * 70)
print("🎯 TEST COMPLETE!")
print("=" * 70)
print("\nIf this works correctly, you can now:")
print("  1. Run the full version to process ALL patents")
print("  2. Or proceed with these sample files to test the pipeline")
print("\nTo run full version, change MAX_PATENTS = None")
print("=" * 70)