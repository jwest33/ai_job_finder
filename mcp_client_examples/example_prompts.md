# MCP Server Example Prompts

Example prompts for interacting with the Job Search MCP server through an LLM.

## Profile Management

### List and View Profiles
```
Show me all my job search profiles
```

```
What profiles do I have and which one is active?
```

```
Give me detailed information about the "ai-engineer" profile
```

### Create Profiles
```
Create a new profile called "senior-software-engineer" for searching senior software engineering positions
```

```
Clone my "default" profile to create a new one called "data-scientist" for data science roles
```

### Switch and Manage Profiles
```
Switch to the "ai-engineer" profile
```

```
Delete the "old-profile" profile
```

```
Show me statistics for all my profiles
```

## Job Searching

### Configure and Run Searches
```
Show me the current scraper configuration
```

```
Run a job search for "machine learning engineer" positions in "Remote" and "San Francisco, CA"
```

```
Search for Python developer jobs remotely with 100 results per search
```

```
Do a dry run of searching for "senior data scientist" in "New York, NY" to see what would happen
```

### Test Proxy
```
Test the proxy connection to make sure it's working
```

## Job Matching

### Run AI Matching
```
Run the full matching pipeline on the latest Indeed jobs
```

```
Score the latest jobs against my resume
```

```
Retry the failed jobs from the scoring stage with higher temperature
```

### View Statistics
```
Show me my job tracker statistics
```

```
What failures have occurred during job processing?
```

## Template Management

### View and Validate Templates
```
List my current resume and requirements templates
```

```
Validate my resume and requirements files
```

### Update Configuration
```
Update the scraper configuration to use 5 results per search
```

```
Set the matcher to use 8 threads for faster processing
```

## System Operations

### Health Checks
```
Run a system health check to make sure everything is configured correctly
```

```
Show me the MCP server configuration
```

### Environment Variables
```
What is the current value of MATCH_THREADS?
```

```
Set LLAMA_TEMPERATURE to 0.4
```

## Resources

### Access Data
```
Get the resume for the "default" profile
```

```
Show me the requirements YAML for the "ai-engineer" profile
```

```
Get the latest scraped jobs from Indeed
```

```
Show me the matched jobs for the current profile
```

```
What are the job tracker statistics for the "default" profile?
```

### Configuration
```
Show me all environment variables (non-sensitive)
```

```
What is the active profile configuration?
```

```
Show me the current scraper settings
```

## Complex Workflows

### Complete Job Search Workflow
```
I want to search for AI engineer positions. Here's what I need:

1. Create a new profile called "ai-engineer"
2. Switch to that profile
3. Run a job search for "ai engineer" and "machine learning engineer" in "Remote"
4. Run the full matching pipeline on those results
5. Show me the top matches

Can you do all of that?
```

### Profile Comparison
```
Compare the statistics between my "default" and "ai-engineer" profiles. Which one has found more high-scoring matches?
```

### Configuration Optimization
```
My job matching is running slow. Check my current matcher configuration and suggest optimizations
```

### Error Recovery
```
I see there were failures during job processing. Can you:
1. Show me the failure statistics
2. Retry the failed jobs with adjusted settings
3. Check if the retries succeeded
```

## Tips for LLM Interaction

### Be Specific
- Specify profile names when working with multiple profiles
- Provide job titles and locations explicitly
- Mention score thresholds for filtering

### Ask for Summaries
```
Summarize the job tracker statistics in a easy-to-read format
```

```
Give me a summary of what would happen if I run this search, including bandwidth estimates
```

### Chain Operations
```
First switch to the "senior-swe" profile, then run a search for senior software engineer jobs, then match them, then show me jobs scoring above 85
```

### Error Handling
```
If the search fails, can you diagnose what went wrong and suggest fixes?
```

### Get Recommendations
```
Based on my current configuration and recent job matches, what search parameters would you recommend for finding more relevant positions?
```

## Advanced Use Cases

### Multi-Profile Workflow
```
I want to run searches for three different career paths:
1. Software engineer positions (use default profile)
2. AI engineer positions (use ai-engineer profile)
3. Data scientist positions (create new profile if needed)

Can you handle all three searches and give me a summary of the best matches from each?
```

### Automated Daily Run
```
Run my daily job search routine:
1. Search for new jobs on all configured job boards
2. Match them against my resume
3. Show me any new high-scoring matches (>85)
4. Email me the results
```

### Configuration Audit
```
Review my entire system configuration and identify any issues or optimization opportunities
```

### Data Analysis
```
Analyze my job tracker database and tell me:
- How many unique companies have I seen?
- What's my average match score?
- Which job titles tend to score highest?
- What skills appear most frequently in high-scoring jobs?
```
