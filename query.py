import duckdb

# Connect to an in-memory database (data is lost when the program ends)
# or specify a file path (e.g., "my_database.duckdb") for persistence.
conn = duckdb.connect('profiles\default\data\jobs.duckdb')

# Run a SQL query
#results = conn.sql("SELECT column_name FROM information_schema.columns where table_name = 'jobs'").fetchall()


results = conn.sql("select * FROM jobs where job_url not in ('https://www.indeed.com/viewjob?jk=8c406a9aee69a93f', 'https://www.glassdoor.com/job-listing/j?jl=1009983375395', 'https://www.glassdoor.com/job-listing/j?jl=1009982645824', 'https://www.glassdoor.com/job-listing/j?jl=1009978648613', 'https://www.glassdoor.com/job-listing/j?jl=1009974646429', 'https://www.glassdoor.com/job-listing/j?jl=1009974503263', 'https://www.glassdoor.com/job-listing/j?jl=1009972687027', 'https://www.glassdoor.com/job-listing/j?jl=1009971638344', 'https://www.glassdoor.com/job-listing/j?jl=1009964279741', 'https://www.glassdoor.com/job-listing/j?jl=1009958050124')").fetchall()


print(results)
# Output: [(42,)]

