"""
Configuration and constants for core
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# IPRoyal proxy configuration
# Loads from .env file or environment variables
def _get_iproyal_proxy():
    """Construct IPRoyal proxy URL from environment variables"""
    # Try to get the pre-constructed proxy URL first
    proxy_url = os.getenv("PROXY_URL")
    if proxy_url:
        return proxy_url

    # Otherwise construct from individual components
    host = os.getenv("IPROYAL_HOST")
    port = os.getenv("IPROYAL_PORT")
    username = os.getenv("IPROYAL_USERNAME")
    password = os.getenv("IPROYAL_PASSWORD")

    if all([host, port, username, password]):
        return f"http://{username}:{password}@{host}:{port}"

    return None

# Default proxy list - IPRoyal rotating residential proxy
IPROYAL_PROXY = _get_iproyal_proxy()

DEFAULT_PROXIES = [
    IPROYAL_PROXY
] if IPROYAL_PROXY else []

# Note: If you want to add additional proxies, you can extend the list:
# DEFAULT_PROXIES = [IPROYAL_PROXY, "http://other-proxy.com:8080"] if IPROYAL_PROXY else []

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Request timeouts (seconds)
REQUEST_TIMEOUT = 15  # Increased from 10 to allow more time

# Rate limiting (seconds between requests)
# Increased to 2-3 seconds to be more human-like and avoid 403 blocks
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "2.5"))

# Maximum results per site
MAX_RESULTS_PER_SITE = 1000

# Safety and Testing Configuration
# These settings help prevent runaway bandwidth usage during testing

# Test mode - set to True for safer testing with additional logging
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Maximum total requests per scraping session (safety limit)
# Set to None to disable, or a number to enforce a hard limit
MAX_REQUESTS_PER_SESSION = int(os.getenv("MAX_REQUESTS_PER_SESSION", "0")) or None

# Bandwidth estimation (KB per request, conservative estimate)
ESTIMATED_KB_PER_REQUEST = 50

# Recommended testing configurations
TESTING_CONFIGS = {
    "minimal": {
        "results_wanted": 1,
        "sites": 1,
        "estimated_requests": 2,
        "estimated_bandwidth_kb": 100,
    },
    "small": {
        "results_wanted": 5,
        "sites": 1,
        "estimated_requests": 5,
        "estimated_bandwidth_kb": 250,
    },
    "medium": {
        "results_wanted": 10,
        "sites": 2,
        "estimated_requests": 12,
        "estimated_bandwidth_kb": 600,
    },
    "large": {
        "results_wanted": 50,
        "sites": 4,
        "estimated_requests": 60,
        "estimated_bandwidth_kb": 3000,
    },
}

# Indeed GraphQL API Configuration
INDEED_API_URL = "https://apis.indeed.com/graphql"

INDEED_API_HEADERS = {
    "Host": "apis.indeed.com",
    "content-type": "application/json",
    "indeed-api-key": "161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8",
    "accept": "application/json",
    "indeed-locale": "en-US",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Indeed App 193.1",
    "indeed-app-info": "appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone",
}

INDEED_GRAPHQL_QUERY = """
query GetJobData {{
    jobSearch(
    {what}
    {location}
    limit: 100
    {cursor}
    sort: RELEVANCE
    {filters}
    ) {{
    pageInfo {{
        nextCursor
    }}
    results {{
        trackingKey
        job {{
        source {{
            name
        }}
        key
        title
        datePublished
        dateOnIndeed
        description {{
            html
        }}
        location {{
            countryName
            countryCode
            admin1Code
            city
            postalCode
            streetAddress
            formatted {{
            short
            long
            }}
        }}
        compensation {{
            estimated {{
            currencyCode
            baseSalary {{
                unitOfWork
                range {{
                ... on Range {{
                    min
                    max
                }}
                }}
            }}
            }}
            baseSalary {{
            unitOfWork
            range {{
                ... on Range {{
                min
                max
                }}
            }}
            }}
            currencyCode
        }}
        attributes {{
            key
            label
        }}
        employer {{
            relativeCompanyPageUrl
            name
            dossier {{
                employerDetails {{
                addresses
                industry
                employeesLocalizedLabel
                revenueLocalizedLabel
                briefDescription
                ceoName
                ceoPhotoUrl
                }}
                images {{
                    headerImageUrl
                    squareLogoUrl
                }}
                links {{
                corporateWebsite
            }}
            }}
        }}
        recruit {{
            viewJobUrl
            detailedSalary
            workSchedule
        }}
        }}
    }}
    }}
}}
"""

# Glassdoor GraphQL API Configuration
GLASSDOOR_API_URL = "https://www.glassdoor.com/graph"

GLASSDOOR_API_HEADERS = {
    "authority": "www.glassdoor.com",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "apollographql-client-name": "job-search-next",
    "apollographql-client-version": "4.65.5",
    "content-type": "application/json",
    "origin": "https://www.glassdoor.com",
    "referer": "https://www.glassdoor.com/",
    "sec-ch-ua": '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
}

GLASSDOOR_GRAPHQL_QUERY = """
query JobSearchResultsQuery(
    $excludeJobListingIds: [Long!],
    $keyword: String,
    $locationId: Int,
    $locationType: LocationTypeEnum,
    $numJobsToShow: Int!,
    $pageCursor: String,
    $pageNumber: Int,
    $filterParams: [FilterParams],
    $originalPageUrl: String,
    $seoFriendlyUrlInput: String,
    $parameterUrlInput: String,
    $seoUrl: Boolean
) {
    jobListings(
        contextHolder: {
            searchParams: {
                excludeJobListingIds: $excludeJobListingIds,
                keyword: $keyword,
                locationId: $locationId,
                locationType: $locationType,
                numPerPage: $numJobsToShow,
                pageCursor: $pageCursor,
                pageNumber: $pageNumber,
                filterParams: $filterParams,
                originalPageUrl: $originalPageUrl,
                seoFriendlyUrlInput: $seoFriendlyUrlInput,
                parameterUrlInput: $parameterUrlInput,
                seoUrl: $seoUrl,
                searchType: SR
            }
        }
    ) {
        companyFilterOptions {
            id
            shortName
            __typename
        }
        filterOptions
        indeedCtk
        jobListings {
            ...JobView
            __typename
        }
        jobListingSeoLinks {
            linkItems {
                position
                url
                __typename
            }
            __typename
        }
        jobSearchTrackingKey
        jobsPageSeoData {
            pageMetaDescription
            pageTitle
            __typename
        }
        paginationCursors {
            cursor
            pageNumber
            __typename
        }
        indexablePageForSeo
        searchResultsMetadata {
            searchCriteria {
                implicitLocation {
                    id
                    localizedDisplayName
                    type
                    __typename
                }
                keyword
                location {
                    id
                    shortName
                    localizedShortName
                    localizedDisplayName
                    type
                    __typename
                }
                __typename
            }
            helpCenterDomain
            helpCenterLocale
            jobSerpJobOutlook {
                occupation
                paragraph
                __typename
            }
            showMachineReadableJobs
            __typename
        }
        totalJobsCount
        __typename
    }
}

