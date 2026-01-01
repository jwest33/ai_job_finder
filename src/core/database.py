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
    """Manages DuckDB database connections and schema for job data.

    Uses short-lived connections with proper synchronization to handle
    concurrent access on Windows where file locking is stricter.
    """

    _instances: Dict[str, "DatabaseManager"] = {}
    _class_lock = threading.Lock()
    _schema_initialized: Dict[str, bool] = {}  # Track which DBs have been initialized
    _db_locks: Dict[str, threading.RLock] = {}  # Per-database file locks

    def __new__(cls, profile_name: Optional[str] = None):
        """Singleton per profile - ensures one manager per profile"""
        paths = ProfilePaths(profile_name)
        profile_key = paths.profile_name

        with cls._class_lock:
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

        # Get or create a lock for this specific database file
        db_key = str(self.db_path)
        with DatabaseManager._class_lock:
            if db_key not in DatabaseManager._db_locks:
                DatabaseManager._db_locks[db_key] = threading.RLock()
            self._conn_lock = DatabaseManager._db_locks[db_key]

        self._initialized = True

        # Connection timeout settings - increased for Windows
        self._connect_timeout = 30  # seconds to wait for lock
        self._connect_retries = 5
        self._retry_delay = 2  # seconds between retries

        self._init_schema()

    def _connect(self, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        """Create a new database connection with retry logic.

        Args:
            read_only: If True, open in read-only mode (allows concurrent readers)

        Returns:
            New database connection

        Note:
            On Windows, DuckDB has stricter file locking. We use a threading lock
            to serialize access within this process, plus retry logic for any
            remaining contention with external processes.
        """
        import time

        last_error = None
        for attempt in range(self._connect_retries):
            try:
                if read_only:
                    return duckdb.connect(str(self.db_path), read_only=True)
                else:
                    return duckdb.connect(str(self.db_path))
            except duckdb.IOException as e:
                last_error = e
                error_str = str(e).lower()
                if "lock" in error_str or "busy" in error_str or "access" in error_str:
                    if attempt < self._connect_retries - 1:
                        print(f"[WARNING] Database locked, retrying in {self._retry_delay}s... (attempt {attempt + 1}/{self._connect_retries})")
                        time.sleep(self._retry_delay)
                        continue
                raise
            except Exception as e:
                print(f"[ERROR] Failed to connect to database: {e}")
                raise

        raise last_error or Exception("Failed to connect after retries")

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Get a database connection (creates new connection each time).

        DEPRECATED: Prefer using execute/fetchone/fetchall/fetchdf methods
        which handle connections automatically.
        """
        return self._connect(read_only=False)

    def _init_schema(self):
        """Initialize database schema (only once per database file).
        Thread-safe: uses lock to prevent concurrent schema initialization.
        """
        db_key = str(self.db_path)
        if db_key in DatabaseManager._schema_initialized:
            return

        with self._conn_lock:
            # Double-check after acquiring lock (another thread may have initialized)
            if db_key in DatabaseManager._schema_initialized:
                return

            conn = self._connect(read_only=False)
            try:
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

                # Job applications - tracks application status for jobs
                conn.execute("""
                CREATE TABLE IF NOT EXISTS job_applications (
                job_url VARCHAR PRIMARY KEY,
                status VARCHAR NOT NULL DEFAULT 'not_applied',
                applied_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                next_action VARCHAR,
                next_action_date DATE,
                resume_version VARCHAR,
                cover_letter TEXT,
                contact_name VARCHAR,
                contact_email VARCHAR,
                interview_dates TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Job attachments - stores resume and cover letter files for applications
                conn.execute("""
                CREATE TABLE IF NOT EXISTS job_attachments (
                id VARCHAR PRIMARY KEY,
                job_url VARCHAR NOT NULL,
                attachment_type VARCHAR NOT NULL,
                filename VARCHAR NOT NULL,
                stored_filename VARCHAR NOT NULL,
                file_extension VARCHAR NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type VARCHAR NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON job_applications(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_updated ON job_applications(updated_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_attachments_job_url ON job_attachments(job_url)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_attachments_type ON job_attachments(attachment_type)")

                DatabaseManager._schema_initialized[db_key] = True
            finally:
                conn.close()

    def close(self):
        """Close database connections (no-op for short-lived connections)"""
        pass  # Connections are now short-lived, no need to close

    @classmethod
    def close_all(cls):
        """Clear all database manager instances and locks"""
        with cls._class_lock:
            cls._instances.clear()
            cls._schema_initialized.clear()
            cls._db_locks.clear()

    def _is_read_query(self, query: str) -> bool:
        """Check if a query is read-only"""
        query_upper = query.strip().upper()
        return query_upper.startswith(('SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN'))

    def execute(self, query: str, params: tuple = None) -> duckdb.DuckDBPyConnection:
        """Execute a write query with short-lived connection.

        For write operations (INSERT, UPDATE, DELETE, CREATE, etc.)
        Creates a new connection, executes, and closes it.
        Thread-safe: uses lock to prevent concurrent access issues on Windows.
        """
        with self._conn_lock:
            conn = self._connect(read_only=False)
            try:
                if params:
                    result = conn.execute(query, params)
                else:
                    result = conn.execute(query)
                # Fetch results before closing connection
                return result
            finally:
                conn.close()

    def execute_fetch(self, query: str, params: tuple = None) -> tuple:
        """Execute query and return (columns, rows) in one atomic operation.

        Uses read-only connection for SELECT queries, write connection otherwise.
        Thread-safe: uses lock to prevent concurrent access issues on Windows.
        """
        with self._conn_lock:
            read_only = self._is_read_query(query)
            conn = self._connect(read_only=read_only)
            try:
                result = conn.execute(query, params) if params else conn.execute(query)
                columns = [desc[0] for desc in result.description] if result.description else []
                rows = result.fetchall()
                return columns, rows
            finally:
                conn.close()

    def fetchone(self, query: str, params: tuple = None) -> Optional[tuple]:
        """Execute query and fetch one result (uses read-only connection for SELECTs).
        Thread-safe: uses lock to prevent concurrent access issues on Windows.
        """
        with self._conn_lock:
            read_only = self._is_read_query(query)
            conn = self._connect(read_only=read_only)
            try:
                result = conn.execute(query, params) if params else conn.execute(query)
                return result.fetchone()
            finally:
                conn.close()

    def fetchall(self, query: str, params: tuple = None) -> List[tuple]:
        """Execute query and fetch all results (uses read-only connection for SELECTs).
        Thread-safe: uses lock to prevent concurrent access issues on Windows.
        """
        with self._conn_lock:
            read_only = self._is_read_query(query)
            conn = self._connect(read_only=read_only)
            try:
                result = conn.execute(query, params) if params else conn.execute(query)
                return result.fetchall()
            finally:
                conn.close()

    def fetchdf(self, query: str, params: tuple = None):
        """Execute query and return as pandas DataFrame (uses read-only connection).
        Thread-safe: uses lock to prevent concurrent access issues on Windows.
        """
        with self._conn_lock:
            conn = self._connect(read_only=True)
            try:
                result = conn.execute(query, params) if params else conn.execute(query)
                return result.fetchdf()
            finally:
                conn.close()


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
