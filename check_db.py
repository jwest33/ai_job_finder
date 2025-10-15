#!/usr/bin/env python3
"""Check job tracker database issue"""

import sqlite3
import json
from pathlib import Path

# Connect to database
db_path = Path("profiles/default/data/job_tracker.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get total in database
cursor.execute("SELECT COUNT(*) FROM processed_jobs")
total_db = cursor.fetchone()[0]
print(f"Total jobs in database: {total_db}")

# Load Indeed jobs from file
indeed_file = Path("profiles/default/data/jobs_indeed_latest.json")
with open(indeed_file, 'r', encoding='utf-8') as f:
    indeed_jobs = json.load(f)

print(f"Total Indeed jobs in file: {len(indeed_jobs)}")

# Check if Indeed URLs are in database
sample_url = indeed_jobs[0]['job_url']
print(f"\nSample URL from Indeed file:")
print(f"  {sample_url}")

cursor.execute("SELECT COUNT(*) FROM processed_jobs WHERE job_url = ?", (sample_url,))
is_tracked = cursor.fetchone()[0]
print(f"  Is this URL in database? {is_tracked > 0}")

# Count how many Indeed jobs are tracked
tracked_count = 0
for job in indeed_jobs:
    url = job['job_url']
    cursor.execute("SELECT COUNT(*) FROM processed_jobs WHERE job_url = ?", (url,))
    if cursor.fetchone()[0] > 0:
        tracked_count += 1

print(f"\nIndeed jobs already tracked: {tracked_count} out of {len(indeed_jobs)}")
print(f"Untracked Indeed jobs: {len(indeed_jobs) - tracked_count}")

# Check database URLs vs. current job URLs
cursor.execute("SELECT job_url FROM processed_jobs LIMIT 5")
db_urls = cursor.fetchall()
print(f"\nSample URLs in database:")
for url in db_urls:
    print(f"  {url[0]}")

print(f"\nSample URLs in Indeed file:")
for i in range(min(5, len(indeed_jobs))):
    print(f"  {indeed_jobs[i]['job_url']}")

conn.close()
