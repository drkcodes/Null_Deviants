import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "weatherguard.db"

print("=" * 70)
print("SKYGUARDAI — PRESENTATION RESET")
print("=" * 70)

if not DB_PATH.exists():
    print(f"ERROR: Database not found: {DB_PATH}")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Show current state
cursor.execute("SELECT COUNT(*) FROM readings")
before_total = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*)
    FROM readings
    WHERE anomaly = 1
""")
before_anomalies = cursor.fetchone()[0]

print(f"Current readings  : {before_total}")
print(f"Current anomalies : {before_anomalies}")
print()

# ------------------------------------------------------------------
# IMPORTANT:
# The benchmark/history data is from 2025.
# simulate.py uses the CURRENT timestamp for live replay.
#
# Therefore we remove only 2026/current simulator records.
# This preserves:
#   - 2025 seven-day benchmark history
#   - benchmark anomaly records
#   - Demo Center benchmark results
# ------------------------------------------------------------------

cursor.execute("""
    DELETE FROM readings
    WHERE source = 'live'
""")

deleted = cursor.rowcount

conn.commit()

# Final state
cursor.execute("SELECT COUNT(*) FROM readings")
after_total = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*)
    FROM readings
    WHERE source = 'live'
      AND anomaly = 1
""")
after_anomalies = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(DISTINCT station_id)
    FROM readings
""")
stations = cursor.fetchone()[0]

conn.close()

print("Presentation cleanup completed.")
print()
print(f"Live/current records removed : {deleted}")
print(f"Remaining readings           : {after_total}")
print(f"Remaining benchmark anomalies: {after_anomalies}")
print(f"Stations represented         : {stations}")
print()
print("7-day benchmark history was preserved.")
print("Demo Center benchmark records were preserved.")
print("=" * 70)