fragment JobView on JobListingSearchResult {
    jobview {
        header {
            adOrderId
            advertiserType
            adOrderSponsorshipLevel
            ageInDays
            divisionEmployerName
            easyApply
            employer {
                id
                name
                shortName
                __typename
            }
            employerNameFromSearch
            goc
            gocConfidence
            gocId
            jobCountryId
            jobLink
            jobResultTrackingKey
            jobTitleText
            locationName
            locationType
            locId
            needsCommission
            payCurrency
            payPeriod
            payPeriodAdjustedPay {
                p10
                p50
                p90
                __typename
            }
            rating
            salarySource
            savedJobId
            sponsored
            __typename
        }
        job {
            description
            importConfigId
            jobTitleId
            jobTitleText
            listingId
            __typename
        }
        jobListingAdminDetails {
            cpcVal
            importConfigId
            jobListingId
            jobSourceId
            userEligibleForAdminJobDetails
            __typename
        }
        overview {
            shortName
            squareLogoUrl
            __typename
        }
        __typename
    }
    __typename
}
"""

GLASSDOOR_DESCRIPTION_QUERY = """
query JobDetailQuery($jl: Long!, $queryString: String, $pageTypeEnum: PageTypeEnum) {
    jobview: jobView(
        listingId: $jl
        contextHolder: {queryString: $queryString, pageTypeEnum: $pageTypeEnum}
    ) {
        job {
            description
            __typename
        }
        __typename
    }
}
"""

# Fallback CSRF token (if token fetch fails)
GLASSDOOR_FALLBACK_TOKEN = "Ft6oHEWlRZrxDww95Cpazw:0pGUrkb2y3TyOpAIqF2vbPmUXoXVkD3oEGDVkvfeCerceQ5-n8mBg3BovySUIjmCPHCaW0H2nQVdqzbtsYqf4Q:wcqRqeegRUa9MVLJGyujVXB7vWFPjdaS1CtrrzJq-ok"

# Site-specific configurations
SITE_CONFIGS = {
    "indeed": {
        "base_url": "https://www.indeed.com",
        "search_path": "/jobs",
        "max_results": 1000,
    },
    "linkedin": {
        "base_url": "https://www.linkedin.com",
        "search_path": "/jobs/search",
        "max_results": 100,  # LinkedIn is more restrictive
    },
    "zip_recruiter": {
        "base_url": "https://www.ziprecruiter.com",
        "search_path": "/jobs-search",
        "max_results": 1000,
    },
    "glassdoor": {
        "base_url": "https://www.glassdoor.com",
        "search_path": "/Job/jobs.htm",
        "max_results": 900,
    },
}

# VLM Scraper Configuration
# Enable VLM-based Glassdoor scraper (uses visual automation instead of GraphQL)
# Falls back to GraphQL if VLM is unavailable
USE_VLM_GLASSDOOR = os.getenv("USE_VLM_GLASSDOOR", "true").lower() == "true"

# Maximum actions the VLM agent can take per scraping session
VLM_MAX_ACTIONS = int(os.getenv("VLM_MAX_ACTIONS", "100"))

# Maximum pages to scrape with VLM
VLM_MAX_PAGES = int(os.getenv("VLM_MAX_PAGES", "10"))
