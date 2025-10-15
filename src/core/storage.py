"""
Data storage module for job postings

Handles saving job data to CSV and JSON formats with deduplication.
"""

import os
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .models import JobPost


class JobStorage:
    """Handles storage and retrieval of job postings"""

    def __init__(self, output_dir: str = "data"):
        """
        Initialize job storage

        Args:
            output_dir: Directory to store job data (default: "data")
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def save_jobs(
        self,
        jobs: List[JobPost],
        format: str = "both",
        deduplicate: bool = True,
        append_to_latest: bool = True,
        source: str = "indeed",
    ) -> dict:
        """
        Save job postings to file(s)

        Args:
            jobs: List of JobPost objects to save
            format: Output format - "csv", "json", or "both" (default: "both")
            deduplicate: Remove duplicate jobs based on job_url (default: True)
            append_to_latest: Also append to a "latest" file (default: True)
            source: Job source identifier for filename (default: "indeed")

        Returns:
            Dictionary with paths to saved files
        """
        if not jobs:
            print("[WARNING] No jobs to save")
            return {}

        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame([job.to_dict() for job in jobs])

        # Handle list fields for CSV storage (convert to comma-separated strings)
        list_fields = ['skills', 'requirements', 'benefits', 'work_arrangements']
        df_csv = df.copy()
        for field in list_fields:
            if field in df_csv.columns:
                # Convert lists to comma-separated strings for CSV
                df_csv[field] = df_csv[field].apply(
                    lambda x: ', '.join(x) if isinstance(x, list) and x else None
                )

        # Deduplicate if requested
        if deduplicate:
            original_count = len(df)
            df = df.drop_duplicates(subset=["job_url"], keep="first")
            df_csv = df_csv.drop_duplicates(subset=["job_url"], keep="first")
            removed = original_count - len(df)
            if removed > 0:
                print(f"[INFO] Removed {removed} duplicate job(s)")

        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        saved_files = {}

        # Save to CSV
        if format in ["csv", "both"]:
            csv_path = self.output_dir / f"jobs_{source}_{timestamp}.csv"
            df_csv.to_csv(csv_path, index=False)
            saved_files["csv"] = str(csv_path)
            print(f"[SUCCESS] Saved {len(df_csv)} jobs to CSV: {csv_path}")

            # Also save/append to latest CSV
            if append_to_latest:
                latest_csv = self.output_dir / f"jobs_{source}_latest.csv"
                if latest_csv.exists():
                    # Read existing data
                    existing_df = pd.read_csv(latest_csv)
                    # Combine and deduplicate
                    combined_df = pd.concat([existing_df, df_csv], ignore_index=True)
                    if deduplicate:
                        combined_df = combined_df.drop_duplicates(
                            subset=["job_url"], keep="last"
                        )
                    combined_df.to_csv(latest_csv, index=False)
                    print(
                        f"[INFO] Appended to latest CSV (now contains {len(combined_df)} unique jobs)"
                    )
                else:
                    df_csv.to_csv(latest_csv, index=False)
                    print(f"[INFO] Created latest CSV: {latest_csv}")

                saved_files["csv_latest"] = str(latest_csv)

        # Save to JSON
        if format in ["json", "both"]:
            json_path = self.output_dir / f"jobs_{source}_{timestamp}.json"
            # Replace NaN with None before converting to dict (NaN is not valid JSON)
            jobs_dict = df.where(pd.notna(df), None).to_dict(orient="records")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(jobs_dict, f, indent=2, ensure_ascii=False)

            saved_files["json"] = str(json_path)
            print(f"[SUCCESS] Saved {len(df)} jobs to JSON: {json_path}")

            # Also save/append to latest JSON
            if append_to_latest:
                latest_json = self.output_dir / f"jobs_{source}_latest.json"
                if latest_json.exists():
                    # Read existing data
                    with open(latest_json, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                    existing_df = pd.DataFrame(existing_data)
                    # Combine and deduplicate
                    combined_df = pd.concat([existing_df, df], ignore_index=True)
                    if deduplicate:
                        combined_df = combined_df.drop_duplicates(
                            subset=["job_url"], keep="last"
                        )
                    # Replace NaN with None before converting to dict (NaN is not valid JSON)
                    combined_dict = combined_df.where(pd.notna(combined_df), None).to_dict(orient="records")
                    with open(latest_json, "w", encoding="utf-8") as f:
                        json.dump(
                            combined_dict, f, indent=2, ensure_ascii=False
                        )
                    print(
                        f"[INFO] Appended to latest JSON (now contains {len(combined_df)} unique jobs)"
                    )
                else:
                    with open(latest_json, "w", encoding="utf-8") as f:
                        json.dump(jobs_dict, f, indent=2, ensure_ascii=False)
                    print(f"[INFO] Created latest JSON: {latest_json}")

                saved_files["json_latest"] = str(latest_json)

        return saved_files

    def load_latest(self, format: str = "csv", source: str = "indeed") -> Optional[pd.DataFrame]:
        """
        Load the latest job data

        Args:
            format: Format to load - "csv" or "json" (default: "csv")
            source: Job source identifier (default: "indeed")

        Returns:
            DataFrame with job data or None if file doesn't exist
        """
        if format == "csv":
            latest_file = self.output_dir / f"jobs_{source}_latest.csv"
            if latest_file.exists():
                return pd.read_csv(latest_file)
            # Fallback to legacy naming for backward compatibility
            legacy_file = self.output_dir / "jobs_latest.csv"
            if legacy_file.exists():
                print(f"[WARNING] Using legacy file: {legacy_file} (consider renaming to jobs_{source}_latest.csv)")
                return pd.read_csv(legacy_file)
        elif format == "json":
            latest_file = self.output_dir / f"jobs_{source}_latest.json"
            if latest_file.exists():
                with open(latest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return pd.DataFrame(data)
            # Fallback to legacy naming for backward compatibility
            legacy_file = self.output_dir / "jobs_latest.json"
            if legacy_file.exists():
                print(f"[WARNING] Using legacy file: {legacy_file} (consider renaming to jobs_{source}_latest.json)")
                with open(legacy_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return pd.DataFrame(data)

        return None

    def get_all_saved_files(self, source: Optional[str] = None) -> dict:
        """
        Get list of all saved job data files

        Args:
            source: Optional source filter (e.g., "indeed", "linkedin")

        Returns:
            Dictionary with lists of CSV and JSON files
        """
        if source:
            csv_files = sorted(self.output_dir.glob(f"jobs_{source}_*.csv"))
            json_files = sorted(self.output_dir.glob(f"jobs_{source}_*.json"))
        else:
            csv_files = sorted(self.output_dir.glob("jobs_*.csv"))
            json_files = sorted(self.output_dir.glob("jobs_*.json"))

        return {
            "csv": [str(f) for f in csv_files],
            "json": [str(f) for f in json_files],
        }

    def clear_old_files(self, keep_latest: bool = True, keep_count: int = 10, source: Optional[str] = None):
        """
        Clear old job data files, keeping only recent ones

        Args:
            keep_latest: Keep the "jobs_latest" files (default: True)
            keep_count: Number of timestamped files to keep (default: 10)
            source: Optional source filter (e.g., "indeed", "linkedin")
        """
        # Get all timestamped files (exclude "latest" files)
        if source:
            csv_files = sorted(
                [f for f in self.output_dir.glob(f"jobs_{source}_*.csv") if "latest" not in f.name]
            )
            json_files = sorted(
                [f for f in self.output_dir.glob(f"jobs_{source}_*.json") if "latest" not in f.name]
            )
        else:
            csv_files = sorted(
                [f for f in self.output_dir.glob("jobs_*.csv") if "latest" not in f.name]
            )
            json_files = sorted(
                [f for f in self.output_dir.glob("jobs_*.json") if "latest" not in f.name]
            )

        # Remove old CSV files
        if len(csv_files) > keep_count:
            for f in csv_files[:-keep_count]:
                f.unlink()
                print(f"[INFO] Removed old file: {f}")

        # Remove old JSON files
        if len(json_files) > keep_count:
            for f in json_files[:-keep_count]:
                f.unlink()
                print(f"[INFO] Removed old file: {f}")
