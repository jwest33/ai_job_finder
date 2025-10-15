"""
Job Matcher - AI-Powered Job Matching and Resume Optimization

This package provides tools for matching jobs to resumes using AI analysis,
generating gap reports, and providing resume optimization recommendations.
"""

__version__ = "1.0.0"

from .job_tracker import JobTracker
from .llama_client import LlamaClient
from .resume_analyzer import ResumeAnalyzer
from .match_scorer import MatchScorer
from .gap_analyzer import GapAnalyzer
from .resume_optimizer import ResumeOptimizer
from .report_generator import ReportGenerator
from .checkpoint_manager import CheckpointManager
from .email_service import EmailService
from .failure_tracker import FailureTracker, ErrorType
from .smooth_batch_processor import SmoothBatchProcessor

__all__ = [
    "JobTracker",
    "LlamaClient",
    "ResumeAnalyzer",
    "MatchScorer",
    "GapAnalyzer",
    "ResumeOptimizer",
    "ReportGenerator",
    "CheckpointManager",
    "EmailService",
    "FailureTracker",
    "ErrorType",
    "SmoothBatchProcessor",
]
