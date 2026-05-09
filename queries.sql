-- ============================================================
-- Project: Global Patent Intelligence Data Pipeline
-- Author:  Opiyo Oscar | Student: 2300701330
-- Course:  Cloud Computing & Big Data Analytics
-- All 7 required analytics queries
-- ============================================================

-- Q1: Top Inventors (who has the most patents?)
-----------------------------------------
SELECT i.name, i.country, COUNT(DISTINCT r.patent_id) AS patent_count
FROM inventors i
JOIN patent_relationships r ON i.inventor_id = r.inventor_id
GROUP BY i.inventor_id
ORDER BY patent_count DESC
LIMIT 20;

-- Q2: Top Companies (which companies own the most patents?)
-----------------------------------------
SELECT c.name, COUNT(DISTINCT r.patent_id) AS patent_count
FROM companies c
JOIN patent_relationships r ON c.company_id = r.company_id
GROUP BY c.company_id
ORDER BY patent_count DESC
LIMIT 20;

-- Q3: Top Countries by patent production
-----------------------------------------
SELECT i.country, COUNT(DISTINCT r.patent_id) AS patent_count,
       ROUND(100.0 * COUNT(DISTINCT r.patent_id) / 
             (SELECT COUNT(*) FROM patents), 2) AS share_pct
FROM inventors i
JOIN patent_relationships r ON i.inventor_id = r.inventor_id
WHERE i.country IS NOT NULL AND i.country != ''
GROUP BY i.country
ORDER BY patent_count DESC
LIMIT 20;

-- Q4: Yearly Trends (patents per year)
-----------------------------------------
SELECT year, COUNT(*) AS patent_count
FROM patents
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year;

-- Q5: JOIN Query (patents + inventors + companies)
-----------------------------------------
SELECT p.patent_id, p.title, p.year,
       i.name AS inventor_name, i.country,
       c.name AS company_name
FROM patents p
JOIN patent_relationships r ON p.patent_id = r.patent_id
JOIN inventors i            ON r.inventor_id = i.inventor_id
LEFT JOIN companies c       ON r.company_id = c.company_id
LIMIT 1000;

-- Q6: CTE Query (prolific inventors with top company)
-----------------------------------------
WITH prolific AS (
    SELECT i.inventor_id, i.name, i.country,
           COUNT(DISTINCT r.patent_id) AS patent_count
    FROM inventors i
    JOIN patent_relationships r ON i.inventor_id = r.inventor_id
    GROUP BY i.inventor_id
    HAVING patent_count >= 10
),
top_companies AS (
    SELECT r.inventor_id, c.name AS top_company,
           COUNT(*) AS collab_count
    FROM patent_relationships r
    JOIN companies c ON r.company_id = c.company_id
    GROUP BY r.inventor_id, c.company_id
)
SELECT p.name, p.country, p.patent_count, tc.top_company
FROM prolific p
LEFT JOIN top_companies tc ON p.inventor_id = tc.inventor_id
ORDER BY p.patent_count DESC
LIMIT 50;

-- Q7: Ranking Query (window function: rank inventors within each country)
-----------------------------------------
WITH inventor_stats AS (
    SELECT i.country, i.name,
           COUNT(DISTINCT r.patent_id) AS patent_count
    FROM inventors i
    JOIN patent_relationships r ON i.inventor_id = r.inventor_id
    WHERE i.country IS NOT NULL AND i.country != ''
    GROUP BY i.inventor_id
),
ranked AS (
    SELECT country, name, patent_count,
           RANK() OVER (PARTITION BY country ORDER BY patent_count DESC) AS country_rank
    FROM inventor_stats
)
SELECT country, name, patent_count, country_rank
FROM ranked
WHERE country_rank <= 5
ORDER BY country, country_rank;