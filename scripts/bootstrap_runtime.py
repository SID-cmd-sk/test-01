from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
for rel in ["data", "data/uploads", "data/jobs", "data/exports", "logs", "jobs/state", "samples/input"]:
    (ROOT / rel).mkdir(parents=True, exist_ok=True)

db = ROOT / "data" / "learning.db"
conn = sqlite3.connect(db)
conn.executescript((ROOT / "learning" / "schema.sql").read_text(encoding="utf-8"))
conn.close()
print("Bootstrap complete")
