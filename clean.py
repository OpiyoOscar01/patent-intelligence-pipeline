#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
clean.py
Clean raw TSV files in chunks, produce normalised CSV tables.
Processes all rows (millions) using pandas chunksize.
FIXED: Handles actual column names from USPTO data.
"""

import logging
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# ---------- Configuration ----------
RAW_DIR = Path("raw_data")
CLEAN_DIR = Path("clean_data")
CLEAN_DIR.mkdir(exist_ok=True)

CHUNKSIZE = 50000

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def clean_patents():
    """Process g_patent.tsv -> clean_patents.csv"""
    input_file = RAW_DIR / "g_patent.tsv"
    output_file = CLEAN_DIR / "clean_patents.csv"
    
    if not input_file.exists():
        logger.error(f"File not found: {input_file}")
        return
        
    if output_file.exists():
        logger.info("clean_patents.csv already exists, skipping.")
        return

    # First, check what columns are available
    sample = pd.read_csv(input_file, sep='\t', nrows=5)
    logger.info(f"Available columns in patents: {sample.columns.tolist()}")
    
    # Determine column names (handle different naming conventions)
    patent_id_col = None
    title_col = None
    abstract_col = None
    date_col = None
    
    for col in sample.columns:
        col_lower = col.lower()
        if 'patent_id' in col_lower or col_lower == 'id':
            patent_id_col = col
        elif 'title' in col_lower:
            title_col = col
        elif 'abstract' in col_lower:
            abstract_col = col
        elif 'date' in col_lower or 'filing' in col_lower:
            date_col = col
    
    if not patent_id_col:
        # Try to use first column as ID
        patent_id_col = sample.columns[0]
        logger.warning(f"No patent_id column found, using {patent_id_col}")
    
    logger.info(f"Mapping: patent_id={patent_id_col}, title={title_col}, abstract={abstract_col}, date={date_col}")
    
    total_rows = 0
    kept_rows = 0
    first_chunk = True

    for chunk in tqdm(pd.read_csv(input_file, sep="\t", chunksize=CHUNKSIZE, low_memory=False),
                      desc="Clean patents"):
        total_rows += len(chunk)
        
        # Create clean dataframe with standard column names
        clean_chunk = pd.DataFrame()
        clean_chunk['patent_id'] = chunk[patent_id_col] if patent_id_col else None
        clean_chunk['title'] = chunk[title_col] if title_col else "Unknown"
        clean_chunk['abstract'] = chunk[abstract_col] if abstract_col else ""
        clean_chunk['filing_date'] = chunk[date_col] if date_col else None

        # drop rows without patent_id
        clean_chunk = clean_chunk.dropna(subset=["patent_id"])

        # extract year from filing_date
        clean_chunk["filing_date"] = pd.to_datetime(clean_chunk["filing_date"], errors="coerce")
        clean_chunk["year"] = clean_chunk["filing_date"].dt.year

        # remove rows with invalid year
        clean_chunk = clean_chunk.dropna(subset=["year"])
        clean_chunk["year"] = clean_chunk["year"].astype(int)

        # clean text fields
        clean_chunk["title"] = clean_chunk["title"].fillna("Unknown").astype(str).str.strip()
        clean_chunk["abstract"] = clean_chunk["abstract"].fillna("").astype(str).str.strip()

        kept_rows += len(clean_chunk)
        clean_chunk.to_csv(output_file, mode="a", header=first_chunk, index=False)
        first_chunk = False

    logger.info(f"Patents: processed {total_rows:,} rows, kept {kept_rows:,} rows.")


def clean_inventors():
    """g_inventor_disambiguated.tsv -> clean_inventors.csv"""
    input_file = RAW_DIR / "g_inventor_disambiguated.tsv"
    output_file = CLEAN_DIR / "clean_inventors.csv"
    
    if not input_file.exists():
        logger.error(f"File not found: {input_file}")
        return
        
    if output_file.exists():
        logger.info("clean_inventors.csv already exists, skipping.")
        return

    # Check what columns are available
    sample = pd.read_csv(input_file, sep='\t', nrows=5)
    logger.info(f"Available columns in inventors: {sample.columns.tolist()}")
    
    # Determine column names
    inventor_id_col = None
    first_name_col = None
    last_name_col = None
    country_col = None
    
    for col in sample.columns:
        col_lower = col.lower()
        if 'inventor_id' in col_lower:
            inventor_id_col = col
        elif 'first' in col_lower or 'given' in col_lower:
            first_name_col = col
        elif 'last' in col_lower or 'family' in col_lower or 'surname' in col_lower:
            last_name_col = col
        elif 'country' in col_lower:
            country_col = col
    
    if not inventor_id_col:
        # Try to find any ID column
        for col in sample.columns:
            if 'id' in col.lower():
                inventor_id_col = col
                break
    
    logger.info(f"Mapping: inventor_id={inventor_id_col}, first={first_name_col}, last={last_name_col}, country={country_col}")
    
    total_rows = 0
    kept_rows = 0
    first_chunk = True

    for chunk in tqdm(pd.read_csv(input_file, sep="\t", chunksize=CHUNKSIZE, low_memory=False),
                      desc="Clean inventors"):
        total_rows += len(chunk)
        
        clean_chunk = pd.DataFrame()
        clean_chunk['inventor_id'] = chunk[inventor_id_col] if inventor_id_col else None
        
        # combine name
        if first_name_col and last_name_col:
            clean_chunk['name'] = chunk[first_name_col].fillna("") + " " + chunk[last_name_col].fillna("")
        elif first_name_col:
            clean_chunk['name'] = chunk[first_name_col].fillna("")
        elif last_name_col:
            clean_chunk['name'] = chunk[last_name_col].fillna("")
        else:
            clean_chunk['name'] = "Unknown"
            
        clean_chunk['name'] = clean_chunk['name'].str.strip()
        
        # country
        clean_chunk['country'] = chunk[country_col] if country_col else "Unknown"
        
        # drop rows with no inventor_id or name
        clean_chunk = clean_chunk.dropna(subset=["inventor_id", "name"])
        clean_chunk = clean_chunk[clean_chunk["name"] != ""]

        kept_rows += len(clean_chunk)
        clean_chunk.to_csv(output_file, mode="a", header=first_chunk, index=False)
        first_chunk = False

    logger.info(f"Inventors: processed {total_rows:,} rows, kept {kept_rows:,} rows.")


def clean_companies():
    """g_assignee_disambiguated.tsv -> clean_companies.csv"""
    input_file = RAW_DIR / "g_assignee_disambiguated.tsv"
    output_file = CLEAN_DIR / "clean_companies.csv"
    
    if not input_file.exists():
        logger.error(f"File not found: {input_file}")
        return
        
    if output_file.exists():
        logger.info("clean_companies.csv already exists, skipping.")
        return

    # Check what columns are available
    sample = pd.read_csv(input_file, sep='\t', nrows=5)
    logger.info(f"Available columns in companies: {sample.columns.tolist()}")
    
    # Determine column names
    company_id_col = None
    name_col = None
    
    for col in sample.columns:
        col_lower = col.lower()
        if 'assignee_id' in col_lower or 'company_id' in col_lower:
            company_id_col = col
        elif 'organization' in col_lower or 'name' in col_lower:
            name_col = col
    
    if not company_id_col:
        # Try to use first column as ID
        company_id_col = sample.columns[0]
        logger.warning(f"No company_id column found, using {company_id_col}")
    
    logger.info(f"Mapping: company_id={company_id_col}, name={name_col}")
    
    total_rows = 0
    kept_rows = 0
    first_chunk = True

    for chunk in tqdm(pd.read_csv(input_file, sep="\t", chunksize=CHUNKSIZE, low_memory=False),
                      desc="Clean companies"):
        total_rows += len(chunk)
        
        clean_chunk = pd.DataFrame()
        clean_chunk['company_id'] = chunk[company_id_col] if company_id_col else None
        clean_chunk['name'] = chunk[name_col] if name_col else "Unknown"

        clean_chunk = clean_chunk.dropna(subset=["company_id", "name"])
        clean_chunk["name"] = clean_chunk["name"].astype(str).str.strip()
        clean_chunk = clean_chunk[clean_chunk["name"] != ""]

        kept_rows += len(clean_chunk)
        clean_chunk.to_csv(output_file, mode="a", header=first_chunk, index=False)
        first_chunk = False

    logger.info(f"Companies: processed {total_rows:,} rows, kept {kept_rows:,} rows.")


def clean_relationships():
    """Join patent_inventor and patent_assignee -> clean_relationships.csv"""
    # Look for relationship files (could have different names)
    inv_file_candidates = [
        RAW_DIR / "g_patent_inventor_disambiguated.tsv",
        RAW_DIR / "g_patent_inventor.tsv",
        RAW_DIR / "g_persistent_inventor.tsv"
    ]
    
    ass_file_candidates = [
        RAW_DIR / "g_patent_assignee_disambiguated.tsv",
        RAW_DIR / "g_patent_assignee.tsv",
        RAW_DIR / "g_persistent_assignee.tsv"
    ]
    
    inv_file = None
    for candidate in inv_file_candidates:
        if candidate.exists():
            inv_file = candidate
            break
    
    ass_file = None
    for candidate in ass_file_candidates:
        if candidate.exists():
            ass_file = candidate
            break
    
    out_file = CLEAN_DIR / "clean_relationships.csv"
    
    if out_file.exists():
        logger.info("clean_relationships.csv already exists, skipping.")
        return
    
    if not inv_file:
        logger.warning("No inventor relationship file found. Creating empty relationships file.")
        pd.DataFrame(columns=['patent_id', 'inventor_id', 'company_id']).to_csv(out_file, index=False)
        return

    logger.info(f"Using inventor relationships: {inv_file.name}")
    if ass_file:
        logger.info(f"Using assignee relationships: {ass_file.name}")

    # Load all patent-inventor links
    inv_df = pd.read_csv(inv_file, sep="\t")
    # Find correct column names
    patent_col = 'patent_id' if 'patent_id' in inv_df.columns else inv_df.columns[0]
    inventor_col = 'inventor_id' if 'inventor_id' in inv_df.columns else inv_df.columns[1]
    
    inv_df = inv_df.rename(columns={patent_col: 'patent_id', inventor_col: 'inventor_id'})
    inv_df = inv_df[['patent_id', 'inventor_id']].dropna()

    # Load assignee relationships if available
    if ass_file:
        ass_df = pd.read_csv(ass_file, sep="\t")
        patent_col2 = 'patent_id' if 'patent_id' in ass_df.columns else ass_df.columns[0]
        assignee_col = 'assignee_id' if 'assignee_id' in ass_df.columns else ass_df.columns[1]
        
        ass_df = ass_df.rename(columns={patent_col2: 'patent_id', assignee_col: 'company_id'})
        ass_df = ass_df[['patent_id', 'company_id']].dropna()
        
        # Merge
        merged = inv_df.merge(ass_df, on="patent_id", how="left")
    else:
        merged = inv_df.copy()
        merged['company_id'] = None

    merged.to_csv(out_file, index=False)
    logger.info(f"Relationships: {len(merged):,} rows")


def main():
    """Run all cleaning steps in order."""
    logger.info("Starting data cleaning (chunked processing).")
    clean_patents()
    clean_inventors()
    clean_companies()
    clean_relationships()
    logger.info("Cleaning completed.")


if __name__ == "__main__":
    main()