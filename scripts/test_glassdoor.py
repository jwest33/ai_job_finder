#!/usr/bin/env python3
"""
Test script for Glassdoor scrapers (VLM and GraphQL).

Run with: python scripts/test_glassdoor.py

Options:
  --vlm       Force VLM scraper (default)
  --graphql   Force GraphQL scraper
  --jobs N    Number of jobs to scrape (default: 5)
  --query Q   Search query (default: "software engineer")
  --location L Location (default: "Remote")
"""

import sys
# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import argparse
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def test_vlm_scraper(search_term: str, location: str, results_wanted: int):
    """Test the VLM-powered Glassdoor scraper."""
    print("=" * 60)
    print("VLM GLASSDOOR SCRAPER TEST")
    print("=" * 60)
    print(f"Search: '{search_term}' in '{location}'")
    print(f"Results wanted: {results_wanted}")
    print("=" * 60)

    scraper = None
    try:
        from src.core.scrapers.glassdoor_vlm import GlassdoorVLMScraper, close_singleton_browser

        print("\n[1/4] Initializing VLM scraper...")
        scraper = GlassdoorVLMScraper()

        if not scraper.vlm_available:
            print("[FAIL] VLM agent not available!")
            print("  Check that:")
            print("  - VLM_AGENT_PATH is correct in .env")
            print("  - llama-server is running with Qwen3-VL model")
            print("  - OmniParser models are downloaded")
            return False

        print("[OK] VLM agent loaded successfully")

        print("\n[2/4] Starting scrape...")
        print("  (Watch the browser window for visual automation)")
        print("-" * 40)

        start_time = time.time()
        jobs = scraper.scrape(
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
        )
        elapsed = time.time() - start_time

        print("-" * 40)
        print(f"\n[3/4] Scraping complete in {elapsed:.1f}s")
        print(f"  Jobs found: {len(jobs)}")

        if jobs:
            print("\n[4/4] Sample jobs extracted:")
            print("-" * 40)
            for i, job in enumerate(jobs[:5], 1):
                print(f"\nJob {i}:")
                print(f"  Title:    {job.title}")
                print(f"  Company:  {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Remote:   {job.remote}")
                if job.salary_min or job.salary_max:
                    print(f"  Salary:   ${job.salary_min:,.0f} - ${job.salary_max:,.0f} {job.salary_period}")
                if job.date_posted:
                    print(f"  Posted:   {job.date_posted}")
                if job.description:
                    desc_preview = job.description[:150].replace('\n', ' ')
                    print(f"  Desc:     {desc_preview}...")
                print(f"  URL:      {job.job_url}")

            print("\n" + "=" * 60)
            print("[SUCCESS] VLM scraper test passed!")
            print("=" * 60)
            return True
        else:
            print("\n[WARN] No jobs extracted")
            print("  This could mean:")
            print("  - Captcha blocked the scraper")
            print("  - VLM failed to parse the page")
            print("  - No jobs match the search")
            return False

    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        print("  Make sure VLM_AGENT_PATH is set correctly")
        return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            if scraper:
                scraper.close()
            # Close the singleton browser completely
            close_singleton_browser()
        except:
            pass


