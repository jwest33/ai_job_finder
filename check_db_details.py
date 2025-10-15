#!/usr/bin/env python3
"""Check when jobs were added to tracker"""

import sqlite3
import json
from pathlib import Path
from collections import Counter

# Connect to database
db_path = Path("profiles/default/data/job_tracker.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get schema
cursor.execute("PRAGMA table_info(processed_jobs)")
columns = cursor.fetchall()
print("Database schema:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Load Indeed jobs from file
indeed_file = Path("profiles/default/data/jobs_indeed_latest.json")
with open(indeed_file, 'r', encoding='utf-8') as f:
    indeed_jobs = json.load(f)

# Check when these jobs were added
sample_url = indeed_jobs[0]['job_url']
cursor.execute("""
    SELECT job_url, job_title, match_score, first_seen, last_seen, times_seen
    FROM processed_jobs
    WHERE job_url = ?
""", (sample_url,))
row = cursor.fetchone()
if row:
    print(f"\nSample job details:")
    print(f"  URL: {row[0]}")
    print(f"  Title: {row[1]}")
    print(f"  Match Score: {row[2]}")
    print(f"  First Seen: {row[3]}")
    print(f"  Last Seen: {row[4]}")
    print(f"  Times Seen: {row[5]}")

# Check match scores distribution for Indeed jobs
match_scores = []
for job in indeed_jobs[:20]:  # Check first 20
    url = job['job_url']
    cursor.execute("SELECT match_score FROM processed_jobs WHERE job_url = ?", (url,))
    result = cursor.fetchone()
    if result:
        match_scores.append(result[0])

print(f"\nMatch scores for sample of Indeed jobs:")
score_counts = Counter(match_scores)
for score, count in sorted(score_counts.items()):
    print(f"  Score {score}: {count} jobs")

# Check if there's a "source" field
cursor.execute("PRAGMA table_info(processed_jobs)")
columns = [col[1] for col in cursor.fetchall()]
if 'source' in columns:
    cursor.execute("SELECT COUNT(*) FROM processed_jobs WHERE source = 'indeed'")
    indeed_count = cursor.fetchone()[0]
    print(f"\nIndeed jobs in database (by source field): {indeed_count}")

conn.close()
