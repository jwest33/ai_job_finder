"""
Data storage module for job postings

Handles saving job data to DuckDB with deduplication.
"""

import json
import math
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import JobPost
from .database import get_database


def _clean_value(value):
    """Clean a value for database insertion - convert NaN/inf to None"""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _clean_int(value):
    """Clean an integer value - convert NaN/inf to None, otherwise int"""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return int(value)
    return value


class JobStorage:
    """Handles storage and retrieval of job postings using DuckDB"""

    def __init__(self, output_dir: str = "data", profile_name: Optional[str] = None):
        """
        Initialize job storage

        Args:
            output_dir: Directory for any file outputs (kept for compatibility)
            profile_name: Profile name for database connection
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.db = get_database(profile_name)

    def save_jobs(
        self,
        jobs: List[JobPost],
        format: str = "both",
        deduplicate: bool = True,
        append_to_latest: bool = True,
        source: str = "indeed",
    ) -> dict:
        """
        Save job postings to DuckDB

        Args:
            jobs: List of JobPost objects to save
            format: Ignored (kept for compatibility)
            deduplicate: Deduplicate by job_url (default: True)
            append_to_latest: Ignored (always upserts to DB)
            source: Job source identifier (default: "indeed")

        Returns:
            Dictionary with save statistics
        """
        if not jobs:
            print("[WARNING] No jobs to save")
            return {}

        saved_count = 0
        updated_count = 0

        for job in jobs:
            job_dict = job.to_dict()
            job_url = job_dict.get("job_url")

            if not job_url:
                continue

            # Check if job exists
            existing = self.db.fetchone(
                "SELECT job_url FROM jobs WHERE job_url = ?",
                (job_url,)
            )

            now = datetime.now()

            if existing:
                # Update existing job
                self._update_job(job_dict, source, now)
                updated_count += 1
            else:
                # Insert new job
                self._insert_job(job_dict, source, now)
                saved_count += 1

        total = saved_count + updated_count
        print(f"[SUCCESS] Saved {saved_count} new jobs, updated {updated_count} existing ({total} total)")

        return {
            "saved": saved_count,
            "updated": updated_count,
            "total": total,
            "source": source,
        }

    def _insert_job(self, job_dict: Dict[str, Any], source: str, timestamp: datetime):
        """Insert a new job into the database"""
        # Prepare values - convert lists to proper format for DuckDB
        skills = job_dict.get("skills") or []
        requirements = job_dict.get("requirements") or []
        benefits = job_dict.get("benefits") or []
        work_arrangements = job_dict.get("work_arrangements") or []

        self.db.execute("""
            INSERT INTO jobs (
                job_url, source, title, company, location, site, description,
                job_type, date_posted, salary_min, salary_max, salary_currency,
                salary_period, company_url, company_industry, remote,
                skills, requirements, benefits, work_arrangements,
                location_country_code, location_country_name, location_city,
                location_state, location_postal_code,
                company_size, company_revenue, company_description, company_ceo,
                company_website, company_logo_url, company_header_image_url,
                work_schedule, detailed_salary, source_site, tracking_key, date_on_site,
                glassdoor_listing_id, glassdoor_tracking_key, glassdoor_job_link,
                easy_apply, occupation_code, occupation_id, occupation_confidence,
                company_full_name, company_short_name, company_division,
                company_rating, company_glassdoor_id, salary_source,
                is_sponsored, sponsorship_level, location_id, location_country_id,
                first_seen, last_seen
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?
            )
        """, (
            job_dict.get("job_url"),
            source,
            job_dict.get("title"),
            job_dict.get("company"),
            job_dict.get("location"),
            job_dict.get("site"),
            job_dict.get("description"),
            job_dict.get("job_type"),
            job_dict.get("date_posted"),
            _clean_value(job_dict.get("salary_min")),
            _clean_value(job_dict.get("salary_max")),
            job_dict.get("salary_currency"),
            job_dict.get("salary_period"),
            job_dict.get("company_url"),
            job_dict.get("company_industry"),
            job_dict.get("remote"),
            skills,
            requirements,
            benefits,
            work_arrangements,
            job_dict.get("location_country_code"),
            job_dict.get("location_country_name"),
            job_dict.get("location_city"),
            job_dict.get("location_state"),
            job_dict.get("location_postal_code"),
            job_dict.get("company_size"),
            job_dict.get("company_revenue"),
            job_dict.get("company_description"),
            job_dict.get("company_ceo"),
            job_dict.get("company_website"),
            job_dict.get("company_logo_url"),
            job_dict.get("company_header_image_url"),
            job_dict.get("work_schedule"),
            job_dict.get("detailed_salary"),
            job_dict.get("source_site"),
            job_dict.get("tracking_key"),
            job_dict.get("date_on_site"),
            _clean_int(job_dict.get("glassdoor_listing_id")),
            job_dict.get("glassdoor_tracking_key"),
            job_dict.get("glassdoor_job_link"),
            job_dict.get("easy_apply"),
            job_dict.get("occupation_code"),
            _clean_int(job_dict.get("occupation_id")),
            _clean_value(job_dict.get("occupation_confidence")),
            job_dict.get("company_full_name"),
            job_dict.get("company_short_name"),
            job_dict.get("company_division"),
            _clean_value(job_dict.get("company_rating")),
            _clean_int(job_dict.get("company_glassdoor_id")),
            job_dict.get("salary_source"),
            job_dict.get("is_sponsored"),
            job_dict.get("sponsorship_level"),
            _clean_int(job_dict.get("location_id")),
            _clean_int(job_dict.get("location_country_id")),
            timestamp,
            timestamp,
        ))

    def _update_job(self, job_dict: Dict[str, Any], source: str, timestamp: datetime):
        """Update an existing job in the database"""
        skills = job_dict.get("skills") or []
        requirements = job_dict.get("requirements") or []
        benefits = job_dict.get("benefits") or []
        work_arrangements = job_dict.get("work_arrangements") or []

        self.db.execute("""
            UPDATE jobs SET
                source = ?,
                title = ?,
                company = ?,
                location = ?,
                site = ?,
                description = ?,
                job_type = ?,
                date_posted = ?,
                salary_min = ?,
                salary_max = ?,
                salary_currency = ?,
                salary_period = ?,
                company_url = ?,
                company_industry = ?,
                remote = ?,
                skills = ?,
                requirements = ?,
                benefits = ?,
                work_arrangements = ?,
                location_country_code = ?,
                location_country_name = ?,
                location_city = ?,
                location_state = ?,
                location_postal_code = ?,
                company_size = ?,
                company_revenue = ?,
                company_description = ?,
                company_ceo = ?,
                company_website = ?,
                company_logo_url = ?,
                company_header_image_url = ?,
                work_schedule = ?,
                detailed_salary = ?,
                source_site = ?,
                tracking_key = ?,
                date_on_site = ?,
                glassdoor_listing_id = ?,
                glassdoor_tracking_key = ?,
                glassdoor_job_link = ?,
                easy_apply = ?,
                occupation_code = ?,
                occupation_id = ?,
                occupation_confidence = ?,
                company_full_name = ?,
                company_short_name = ?,
                company_division = ?,
                company_rating = ?,
                company_glassdoor_id = ?,
                salary_source = ?,
                is_sponsored = ?,
                sponsorship_level = ?,
                location_id = ?,
                location_country_id = ?,
                last_seen = ?
            WHERE job_url = ?
        """, (
            source,
            job_dict.get("title"),
            job_dict.get("company"),
            job_dict.get("location"),
            job_dict.get("site"),
            job_dict.get("description"),
            job_dict.get("job_type"),
            job_dict.get("date_posted"),
            _clean_value(job_dict.get("salary_min")),
            _clean_value(job_dict.get("salary_max")),
            job_dict.get("salary_currency"),
            job_dict.get("salary_period"),
            job_dict.get("company_url"),
            job_dict.get("company_industry"),
            job_dict.get("remote"),
            skills,
            requirements,
            benefits,
            work_arrangements,
            job_dict.get("location_country_code"),
            job_dict.get("location_country_name"),
            job_dict.get("location_city"),
            job_dict.get("location_state"),
            job_dict.get("location_postal_code"),
            job_dict.get("company_size"),
            job_dict.get("company_revenue"),
            job_dict.get("company_description"),
            job_dict.get("company_ceo"),
            job_dict.get("company_website"),
            job_dict.get("company_logo_url"),
            job_dict.get("company_header_image_url"),
            job_dict.get("work_schedule"),
            job_dict.get("detailed_salary"),
            job_dict.get("source_site"),
            job_dict.get("tracking_key"),
            job_dict.get("date_on_site"),
            _clean_int(job_dict.get("glassdoor_listing_id")),
            job_dict.get("glassdoor_tracking_key"),
            job_dict.get("glassdoor_job_link"),
            job_dict.get("easy_apply"),
            job_dict.get("occupation_code"),
            _clean_int(job_dict.get("occupation_id")),
            _clean_value(job_dict.get("occupation_confidence")),
            job_dict.get("company_full_name"),
            job_dict.get("company_short_name"),
            job_dict.get("company_division"),
            _clean_value(job_dict.get("company_rating")),
            _clean_int(job_dict.get("company_glassdoor_id")),
            job_dict.get("salary_source"),
            job_dict.get("is_sponsored"),
            job_dict.get("sponsorship_level"),
            _clean_int(job_dict.get("location_id")),
            _clean_int(job_dict.get("location_country_id")),
            timestamp,
            job_dict.get("job_url"),
        ))

    def load_latest(self, format: str = "csv", source: str = "indeed") -> Optional[pd.DataFrame]:
        """
        Load the latest job data for a source

        Args:
            format: Ignored (kept for compatibility)
            source: Job source identifier (default: "indeed")

        Returns:
            DataFrame with job data or None if no jobs found
        """
        df = self.db.fetchdf(
            "SELECT * FROM jobs WHERE source = ? ORDER BY last_seen DESC",
            (source,)
        )

        if df.empty:
            return None

        return df

    def load_all_jobs(self, source: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Load all jobs, optionally filtered by source

        Args:
            source: Optional source filter

        Returns:
            DataFrame with job data or None if no jobs found
        """
        if source:
            df = self.db.fetchdf(
                "SELECT * FROM jobs WHERE source = ? ORDER BY last_seen DESC",
                (source,)
            )
        else:
            df = self.db.fetchdf("SELECT * FROM jobs ORDER BY last_seen DESC")

        if df.empty:
            return None

        return df

    def load_unprocessed_jobs(self, source: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Load jobs that haven't been scored yet

        Args:
            source: Optional source filter

        Returns:
            DataFrame with unprocessed jobs
        """
        if source:
            df = self.db.fetchdf(
                "SELECT * FROM jobs WHERE source = ? AND match_score IS NULL ORDER BY first_seen DESC",
                (source,)
            )
        else:
            df = self.db.fetchdf(
                "SELECT * FROM jobs WHERE match_score IS NULL ORDER BY first_seen DESC"
            )

        if df.empty:
            return None

        return df

    def load_matched_jobs(
        self,
        source: Optional[str] = None,
        min_score: float = 0.0
    ) -> Optional[pd.DataFrame]:
        """
        Load jobs that have been scored and meet threshold

        Args:
            source: Optional source filter
            min_score: Minimum match score (default: 0.0)

        Returns:
            DataFrame with matched jobs
        """
        if source:
            df = self.db.fetchdf(
                """SELECT * FROM jobs
                   WHERE source = ? AND match_score IS NOT NULL AND match_score >= ?
                   ORDER BY match_score DESC""",
                (source, min_score)
            )
        else:
            df = self.db.fetchdf(
                """SELECT * FROM jobs
                   WHERE match_score IS NOT NULL AND match_score >= ?
                   ORDER BY match_score DESC""",
                (min_score,)
            )

        if df.empty:
            return None

        return df

    def update_match_results(
        self,
        job_url: str,
        match_score: float,
        match_explanation: str,
        is_relevant: bool,
        gap_analysis: Optional[str] = None,
        resume_suggestions: Optional[str] = None
    ) -> bool:
        """
        Update match results for a job

        Args:
            job_url: The job URL
            match_score: Match score (0-100)
            match_explanation: Explanation of the match
            is_relevant: Whether the job is relevant
            gap_analysis: Optional gap analysis text
            resume_suggestions: Optional resume suggestions

        Returns:
            True if updated successfully
        """
        self.db.execute("""
            UPDATE jobs SET
                match_score = ?,
                match_explanation = ?,
                is_relevant = ?,
                gap_analysis = ?,
                resume_suggestions = ?
            WHERE job_url = ?
        """, (
            match_score,
            match_explanation,
            is_relevant,
            gap_analysis,
            resume_suggestions,
            job_url,
        ))

        return True

    def get_job(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Get a single job by URL

        Args:
            job_url: The job URL

        Returns:
            Job dict or None if not found
        """
        df = self.db.fetchdf(
            "SELECT * FROM jobs WHERE job_url = ?",
            (job_url,)
        )

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    def get_job_count(self, source: Optional[str] = None) -> int:
        """
        Get count of jobs in database

        Args:
            source: Optional source filter

        Returns:
            Number of jobs
        """
        if source:
            result = self.db.fetchone(
                "SELECT COUNT(*) FROM jobs WHERE source = ?",
                (source,)
            )
        else:
            result = self.db.fetchone("SELECT COUNT(*) FROM jobs")

        return result[0] if result else 0

    def get_stats(self, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about stored jobs

        Args:
            source: Optional source filter

        Returns:
            Statistics dict
        """
        where_clause = "WHERE source = ?" if source else ""
        params = (source,) if source else ()

        # Total jobs
        total = self.db.fetchone(
            f"SELECT COUNT(*) FROM jobs {where_clause}",
            params
        )[0]

        # Scored jobs
        scored = self.db.fetchone(
            f"SELECT COUNT(*) FROM jobs {where_clause} {'AND' if source else 'WHERE'} match_score IS NOT NULL",
            params
        )[0]

        # Average score
        avg_result = self.db.fetchone(
            f"SELECT AVG(match_score) FROM jobs {where_clause} {'AND' if source else 'WHERE'} match_score IS NOT NULL",
            params
        )
        avg_score = avg_result[0] if avg_result and avg_result[0] else 0

        # Score distribution
        high = self.db.fetchone(
            f"SELECT COUNT(*) FROM jobs {where_clause} {'AND' if source else 'WHERE'} match_score >= 80",
            params
        )[0]

        medium = self.db.fetchone(
            f"SELECT COUNT(*) FROM jobs {where_clause} {'AND' if source else 'WHERE'} match_score >= 60 AND match_score < 80",
            params
        )[0]

        low = self.db.fetchone(
            f"SELECT COUNT(*) FROM jobs {where_clause} {'AND' if source else 'WHERE'} match_score < 60 AND match_score IS NOT NULL",
            params
        )[0]

        return {
            "total_jobs": total,
            "scored_jobs": scored,
            "unscored_jobs": total - scored,
            "avg_score": round(avg_score, 1),
            "high_matches": high,
            "medium_matches": medium,
            "low_matches": low,
        }

    def get_all_saved_files(self, source: Optional[str] = None) -> dict:
        """
        Get list of sources in database (compatibility method)

        Args:
            source: Optional source filter

        Returns:
            Dictionary with sources
        """
        if source:
            count = self.get_job_count(source)
            return {"sources": [source] if count > 0 else []}

        result = self.db.fetchall("SELECT DISTINCT source FROM jobs")
        sources = [row[0] for row in result]
        return {"sources": sources}

    def clear_old_files(self, keep_latest: bool = True, keep_count: int = 10, source: Optional[str] = None):
        """
        Clear old jobs (kept for compatibility, but now clears from DB)

        Args:
            keep_latest: Ignored
            keep_count: Number of most recent jobs to keep per source
            source: Optional source filter
        """
        if source:
            self.db.execute("""
                DELETE FROM jobs WHERE source = ? AND job_url NOT IN (
                    SELECT job_url FROM jobs WHERE source = ?
                    ORDER BY last_seen DESC
                    LIMIT ?
                )
            """, (source, source, keep_count))
        else:
            # Clear for each source
            sources = self.db.fetchall("SELECT DISTINCT source FROM jobs")
            for (src,) in sources:
                self.db.execute("""
                    DELETE FROM jobs WHERE source = ? AND job_url NOT IN (
                        SELECT job_url FROM jobs WHERE source = ?
                        ORDER BY last_seen DESC
                        LIMIT ?
                    )
                """, (src, src, keep_count))

    def delete_jobs(self, source: Optional[str] = None, older_than_days: Optional[int] = None):
        """
        Delete jobs from database

        Args:
            source: Optional source filter
            older_than_days: Delete jobs older than this many days
        """
        conditions = []
        params = []

        if source:
            conditions.append("source = ?")
            params.append(source)

        if older_than_days:
            conditions.append("last_seen < CURRENT_TIMESTAMP - INTERVAL ? DAY")
            params.append(older_than_days)

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
            self.db.execute(f"DELETE FROM jobs {where_clause}", tuple(params))
        else:
            self.db.execute("DELETE FROM jobs")