def test_graphql_scraper(search_term: str, location: str, results_wanted: int):
    """Test the GraphQL-based Glassdoor scraper."""
    print("=" * 60)
    print("GRAPHQL GLASSDOOR SCRAPER TEST")
    print("=" * 60)
    print(f"Search: '{search_term}' in '{location}'")
    print(f"Results wanted: {results_wanted}")
    print("=" * 60)

    try:
        from src.core.scrapers.glassdoor import GlassdoorScraper

        print("\n[1/4] Initializing GraphQL scraper...")
        scraper = GlassdoorScraper()
        print("[OK] GraphQL scraper initialized")

        print("\n[2/4] Starting scrape...")
        print("  (Uses Playwright + GraphQL API)")
        print("-" * 40)

        start_time = time.time()
        jobs = scraper.scrape(
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
        )
        elapsed = time.time() - start_time

        print("-" * 40)
        print(f"\n[3/4] Scraping complete in {elapsed:.1f}s")
        print(f"  Jobs found: {len(jobs)}")

        if jobs:
            print("\n[4/4] Sample jobs extracted:")
            print("-" * 40)
            for i, job in enumerate(jobs[:5], 1):
                print(f"\nJob {i}:")
                print(f"  Title:    {job.title}")
                print(f"  Company:  {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Remote:   {job.remote}")
                if job.salary_min or job.salary_max:
                    print(f"  Salary:   ${job.salary_min:,.0f} - ${job.salary_max:,.0f} {job.salary_period}")
                if job.date_posted:
                    print(f"  Posted:   {job.date_posted}")
                if job.description:
                    desc_preview = job.description[:150].replace('\n', ' ')
                    print(f"  Desc:     {desc_preview}...")
                print(f"  URL:      {job.job_url}")

            print("\n" + "=" * 60)
            print("[SUCCESS] GraphQL scraper test passed!")
            print("=" * 60)
            return True
        else:
            print("\n[WARN] No jobs extracted")
            print("  This likely means Cloudflare blocked the request")
            print("  Check for CF-103 or captcha errors above")
            return False

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            scraper.close()
        except:
            pass


def test_factory(search_term: str, location: str, results_wanted: int):
    """Test the scraper factory (auto-selects VLM or GraphQL)."""
    print("=" * 60)
    print("SCRAPER FACTORY TEST (AUTO-SELECT)")
    print("=" * 60)
    print(f"Search: '{search_term}' in '{location}'")
    print(f"Results wanted: {results_wanted}")
    print("=" * 60)

    scraper = None
    try:
        from src.core.scraper import get_glassdoor_scraper, cleanup_glassdoor_browser

        print("\n[1/4] Getting scraper from factory...")
        scraper = get_glassdoor_scraper()
        scraper_type = type(scraper).__name__
        print(f"[OK] Factory returned: {scraper_type}")

        print("\n[2/4] Starting scrape...")
        print("-" * 40)

        start_time = time.time()
        jobs = scraper.scrape(
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
        )
        elapsed = time.time() - start_time

        print("-" * 40)
        print(f"\n[3/4] Scraping complete in {elapsed:.1f}s")
        print(f"  Jobs found: {len(jobs)}")

        if jobs:
            print("\n[4/4] Sample jobs extracted:")
            print("-" * 40)
            for i, job in enumerate(jobs[:3], 1):
                print(f"\nJob {i}: {job.title} at {job.company}")
                print(f"        {job.location} | Remote: {job.remote}")

            print("\n" + "=" * 60)
            print(f"[SUCCESS] Factory test passed using {scraper_type}!")
            print("=" * 60)
            return True
        else:
            print("\n[WARN] No jobs extracted")
            return False

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            if scraper:
                scraper.close()
            # Cleanup Glassdoor browser
            cleanup_glassdoor_browser()
        except:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Test Glassdoor scrapers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/test_glassdoor.py --vlm
  python scripts/test_glassdoor.py --graphql --jobs 10
  python scripts/test_glassdoor.py --query "data scientist" --location "New York"
  python scripts/test_glassdoor.py --factory
        """
    )

    parser.add_argument(
        "--vlm",
        action="store_true",
        help="Test VLM-powered scraper (default)"
    )
    parser.add_argument(
        "--graphql",
        action="store_true",
        help="Test GraphQL-based scraper"
    )
    parser.add_argument(
        "--factory",
        action="store_true",
        help="Test scraper factory (auto-selects)"
    )
    parser.add_argument(
        "--jobs", "-n",
        type=int,
        default=5,
        help="Number of jobs to scrape (default: 5)"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default="software engineer",
        help="Search query (default: 'software engineer')"
    )
    parser.add_argument(
        "--location", "-l",
        type=str,
        default="Remote",
        help="Location (default: 'Remote')"
    )

    args = parser.parse_args()

    # Default to VLM if no scraper specified
    if not args.vlm and not args.graphql and not args.factory:
        args.vlm = True

    success = True

    if args.factory:
        success = test_factory(args.query, args.location, args.jobs)
    elif args.graphql:
        success = test_graphql_scraper(args.query, args.location, args.jobs)
    elif args.vlm:
        success = test_vlm_scraper(args.query, args.location, args.jobs)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
