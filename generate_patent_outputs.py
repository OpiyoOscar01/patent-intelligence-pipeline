#!/usr/bin/env python3
"""
Generate required patent pipeline outputs from pre-cleaned CSV files using low-memory,
chunked processing. Designed for laptops that cannot load multi-GB datasets at once.

Expected input files in clean_data/ (or a custom input dir):
- clean_patents.csv          columns: patent_id, title, abstract, filing_date, year
- clean_inventors.csv        columns: inventor_id, name, country
- clean_companies.csv        columns: company_id, name
- clean_relationships.csv    columns: patent_id, inventor_id, company_id

Outputs in outputs/:
1. top_inventors.csv
2. top_companies.csv
3. country_trends.csv
4. yearly_trends.csv
5. join_sample.csv
6. prolific_inventors.csv
7. ranked_inventors_by_country.csv
8. patent_report.json
9. chart_top_inventors.png
10. chart_top_companies.png
11. chart_top_countries.png
12. chart_yearly_trend.png
13. chart_yearly_growth_rate.png
14. chart_country_pie.png
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple

import matplotlib.pyplot as plt
import pandas as pd

# ---------- Config ----------
PATENT_CHUNK = 100_000
LOOKUP_CHUNK = 100_000
REL_DTYPE = {
    "patent_id": "string",
    "inventor_id": "string",
    "company_id": "string",
}

plt.style.use("ggplot")


# ---------- Helpers ----------
def safe_read_csv(path: Path, usecols=None, chunksize: Optional[int] = None, dtype=None):
    """Robust CSV reader with sane defaults for large files."""
    return pd.read_csv(
        path,
        usecols=usecols,
        chunksize=chunksize,
        dtype=dtype,
        encoding="utf-8",
        encoding_errors="ignore",
        low_memory=False,
    )


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def unique_count_from_counter(counter_like: Counter) -> int:
    return len(counter_like)


# ---------- Core processing ----------
def process_relationships(rel_path: Path):
    """
    Relationships file is small in the user's description (~10MB), so loading it once is OK.
    We still restrict columns and dtypes.
    """
    rel = pd.read_csv(rel_path, dtype=REL_DTYPE, low_memory=False)
    rel = rel[[c for c in ["patent_id", "inventor_id", "company_id"] if c in rel.columns]].copy()
    rel["patent_id"] = rel["patent_id"].astype("string").str.strip()
    rel["inventor_id"] = rel["inventor_id"].astype("string").str.strip()
    if "company_id" in rel.columns:
        rel["company_id"] = rel["company_id"].astype("string").str.strip()
    else:
        rel["company_id"] = pd.NA

    rel = rel.dropna(subset=["patent_id", "inventor_id"])
    rel = rel[(rel["patent_id"] != "") & (rel["inventor_id"] != "")]

    # Deduplicate to avoid inflated counts.
    rel = rel.drop_duplicates(subset=["patent_id", "inventor_id", "company_id"])

    inventor_counts = (
        rel[["inventor_id", "patent_id"]]
        .drop_duplicates()
        .groupby("inventor_id")["patent_id"]
        .nunique()
        .sort_values(ascending=False)
    )

    company_counts = (
        rel.dropna(subset=["company_id"])[["company_id", "patent_id"]]
        .drop_duplicates()
        .groupby("company_id")["patent_id"]
        .nunique()
        .sort_values(ascending=False)
    )

    sample_rel = rel.head(100).copy()

    return rel, inventor_counts, company_counts, sample_rel


def scan_patents(patent_path: Path, needed_patent_ids: Set[str]):
    total_patents = 0
    yearly_counts: Counter = Counter()
    patent_title_map: Dict[str, str] = {}

    for chunk in safe_read_csv(
        patent_path,
        usecols=["patent_id", "title", "year"],
        chunksize=PATENT_CHUNK,
        dtype={"patent_id": "string", "title": "string", "year": "Int64"},
    ):
        chunk["patent_id"] = chunk["patent_id"].astype("string").str.strip()
        chunk = chunk.dropna(subset=["patent_id"])
        chunk = chunk[chunk["patent_id"] != ""]
        total_patents += len(chunk)

        years = pd.to_numeric(chunk["year"], errors="coerce").dropna().astype(int)
        yearly_counts.update(years.tolist())

        if needed_patent_ids:
            sub = chunk[chunk["patent_id"].isin(needed_patent_ids)][["patent_id", "title"]]
            for row in sub.itertuples(index=False):
                patent_title_map[str(row.patent_id)] = "" if pd.isna(row.title) else str(row.title)

    return total_patents, yearly_counts, patent_title_map


def scan_inventors(
    inventor_path: Path,
    needed_inventor_ids: Set[str],
    inventor_counts: pd.Series,
):
    total_inventors = 0
    inventor_meta: Dict[str, Tuple[str, str]] = {}
    country_counts: Counter = Counter()
    country_rank_rows = []
    prolific_rows = []

    needed_count_lookup = inventor_counts.to_dict()

    for chunk in safe_read_csv(
        inventor_path,
        usecols=["inventor_id", "name", "country"],
        chunksize=LOOKUP_CHUNK,
        dtype={"inventor_id": "string", "name": "string", "country": "string"},
    ):
        total_inventors += len(chunk)
        chunk["inventor_id"] = chunk["inventor_id"].astype("string").str.strip()
        chunk = chunk.dropna(subset=["inventor_id"])
        chunk = chunk[chunk["inventor_id"] != ""]

        if needed_inventor_ids:
            sub = chunk[chunk["inventor_id"].isin(needed_inventor_ids)].copy()
        else:
            sub = chunk.iloc[0:0].copy()

        if sub.empty:
            continue

        sub["name"] = sub["name"].fillna("Unknown").astype(str).str.strip()
        sub["country"] = sub["country"].fillna("Unknown").astype(str).str.strip()
        sub.loc[sub["country"] == "", "country"] = "Unknown"
        sub.loc[sub["name"] == "", "name"] = "Unknown"
        sub["patent_count"] = sub["inventor_id"].map(needed_count_lookup).fillna(0).astype(int)

        for row in sub.itertuples(index=False):
            inventor_meta[str(row.inventor_id)] = (str(row.name), str(row.country))
            if row.country and row.country != "Unknown":
                country_counts[str(row.country)] += int(row.patent_count)
                country_rank_rows.append(
                    {
                        "country": str(row.country),
                        "inventor_name": str(row.name),
                        "patent_count": int(row.patent_count),
                    }
                )
            if int(row.patent_count) > 50:
                prolific_rows.append(
                    {
                        "name": str(row.name),
                        "patent_count": int(row.patent_count),
                        "country": str(row.country),
                    }
                )

    return total_inventors, inventor_meta, country_counts, country_rank_rows, prolific_rows


def scan_companies(company_path: Path, needed_company_ids: Set[str]):
    total_companies = 0
    company_meta: Dict[str, str] = {}

    for chunk in safe_read_csv(
        company_path,
        usecols=["company_id", "name"],
        chunksize=LOOKUP_CHUNK,
        dtype={"company_id": "string", "name": "string"},
    ):
        total_companies += len(chunk)
        chunk["company_id"] = chunk["company_id"].astype("string").str.strip()
        chunk = chunk.dropna(subset=["company_id"])
        chunk = chunk[chunk["company_id"] != ""]

        if needed_company_ids:
            sub = chunk[chunk["company_id"].isin(needed_company_ids)][["company_id", "name"]].copy()
            sub["name"] = sub["name"].fillna("Unknown").astype(str).str.strip()
            sub.loc[sub["name"] == "", "name"] = "Unknown"
            for row in sub.itertuples(index=False):
                company_meta[str(row.company_id)] = str(row.name)

    return total_companies, company_meta


# ---------- Output assembly ----------
def build_top_inventors(inventor_counts: pd.Series, inventor_meta: Dict[str, Tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for inventor_id, patent_count in inventor_counts.head(10).items():
        name, _country = inventor_meta.get(str(inventor_id), ("Unknown", "Unknown"))
        rows.append({"name": name, "patent_count": int(patent_count)})
    return pd.DataFrame(rows)



def build_top_companies(company_counts: pd.Series, company_meta: Dict[str, str]) -> pd.DataFrame:
    rows = []
    for company_id, patent_count in company_counts.head(10).items():
        rows.append({"name": company_meta.get(str(company_id), "Unknown"), "patent_count": int(patent_count)})
    return pd.DataFrame(rows)



def build_country_trends(country_counts: Counter) -> pd.DataFrame:
    rows = [{"country": k, "patent_count": int(v)} for k, v in country_counts.items()]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["country", "patent_count"])
    return df.sort_values(["patent_count", "country"], ascending=[False, True]).reset_index(drop=True)



def build_yearly_trends(yearly_counts: Counter) -> pd.DataFrame:
    rows = [{"year": int(y), "patent_count": int(c)} for y, c in yearly_counts.items() if not pd.isna(y)]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["year", "patent_count"])
    return df.sort_values("year").reset_index(drop=True)



def build_join_sample(sample_rel: pd.DataFrame, patent_title_map, inventor_meta, company_meta) -> pd.DataFrame:
    rows = []
    for row in sample_rel.itertuples(index=False):
        inventor_name, _country = inventor_meta.get(str(row.inventor_id), ("Unknown", "Unknown"))
        company_name = "Unknown"
        if not pd.isna(row.company_id):
            company_name = company_meta.get(str(row.company_id), "Unknown")
        rows.append(
            {
                "patent_id": str(row.patent_id),
                "title": patent_title_map.get(str(row.patent_id), ""),
                "inventor_name": inventor_name,
                "company_name": company_name,
                "year": pd.NA,
            }
        )
    df = pd.DataFrame(rows)
    return df



def attach_year_to_join_sample(df_join: pd.DataFrame, patent_path: Path) -> pd.DataFrame:
    if df_join.empty:
        return df_join
    needed_patent_ids = set(df_join["patent_id"].astype(str).tolist())
    year_map = {}
    for chunk in safe_read_csv(
        patent_path,
        usecols=["patent_id", "year"],
        chunksize=LOOKUP_CHUNK,
        dtype={"patent_id": "string", "year": "Int64"},
    ):
        chunk["patent_id"] = chunk["patent_id"].astype("string").str.strip()
        sub = chunk[chunk["patent_id"].isin(needed_patent_ids)][["patent_id", "year"]]
        for row in sub.itertuples(index=False):
            year_map[str(row.patent_id)] = None if pd.isna(row.year) else int(row.year)
    df_join["year"] = df_join["patent_id"].map(year_map)
    return df_join



def build_prolific_inventors(prolific_rows) -> pd.DataFrame:
    df = pd.DataFrame(prolific_rows)
    if df.empty:
        return pd.DataFrame(columns=["name", "patent_count", "country"])
    return df.sort_values(["patent_count", "name"], ascending=[False, True]).reset_index(drop=True)



def build_ranked_inventors_by_country(country_rank_rows) -> pd.DataFrame:
    df = pd.DataFrame(country_rank_rows)
    if df.empty:
        return pd.DataFrame(columns=["country", "inventor_name", "rank", "patent_count"])

    df = df.sort_values(["country", "patent_count", "inventor_name"], ascending=[True, False, True]).reset_index(drop=True)
    df["rank"] = df.groupby("country")["patent_count"].rank(method="dense", ascending=False).astype(int)
    df = df[df["rank"] <= 5].copy()
    return df[["country", "inventor_name", "rank", "patent_count"]].sort_values(
        ["country", "rank", "inventor_name"], ascending=[True, True, True]
    ).reset_index(drop=True)



def build_patent_report(
    total_patents: int,
    total_inventors: int,
    total_companies: int,
    top_inventors_df: pd.DataFrame,
    top_companies_df: pd.DataFrame,
    yearly_df: pd.DataFrame,
):
    top_inventor = {"name": None, "patents": None}
    top_company = {"name": None, "patents": None}

    if not top_inventors_df.empty:
        top_inventor = {
            "name": str(top_inventors_df.iloc[0]["name"]),
            "patents": int(top_inventors_df.iloc[0]["patent_count"]),
        }
    if not top_companies_df.empty:
        top_company = {
            "name": str(top_companies_df.iloc[0]["name"]),
            "patents": int(top_companies_df.iloc[0]["patent_count"]),
        }

    patents_by_year = {str(int(row.year)): int(row.patent_count) for row in yearly_df.itertuples(index=False)}

    return {
        "total_patents": int(total_patents),
        "total_inventors": int(total_inventors),
        "total_companies": int(total_companies),
        "top_inventor": top_inventor,
        "top_company": top_company,
        "patents_by_year": patents_by_year,
    }


# ---------- Charts ----------
def save_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str, out_path: Path, color: str = "steelblue"):
    if df.empty:
        return
    plt.figure(figsize=(12, 7))
    plt.bar(df[x_col].astype(str), df[y_col], color=color)
    plt.title(title)
    plt.xlabel(x_col.replace("_", " ").title())
    plt.ylabel(y_col.replace("_", " ").title())
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()



def save_line_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str, out_path: Path, color: str = "darkgreen"):
    if df.empty:
        return
    plt.figure(figsize=(12, 7))
    plt.plot(df[x_col], df[y_col], marker="o", markersize=3, linewidth=2, color=color, label=y_col.replace("_", " ").title())
    plt.title(title)
    plt.xlabel(x_col.replace("_", " ").title())
    plt.ylabel(y_col.replace("_", " ").title())
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()



def save_growth_chart(yearly_df: pd.DataFrame, out_path: Path):
    if yearly_df.empty:
        return
    df = yearly_df.copy()
    df["growth_rate_pct"] = df["patent_count"].pct_change() * 100
    plt.figure(figsize=(12, 7))
    plt.plot(df["year"], df["growth_rate_pct"], marker="o", markersize=3, linewidth=2, color="purple", label="Growth Rate %")
    plt.axhline(0, color="black", linewidth=1, linestyle="--")
    plt.title("Yearly Patent Growth Rate")
    plt.xlabel("Year")
    plt.ylabel("Growth Rate (%)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()



def save_country_pie(country_df: pd.DataFrame, out_path: Path):
    if country_df.empty:
        return
    top10 = country_df.head(10).copy()
    plt.figure(figsize=(10, 10))
    plt.pie(top10["patent_count"], labels=top10["country"], autopct="%1.1f%%", startangle=140)
    plt.title("Patent Share by Top 10 Countries")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="Generate patent analysis outputs from clean CSV files")
    parser.add_argument("--input-dir", default="clean_data", help="Directory containing clean CSV files")
    parser.add_argument("--output-dir", default="outputs", help="Directory to save output files")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    ensure_output_dir(output_dir)

    patent_path = input_dir / "clean_patents.csv"
    inventor_path = input_dir / "clean_inventors.csv"
    company_path = input_dir / "clean_companies.csv"
    rel_path = input_dir / "clean_relationships.csv"

    required = [patent_path, inventor_path, company_path, rel_path]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required input files:\n- " + "\n- ".join(missing))

    print("[1/6] Processing relationships...")
    rel, inventor_counts, company_counts, sample_rel = process_relationships(rel_path)

    sample_patent_ids = set(sample_rel["patent_id"].astype(str).tolist())
    sample_inventor_ids = set(sample_rel["inventor_id"].astype(str).tolist())
    sample_company_ids = set(sample_rel["company_id"].dropna().astype(str).tolist())

    top_inventor_ids = set(inventor_counts.head(10).index.astype(str).tolist())
    prolific_ids = set(inventor_counts[inventor_counts > 50].index.astype(str).tolist())
    ranked_ids = set(inventor_counts.index.astype(str).tolist())  # needed to rank by country accurately
    needed_inventor_ids = top_inventor_ids | prolific_ids | sample_inventor_ids | ranked_ids

    top_company_ids = set(company_counts.head(10).index.astype(str).tolist())
    needed_company_ids = top_company_ids | sample_company_ids

    print("[2/6] Scanning patents in chunks...")
    total_patents, yearly_counts, patent_title_map = scan_patents(patent_path, sample_patent_ids)

    print("[3/6] Scanning inventors in chunks...")
    total_inventors, inventor_meta, country_counts, country_rank_rows, prolific_rows = scan_inventors(
        inventor_path, needed_inventor_ids, inventor_counts
    )

    print("[4/6] Scanning companies in chunks...")
    total_companies, company_meta = scan_companies(company_path, needed_company_ids)

    print("[5/6] Building output tables...")
    top_inventors_df = build_top_inventors(inventor_counts, inventor_meta)
    top_companies_df = build_top_companies(company_counts, company_meta)
    country_trends_df = build_country_trends(country_counts)
    yearly_trends_df = build_yearly_trends(yearly_counts)
    join_sample_df = build_join_sample(sample_rel, patent_title_map, inventor_meta, company_meta)
    join_sample_df = attach_year_to_join_sample(join_sample_df, patent_path)
    prolific_df = build_prolific_inventors(prolific_rows)
    ranked_df = build_ranked_inventors_by_country(country_rank_rows)
    report_obj = build_patent_report(
        total_patents=total_patents,
        total_inventors=total_inventors,
        total_companies=total_companies,
        top_inventors_df=top_inventors_df,
        top_companies_df=top_companies_df,
        yearly_df=yearly_trends_df,
    )

    print("[6/6] Writing files and charts...")
    top_inventors_df.to_csv(output_dir / "top_inventors.csv", index=False)
    top_companies_df.to_csv(output_dir / "top_companies.csv", index=False)
    country_trends_df.to_csv(output_dir / "country_trends.csv", index=False)
    yearly_trends_df.to_csv(output_dir / "yearly_trends.csv", index=False)
    join_sample_df.to_csv(output_dir / "join_sample.csv", index=False)
    prolific_df.to_csv(output_dir / "prolific_inventors.csv", index=False)
    ranked_df.to_csv(output_dir / "ranked_inventors_by_country.csv", index=False)

    with open(output_dir / "patent_report.json", "w", encoding="utf-8") as f:
        json.dump(report_obj, f, indent=2, ensure_ascii=False)

    save_bar_chart(top_inventors_df, "name", "patent_count", "Top 10 Inventors by Patent Count", output_dir / "chart_top_inventors.png", color="royalblue")
    save_bar_chart(top_companies_df, "name", "patent_count", "Top 10 Companies by Patent Count", output_dir / "chart_top_companies.png", color="seagreen")
    save_bar_chart(country_trends_df.head(10), "country", "patent_count", "Top 10 Countries by Patent Count", output_dir / "chart_top_countries.png", color="darkorange")
    save_line_chart(yearly_trends_df, "year", "patent_count", "Yearly Patent Trend", output_dir / "chart_yearly_trend.png", color="firebrick")
    save_growth_chart(yearly_trends_df, output_dir / "chart_yearly_growth_rate.png")
    save_country_pie(country_trends_df, output_dir / "chart_country_pie.png")

    print("Done. Generated files:")
    for path in sorted(output_dir.iterdir()):
        print(f" - {path.name}")


if __name__ == "__main__":
    main()