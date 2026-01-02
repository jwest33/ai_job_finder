"""
VLM State Manager Harness for orchestrating VLM agent workflows.

Provides structured stage-based workflow execution with:
- Dynamic context injection
- Checkpoint validation
- Rich prompts per stage
- Error handling and retries
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from enum import Enum

from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of a workflow stage."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStage:
    """Definition of a workflow stage."""
    name: str
    goal: str
    prompt_template: str
    max_actions: int = 10
    timeout_seconds: int = 60
    retry_count: int = 2
    next_stage: Optional[str] = None
    skip_condition: Optional[Callable[["VLMStateManager"], bool]] = None


@dataclass
class DynamicContext:
    """Dynamic context injected into VLM prompts."""
    current_url: str = ""
    page_title: str = ""
    previous_actions: List[str] = field(default_factory=list)
    stage_goal: str = ""
    search_term: str = ""
    location: str = ""
    jobs_found_so_far: int = 0
    error_message: str = ""
    retry_attempt: int = 0
    custom_data: Dict[str, Any] = field(default_factory=dict)


class VLMStateManager:
    """
    Orchestrates VLM agent through structured workflow stages.

    Provides:
    - Stage-based workflow execution
    - Dynamic context injection into prompts
    - Checkpoint validation between stages
    - Retry logic with adjusted prompts
    """

    def __init__(
        self,
        vlm_agent,
        page: Page,
        stages: List[WorkflowStage],
        search_term: str = "",
        location: str = "",
    ):
        """
        Initialize the state manager.

        Args:
            vlm_agent: VLM Agent instance
            page: Playwright page for checkpoint validation
            stages: List of workflow stages to execute
            search_term: Job search term
            location: Job location
        """
        self.vlm_agent = vlm_agent
        self.page = page
        self.stages = {s.name: s for s in stages}
        self.stage_order = [s.name for s in stages]

        self.search_term = search_term
        self.location = location

        self.current_stage: Optional[str] = None
        self.stage_status: Dict[str, StageStatus] = {
            s.name: StageStatus.PENDING for s in stages
        }
        self.action_history: List[str] = []
        self.extracted_jobs: List[Dict] = []

        # Checkpoint validators (can be overridden)
        self._checkpoint_validators: Dict[str, Callable[[], bool]] = {}

    def register_checkpoint(self, stage_name: str, validator: Callable[[], bool]):
        """Register a checkpoint validator for a stage."""
        self._checkpoint_validators[stage_name] = validator

    def get_context(self) -> DynamicContext:
        """Build current dynamic context for prompt injection."""
        try:
            current_url = self.page.url
            page_title = self.page.title()
        except Exception:
            current_url = ""
            page_title = ""

        stage = self.stages.get(self.current_stage)

        return DynamicContext(
            current_url=current_url,
            page_title=page_title,
            previous_actions=self.action_history[-5:],
            stage_goal=stage.goal if stage else "",
            search_term=self.search_term,
            location=self.location,
            jobs_found_so_far=len(self.extracted_jobs),
        )

    def build_prompt(self, stage: WorkflowStage, context: DynamicContext) -> str:
        """Build the prompt for a stage with context injection."""
        prompt = stage.prompt_template

        # Inject context values
        replacements = {
            "{current_url}": context.current_url,
            "{page_title}": context.page_title,
            "{previous_actions}": "\n".join(context.previous_actions) or "None",
            "{stage_goal}": context.stage_goal,
            "{search_term}": context.search_term,
            "{location}": context.location,
            "{jobs_found}": str(context.jobs_found_so_far),
            "{error_message}": context.error_message,
            "{retry_attempt}": str(context.retry_attempt),
        }

        for key, value in replacements.items():
            prompt = prompt.replace(key, value)

        # Also inject any custom data
        for key, value in context.custom_data.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))

        return prompt

    def check_checkpoint(self, stage_name: str) -> bool:
        """
        Check if a stage's checkpoint/goal is achieved.

        Uses registered validator if available, otherwise returns True.
        """
        if stage_name in self._checkpoint_validators:
            try:
                return self._checkpoint_validators[stage_name]()
            except Exception as e:
                logger.warning(f"Checkpoint validator error for {stage_name}: {e}")
                return False
        return True

    def execute_stage(self, stage_name: str) -> bool:
        """
        Execute a single workflow stage.

        Returns:
            True if stage completed successfully
        """
        stage = self.stages.get(stage_name)
        if not stage:
            logger.error(f"Unknown stage: {stage_name}")
            return False

        self.current_stage = stage_name
        self.stage_status[stage_name] = StageStatus.IN_PROGRESS

        print(f"[VLMStateManager] Executing stage: {stage_name}", flush=True)
        print(f"[VLMStateManager] Goal: {stage.goal}", flush=True)

        # Check skip condition
        if stage.skip_condition and stage.skip_condition(self):
            print(f"[VLMStateManager] Skipping stage {stage_name} (condition met)")
            self.stage_status[stage_name] = StageStatus.SKIPPED
            return True

        # Execute with retries
        for attempt in range(stage.retry_count + 1):
            context = self.get_context()
            context.retry_attempt = attempt

            if attempt > 0:
                context.error_message = f"Retry attempt {attempt} - previous attempt failed"
                print(f"[VLMStateManager] Retry {attempt}/{stage.retry_count}")

            prompt = self.build_prompt(stage, context)

            print(f"[VLMStateManager] Running VLM with max_actions={stage.max_actions}")

            try:
                # Focus browser before VLM interaction
                self._focus_browser()

                # Run VLM agent
                result = self.vlm_agent.run(
                    task=prompt,
                    max_actions=stage.max_actions,
                    history=self.action_history.copy(),
                )

                print(f"[VLMStateManager] VLM result: {result}")

                # Record action
                self.action_history.append(f"Stage {stage_name}: {result}")

                # Check checkpoint
                time.sleep(1)  # Allow page to update
                if self.check_checkpoint(stage_name):
                    print(f"[VLMStateManager] Checkpoint passed for {stage_name}")
                    self.stage_status[stage_name] = StageStatus.COMPLETED
                    return True
                else:
                    print(f"[VLMStateManager] Checkpoint NOT passed for {stage_name}")

            except Exception as e:
                logger.error(f"Stage {stage_name} error: {e}")
                print(f"[VLMStateManager] Error: {e}")

        # All retries exhausted
        self.stage_status[stage_name] = StageStatus.FAILED
        print(f"[VLMStateManager] Stage {stage_name} FAILED after {stage.retry_count + 1} attempts")
        return False

    def run_workflow(self) -> bool:
        """
        Run the complete workflow through all stages.

        Returns:
            True if workflow completed successfully
        """
        print(f"[VLMStateManager] Starting workflow with {len(self.stage_order)} stages")
        print(f"[VLMStateManager] Stages: {' -> '.join(self.stage_order)}")

        for stage_name in self.stage_order:
            success = self.execute_stage(stage_name)

            if not success:
                # Check if this is a critical stage
                stage = self.stages[stage_name]
                if stage_name in ["NAVIGATE", "SEARCH"]:
                    print(f"[VLMStateManager] Critical stage {stage_name} failed, aborting workflow")
                    return False
                else:
                    print(f"[VLMStateManager] Non-critical stage {stage_name} failed, continuing")

        print("[VLMStateManager] Workflow completed")
        return True

    def _focus_browser(self):
        """Bring browser window to foreground."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            def get_browser_window():
                windows = []
                def enum_callback(hwnd, _):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            if any(x in title for x in ["Chromium", "Glassdoor", "Jobs", "Chrome"]):
                                windows.append(hwnd)
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
                return windows[0] if windows else None

            hwnd = get_browser_window()
            if hwnd:
                user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Could not focus browser: {e}")

    def get_results(self) -> Dict[str, Any]:
        """Get workflow results."""
        return {
            "stages": {name: status.value for name, status in self.stage_status.items()},
            "action_history": self.action_history,
            "jobs_found": len(self.extracted_jobs),
            "extracted_jobs": self.extracted_jobs,
        }
