#!/usr/bin/env python3
# ============================================================
# Project: Global Patent Intelligence Data Pipeline
# Author:  Opiyo Oscar
# Student: 2300701330
# Course: Cloud Computing and Big Data Analytics
# University: Makerere University
# ============================================================
"""
Generate Matplotlib charts from patents.db (reproducible, data-driven).
Run after: python store.py && python report.py
Usage: python generate_patent_outputs.py
"""

import logging
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DB_PATH = Path("patents.db")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _chart_style():
    for name in ("seaborn-v0_8-darkgrid", "seaborn-v0_8", "ggplot"):
        try:
            plt.style.use(name)
            return
        except OSError:
            continue


def _ensure_agg_tables(conn: sqlite3.Connection) -> None:
    """Pre-aggregate large relationship counts once (fast repeat queries on big DBs)."""
    conn.execute("DROP TABLE IF EXISTS temp_inventor_counts")
    conn.execute("DROP TABLE IF EXISTS temp_company_counts")
    conn.execute("DROP TABLE IF EXISTS temp_country_counts")
    conn.execute(
        """
        CREATE TEMP TABLE temp_inventor_counts AS
        SELECT inventor_id, COUNT(patent_id) AS patent_count
        FROM patent_relationships
        GROUP BY inventor_id
        """
    )
    conn.execute(
        """
        CREATE TEMP TABLE temp_company_counts AS
        SELECT company_id, COUNT(patent_id) AS patent_count
        FROM patent_relationships
        WHERE company_id IS NOT NULL
        GROUP BY company_id
        """
    )
    conn.execute("DROP TABLE IF EXISTS patent_country_pairs")
    conn.execute("DROP TABLE IF EXISTS temp_country_counts")
    conn.execute(
        """
        CREATE TEMP TABLE patent_country_pairs AS
        SELECT DISTINCT r.patent_id, TRIM(i.country) AS country
        FROM patent_relationships r
        JOIN inventors i ON r.inventor_id = i.inventor_id
        WHERE i.country IS NOT NULL AND TRIM(i.country) != '' AND TRIM(i.country) != 'Unknown'
        """
    )
    conn.execute(
        """
        CREATE TEMP TABLE temp_country_counts AS
        SELECT country, COUNT(*) AS patent_count
        FROM patent_country_pairs
        GROUP BY country
        """
    )


def load_frames(conn: sqlite3.Connection):
    total_patents = conn.execute("SELECT COUNT(*) FROM patents").fetchone()[0]
    _ensure_agg_tables(conn)

    top_inventors = pd.read_sql_query(
        """
        SELECT i.name, c.patent_count
        FROM temp_inventor_counts c
        JOIN inventors i ON c.inventor_id = i.inventor_id
        ORDER BY c.patent_count DESC
        LIMIT 15
        """,
        conn,
    )

    top_companies = pd.read_sql_query(
        """
        SELECT co.name, cc.patent_count
        FROM temp_company_counts cc
        JOIN companies co ON cc.company_id = co.company_id
        ORDER BY cc.patent_count DESC
        LIMIT 15
        """,
        conn,
    )

    countries = pd.read_sql_query(
        """
        SELECT country, patent_count
        FROM temp_country_counts
        ORDER BY patent_count DESC
        LIMIT 15
        """,
        conn,
    )

    yearly = pd.read_sql_query(
        """
        SELECT year, COUNT(*) AS patent_count
        FROM patents
        WHERE year IS NOT NULL AND year BETWEEN 1976 AND 2030
        GROUP BY year
        ORDER BY year
        """,
        conn,
    )

    return total_patents, top_inventors, top_companies, countries, yearly


