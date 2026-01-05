"""
LLM Tracer - Captures and stores LLM interactions for debugging and prompt tuning.

Provides visibility into:
- System prompts being used
- User prompts sent to the LLM
- LLM responses
- Validation results and retries
- Timing information
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from threading import Lock
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class LLMTrace:
    """A single LLM interaction trace."""
    id: str
    timestamp: str
    operation: str  # e.g., "rewrite_summary", "generate_cover_letter"
    model: str
    temperature: float

    # Prompts
    system_prompt: str
    user_prompt: str

    # Response
    response: Optional[str] = None
    parsed_response: Optional[Dict[str, Any]] = None

    # Validation
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)
    retry_count: int = 0

    # Timing
    duration_ms: Optional[float] = None

    # Metadata
    job_title: Optional[str] = None
    job_company: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class LLMTracer:
    """
    Singleton tracer that captures LLM interactions.

    Usage:
        tracer = LLMTracer.get_instance()
        trace_id = tracer.start_trace("rewrite_summary", system_prompt, user_prompt)
        # ... perform LLM call ...
        tracer.complete_trace(trace_id, response, parsed_response)
    """

    _instance: Optional['LLMTracer'] = None
    _lock = Lock()

    # Maximum traces to keep in memory
    MAX_TRACES = 100

    def __init__(self):
        self._traces: deque = deque(maxlen=self.MAX_TRACES)
        self._active_traces: Dict[str, LLMTrace] = {}
        self._trace_counter = 0
        self._enabled = True

    @classmethod
    def get_instance(cls) -> 'LLMTracer':
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def start_trace(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        model: str = "unknown",
        temperature: float = 0.0,
        job_title: Optional[str] = None,
        job_company: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a new trace for an LLM operation.

        Returns:
            Trace ID for completing the trace later
        """
        if not self._enabled:
            return ""

        with self._lock:
            self._trace_counter += 1
            trace_id = f"trace_{self._trace_counter}_{datetime.now().strftime('%H%M%S')}"

        trace = LLMTrace(
            id=trace_id,
            timestamp=datetime.now().isoformat(),
            operation=operation,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            job_title=job_title,
            job_company=job_company,
            metadata=metadata or {},
        )

        self._active_traces[trace_id] = trace
        logger.debug(f"Started LLM trace: {trace_id} for {operation}")
        return trace_id

    def complete_trace(
        self,
        trace_id: str,
        response: Optional[str] = None,
        parsed_response: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        validation_passed: bool = True,
        validation_errors: Optional[List[str]] = None,
    ):
        """Complete a trace with the LLM response."""
        if not self._enabled or not trace_id:
            return

        trace = self._active_traces.pop(trace_id, None)
        if trace is None:
            logger.warning(f"Trace not found: {trace_id}")
            return

        trace.response = response
        trace.parsed_response = parsed_response
        trace.duration_ms = duration_ms
        trace.validation_passed = validation_passed
        trace.validation_errors = validation_errors or []

        self._traces.append(trace)
        logger.debug(f"Completed LLM trace: {trace_id}, validation={validation_passed}")

    def record_retry(self, trace_id: str, error: str):
        """Record a validation retry for a trace."""
        if not self._enabled or not trace_id:
            return

        trace = self._active_traces.get(trace_id)
        if trace:
            trace.retry_count += 1
            trace.validation_errors.append(error)
            logger.debug(f"Trace {trace_id} retry #{trace.retry_count}: {error}")

    def fail_trace(self, trace_id: str, error: str):
        """Mark a trace as failed."""
        if not self._enabled or not trace_id:
            return

        trace = self._active_traces.pop(trace_id, None)
        if trace:
            trace.validation_passed = False
            trace.validation_errors.append(f"FAILED: {error}")
            self._traces.append(trace)
            logger.debug(f"Failed LLM trace: {trace_id}: {error}")

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent traces (newest first)."""
        traces = list(self._traces)[-limit:]
        traces.reverse()
        return [t.to_dict() for t in traces]

    def get_traces_by_operation(self, operation: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get traces for a specific operation."""
        matching = [t for t in self._traces if t.operation == operation][-limit:]
        matching.reverse()
        return [t.to_dict() for t in matching]

    def get_failed_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get traces that had validation failures."""
        failed = [t for t in self._traces if not t.validation_passed][-limit:]
        failed.reverse()
        return [t.to_dict() for t in failed]

    def get_trace_by_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific trace by ID."""
        for trace in self._traces:
            if trace.id == trace_id:
                return trace.to_dict()
        return None

    def clear_traces(self):
        """Clear all stored traces."""
        self._traces.clear()
        self._active_traces.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get tracing statistics."""
        traces = list(self._traces)
        if not traces:
            return {
                "total_traces": 0,
                "failed_traces": 0,
                "operations": {},
                "avg_retries": 0,
            }

        operations: Dict[str, int] = {}
        total_retries = 0
        failed_count = 0

        for t in traces:
            operations[t.operation] = operations.get(t.operation, 0) + 1
            total_retries += t.retry_count
            if not t.validation_passed:
                failed_count += 1

        return {
            "total_traces": len(traces),
            "failed_traces": failed_count,
            "success_rate": (len(traces) - failed_count) / len(traces) * 100 if traces else 0,
            "operations": operations,
            "avg_retries": total_retries / len(traces) if traces else 0,
            "active_traces": len(self._active_traces),
        }


# Convenience function
def get_tracer() -> LLMTracer:
    """Get the LLM tracer instance."""
    return LLMTracer.get_instance()
