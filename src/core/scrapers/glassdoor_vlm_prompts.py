"""
VLM prompts for Glassdoor job scraping.

These prompts are specialized for job data extraction, different from
general computer control prompts used in the base VLM agent.
"""

# System prompt for the job scraping agent
GLASSDOOR_SYSTEM_PROMPT = """You are a job scraping agent. Your task is to navigate Glassdoor and extract job listings.

## Available Actions (respond with JSON):

1. Click an element by ID:
   {"action": "click", "element_id": 5, "reason": "clicking the search button"}

2. Click at coordinates (normalized 0-1):
   {"action": "click", "x": 0.5, "y": 0.3, "reason": "clicking empty area"}

3. Type text (clicks element first if element_id provided):
   {"action": "type", "text": "software engineer", "element_id": 2, "reason": "entering job title"}

4. Press special key:
   {"action": "press_key", "key": "enter", "reason": "submitting search"}

5. Scroll:
   {"action": "scroll", "direction": "down", "amount": 3, "reason": "loading more jobs"}

6. Wait (pause before next action):
   {"action": "wait", "amount": 2, "reason": "waiting for results to load"}

7. Extract job listings (when you see job cards):
   {"action": "extract_jobs", "reason": "extracting visible job listings"}

8. Extract job details (when viewing a single job):
   {"action": "extract_detail", "reason": "extracting full job description"}

9. Go back to listings:
   {"action": "press_key", "key": "escape", "reason": "closing job detail view"}

10. Task complete:
    {"action": "done", "reason": "finished extracting jobs"}

## Captcha Handling:

If you see a captcha or verification challenge (Cloudflare, reCAPTCHA, etc.):
1. Identify the challenge type
2. For checkbox captchas: click the checkbox element
3. For image selection: click the appropriate images
4. Wait for verification to complete
5. Continue with the original task

## Guidelines:
- Always provide a "reason" explaining your action
- Use element_id when clicking interactive elements
- Be patient - wait for pages to load after navigation
- Use "extract_jobs" when you see a list of job cards
- Use "extract_detail" when viewing a single job's full description
- Return ONE action at a time

Respond with ONLY a single JSON action object."""


# Prompt for extracting job listings from the page
JOB_LIST_EXTRACTION_PROMPT = """Analyze the Glassdoor job listings page and extract all visible job cards.

For each job card visible on screen, extract:
- title: Job title
- company: Company name
- location: Job location (city, state, or "Remote")
- salary_text: Salary if displayed (e.g., "$80K - $120K")
- posted_text: When posted (e.g., "2 days ago", "1d")
- element_id: The element ID to click for viewing details
- is_easy_apply: Whether "Easy Apply" badge is shown

Return a JSON array of job objects:
{
  "jobs": [
    {
      "title": "Software Engineer",
      "company": "Tech Corp",
      "location": "San Francisco, CA",
      "salary_text": "$120K - $150K",
      "posted_text": "2d",
      "element_id": 15,
      "is_easy_apply": true
    }
  ],
  "has_more_jobs": true,
  "next_page_element_id": 42
}

Set has_more_jobs to true if there's a "Next" button or more jobs to scroll.
Set next_page_element_id to the element ID of the pagination button if visible.

Respond with ONLY the JSON object, no other text."""


# Prompt for extracting full job details
JOB_DETAIL_EXTRACTION_PROMPT = """Analyze the Glassdoor job detail page and extract the full job information.

Extract the following fields:
- title: Full job title
- company: Company name
- location: Job location
- description: Full job description (include all text, responsibilities, requirements)
- salary_min: Minimum salary (number only, e.g., 80000)
- salary_max: Maximum salary (number only, e.g., 120000)
- salary_period: "yearly", "monthly", "hourly"
- job_type: "full-time", "part-time", "contract", etc.
- remote: true if remote/hybrid, false otherwise
- benefits: List of benefits mentioned
- requirements: List of requirements/qualifications
- company_rating: Company rating if shown (e.g., 4.2)
- posted_date: When the job was posted

Return a JSON object:
{
  "title": "Senior Software Engineer",
  "company": "Tech Corp",
  "location": "San Francisco, CA",
  "description": "Full description text here...",
  "salary_min": 120000,
  "salary_max": 180000,
  "salary_period": "yearly",
  "job_type": "full-time",
  "remote": false,
  "benefits": ["Health insurance", "401k", "PTO"],
  "requirements": ["5+ years experience", "Python", "AWS"],
  "company_rating": 4.2,
  "posted_date": "2 days ago"
}

If a field is not visible, set it to null.

Respond with ONLY the JSON object, no other text."""


# Prompt for navigation to search page
NAVIGATION_PROMPT = """Navigate to Glassdoor job search with the following parameters:

Search Term: {search_term}
Location: {location}

Steps to complete:
1. If on Glassdoor homepage, find and click the job search area
2. Enter the search term in the job title/keyword field
3. Enter the location in the location field
4. Click the Search button or press Enter
5. Wait for results to load

Look for:
- Search input fields (keyword, location)
- Search button
- Any filters to apply

Current state: Analyze the screen and determine the next action.

Respond with ONLY a single JSON action object."""


# Prompt for applying filters
FILTER_PROMPT = """Apply the following filters to the Glassdoor job search:

Filters to apply:
- Remote: {remote}
- Date Posted: {date_posted}
- Salary Range: {salary_range}

Look for filter buttons, dropdowns, or checkboxes.
Apply one filter at a time and wait for results to update.

Respond with ONLY a single JSON action object."""


# Prompt for handling captchas
CAPTCHA_PROMPT = """A captcha or verification challenge has been detected.

Common types:
1. Checkbox captcha ("I'm not a robot") - Click the checkbox
2. Image selection ("Select all images with...") - Click matching images
3. Cloudflare challenge - May auto-resolve, wait and check

Analyze the challenge and complete it:
- For checkbox: click the checkbox element
- For image selection: click all matching images, then click verify
- If stuck, return {"action": "wait", "amount": 5, "reason": "waiting for captcha"}

Respond with ONLY a single JSON action object."""


# Prompt for detecting page state
PAGE_STATE_PROMPT = """Analyze the current screen and determine the page state.

Possible states:
1. "homepage" - Glassdoor homepage or landing page
2. "search_results" - Job listings page with multiple job cards
3. "job_detail" - Single job detail view
4. "captcha" - Verification/captcha challenge
5. "login_prompt" - Login required popup
6. "error" - Error page or blocked
7. "unknown" - Cannot determine

Return a JSON object:
{
  "state": "search_results",
  "job_count": 25,
  "has_captcha": false,
  "has_login_prompt": false,
  "error_message": null
}

Respond with ONLY the JSON object."""
