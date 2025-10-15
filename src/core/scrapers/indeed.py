"""
Indeed job board scraper using GraphQL API

This scraper uses Indeed's mobile GraphQL API which is more reliable
and has no rate limiting compared to web scraping.

Based on JobSpy by speedyapply: https://github.com/speedyapply/JobSpy
Copyright (c) 2023 Cullen Watson
Licensed under MIT License. See LICENSE-JOBSPY for details.
"""

import json
import os
import time
import random
import string
from typing import List, Optional, Dict, Any
from datetime import datetime
from markdownify import markdownify as md

try:
    import tls_client
except ImportError:
    raise ImportError(
        "tls-client is required for Indeed scraper. "
        "Install it with: pip install tls-client"
    )

from ..models import JobPost
from ..config import (
    INDEED_API_URL,
    INDEED_API_HEADERS,
    INDEED_GRAPHQL_QUERY,
    RATE_LIMIT_DELAY,
    DEFAULT_PROXIES,
)
from .base import BaseScraper


class IndeedScraper(BaseScraper):
    """Scraper for Indeed.com using GraphQL API"""

    def __init__(self, proxies: Optional[List[str]] = None, use_proxies: bool = True, proxy_session: Optional[str] = None):
        super().__init__("indeed", proxies=proxies, use_proxies=use_proxies)
        self.api_url = INDEED_API_URL
        self.api_headers = INDEED_API_HEADERS.copy()

        # Initialize TLS client session
        self.session = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )

        # Get proxy URL if using proxies
        self.proxy_url = None
        self.proxy_session = proxy_session

        if use_proxies:
            if proxies:
                base_proxy = proxies[0] if proxies else None
            elif DEFAULT_PROXIES:
                base_proxy = DEFAULT_PROXIES[0]
            else:
                base_proxy = None

            # Build proxy URL with session ID if provided
            if base_proxy:
                self.proxy_url = self._build_session_proxy(base_proxy, proxy_session)

    @staticmethod
    def _generate_session_id(length: int = 10) -> str:
        """
        Generate a random session ID for proxy rotation

        Args:
            length: Length of session ID

        Returns:
            Random alphanumeric session ID
        """
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _build_session_proxy(self, base_proxy_url: str, session_id: Optional[str] = None) -> str:
        """
        Build proxy URL with IPRoyal session ID for IP rotation

        IPRoyal format: http://username:password_country-us_session-{id}_lifetime-30m@host:port

        Args:
            base_proxy_url: Base proxy URL (http://username:password@host:port)
            session_id: Optional session ID (generates random if None)

        Returns:
            Proxy URL with session parameters embedded in password field
        """
        if not session_id:
            return base_proxy_url

        # Parse the proxy URL
        # Format: http://username:password@host:port
        if "@" in base_proxy_url:
            protocol_and_auth, host_and_port = base_proxy_url.split("@", 1)
            protocol, auth = protocol_and_auth.split("://", 1)
            # Only split on first colon to handle passwords containing ':'
            username, password = auth.split(":", 1)

            # Add session parameters to password (IPRoyal format)
            # Format: password_country-us_session-{id}_lifetime-30m
            password_with_session = f"{password}_country-us_session-{session_id}_lifetime-30m"

            # Rebuild proxy URL with session in password field
            proxy_url = f"{protocol}://{username}:{password_with_session}@{host_and_port}"

            # Debug logging (mask password but show session)
            if os.getenv("DEBUG", "false").lower() == "true":
                masked_proxy = f"{protocol}://{username}:****_country-us_session-{session_id}_lifetime-30m@{host_and_port}"
                print(f"[INFO] Built session proxy: {masked_proxy}")

            return proxy_url
        else:
            # No auth in proxy URL, return as-is
            return base_proxy_url

    def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int = 10,
        country: str = "USA",
        hours_old: Optional[int] = None,
        is_remote: Optional[bool] = None,
        job_type: Optional[str] = None,
        **kwargs,
    ) -> List[JobPost]:
        """
        Scrape job postings from Indeed using GraphQL API

        Args:
            search_term: Job title or keywords
            location: Geographic location
            results_wanted: Number of results to retrieve
            country: Country for search (default: USA)
            hours_old: Filter jobs posted within X hours
            is_remote: Filter for remote jobs
            job_type: Filter by job type (fulltime, parttime, contract, etc.)
            **kwargs: Additional parameters

        Returns:
            List of JobPost objects
        """
        jobs = []
        cursor = None

        print(f"[INFO] Scraping Indeed for '{search_term}' in '{location}'...")

        while len(jobs) < results_wanted:
            # Build GraphQL query variables
            variables = self._build_query_variables(
                search_term=search_term,
                location=location,
                cursor=cursor,
                hours_old=hours_old,
                is_remote=is_remote,
                job_type=job_type,
            )

            # Make GraphQL API request
            response_data = self._make_graphql_request(variables)

            if not response_data:
                print("[ERROR] Failed to fetch data from Indeed API")
                break

            # Parse job results
            job_search = response_data.get("data", {}).get("jobSearch", {})
            results = job_search.get("results", [])

            if not results:
                print("[INFO] No more results found")
                break

            # Process each job
            for result in results:
                if len(jobs) >= results_wanted:
                    break

                try:
                    job = self._parse_job(result)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    print(f"[WARNING] Error parsing job: {e}")
                    continue

            # Get next cursor for pagination
            page_info = job_search.get("pageInfo", {})
            cursor = page_info.get("nextCursor")

            if not cursor:
                print("[INFO] No more pages available")
                break

            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)

        print(f"[SUCCESS] Successfully scraped {len(jobs)} jobs from Indeed")
        return jobs[:results_wanted]

    def _build_query_variables(
        self,
        search_term: str,
        location: str,
        cursor: Optional[str] = None,
        hours_old: Optional[int] = None,
        is_remote: Optional[bool] = None,
        job_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build GraphQL query variables

        Args:
            search_term: Job search keywords
            location: Job location
            cursor: Pagination cursor
            hours_old: Filter jobs by age
            is_remote: Filter for remote jobs
            job_type: Filter by employment type

        Returns:
            Dictionary of GraphQL variables
        """
        # Build what clause (job search keywords)
        # Escape quotes in search term
        escaped_search_term = search_term.replace('"', '\\"') if search_term else ""
        what_clause = f'what: "{escaped_search_term}"' if escaped_search_term else ""

        # Build location clause with radius
        if location:
            location_clause = f'location: {{where: "{location}", radius: 50, radiusUnit: MILES}}'
        else:
            location_clause = ""

        # Build cursor clause for pagination
        cursor_clause = f'cursor: "{cursor}"' if cursor else ""

        # Build filters clause
        filters = []

        if hours_old:
            # Convert hours to days for Indeed API
            days = max(1, hours_old // 24)
            filters.append(f'datePosted: "{days}"')

        if is_remote:
            filters.append('remoteLocation: "REMOTE"')

        if job_type:
            # Map job types to Indeed API values
            job_type_map = {
                "fulltime": "FULLTIME",
                "full-time": "FULLTIME",
                "parttime": "PARTTIME",
                "part-time": "PARTTIME",
                "contract": "CONTRACT",
                "temporary": "TEMPORARY",
                "internship": "INTERNSHIP",
            }
            indeed_job_type = job_type_map.get(job_type.lower().replace(" ", ""))
            if indeed_job_type:
                filters.append(f'jobType: {indeed_job_type}')

        filters_clause = f'filters: {{{", ".join(filters)}}}' if filters else ""

        # Format the GraphQL query with variables
        query = INDEED_GRAPHQL_QUERY.format(
            what=what_clause,
            location=location_clause,
            cursor=cursor_clause,
            filters=filters_clause,
        )

        return {"query": query}

    def _make_graphql_request(self, variables: Dict[str, Any]) -> Optional[Dict]:
        """
        Make a GraphQL API request to Indeed

        Args:
            variables: GraphQL query variables

        Returns:
            Parsed JSON response or None on failure
        """
        try:
            # Prepare request payload
            payload = json.dumps(variables)

            # Make request with TLS client
            if self.proxy_url:
                response = self.session.post(
                    self.api_url,
                    headers=self.api_headers,
                    data=payload,
                    proxy=self.proxy_url,
                )
            else:
                response = self.session.post(
                    self.api_url,
                    headers=self.api_headers,
                    data=payload,
                )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] API request failed with status {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"[ERROR] Error making API request: {e}")
            return None

    @staticmethod
    def _categorize_attributes(attributes: List[Dict]) -> Dict[str, List[str]]:
        """
        Categorize job attributes into skills, requirements, benefits, and work arrangements

        Args:
            attributes: List of attribute dictionaries with 'key' and 'label' fields

        Returns:
            Dictionary with categorized attribute lists
        """
        # Define categorization patterns
        skill_keywords = {
            'crm', 'software', 'programming', 'database', 'api', 'automation', 'ai', 'machine learning',
            'javascript', 'python', 'java', 'sql', 'excel', 'salesforce', 'sap', 'oracle', 'aws',
            'azure', 'cloud', 'docker', 'kubernetes', 'git', 'agile', 'scrum', 'json', 'rest',
            'graphql', 'testing', 'debugging', 'development', 'engineering', 'technical', 'analytics',
            'data', 'reporting', 'analysis', 'design', 'ui', 'ux', 'web', 'mobile', 'app'
        }

        requirement_keywords = {
            'level', 'experience', 'years', 'degree', 'certification', 'license', 'background check',
            'security clearance', 'qualification', 'education', 'bachelor', 'master', 'phd', 'associate',
            'entry', 'junior', 'mid', 'senior', 'lead', 'principal', 'expert', 'proficiency', 'fluent'
        }

        benefit_keywords = {
            'bonus', 'benefits', '401k', 'insurance', 'health', 'dental', 'vision', 'pto', 'vacation',
            'paid time off', 'retirement', 'stock', 'equity', 'pension', 'gym', 'wellness', 'tuition',
            'reimbursement', 'training', 'development', 'career growth', 'opportunities', 'parental leave',
            'childcare', 'flexible', 'work from home', 'wfh'
        }

        work_arrangement_keywords = {
            'remote', 'hybrid', 'onsite', 'in-office', 'telecommute', 'work from home', 'flexible',
            'schedule', 'shift', 'hours', 'full-time', 'part-time', 'contract', 'temporary', 'permanent',
            'freelance', 'monday to friday', 'weekends', 'nights', 'overtime', 'travel', 'relocation'
        }

        categorized = {
            'skills': [],
            'requirements': [],
            'benefits': [],
            'work_arrangements': []
        }

        for attr in attributes:
            if not isinstance(attr, dict):
                continue

            label = attr.get('label', '').lower()
            if not label:
                continue

            # Categorize based on keywords (can match multiple categories)
            categorized_count = 0

            if any(keyword in label for keyword in skill_keywords):
                categorized['skills'].append(attr.get('label'))
                categorized_count += 1

            if any(keyword in label for keyword in requirement_keywords):
                categorized['requirements'].append(attr.get('label'))
                categorized_count += 1

            if any(keyword in label for keyword in benefit_keywords):
                categorized['benefits'].append(attr.get('label'))
                categorized_count += 1

            if any(keyword in label for keyword in work_arrangement_keywords):
                categorized['work_arrangements'].append(attr.get('label'))
                categorized_count += 1

            # If no category matched, add to requirements as default
            if categorized_count == 0:
                categorized['requirements'].append(attr.get('label'))

        return categorized

    def _parse_job(self, result: Dict) -> Optional[JobPost]:
        """
        Parse a job from Indeed API response

        Args:
            result: Job result from API

        Returns:
            JobPost object or None
        """
        try:
            # Validate result structure
            if not result or not isinstance(result, dict):
                return None

            job_data = result.get("job")

            # Check if job_data exists and is a dictionary
            if not job_data or not isinstance(job_data, dict):
                return None

            # Basic job information
            title = job_data.get("title", "")
            job_key = job_data.get("key", "")

            # Skip jobs without essential information
            if not title or not job_key:
                return None

            # Build job URL
            job_url = f"https://www.indeed.com/viewjob?jk={job_key}"

            # Company information - safely handle None employer
            employer = job_data.get("employer")
            if employer and isinstance(employer, dict):
                company = employer.get("name", "Unknown")
                company_url = employer.get("relativeCompanyPageUrl", "")
                if company_url:
                    company_url = f"https://www.indeed.com{company_url}"
            else:
                company = "Unknown"
                company_url = ""

            # Location information - safely handle None location
            location_data = job_data.get("location")
            if location_data and isinstance(location_data, dict):
                location_formatted = location_data.get("formatted")
                if location_formatted and isinstance(location_formatted, dict):
                    location = location_formatted.get("short", "") or location_formatted.get("long", "Unknown")
                else:
                    location = "Unknown"
            else:
                location = "Unknown"

            # Description (convert HTML to markdown) - safely handle None
            description_data = job_data.get("description")
            description = None
            if description_data and isinstance(description_data, dict):
                description_html = description_data.get("html", "")
                if description_html:
                    try:
                        description = md(description_html).strip()
                    except:
                        description = None

            # Compensation information - safely handle None
            compensation = job_data.get("compensation")
            salary_min = None
            salary_max = None
            salary_currency = None
            salary_period = None

            if compensation and isinstance(compensation, dict):
                # Try base salary first
                base_salary = compensation.get("baseSalary")
                if base_salary and isinstance(base_salary, dict):
                    salary_range = base_salary.get("range")
                    if salary_range and isinstance(salary_range, dict):
                        salary_min = salary_range.get("min")
                        salary_max = salary_range.get("max")
                        salary_currency = compensation.get("currencyCode", "USD")

                        # Map unitOfWork to period
                        unit_of_work = base_salary.get("unitOfWork", "")
                        if unit_of_work:
                            unit_of_work = unit_of_work.upper()
                            period_map = {
                                "HOUR": "hourly",
                                "DAY": "daily",
                                "WEEK": "weekly",
                                "MONTH": "monthly",
                                "YEAR": "yearly",
                            }
                            salary_period = period_map.get(unit_of_work, "yearly")

                # If no base salary, try estimated
                if not salary_min:
                    estimated = compensation.get("estimated")
                    if estimated and isinstance(estimated, dict):
                        estimated_salary = estimated.get("baseSalary")
                        if estimated_salary and isinstance(estimated_salary, dict):
                            salary_range = estimated_salary.get("range")
                            if salary_range and isinstance(salary_range, dict):
                                salary_min = salary_range.get("min")
                                salary_max = salary_range.get("max")
                                salary_currency = estimated.get("currencyCode", "USD")

                                unit_of_work = estimated_salary.get("unitOfWork", "")
                                if unit_of_work:
                                    unit_of_work = unit_of_work.upper()
                                    period_map = {
                                        "HOUR": "hourly",
                                        "DAY": "daily",
                                        "WEEK": "weekly",
                                        "MONTH": "monthly",
                                        "YEAR": "yearly",
                                    }
                                    salary_period = period_map.get(unit_of_work, "yearly")

            # Phase 2: Job attributes - categorize into skills, requirements, benefits, work arrangements
            attributes = job_data.get("attributes", [])
            job_type = None
            remote = False

            # Categorize attributes using helper method
            categorized_attrs = self._categorize_attributes(attributes) if attributes else {
                'skills': [],
                'requirements': [],
                'benefits': [],
                'work_arrangements': []
            }

            # Extract job type and remote status from attributes
            if attributes and isinstance(attributes, list):
                for attr in attributes:
                    if not attr or not isinstance(attr, dict):
                        continue

                    label = attr.get("label", "")
                    if not label:
                        continue

                    label = label.lower()
                    if "full-time" in label or "full time" in label:
                        job_type = "full-time"
                    elif "part-time" in label or "part time" in label:
                        job_type = "part-time"
                    elif "contract" in label:
                        job_type = "contract"
                    elif "temporary" in label:
                        job_type = "temporary"
                    elif "internship" in label:
                        job_type = "internship"

                    if "remote" in label:
                        remote = True

            # Also check location for remote
            if not remote and location:
                remote = "remote" in location.lower()

            # Phase 3: Extract enhanced location data
            location_country_code = None
            location_country_name = None
            location_city = None
            location_state = None
            location_postal_code = None

            if location_data and isinstance(location_data, dict):
                location_country_code = location_data.get("countryCode")
                location_country_name = location_data.get("countryName")
                location_city = location_data.get("city")
                location_state = location_data.get("admin1Code")  # State/province code
                location_postal_code = location_data.get("postalCode")

            # Phase 4: Extract company enrichment data
            company_size = None
            company_revenue = None
            company_description = None
            company_ceo = None
            company_website = None
            company_logo_url = None
            company_header_image_url = None

            if employer and isinstance(employer, dict):
                dossier = employer.get("dossier")
                if dossier and isinstance(dossier, dict):
                    # Employer details
                    employer_details = dossier.get("employerDetails", {})
                    if employer_details and isinstance(employer_details, dict):
                        company_size = employer_details.get("employeesLocalizedLabel")
                        company_revenue = employer_details.get("revenueLocalizedLabel")
                        company_description = employer_details.get("briefDescription")
                        company_ceo = employer_details.get("ceoName")

                    # Company images
                    images = dossier.get("images", {})
                    if images and isinstance(images, dict):
                        company_logo_url = images.get("squareLogoUrl")
                        company_header_image_url = images.get("headerImageUrl")

                    # Company links
                    links = dossier.get("links", {})
                    if links and isinstance(links, dict):
                        company_website = links.get("corporateWebsite")

            # Phase 5: Extract advanced fields
            work_schedule = None
            detailed_salary = None
            source_site = None
            tracking_key = None
            date_on_site = None

            # Recruit data
            recruit = job_data.get("recruit")
            if recruit and isinstance(recruit, dict):
                work_schedule = recruit.get("workSchedule")
                detailed_salary = recruit.get("detailedSalary")

            # Source information
            source = job_data.get("source")
            if source and isinstance(source, dict):
                source_site = source.get("name")

            # Tracking key from result
            tracking_key = result.get("trackingKey")

            # Date on Indeed (separate from date posted)
            date_on_indeed = job_data.get("dateOnIndeed")
            if date_on_indeed:
                try:
                    if isinstance(date_on_indeed, (int, float)):
                        date_on_site_dt = datetime.fromtimestamp(date_on_indeed / 1000)
                        date_on_site = str(date_on_site_dt.date())
                    else:
                        date_on_site_dt = datetime.fromisoformat(date_on_indeed.replace("Z", "+00:00"))
                        date_on_site = str(date_on_site_dt.date())
                except:
                    date_on_site = None

            # Date posted - safely handle None
            # Indeed returns Unix timestamp in milliseconds
            date_posted = job_data.get("datePublished")
            if date_posted:
                try:
                    # Check if it's a Unix timestamp (number) or ISO string
                    if isinstance(date_posted, (int, float)):
                        # Convert milliseconds to seconds and create datetime
                        date_posted = datetime.fromtimestamp(date_posted / 1000)
                    else:
                        # Handle ISO format string
                        date_posted = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
                except Exception as e:
                    if os.getenv("DEBUG", "false").lower() == "true":
                        print(f"[WARNING] Date parsing error: {e}")
                    date_posted = None

            # Build comprehensive JobPost object with all enriched data
            return JobPost(
                # Core fields
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                site="indeed",
                description=description,
                job_type=job_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                salary_period=salary_period,
                remote=remote,
                date_posted=str(date_posted.date()) if date_posted else None,
                company_url=company_url if company_url else None,

                # Phase 2: Rich Attributes
                skills=categorized_attrs.get('skills', []),
                requirements=categorized_attrs.get('requirements', []),
                benefits=categorized_attrs.get('benefits', []),
                work_arrangements=categorized_attrs.get('work_arrangements', []),

                # Phase 3: Enhanced Location
                location_country_code=location_country_code,
                location_country_name=location_country_name,
                location_city=location_city,
                location_state=location_state,
                location_postal_code=location_postal_code,

                # Phase 4: Company Enrichment
                company_size=company_size,
                company_revenue=company_revenue,
                company_description=company_description,
                company_ceo=company_ceo,
                company_website=company_website,
                company_logo_url=company_logo_url,
                company_header_image_url=company_header_image_url,

                # Phase 5: Advanced Fields
                work_schedule=work_schedule,
                detailed_salary=detailed_salary,
                source_site=source_site,
                tracking_key=tracking_key,
                date_on_site=date_on_site,
            )

        except Exception as e:
            # This should rarely happen now with defensive null checking
            # Only log if it's truly unexpected
            import traceback
            print(f"[WARNING] Unexpected error parsing job (skipping): {type(e).__name__}")
            if os.getenv("DEBUG", "false").lower() == "true":
                traceback.print_exc()
            return None

    def close(self):
        """Close the TLS client session"""
        if hasattr(self, 'session'):
            self.session.close()
