#!/usr/bin/env python3
"""
Email Setup Wizard - Configure Gmail API for Job Matcher

Interactive setup script for configuring Gmail OAuth2 authentication.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()


def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_step(number: int, text: str):
    """Print step number and text"""
    print(f"\n[INFO] Step {number}: {text}")
    print("-" * 80)


def print_success(text: str):
    """Print success message"""
    print(f"{text}")


def print_error(text: str):
    """Print error message"""
    print(f"X {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"[WARNING] {text}")


def print_info(text: str):
    """Print info message"""
    print(f"[INFO] {text}")


def main():
    """Run email setup wizard"""

    print_header("Job Matcher - Email Setup Wizard")

    print("""
This wizard will help you configure Gmail API integration for automated
email delivery of job match reports.

You will need:
1. A Google Cloud Console account (free)
2. Gmail API enabled
3. OAuth2 client credentials
    """)

    input("Press Enter to continue...")

    # Step 1: Google Cloud Console Setup
    print_step(1, "Google Cloud Console Setup")

    print("""
1. Go to: https://console.cloud.google.com/
2. Create a new project (or select existing):
   - Click "Select a project" → "New Project"
   - Name it "Job Matcher" (or any name)
   - Click "Create"

3. Enable Gmail API:
   - Go to: https://console.cloud.google.com/apis/library/gmail.googleapis.com
   - Click "Enable"

4. Configure OAuth consent screen:
   - Go to: https://console.cloud.google.com/apis/credentials/consent
   - Select "External" user type → Click "Create"
   - Fill in App information:
     * App name: "Job Matcher"
     * User support email: (your email)
     * Developer contact: (your email)
   - Click "Save and Continue"
   - Scopes: Click "Save and Continue" (no changes needed)
   - Test users: Add your Gmail address → Click "Save and Continue"
   - Click "Back to Dashboard"

5. Create OAuth2 credentials:
   - Go to: https://console.cloud.google.com/apis/credentials
   - Click "+ CREATE CREDENTIALS" → "OAuth client ID"
   - Application type: "Desktop app"
   - Name: "Job Matcher Desktop"
   - Click "Create"
   - Click "Download JSON" (IMPORTANT: Save this file!)
    """)

    input("\nPress Enter once you've downloaded the credentials JSON file...")

    # Step 2: Save credentials file
    print_step(2, "Save OAuth2 Credentials")

    print("""
You should have downloaded a JSON file named something like:
    client_secret_XXXX.apps.googleusercontent.com.json

We need to save this as 'gmail_client_secrets.json' in the credentials folder.
    """)

    # Create credentials directory
    credentials_dir = Path("credentials")
    credentials_dir.mkdir(parents=True, exist_ok=True)
    print_success(f"Created credentials directory: {credentials_dir}")

    # Get path to downloaded file
    while True:
        print("\nEnter the full path to your downloaded credentials JSON file:")
        print("(e.g., C:\\Users\\YourName\\Downloads\\client_secret_xxx.json)")
        source_path = input("> ").strip().strip('"').strip("'")

        if not source_path:
            print_error("Path cannot be empty")
            continue

        source_file = Path(source_path)

        if not source_file.exists():
            print_error(f"File not found: {source_file}")
            retry = input("Try again? (y/n): ").lower()
            if retry != 'y':
                print("\nExiting setup. Run 'python setup_email.py' again when ready.")
                sys.exit(0)
            continue

        # Validate JSON
        try:
            with open(source_file, 'r') as f:
                credentials_data = json.load(f)

            # Check for required fields
            if "installed" not in credentials_data and "web" not in credentials_data:
                print_error("Invalid credentials file format")
                continue

            # Copy to credentials directory
            dest_file = credentials_dir / "gmail_client_secrets.json"
            with open(dest_file, 'w') as f:
                json.dump(credentials_data, f, indent=2)

            print_success(f"Credentials saved to: {dest_file}")
            break

        except json.JSONDecodeError:
            print_error("Invalid JSON file")
            continue
        except Exception as e:
            print_error(f"Error reading file: {e}")
            continue

    # Step 3: Configure .env
    print_step(3, "Configure Email Settings")

    env_file = Path(".env")

    # Get email recipients (can be multiple, comma-separated)
    current_email = os.getenv("EMAIL_RECIPIENT", "")
    if current_email:
        print(f"\nCurrent email recipient(s): {current_email}")
        use_current = input("Keep these email(s)? (y/n): ").lower()
        if use_current != 'y':
            current_email = ""

    if not current_email:
        print("\n[INFO] You can enter multiple email addresses separated by commas")
        print("   Example: user1@gmail.com,user2@gmail.com")
        while True:
            email_input = input("\nEnter email address(es) where reports will be sent: ").strip()

            # Parse comma-separated emails
            emails = [e.strip() for e in email_input.split(',') if e.strip()]

            # Validate all emails
            all_valid = True
            for email in emails:
                if "@" not in email or "." not in email:
                    print_error(f"Invalid email format: {email}")
                    all_valid = False
                    break

            if all_valid and emails:
                current_email = ','.join(emails)
                if len(emails) > 1:
                    print_success(f"[SUCCESS] Configured {len(emails)} email recipients")
                break
            else:
                print_error("Please enter at least one valid email address")

    # Get email enabled setting
    print("\nEnable automatic email delivery?")
    print("  - If enabled, reports will be emailed automatically when job matching completes")
    print("  - If disabled, you can still send emails manually with --email flag")
    enable_email = input("Enable automatic emails? (y/n) [y]: ").lower()
    email_enabled = "true" if enable_email != 'n' else "false"

    # Get minimum matches threshold
    print("\nMinimum matches to trigger email:")
    print("  - Only send email if at least this many jobs match")
    min_matches = input("Minimum matches [1]: ").strip()
    if not min_matches or not min_matches.isdigit():
        min_matches = "1"

    # Get subject prefix
    print("\nEmail subject prefix:")
    current_prefix = os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]")
    print(f"  Current: {current_prefix}")
    subject_prefix = input(f"Subject prefix [{current_prefix}]: ").strip()
    if not subject_prefix:
        subject_prefix = current_prefix

    # Update .env file
    print("\nUpdating .env file...")

    # Read existing .env content
    env_content = ""
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()

    # Check if email section exists
    if "# Email Configuration" not in env_content:
        # Add email configuration section
        email_config = f"""
