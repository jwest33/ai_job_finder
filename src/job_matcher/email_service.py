"""
EmailService - Gmail API Integration for Report Delivery

Automatically sends job match reports via Gmail using OAuth2 authentication.
"""

import os
import sys
import base64
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add parent directory to path for profile_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfileManager


class EmailService:
    """Gmail API email service for sending job match reports"""

    # Gmail API scope for sending emails
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(
        self,
        credentials_dir: str = "credentials",
        token_file: str = "gmail_token.json",
        client_secrets_file: str = "gmail_client_secrets.json",
        profile_name: Optional[str] = None,
    ):
        """
        Initialize EmailService

        Args:
            credentials_dir: Directory to store credentials
            token_file: Filename for OAuth2 token
            client_secrets_file: Filename for OAuth2 client secrets
            profile_name: Profile name for profile-specific email config (default: from .env ACTIVE_PROFILE)
        """
        self.credentials_dir = Path(credentials_dir)
        self.token_path = self.credentials_dir / token_file
        self.client_secrets_path = self.credentials_dir / client_secrets_file
        self.profile_name = profile_name or os.getenv("ACTIVE_PROFILE", "default")

        # Create credentials directory if needed
        self.credentials_dir.mkdir(parents=True, exist_ok=True)

        self.service = None
        self._initialize_service()

        # Load profile-specific email config with fallback to global .env
        self._load_email_config()

    def _initialize_service(self) -> bool:
        """
        Initialize Gmail API service with OAuth2 credentials

        Returns:
            True if successful, False otherwise
        """
        try:
            creds = None

            # Load existing token if available
            if self.token_path.exists():
                creds = Credentials.from_authorized_user_file(
                    str(self.token_path), self.SCOPES
                )

            # Refresh or obtain new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # Refresh expired token
                    creds.refresh(Request())
                else:
                    # No valid credentials - need to run OAuth2 flow
                    if not self.client_secrets_path.exists():
                        print(
                            f"[WARNING] Gmail client secrets not found at {self.client_secrets_path}"
                        )
                        print(
                            "   Run 'python setup_email.py' to configure email delivery"
                        )
                        return False

                    # Run OAuth2 flow
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.client_secrets_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Save credentials for next run
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())

            # Build Gmail service
            self.service = build("gmail", "v1", credentials=creds)
            return True

        except Exception as e:
            print(f"[WARNING] Failed to initialize Gmail service: {e}")
            return False

    def _load_email_config(self):
        """Load email configuration from profile or global .env"""
        # Try to load profile-specific config
        try:
            manager = ProfileManager()
            profile_email_config = manager.get_profile_email_config(self.profile_name)

            if profile_email_config:
                # Use profile-specific settings
                self.recipients = profile_email_config.get("recipients", [])
                self.subject_prefix = profile_email_config.get(
                    "subject_prefix", os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]")
                )
                self.enabled = profile_email_config.get(
                    "enabled", os.getenv("EMAIL_ENABLED", "true").lower() == "true"
                )
                self.min_matches = profile_email_config.get(
                    "min_matches", int(os.getenv("EMAIL_MIN_MATCHES", "1"))
                )
                self.config_source = "profile"
            else:
                # Fall back to global .env settings
                self._load_global_config()
        except Exception:
            # If profile loading fails, fall back to global
            self._load_global_config()

    def _load_global_config(self):
        """Load email configuration from global .env"""
        # Parse recipients from .env (comma-separated)
        email_recipient = os.getenv("EMAIL_RECIPIENT", "")
        self.recipients = [e.strip() for e in email_recipient.split(",") if e.strip()]

        self.subject_prefix = os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]")
        self.enabled = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
        self.min_matches = int(os.getenv("EMAIL_MIN_MATCHES", "1"))
        self.config_source = "global"

    def get_recipients(self) -> List[str]:
        """Get list of email recipients for this profile"""
        return self.recipients

    def get_subject_prefix(self) -> str:
        """Get email subject prefix for this profile"""
        return self.subject_prefix

    def is_enabled(self) -> bool:
        """Check if email is enabled for this profile"""
        return self.enabled

    def get_min_matches(self) -> int:
        """Get minimum matches threshold for this profile"""
        return self.min_matches

    def is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return self.service is not None and len(self.recipients) > 0

    def send_report_to_all(
        self,
        jobs: List[Dict[str, Any]],
        report_path: str,
    ) -> bool:
        """
        Send job match report to all configured recipients

        Args:
            jobs: List of matched jobs
            report_path: Path to HTML report file

        Returns:
            True if at least one email sent successfully
        """
        if not self.recipients:
            print("[WARNING] No email recipients configured")
            return False

        success_count = 0
        for recipient in self.recipients:
            if self.send_report(recipient, jobs, report_path, self.subject_prefix):
                success_count += 1

        return success_count > 0

    def send_report(
        self,
        recipient: str,
        jobs: List[Dict[str, Any]],
        report_path: str,
        subject_prefix: Optional[str] = None,
    ) -> bool:
        """
        Send job match report via email

        Args:
            recipient: Email address to send report to
            jobs: List of matched jobs
            report_path: Path to HTML report file
            subject_prefix: Prefix for email subject (default: from profile/global config)

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.service:
            print("[WARNING] Email service not configured. Skipping email delivery.")
            return False

        # Use configured subject prefix if not provided
        if subject_prefix is None:
            subject_prefix = self.subject_prefix

        try:
            # Generate email content
            subject = self._generate_subject(jobs, subject_prefix)
            body_html = self._generate_email_body(jobs, report_path)

            # Create email message
            message = self._create_message_with_attachment(
                recipient, subject, body_html, report_path
            )

            # Send email
            self.service.users().messages().send(
                userId="me", body=message
            ).execute()

            print(f"Email sent to {recipient}")
            return True

        except HttpError as e:
            print(f"[ERROR] Failed to send email: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error sending email: {e}")
            return False

    def send_multi_source_report(
        self,
        recipient: str,
        jobs_by_source: List[Tuple[str, List[Dict[str, Any]]]],
        report_paths: List[str],
        subject_prefix: str = "[Job Matcher]",
    ) -> bool:
        """
        Send multi-source job match report via email

        Args:
            recipient: Email address to send report to
            jobs_by_source: List of (source, jobs) tuples
            report_paths: List of paths to HTML report files
            subject_prefix: Prefix for email subject

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.service:
            print("[WARNING] Email service not configured. Skipping email delivery.")
            return False

        try:
            # Generate email content
            subject = self._generate_multi_source_subject(jobs_by_source, subject_prefix)
            body_html = self._generate_multi_source_email_body(jobs_by_source, report_paths)

            # Create email message with multiple attachments
            message = self._create_message_with_multiple_attachments(
                recipient, subject, body_html, report_paths
            )

            # Send email
            self.service.users().messages().send(
                userId="me", body=message
            ).execute()

            print(f"Email sent to {recipient}")
            return True

        except HttpError as e:
            print(f"[ERROR] Failed to send email: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error sending email: {e}")
            return False

    def _generate_subject(
        self, jobs: List[Dict[str, Any]], prefix: str
    ) -> str:
        """Generate email subject line with metadata"""
        total_jobs = len(jobs)
        today = datetime.now().strftime("%b %d")  # e.g., "Oct 11"

        if total_jobs == 0:
            return f"{prefix} No New Matches | {today}"

        # Calculate excellent matches
        excellent = sum(1 for job in jobs if job.get("match_score", 0) >= 90)

        # Format: [Prefix] X Job Matches Found (Y Excellent) | Date
        match_text = f"{total_jobs} Job {'Match' if total_jobs == 1 else 'Matches'} Found"

        # Add excellent count if any
        if excellent > 0:
            match_text += f" ({excellent} Excellent)"

        return f"{prefix} {match_text} | {today}"

    def _get_random_image(self, assets_dir: str = "assets") -> Optional[Tuple[bytes, str]]:
        """
        Get a random image from the assets directory

        Args:
            assets_dir: Directory containing image assets

        Returns:
            Tuple of (image_bytes, filename) or None if no images found
        """
        assets_path = Path(assets_dir)

        if not assets_path.exists():
            return None

        # Find all JPEG images
        image_files = list(assets_path.glob("*.jpeg")) + list(assets_path.glob("*.jpg"))

        if not image_files:
            return None

        # Select random image
        selected_image = random.choice(image_files)

        try:
            with open(selected_image, "rb") as f:
                image_bytes = f.read()
            return (image_bytes, selected_image.name)
        except Exception as e:
            print(f"Warning: Failed to load image {selected_image}: {e}")
            return None

    def _generate_email_body(
        self, jobs: List[Dict[str, Any]], report_path: str
    ) -> str:
        """Generate HTML email body with summary and top jobs"""

        if not jobs:
            return """
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <h2>Job Matcher Report</h2>
                    <p>No new job matches found.</p>
                    <p style="color: #666; font-size: 0.9em;">
                        Generated: {timestamp}
                    </p>
                </body>
            </html>
            """.format(
                timestamp=datetime.now().strftime("%B %d, %Y at %I:%M %p")
            )

        # Calculate statistics
        total_jobs = len(jobs)
        avg_score = sum(job.get("match_score", 0) for job in jobs) / total_jobs
        excellent = sum(1 for job in jobs if job.get("match_score", 0) >= 90)
        good = sum(1 for job in jobs if 80 <= job.get("match_score", 0) < 90)
        fair = sum(1 for job in jobs if 70 <= job.get("match_score", 0) < 80)

        # Sort jobs by score
        sorted_jobs = sorted(
            jobs, key=lambda x: x.get("match_score", 0), reverse=True
        )

        # Get top 5 jobs
        top_jobs = sorted_jobs[:5]

        # Build email HTML
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #2c3e50;">Job Matcher Report</h2>

                <div style="background: #e8f5e9; border: 2px solid #27ae60; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <h3 style="margin: 0 0 10px 0; color: #27ae60;">[INFO] Full Interactive Report Attached</h3>
                    <p style="margin: 0; font-size: 1.1em;">
                        <strong>Open the attached HTML file</strong> to view the complete report
                    </p>
                </div>

                <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Summary</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px;"><strong>Total Matches:</strong></td>
                            <td style="padding: 8px;">{total_jobs}</td>
                        </tr>
                    </table>
                </div>

                <h3 style="color: #2c3e50;">Top 5 Matches (Preview)</h3>
        """

        # Add top job cards
        for i, job in enumerate(top_jobs, 1):
            title = job.get("title", "Unknown Position")
            company = job.get("company", "Unknown Company")
            location = job.get("location", "Unknown Location")
            score = job.get("match_score", 0)
            job_url = job.get("job_url", "#")
            remote = job.get("remote", False)
            salary_min = job.get("salary_min")
            salary_max = job.get("salary_max")

            # Score color
            if score >= 90:
                score_color = "#27ae60"
            elif score >= 80:
                score_color = "#3498db"
            else:
                score_color = "#f39c12"

            # Salary info
            salary_html = ""
            # Defensive type conversion: handle string/int/float salary values
            try:
                if salary_min:
                    salary_min = float(salary_min)
                if salary_max:
                    salary_max = float(salary_max)

                if salary_min and salary_max:
                    salary_html = f'<p style="margin: 5px 0; color: #27ae60; font-weight: 600;">${salary_min:,.0f} - ${salary_max:,.0f}</p>'
                elif salary_min:
                    salary_html = f'<p style="margin: 5px 0; color: #27ae60; font-weight: 600;">${salary_min:,.0f}+</p>'
            except (TypeError, ValueError):
                # If conversion fails, skip salary display
                pass

            html += f"""
                <div style="background: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 15px 0;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="vertical-align: top; width: 75%;">
                                <h4 style="margin: 0 0 10px 0; color: #2c3e50;">{title}</h4>
                                <p style="margin: 5px 0; color: #7f8c8d;">
                                    {company} • {location}
                                    {' • <span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em;">Remote</span>' if remote else ''}
                                </p>
                                {salary_html}
                            </td>
                            <td style="vertical-align: top; text-align: right; width: 25%; padding-left: 15px;">
                                <div style="font-size: 1.5em; font-weight: bold; color: {score_color}; margin-bottom: 10px;">{score}</div>
                                <a href="{job_url}" style="background: #3498db; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; display: inline-block; white-space: nowrap;">Apply Now</a>
                            </td>
                        </tr>
                    </table>
                </div>
            """

        # Add footer
        report_filename = Path(report_path).name
        html += f"""
                <div style="background: #fff3cd; border-left: 4px solid #f39c12; padding: 15px; margin: 30px 0;">
                    <p style="margin: 0; font-size: 1em;">
                        <strong>[INFO] Remember:</strong> This is just a preview of the top 5 matches.<br>
                        <strong>Open the attached file <code>{report_filename}</code></strong> to see all {total_jobs} matches with complete details.
                    </p>
                </div>

                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
                    <p style="color: #666; font-size: 0.9em;">
                        Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br>
                        Powered by JobMatcher AI
                    </p>
                </div>

                <div style="text-align: center; margin-top: 30px;">
                    <img src="cid:random_image" alt="Random image" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                </div>
            </body>
        </html>
        """

        return html

    def _create_message_with_attachment(
        self,
        to: str,
        subject: str,
        body_html: str,
        attachment_path: str,
    ) -> Dict[str, str]:
        """
        Create email message with HTML body and attachment

        Args:
            to: Recipient email address
            subject: Email subject
            body_html: HTML email body
            attachment_path: Path to file to attach

        Returns:
            Gmail API message dict
        """
        # Create multipart message
        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject

        # Add HTML body
        message.attach(MIMEText(body_html, "html"))

        # Add random inline image
        random_image = self._get_random_image()
        if random_image:
            image_bytes, image_filename = random_image
            image_part = MIMEImage(image_bytes)
            image_part.add_header("Content-ID", "<random_image>")
            image_part.add_header("Content-Disposition", "inline", filename=image_filename)
            message.attach(image_part)

        # Add attachment
        if Path(attachment_path).exists():
            attachment_filename = Path(attachment_path).name

            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())

            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={attachment_filename}",
            )
            message.attach(part)

        # Encode message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {"raw": raw}

    def send_test_email(self, recipient: str) -> bool:
        """
        Send a test email to verify configuration

        Args:
            recipient: Email address to send test to

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            print("[WARNING] Email service not configured")
            return False

        try:
            # Create simple test message
            message = MIMEText("This is a test email from Job Matcher.")
            message["to"] = recipient
            message["subject"] = "[Job Matcher] Test Email"

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            self.service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()

            print(f"Test email sent to {recipient}")
            return True

        except HttpError as e:
            print(f"[ERROR] Failed to send test email: {e}")
            return False

    def _generate_multi_source_subject(
        self, jobs_by_source: List[Tuple[str, List[Dict[str, Any]]]], prefix: str
    ) -> str:
        """
        Generate email subject line for multi-source reports

        Args:
            jobs_by_source: List of (source, jobs) tuples
            prefix: Email subject prefix

        Returns:
            Subject line string
        """
        today = datetime.now().strftime("%b %d")
        total_jobs = sum(len(jobs) for _, jobs in jobs_by_source)

        if total_jobs == 0:
            return f"{prefix} No New Matches | {today}"

        # Calculate excellent matches across all sources
        excellent = sum(
            sum(1 for job in jobs if job.get("match_score", 0) >= 90)
            for _, jobs in jobs_by_source
        )

        # Build source breakdown (e.g., "Indeed: 30, Glassdoor: 15")
        source_breakdown = ", ".join(
            f"{source.title()}: {len(jobs)}"
            for source, jobs in jobs_by_source
            if len(jobs) > 0
        )

        # Format: [Prefix] X Total Matches (Indeed: Y, Glassdoor: Z) (A Excellent) | Date
        match_text = f"{total_jobs} Total {'Match' if total_jobs == 1 else 'Matches'}"

        if source_breakdown:
            match_text += f" ({source_breakdown})"

        if excellent > 0:
            match_text += f" ({excellent} Excellent)"

        return f"{prefix} {match_text} | {today}"

    def _generate_multi_source_email_body(
        self, jobs_by_source: List[Tuple[str, List[Dict[str, Any]]]], report_paths: List[str]
    ) -> str:
        """
        Generate HTML email body for multi-source reports

        Args:
            jobs_by_source: List of (source, jobs) tuples
            report_paths: List of report file paths

        Returns:
            HTML email body string
        """
        # Calculate overall statistics
        total_jobs = sum(len(jobs) for _, jobs in jobs_by_source)
        all_jobs = [job for _, jobs in jobs_by_source for job in jobs]

        if total_jobs == 0:
            return """
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <h2>Job Matcher Report</h2>
                    <p>No new job matches found across any sources.</p>
                    <p style="color: #666; font-size: 0.9em;">
                        Generated: {timestamp}
                    </p>
                </body>
            </html>
            """.format(
                timestamp=datetime.now().strftime("%B %d, %Y at %I:%M %p")
            )

        avg_score = sum(job.get("match_score", 0) for job in all_jobs) / total_jobs
        excellent = sum(1 for job in all_jobs if job.get("match_score", 0) >= 90)
        good = sum(1 for job in all_jobs if 80 <= job.get("match_score", 0) < 90)
        fair = sum(1 for job in all_jobs if 70 <= job.get("match_score", 0) < 80)

        # Source icons
        source_icons = {
            "indeed": "[Indeed]",
            "glassdoor": "[Glassdoor]",
            "linkedin": "[LinkedIn]",
            "ziprecruiter": "[ZipRecruiter]"
        }

        # Build email HTML
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="background: #e8f5e9; border: 2px solid #27ae60; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <h3 style="margin: 0 0 10px 0; color: #27ae60;">[INFO] Full Interactive Reports Attached</h3>
                    <p style="margin: 0; font-size: 1.1em;">
                        <strong>Open the attached HTML files</strong> to view complete reports for each source
                    </p>
                </div>

                <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Overall Summary</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px;"><strong>Total Matches:</strong></td>
                            <td style="padding: 8px;">{total_jobs}</td>
                        </tr>
        """

        # Add per-source breakdown
        for source, jobs in jobs_by_source:
            icon = source_icons.get(source, "[Other]")
            html += f"""
                        <tr>
                            <td style="padding: 8px; padding-left: 20px;"><em>{icon} {source.title()}:</em></td>
                            <td style="padding: 8px;">{len(jobs)}</td>
                        </tr>
            """

        # Add per-source job previews
        for source, jobs in jobs_by_source:
            if not jobs:
                continue

            icon = source_icons.get(source, "[Other]")
            sorted_jobs = sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)
            top_jobs = sorted_jobs[:5]  # Top 5 per source

            html += f"""
                <div style="background: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #2c3e50;">{icon} {source.upper()} - Top 5 Matches (Preview)</h3>
            """

            for i, job in enumerate(top_jobs, 1):
                title = job.get("title", "Unknown Position")
                company = job.get("company", "Unknown Company")
                location = job.get("location", "Unknown Location")
                score = job.get("match_score", 0)
                job_url = job.get("job_url", "#")
                remote = job.get("remote", False)
                salary_min = job.get("salary_min")
                salary_max = job.get("salary_max")

                # Score color
                if score >= 90:
                    score_color = "#27ae60"
                elif score >= 80:
                    score_color = "#3498db"
                else:
                    score_color = "#f39c12"

                # Salary info
                salary_html = ""
                try:
                    if salary_min:
                        salary_min = float(salary_min)
                    if salary_max:
                        salary_max = float(salary_max)

                    if salary_min and salary_max:
                        salary_html = f'<p style="margin: 5px 0; color: #27ae60; font-weight: 600;">${salary_min:,.0f} - ${salary_max:,.0f}</p>'
                    elif salary_min:
                        salary_html = f'<p style="margin: 5px 0; color: #27ae60; font-weight: 600;">${salary_min:,.0f}+</p>'
                except (TypeError, ValueError):
                    pass

                html += f"""
                    <div style="background: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 15px 0;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="vertical-align: top; width: 75%;">
                                    <h4 style="margin: 0 0 10px 0; color: #2c3e50;">{title}</h4>
                                    <p style="margin: 5px 0; color: #7f8c8d;">
                                        {company} • {location}
                                        {' • <span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em;">Remote</span>' if remote else ''}
                                    </p>
                                    {salary_html}
                                </td>
                                <td style="vertical-align: top; text-align: right; width: 25%; padding-left: 15px;">
                                    <div style="font-size: 1.5em; font-weight: bold; color: {score_color}; margin-bottom: 10px;">{score}</div>
                                    <a href="{job_url}" style="background: #3498db; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; display: inline-block; white-space: nowrap;">Apply Now</a>
                                </td>
                            </tr>
                        </table>
                    </div>
                """

            html += """
                </div>
            """

            # Add footer
            html += f"""
                    <div style="background: #fff3cd; border-left: 4px solid #f39c12; padding: 15px; margin: 30px 0;">
                        <p style="margin: 0; font-size: 1em;">
                            <strong>[INFO] Remember:</strong> This email shows only the top 5 matches per source.<br>
                            <strong>Open the attached HTML files</strong> to see all {total_jobs} matches with complete details.
                        </p>
                    </div>

                    <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
                        <p style="color: #666; font-size: 0.9em;">
                            Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br>
                            Powered by JobMatcher AI
                        </p>
                    </div>
                </body>
            </html>
            """
    
        random_image = self._get_random_image()
        if random_image:

            # Add footer
            html += f"""
                    <div style="text-align: center; margin-top: 30px;">
                        <img src="cid:random_image" alt="Random image" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    </div>
                </body>
            </html>
            """

        return html

    def _create_message_with_multiple_attachments(
        self,
        to: str,
        subject: str,
        body_html: str,
        attachment_paths: List[str],
    ) -> Dict[str, str]:
        """
        Create email message with HTML body and multiple attachments

        Args:
            to: Recipient email address
            subject: Email subject
            body_html: HTML email body
            attachment_paths: List of paths to files to attach

        Returns:
            Gmail API message dict
        """
        # Create multipart message
        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject

        # Add HTML body
        message.attach(MIMEText(body_html, "html"))

        # Add random inline image
        random_image = self._get_random_image()
        if random_image:
            image_bytes, image_filename = random_image
            image_part = MIMEImage(image_bytes)
            image_part.add_header("Content-ID", "<random_image>")
            image_part.add_header("Content-Disposition", "inline", filename=image_filename)
            message.attach(image_part)

        # Add all attachments
        for attachment_path in attachment_paths:
            if Path(attachment_path).exists():
                attachment_filename = Path(attachment_path).name

                with open(attachment_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())

                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={attachment_filename}",
                )
                message.attach(part)

        # Encode message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {"raw": raw}


if __name__ == "__main__":
    # Test email service
    import sys
    from dotenv import load_dotenv

    load_dotenv()

    email_recipient = os.getenv("EMAIL_RECIPIENT")
    if not email_recipient:
        print("[ERROR] EMAIL_RECIPIENT not set in .env file")
        sys.exit(1)

    print("Testing EmailService...")
    service = EmailService()

    if service.is_configured():
        print("Email service configured successfully")
        print(f"\nSending test email to {email_recipient}...")
        if service.send_test_email(email_recipient):
            print("\nTest complete! Check your inbox.")
        else:
            print("\n[ERROR] Test failed")
    else:
        print("[ERROR] Email service not configured")
        print("   Run 'python setup_email.py' to set up email delivery")
