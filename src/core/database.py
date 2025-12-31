"""
DuckDB Database Manager

Centralized database connection management for all job data storage.
Replaces CSV/JSON files and SQLite databases with a unified DuckDB database.
"""

import os
import sys
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import duckdb

# Add parent directory to path for profile_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfilePaths


class DatabaseManager:
    """Manages DuckDB database connections and schema for job data"""

    _instances: Dict[str, "DatabaseManager"] = {}
    _lock = threading.Lock()

    def __new__(cls, profile_name: Optional[str] = None):
        """Singleton per profile - ensures one connection per profile"""
        paths = ProfilePaths(profile_name)
        profile_key = paths.profile_name

        with cls._lock:
            if profile_key not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[profile_key] = instance
            return cls._instances[profile_key]

    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize DatabaseManager for a profile

        Args:
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        if getattr(self, "_initialized", False):
            return

        self.paths = ProfilePaths(profile_name)
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.paths.data_dir / "jobs.duckdb"
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._thread_local = threading.local()
        self._initialized = True
        self._init_schema()

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Get thread-local database connection with validation"""
        if not hasattr(self._thread_local, "conn") or self._thread_local.conn is None:
            try:
                self._thread_local.conn = duckdb.connect(str(self.db_path))
            except Exception as e:
                print(f"[ERROR] Failed to connect to database: {e}")
                raise

        # Validate connection is still alive
        try:
            self._thread_local.conn.execute("SELECT 1")
        except Exception:
            # Reconnect if connection is dead
            try:
                self._thread_local.conn = duckdb.connect(str(self.db_path))
            except Exception as e:
                print(f"[ERROR] Failed to reconnect to database: {e}")
                raise

        return self._thread_local.conn

    def _init_schema(self):
        """Initialize database schema"""
        conn = self.connection

        # Jobs table - main storage for all scraped jobs
        # Using job_url as the effective primary key since it's always unique
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_url VARCHAR PRIMARY KEY,
                source VARCHAR NOT NULL,

                -- Core fields
                title VARCHAR,
                company VARCHAR,
                location VARCHAR,
                site VARCHAR,
                description TEXT,
                job_type VARCHAR,
                date_posted VARCHAR,
                salary_min DOUBLE,
                salary_max DOUBLE,
                salary_currency VARCHAR,
                salary_period VARCHAR,
                company_url VARCHAR,
                company_industry VARCHAR,
                remote BOOLEAN,

                -- List fields (native arrays)
                skills VARCHAR[],
                requirements VARCHAR[],
                benefits VARCHAR[],
                work_arrangements VARCHAR[],

                -- Location fields
                location_country_code VARCHAR,
                location_country_name VARCHAR,
                location_city VARCHAR,
                location_state VARCHAR,
                location_postal_code VARCHAR,

                -- Company fields
                company_size VARCHAR,
                company_revenue VARCHAR,
                company_description TEXT,
                company_ceo VARCHAR,
                company_website VARCHAR,
                company_logo_url VARCHAR,
                company_header_image_url VARCHAR,

                -- Advanced fields
                work_schedule VARCHAR,
                detailed_salary VARCHAR,
                source_site VARCHAR,
                tracking_key VARCHAR,
                date_on_site VARCHAR,

                -- Glassdoor-specific
                glassdoor_listing_id BIGINT,
                glassdoor_tracking_key VARCHAR,
                glassdoor_job_link VARCHAR,
                easy_apply BOOLEAN,
                occupation_code VARCHAR,
                occupation_id BIGINT,
                occupation_confidence DOUBLE,
                company_full_name VARCHAR,
                company_short_name VARCHAR,
                company_division VARCHAR,
                company_rating DOUBLE,
                company_glassdoor_id BIGINT,
                salary_source VARCHAR,
                is_sponsored BOOLEAN,
                sponsorship_level VARCHAR,
                location_id BIGINT,
                location_country_id BIGINT,

                -- Match results (populated after scoring)
                match_score DOUBLE,
                match_explanation TEXT,
                is_relevant BOOLEAN,
                gap_analysis TEXT,
                resume_suggestions TEXT,

                -- Timestamps
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Processed jobs - tracks which jobs were included in reports
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_jobs (
                job_url VARCHAR PRIMARY KEY,
                job_title VARCHAR,
                company VARCHAR,
                location VARCHAR,
                match_score DOUBLE,
                report_date TIMESTAMP,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                times_seen INTEGER DEFAULT 1
            )
        """)

        # Failed jobs - tracks processing failures
        # Using composite primary key (job_url, stage) since same job can fail at different stages
        conn.execute("""
            CREATE TABLE IF NOT EXISTS failed_jobs (
                job_url VARCHAR NOT NULL,
                stage VARCHAR NOT NULL,
                job_title VARCHAR,
                company VARCHAR,
                error_type VARCHAR NOT NULL,
                error_message TEXT,
                failure_count INTEGER DEFAULT 1,
                first_failed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_failed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                raw_job_data TEXT,
                PRIMARY KEY(job_url, stage)
            )
        """)

        # Checkpoints - pipeline resume state
        # Using source as primary key since we only have one active checkpoint per source
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                source VARCHAR PRIMARY KEY,
                min_score DOUBLE,
                stage VARCHAR,
                processed_urls TEXT,
                matched_jobs_data TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON jobs(match_score)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_jobs_url ON processed_jobs(job_url)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_jobs_score ON processed_jobs(match_score)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_failed_jobs_stage ON failed_jobs(stage)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_failed_jobs_error_type ON failed_jobs(error_type)")

    def close(self):
        """Close the database connection for current thread"""
        if hasattr(self._thread_local, "conn") and self._thread_local.conn is not None:
            self._thread_local.conn.close()
            self._thread_local.conn = None

    @classmethod
    def close_all(cls):
        """Close all database connections"""
        with cls._lock:
            for instance in cls._instances.values():
                instance.close()
            cls._instances.clear()

    def execute(self, query: str, params: tuple = None) -> duckdb.DuckDBPyConnection:
        """Execute a query and return the connection for chaining"""
        if params:
            return self.connection.execute(query, params)
        return self.connection.execute(query)

    def fetchone(self, query: str, params: tuple = None) -> Optional[tuple]:
        """Execute query and fetch one result"""
        result = self.execute(query, params)
        return result.fetchone()

    def fetchall(self, query: str, params: tuple = None) -> List[tuple]:
        """Execute query and fetch all results"""
        result = self.execute(query, params)
        return result.fetchall()

    def fetchdf(self, query: str, params: tuple = None):
        """Execute query and return as pandas DataFrame"""
        result = self.execute(query, params)
        return result.fetchdf()


