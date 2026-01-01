"""
Attachments API Endpoints

REST endpoints for managing job application file attachments (resumes, cover letters).
"""

import os
import uuid
from typing import Optional, List
from urllib.parse import unquote
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from dotenv import load_dotenv

from src.core.database import get_database
from src.utils.profile_manager import ProfilePaths

router = APIRouter()

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt'}
ALLOWED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'text/plain': '.txt',
}


def get_profile_database():
    """Get database for the current active profile, reloading env first."""
    load_dotenv(override=True)
    return get_database()


def get_attachments_dir() -> Path:
    """Get attachments directory for current profile."""
    load_dotenv(override=True)
    paths = ProfilePaths()
    attachments_dir = paths.attachments_dir
    attachments_dir.mkdir(parents=True, exist_ok=True)
    return attachments_dir


def get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    return Path(filename).suffix.lower()


def format_file_size(size_bytes: int) -> str:
    """Format file size for display."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# =============================================================================
# Pydantic Models
# =============================================================================


class AttachmentResponse(BaseModel):
    """Single attachment response"""
    id: str
    job_url: str
    attachment_type: str
    filename: str
    file_extension: str
    file_size: int
    file_size_display: str
    mime_type: str
    notes: Optional[str] = None
    created_at: str


class AttachmentListResponse(BaseModel):
    """List of attachments response"""
    items: List[AttachmentResponse]
    total: int


class AttachmentUploadResponse(BaseModel):
    """Upload response"""
    success: bool
    attachment: AttachmentResponse
    message: str


class AttachmentNotesUpdate(BaseModel):
    """Notes update request"""
    notes: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/{job_url:path}", response_model=AttachmentListResponse)
async def get_attachments(job_url: str):
    """
    Get all attachments for a job.
    """
    db = get_profile_database()
    decoded_url = unquote(job_url)

    # Check if job exists
    job = db.fetchone("SELECT job_url FROM jobs WHERE job_url = ?", (decoded_url,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get attachments
    columns, rows = db.execute_fetch("""
        SELECT id, job_url, attachment_type, filename, stored_filename,
               file_extension, file_size, mime_type, notes, created_at
        FROM job_attachments
        WHERE job_url = ?
        ORDER BY attachment_type, created_at DESC
    """, (decoded_url,))

    items = []
    for row in rows:
        attachment_dict = dict(zip(columns, row))
        attachment_dict['created_at'] = str(attachment_dict['created_at'])
        attachment_dict['file_size_display'] = format_file_size(attachment_dict['file_size'])
        # Remove stored_filename from response (internal use only)
        del attachment_dict['stored_filename']
        items.append(AttachmentResponse(**attachment_dict))

    return AttachmentListResponse(items=items, total=len(items))


@router.post("/{job_url:path}/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(
    job_url: str,
    file: UploadFile = File(...),
    attachment_type: str = Form(...),
    notes: Optional[str] = Form(None),
):
    """
    Upload a new attachment for a job.

    - attachment_type: 'resume' or 'cover_letter'
    - file: PDF, Word (.doc, .docx), or text file (max 10MB)
    """
    db = get_profile_database()
    decoded_url = unquote(job_url)

    # Validate job exists
    job = db.fetchone("SELECT job_url FROM jobs WHERE job_url = ?", (decoded_url,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Validate attachment type
    if attachment_type not in ('resume', 'cover_letter'):
        raise HTTPException(
            status_code=400,
            detail="attachment_type must be 'resume' or 'cover_letter'"
        )

    # Validate file extension
    file_extension = get_file_extension(file.filename)
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )

    # Determine MIME type
    mime_type = file.content_type or 'application/octet-stream'
    # Validate MIME type matches extension
    if mime_type in ALLOWED_MIME_TYPES:
        expected_ext = ALLOWED_MIME_TYPES[mime_type]
        if expected_ext != file_extension:
            # Trust the extension over the MIME type
            pass

    # Generate unique IDs
    attachment_id = str(uuid.uuid4())
    stored_filename = f"{attachment_id}{file_extension}"

    # Save file to disk
    attachments_dir = get_attachments_dir()
    file_path = attachments_dir / stored_filename

    try:
        with open(file_path, 'wb') as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Insert database record
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute("""
            INSERT INTO job_attachments
            (id, job_url, attachment_type, filename, stored_filename, file_extension, file_size, mime_type, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attachment_id,
            decoded_url,
            attachment_type,
            file.filename,
            stored_filename,
            file_extension,
            file_size,
            mime_type,
            notes,
            now,
        ))
    except Exception as e:
        # Clean up file if database insert fails
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save attachment record: {str(e)}")

    attachment = AttachmentResponse(
        id=attachment_id,
        job_url=decoded_url,
        attachment_type=attachment_type,
        filename=file.filename,
        file_extension=file_extension,
        file_size=file_size,
        file_size_display=format_file_size(file_size),
        mime_type=mime_type,
        notes=notes,
        created_at=now,
    )

    return AttachmentUploadResponse(
        success=True,
        attachment=attachment,
        message="Attachment uploaded successfully"
    )


@router.get("/{job_url:path}/{attachment_id}/download")
async def download_attachment(job_url: str, attachment_id: str):
    """
    Download an attachment file.
    """
    db = get_profile_database()
    decoded_url = unquote(job_url)

    # Get attachment record
    result = db.fetchone("""
        SELECT filename, stored_filename, mime_type
        FROM job_attachments
        WHERE id = ? AND job_url = ?
    """, (attachment_id, decoded_url))

    if not result:
        raise HTTPException(status_code=404, detail="Attachment not found")

    filename, stored_filename, mime_type = result

    # Get file path
    attachments_dir = get_attachments_dir()
    file_path = attachments_dir / stored_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Attachment file not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=mime_type,
    )


@router.delete("/{job_url:path}/{attachment_id}")
async def delete_attachment(job_url: str, attachment_id: str):
    """
    Delete an attachment.
    """
    db = get_profile_database()
    decoded_url = unquote(job_url)

    # Get attachment record
    result = db.fetchone("""
        SELECT stored_filename
        FROM job_attachments
        WHERE id = ? AND job_url = ?
    """, (attachment_id, decoded_url))

    if not result:
        raise HTTPException(status_code=404, detail="Attachment not found")

    stored_filename = result[0]

    # Delete file from disk
    attachments_dir = get_attachments_dir()
    file_path = attachments_dir / stored_filename

    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

    # Delete database record
    db.execute("""
        DELETE FROM job_attachments
        WHERE id = ? AND job_url = ?
    """, (attachment_id, decoded_url))

    return {"success": True, "message": "Attachment deleted"}


@router.put("/{job_url:path}/{attachment_id}")
async def update_attachment_notes(
    job_url: str,
    attachment_id: str,
    update: AttachmentNotesUpdate,
):
    """
    Update attachment notes.
    """
    db = get_profile_database()
    decoded_url = unquote(job_url)

    # Check attachment exists
    result = db.fetchone("""
        SELECT id FROM job_attachments
        WHERE id = ? AND job_url = ?
    """, (attachment_id, decoded_url))

    if not result:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Update notes
    db.execute("""
        UPDATE job_attachments
        SET notes = ?
        WHERE id = ? AND job_url = ?
    """, (update.notes, attachment_id, decoded_url))

    return {"success": True, "message": "Attachment notes updated"}
