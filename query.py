import duckdb

# Connect to an in-memory database (data is lost when the program ends)
# or specify a file path (e.g., "my_database.duckdb") for persistence.
conn = duckdb.connect('profiles/default/data/jobs.duckdb')

# Run a SQL query
# results = conn.sql("SELECT table_name FROM information_schema.tables").fetchall()

results = conn.sql("SELECT * FROM jobs limit 10").fetchall()

print(results)
# Output: [(42,)]
