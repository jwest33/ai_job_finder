"""
VLM Prompts for Glassdoor scraper.

Provides prompts for captcha solving and other VLM interactions.
"""

# Simple captcha solving prompt (used when captcha is detected)
CAPTCHA_SOLVE_PROMPT = """You are looking at a captcha or security verification page.

Your task is to solve the captcha so the page can continue loading.

LOOK FOR AND HANDLE:
1. **Checkbox**: If you see "I'm not a robot" or similar checkbox, click it
2. **Image Selection**: If asked to select images (e.g., "Select all traffic lights"):
   - Read the instructions carefully
   - Click on ALL matching images
   - Click "Verify" or "Submit" when done
3. **Puzzle**: If there's a sliding puzzle or similar, solve it
4. **Button**: After solving, click any "Continue", "Verify", or "Submit" button

IMPORTANT:
- Take your time with image selections - accuracy matters
- If you see multiple rounds, complete all of them
- The captcha might refresh if you're too slow - work steadily
- Look for any "Skip" option if available

When the captcha is solved and you see the normal website, respond with DONE.
"""


# Alternative prompts for different captcha types
CLOUDFLARE_PROMPT = """You are on a Cloudflare security check page.

This page is verifying you are human. Common patterns:
1. Wait for automatic verification (page may auto-proceed)
2. Click a checkbox if one appears
3. Complete any challenge that appears

Just wait and observe. If a checkbox or challenge appears, complete it.
When the page changes to show normal content, respond with DONE.
"""


# Legacy stage prompts (kept for potential future use with state manager)
from .vlm_state_manager import WorkflowStage

NAVIGATE_PROMPT = """You are automating a web browser to search for jobs on Glassdoor.

CURRENT STATE:
- URL: {current_url}
- Page title: {page_title}

GOAL: Verify you are on the Glassdoor job search page.

INSTRUCTIONS:
1. Look at the current page
2. If you see a job search form (keyword input, location input), respond with DONE
3. If you see a captcha or "verify you are human" challenge, solve it first
4. If you see a login prompt or popup, close it or dismiss it
5. If the page is still loading, wait a moment

Previous actions: {previous_actions}

When the search form is visible and ready, respond with action type DONE.
"""

SEARCH_PROMPT = """You are on Glassdoor's job search page.

CURRENT STATE:
- URL: {current_url}
- Search term to enter: {search_term}
- Location to enter: {location}

GOAL: Search for "{search_term}" jobs in "{location}".

INSTRUCTIONS:
1. Find the job title/keyword input field (usually says "Job title, keywords, or company")
2. Click on it to focus
3. Clear any existing text and type: {search_term}
4. Find the location input field (usually says "Location")
5. Click on it to focus
6. Clear any existing text and type: {location}
7. Click the search button OR press Enter to submit

IMPORTANT:
- If you see an autocomplete dropdown, you can ignore it or click away
- If you see job listings already, the search may have auto-submitted - respond with DONE
- If a captcha appears, solve it first

Previous actions: {previous_actions}

When you see job search results (job cards/listings), respond with action type DONE.
"""

HANDLE_CAPTCHA_PROMPT = """You are looking at a captcha or security verification page.

CURRENT STATE:
- URL: {current_url}
- Page title: {page_title}

GOAL: Solve the captcha/verification to continue.

INSTRUCTIONS:
1. Look for a checkbox (like "I'm not a robot") and click it
2. If there's an image selection challenge:
   - Read the instructions carefully (e.g., "Select all images with traffic lights")
   - Click on all matching images
   - Click "Verify" or "Submit" when done
3. If there's a puzzle to solve, complete it
4. If you see a "Continue" or "Proceed" button after verification, click it

IMPORTANT:
- Take your time with image selections
- If you fail, the captcha may reset - try again
- Some captchas have multiple rounds

Previous actions: {previous_actions}

When the captcha is solved and you see the regular page, respond with DONE.
"""