def save_chart_top_inventors(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 8))
    take = df.head(10).iloc[::-1]
    colors = plt.cm.viridis(np.linspace(0, 0.9, len(take)))
    bars = ax.barh(range(len(take)), take["patent_count"], color=colors)
    labels = [n[:22] + "…" if len(str(n)) > 23 else str(n) for n in take["name"]]
    ax.set_yticks(range(len(take)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Patent count")
    ax.set_title("Top inventors by patent count", fontsize=14, fontweight="bold")
    for bar, val in zip(bars, take["patent_count"]):
        ax.text(val + max(take["patent_count"]) * 0.005, bar.get_y() + bar.get_height() / 2,
                f"{int(val):,}", va="center", fontsize=9)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_top_inventors.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_chart_top_companies(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 8))
    take = df.head(10).iloc[::-1]
    colors = plt.cm.plasma(np.linspace(0, 0.9, len(take)))
    bars = ax.barh(range(len(take)), take["patent_count"], color=colors)
    labels = [n[:28] + "…" if len(str(n)) > 29 else str(n) for n in take["name"]]
    ax.set_yticks(range(len(take)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Patent count")
    ax.set_title("Top companies by patent count", fontsize=14, fontweight="bold")
    for bar, val in zip(bars, take["patent_count"]):
        ax.text(val + max(take["patent_count"]) * 0.005, bar.get_y() + bar.get_height() / 2,
                f"{int(val):,}", va="center", fontsize=9)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_top_companies.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_chart_top_countries(df: pd.DataFrame, total_patents: int) -> None:
    fig, ax = plt.subplots(figsize=(12, 8))
    take = df.head(10).iloc[::-1]
    colors = plt.cm.RdYlGn(np.linspace(0, 1, len(take)))
    bars = ax.barh(range(len(take)), take["patent_count"], color=colors)
    ax.set_yticks(range(len(take)))
    ax.set_yticklabels(take["country"])
    ax.set_xlabel("Patent count (distinct via inventor links)")
    ax.set_title("Top countries by patent count", fontsize=14, fontweight="bold")
    denom = max(total_patents, 1)
    for bar, val in zip(bars, take["patent_count"]):
        pct = 100.0 * float(val) / denom
        ax.text(
            float(val) + max(take["patent_count"]) * 0.005,
            bar.get_y() + bar.get_height() / 2,
            f"{int(val):,} ({pct:.1f}%)",
            va="center",
            fontsize=9,
        )
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_top_countries.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_chart_yearly_trend(yearly: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(yearly["year"], yearly["patent_count"], "b-", lw=2)
    ax.fill_between(yearly["year"], yearly["patent_count"], alpha=0.25)
    ax.set_xlabel("Year")
    ax.set_ylabel("Patents granted (rows in patents table)")
    ax.set_title("Patent grants per year", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_yearly_trend.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_chart_yearly_growth(yearly: pd.DataFrame) -> None:
    if len(yearly) < 2:
        logger.warning("Not enough yearly rows for growth chart.")
        return
    years = yearly["year"].astype(int).tolist()
    counts = yearly["patent_count"].astype(float).tolist()
    growth_years = []
    rates = []
    for i in range(1, len(counts)):
        prev, cur = counts[i - 1], counts[i]
        growth_years.append(years[i])
        rates.append(0.0 if prev <= 0 else (cur - prev) / prev * 100.0)
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["green" if g >= 0 else "red" for g in rates]
    ax.bar(growth_years, rates, color=colors, alpha=0.75)
    ax.axhline(0, color="black", lw=1)
    ax.set_xlabel("Year")
    ax.set_ylabel("Year-over-year change (%)")
    ax.set_title("Year-over-year growth in patent counts", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_yearly_growth_rate.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_chart_country_pie(df: pd.DataFrame) -> None:
    top = df.head(8).copy()
    other = float(df.iloc[8:]["patent_count"].sum()) if len(df) > 8 else 0.0
    sizes = list(top["patent_count"].astype(float)) + ([other] if other > 0 else [])
    labels = list(top["country"]) + (["Other"] if other > 0 else [])
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = plt.cm.Set3(np.linspace(0, 1, max(len(sizes), 1)))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90, textprops={"fontsize": 9})
    ax.set_title("Share of top countries (by patent count)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_country_pie.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    if not DB_PATH.exists():
        logger.error("patents.db not found. Run store.py first.")
        return

    _chart_style()
    plt.rcParams["figure.figsize"] = (12, 8)
    plt.rcParams["font.size"] = 11

    conn = sqlite3.connect(str(DB_PATH))
    try:
        total_patents, top_inv, top_co, countries, yearly = load_frames(conn)
        logger.info("Rendering charts from database…")
        save_chart_top_inventors(top_inv)
        save_chart_top_companies(top_co)
        save_chart_top_countries(countries, total_patents)
        save_chart_yearly_trend(yearly)
        save_chart_yearly_growth(yearly)
        save_chart_country_pie(countries)
        logger.info("Saved PNG charts under %s/", OUTPUT_DIR.resolve())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