# =============================================================================
# Email Configuration
# =============================================================================

# Enable/disable automatic email delivery of reports
EMAIL_ENABLED={email_enabled}

# Email address to send reports to
EMAIL_RECIPIENT={current_email}

# Send email automatically when pipeline completes (requires EMAIL_ENABLED=true)
EMAIL_SEND_ON_COMPLETION={email_enabled}

# Only send email if at least this many matches are found
EMAIL_MIN_MATCHES={min_matches}

# Email subject line prefix
EMAIL_SUBJECT_PREFIX={subject_prefix}
"""
        # Append to .env
        with open(env_file, 'a') as f:
            f.write(email_config)
        print_success("Added email configuration to .env")
    else:
        # Update existing values
        set_key(env_file, "EMAIL_ENABLED", email_enabled)
        set_key(env_file, "EMAIL_RECIPIENT", current_email)
        set_key(env_file, "EMAIL_SEND_ON_COMPLETION", email_enabled)
        set_key(env_file, "EMAIL_MIN_MATCHES", min_matches)
        set_key(env_file, "EMAIL_SUBJECT_PREFIX", subject_prefix)
        print_success("Updated email configuration in .env")

    # Step 4: Test email
    print_step(4, "Test Email Configuration")

    print("""
We'll now test the email configuration by:
1. Running the OAuth2 authentication flow (opens browser)
2. Sending a test email to your inbox
    """)

    test_now = input("\nRun email test now? (y/n) [y]: ").lower()

    if test_now != 'n':
        print("\nInitializing email service...")
        print("(A browser window will open for authentication)")

        try:
            # Import and test email service
            from job_matcher.email_service import EmailService

            service = EmailService()

            if service.is_configured():
                print_success("Email service initialized")

                # Parse recipients
                recipients = [e.strip() for e in current_email.split(',') if e.strip()]

                print(f"\nSending test email to {len(recipients)} recipient(s)...")
                all_success = True
                for recipient in recipients:
                    print(f"  Sending to {recipient}...")
                    if service.send_test_email(recipient):
                        print_success(f"    [SUCCESS] Sent to {recipient}")
                    else:
                        print_error(f"    [ERROR] Failed to send to {recipient}")
                        all_success = False

                if all_success:
                    print_success(f"\n[SUCCESS] Test emails sent successfully to all {len(recipients)} recipient(s)!")
                    print(f"Check inbox(es) at: {current_email}")
                else:
                    print_error("\n[WARNING] Some test emails failed")
            else:
                print_error("Email service initialization failed")

        except Exception as e:
            print_error(f"Test failed: {e}")
            print("\nYou can test manually later with:")
            print("  python -m job_matcher.email_service")

    # Step 5: Complete
    print_step(5, "Setup Complete!")

    # Count recipients
    recipient_count = len([e.strip() for e in current_email.split(',') if e.strip()])
    recipient_label = "recipient" if recipient_count == 1 else "recipients"

    print(f"""
Email delivery is now configured!

Configuration:
  - Credentials: {dest_file}
  - Email {recipient_label}: {current_email}
  - Auto-send enabled: {email_enabled}
  - Minimum matches: {min_matches}
  - Subject prefix: {subject_prefix}

Usage:
  # Automatic email (if EMAIL_ENABLED=true):
  python job_matcher.py --input data/jobs_latest.json --full-pipeline

  # Force email regardless of config:
  python job_matcher.py --input data/jobs_latest.json --full-pipeline --email

  # Skip email even if enabled:
  python job_matcher.py --input data/jobs_latest.json --full-pipeline --no-email

  # Test email service:
  python -m job_matcher.email_service

Next Steps:
  1. Run a job search: python run_job_search.py
  2. Run job matcher with email: python job_matcher.py --input data/jobs_latest.json --full-pipeline
  3. Check your inbox for the report!

Troubleshooting:
  - If authentication fails, delete credentials/gmail_token.json and try again
  - Check that your email is added as a test user in Google Cloud Console
  - Verify Gmail API is enabled in Google Cloud Console
    """)

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[WARNING] Setup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nX Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