SCROLL_RESULTS_PROMPT = """You are viewing job search results on Glassdoor.

CURRENT STATE:
- URL: {current_url}
- Jobs found so far: {jobs_found}

GOAL: Scroll through results to load more jobs.

INSTRUCTIONS:
1. Scroll down the page to load more job listings
2. Look for a "Show more jobs" or "Load more" button and click it if visible
3. Wait for new jobs to load after scrolling
4. Continue until you've loaded enough jobs or reached the end

IMPORTANT:
- Don't click on individual job listings (we'll extract data separately)
- If you see pagination (page numbers), you can click to load more pages
- If a popup appears, dismiss it

Previous actions: {previous_actions}

After scrolling to load more jobs, respond with DONE.
"""

EXTRACT_PROMPT = """You are viewing job search results on Glassdoor.

CURRENT STATE:
- URL: {current_url}
- Jobs found so far: {jobs_found}

GOAL: The job listings are now visible. Signal that extraction can begin.

INSTRUCTIONS:
1. Verify that job listings/cards are visible on the page
2. If you see job cards with titles and company names, respond with DONE
3. If the page is still loading, wait a moment

NOTE: You don't need to extract the data yourself - just confirm the listings are visible.

Respond with DONE when job listings are visible and ready for extraction.
"""


def get_glassdoor_workflow_stages() -> list[WorkflowStage]:
    """
    Get the workflow stages for Glassdoor job search.

    Returns:
        List of WorkflowStage objects defining the workflow
    """
    return [
        WorkflowStage(
            name="NAVIGATE",
            goal="Verify Glassdoor search page is loaded and ready",
            prompt_template=NAVIGATE_PROMPT,
            max_actions=5,
            timeout_seconds=30,
            retry_count=2,
            next_stage="SEARCH",
        ),
        WorkflowStage(
            name="SEARCH",
            goal="Enter search terms and submit job search",
            prompt_template=SEARCH_PROMPT,
            max_actions=15,
            timeout_seconds=60,
            retry_count=2,
            next_stage="SCROLL_RESULTS",
        ),
        WorkflowStage(
            name="HANDLE_CAPTCHA",
            goal="Solve any captcha or verification challenge",
            prompt_template=HANDLE_CAPTCHA_PROMPT,
            max_actions=20,
            timeout_seconds=120,
            retry_count=3,
            next_stage="SEARCH",
            # Skip if no captcha detected
            skip_condition=lambda mgr: not mgr._has_captcha(),
        ),
        WorkflowStage(
            name="SCROLL_RESULTS",
            goal="Scroll to load more job listings",
            prompt_template=SCROLL_RESULTS_PROMPT,
            max_actions=10,
            timeout_seconds=60,
            retry_count=1,
            next_stage="EXTRACT",
        ),
        WorkflowStage(
            name="EXTRACT",
            goal="Confirm job listings are visible for extraction",
            prompt_template=EXTRACT_PROMPT,
            max_actions=3,
            timeout_seconds=30,
            retry_count=1,
            next_stage=None,
        ),
    ]


def get_simplified_workflow_stages() -> list[WorkflowStage]:
    """
    Get a simplified workflow for testing (skip scrolling).

    Returns:
        List of WorkflowStage objects
    """
    return [
        WorkflowStage(
            name="NAVIGATE",
            goal="Verify Glassdoor search page is loaded",
            prompt_template=NAVIGATE_PROMPT,
            max_actions=5,
            timeout_seconds=30,
            retry_count=2,
        ),
        WorkflowStage(
            name="SEARCH",
            goal="Enter search terms and submit",
            prompt_template=SEARCH_PROMPT,
            max_actions=15,
            timeout_seconds=60,
            retry_count=2,
        ),
        WorkflowStage(
            name="EXTRACT",
            goal="Confirm job listings are visible",
            prompt_template=EXTRACT_PROMPT,
            max_actions=3,
            timeout_seconds=30,
            retry_count=1,
        ),
    ]
