# add_indexes.py
import sqlite3

conn = sqlite3.connect("patents.db")
cursor = conn.cursor()

print("Adding indexes for faster queries...")

# Index on frequently searched columns
indexes = [
    "CREATE INDEX IF NOT EXISTS idx_inventors_name ON inventors(name)",
    "CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)",
    "CREATE INDEX IF NOT EXISTS idx_patents_year ON patents(year)",
    "CREATE INDEX IF NOT EXISTS idx_relationships_patent_inventor ON patent_relationships(patent_id, inventor_id)",
]

for idx in indexes:
    try:
        cursor.execute(idx)
        print(f"  ✓ {idx.split('ON')[1].strip()}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

conn.commit()
conn.close()
print("\n✅ Indexes added! Queries will be faster now.")