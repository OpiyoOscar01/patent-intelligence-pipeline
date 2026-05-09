#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330 | Reg: 2300701330
# Course:  Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
Download and extract the required PatentsView TSV files.
Downloads PatentsView zip files (including g_location for inventor countries), shows progress, extracts into raw_data/.
"""

import logging
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

# ---------- Configuration ----------
RAW_DIR = Path("raw_data")
RAW_DIR.mkdir(exist_ok=True)

# Actual PatentsView TSV zip URLs (verified 2025)
FILES = {
    "g_patent.tsv.zip": "https://s3.amazonaws.com/data.patentsview.org/download/g_patent.tsv.zip",
    "g_inventor_disambiguated.tsv.zip": "https://s3.amazonaws.com/data.patentsview.org/download/g_inventor_disambiguated.tsv.zip",
    "g_assignee_disambiguated.tsv.zip": "https://s3.amazonaws.com/data.patentsview.org/download/g_assignee_disambiguated.tsv.zip",
    "g_patent_inventor.tsv.zip": "https://s3.amazonaws.com/data.patentsview.org/download/g_patent_inventor.tsv.zip",
    "g_patent_assignee.tsv.zip": "https://s3.amazonaws.com/data.patentsview.org/download/g_patent_assignee.tsv.zip",
    "g_location_disambiguated.tsv.zip": "https://s3.amazonaws.com/data.patentsview.org/download/g_location_disambiguated.tsv.zip",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def download_file(url: str, dest_path: Path, retries: int = 3) -> None:
    """Download a file with streaming and a progress bar."""
    if dest_path.exists():
        logger.info(f"Skipping {dest_path.name} (already exists)")
        return

    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))
                with open(dest_path, "wb") as f, tqdm(
                    desc=dest_path.name,
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                ) as bar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bar.update(len(chunk))
                logger.info(f"Downloaded: {dest_path.name}")
                return
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            if attempt == retries - 1:
                raise


def extract_zip(zip_path: Path, extract_to: Path) -> None:
    """Extract a zip file, skip if already extracted."""
    extracted_marker = extract_to / f"{zip_path.stem}.done"
    if extracted_marker.exists():
        logger.info(f"Skipping extraction of {zip_path.name} (already extracted)")
        return

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    extracted_marker.touch()
    logger.info(f"Extracted: {zip_path.name} -> {extract_to}")


def main() -> None:
    """Download all required files and extract them."""
    logger.info("Starting download of PatentsView data files")
    for filename, url in FILES.items():
        zip_path = RAW_DIR / filename
        try:
            download_file(url, zip_path)
            extract_zip(zip_path, RAW_DIR)
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            raise
    logger.info("All files downloaded and extracted successfully.")


if __name__ == "__main__":
    main()