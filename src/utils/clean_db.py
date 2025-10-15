import sqlite3
from datetime import datetime

# Function to clean a database
def clean_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get count before deletion
    cursor.execute('SELECT COUNT(*) FROM processed_jobs WHERE report_date >= ? AND report_date < ?',
                ('2025-10-14 00:00:00', '2025-10-16 00:00:00'))
    count_before = cursor.fetchone()[0]

    # Delete all entries from Oct 15, 2025
    cursor.execute('DELETE FROM processed_jobs WHERE report_date >= ? AND report_date < ?',
                ('2025-10-14 00:00:00', '2025-10-16 00:00:00'))

    conn.commit()

    # Get count after deletion
    cursor.execute('SELECT COUNT(*) FROM processed_jobs')
    count_after = cursor.fetchone()[0]

    conn.close()

    return count_before, count_after

# Clean default profile
print('Cleaning default profile database...')
before, after = clean_database('profiles/default/data/job_tracker.db')
print(f'  Deleted {before} entries from Oct 15')
print(f'  Remaining entries: {after}')

# Clean ai-engineer profile
print('\nCleaning ai-engineer profile database...')
before, after = clean_database('profiles/ai-engineer/data/job_tracker.db')
print(f'  Deleted {before} entries from Oct 15')
print(f'  Remaining entries: {after}')

print('\n[SUCCESS] Database cleanup complete')
