-- ============================================================
-- Project: Global Patent Intelligence Data Pipeline
-- Author:  Opiyo Oscar
-- Student: 2300701330 | Reg: 2300701330
-- Course:  Cloud Computing and Big Data Analytics
-- University: Makerere University
-- ============================================================

DROP TABLE IF EXISTS patents;
CREATE TABLE patents (
  patent_id   TEXT PRIMARY KEY,
  title       TEXT,
  abstract    TEXT,
  filing_date TEXT,
  year        INTEGER
);
DROP TABLE IF EXISTS inventors;
CREATE TABLE inventors (
  inventor_id TEXT PRIMARY KEY,
  name        TEXT,
  country     TEXT
);
DROP TABLE IF EXISTS companies;
CREATE TABLE companies (
  company_id TEXT PRIMARY KEY,
  name       TEXT
);
DROP TABLE IF EXISTS patent_relationships;
CREATE TABLE patent_relationships (
  patent_id   TEXT,
  inventor_id TEXT,
  company_id  TEXT
);
-- Performance indexes
CREATE INDEX idx_rel_patent ON patent_relationships(patent_id);
CREATE INDEX idx_rel_inventor ON patent_relationships(inventor_id);
CREATE INDEX idx_rel_company ON patent_relationships(company_id);
CREATE INDEX idx_patents_year ON patents(year);
CREATE INDEX idx_inv_country ON inventors(country);