def get_database(profile_name: Optional[str] = None) -> DatabaseManager:
    """
    Get DatabaseManager instance for a profile

    Args:
        profile_name: Profile name (default: from .env ACTIVE_PROFILE)

    Returns:
        DatabaseManager instance (singleton per profile)
    """
    return DatabaseManager(profile_name)


if __name__ == "__main__":
    # Test the database manager
    print("Testing DatabaseManager...")

    db = get_database()
    print(f"Database path: {db.db_path}")

    # Test insert using proper DuckDB upsert syntax
    print("\nInserting test job...")
    db.execute("""
        INSERT INTO jobs (job_url, source, title, company, location, site)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (job_url) DO UPDATE SET
            source = EXCLUDED.source,
            title = EXCLUDED.title,
            company = EXCLUDED.company,
            location = EXCLUDED.location,
            site = EXCLUDED.site
    """, ("https://example.com/job/test123", "test", "Test Job", "Test Company", "Remote", "test"))

    # Test query
    print("\nQuerying jobs...")
    result = db.fetchall("SELECT job_url, title, company FROM jobs LIMIT 5")
    for row in result:
        print(f"  {row}")

    # Test DataFrame query
    print("\nQuerying as DataFrame...")
    df = db.fetchdf("SELECT job_url, title, company FROM jobs LIMIT 5")
    print(df)

    print("\nDatabaseManager test complete")
