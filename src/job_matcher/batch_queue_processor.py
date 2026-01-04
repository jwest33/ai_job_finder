"""
Batch Queue Processor - Constant GPU Load Processing

This module provides a batch processing strategy that maintains constant GPU
utilization by pre-generating all prompts and queuing them continuously to
the AI server.

Key Features:
- Pre-generates all prompts before any AI execution
- Queues all requests rapidly to keep GPU fully loaded
- Eliminates power oscillations that cause coil whine
- Thread-safe with checkpoint and failure tracking support
- Maps results back to jobs after completion

Architecture:
1. Prompt Generation Phase: Creates all prompts upfront
2. Execution Phase: Queues all AI requests with minimal delays
3. Result Mapping Phase: Maps responses back to original jobs
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Any, Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class QueuedJob:
    """
    Container for a job with its pre-generated prompt

    Attributes:
        index: Original position in job list
        job: Job data dictionary
        prompt: Pre-generated prompt string
        job_url: Job URL for checkpoint tracking
    """
    index: int
    job: Dict[str, Any]
    prompt: str
    job_url: str


class BatchQueueProcessor:
    """
    Process jobs by pre-generating all prompts and queuing AI requests
    continuously to maintain constant GPU load.

    This eliminates the GPU power spikes caused by sequential processing
    where each job waits for the previous one to complete.
    """

    def __init__(
        self,
        max_workers: int = 4,
        queue_delay_ms: int = 50,
    ):
        """
        Initialize batch queue processor

        Args:
            max_workers: Maximum concurrent threads for AI requests
            queue_delay_ms: Milliseconds between request submissions (0 = immediate)
                           Small delay (50-100ms) can smooth out request flow
        """
        self.max_workers = max_workers
        self.queue_delay_ms = queue_delay_ms
        self.results_lock = threading.Lock()

    def process_batch(
        self,
        jobs: List[Dict[str, Any]],
        prompt_generator: Callable[[Dict[str, Any]], str],
        ai_executor: Callable[[str], Optional[Dict[str, Any]]],
        result_merger: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        checkpoint_manager = None,
        checkpoint_stage: str = None,
        failure_tracker = None,
        failure_stage: str = None,
        llama_client = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process batch of jobs with pre-generated prompts and continuous queuing

        This is the main entry point for batch queue processing. It coordinates:
        1. Prompt pre-generation for all jobs
        2. Continuous AI request queuing
        3. Result mapping back to jobs

        Args:
            jobs: List of job dictionaries to process
            prompt_generator: Function that creates prompt from job dict
                             Signature: (job: Dict) -> str
            ai_executor: Function that executes AI request with prompt
                        Signature: (prompt: str) -> Optional[Dict]
                        Returns None on failure (only used if llama_client not provided)
            result_merger: Function that merges AI result into job dict
                          Signature: (job: Dict, result: Dict) -> Dict
            progress_callback: Optional callback(current, total, job)
            checkpoint_manager: Optional CheckpointManager for resume support
            checkpoint_stage: Stage name for checkpoint tracking
            failure_tracker: Optional FailureTracker for failure recording
            failure_stage: Stage name for failure tracking
            llama_client: Optional LlamaClient instance for async batch mode
            temperature: Temperature for AI generation (required if llama_client provided)
            max_tokens: Max tokens for AI generation (required if llama_client provided)
            json_schema: JSON schema for AI generation (required if llama_client provided)

        Returns:
            List of processed jobs with AI results merged in
        """
        if not jobs:
            return []

        total = len(jobs)

        # PHASE 1: PRE-GENERATE ALL PROMPTS
        print(f"\n[INFO] Pre-generating {total} prompts...")
        phase_start = time.time()

        queued_jobs = self._prepare_prompts(
            jobs,
            prompt_generator,
            checkpoint_manager,
            checkpoint_stage
        )

        if not queued_jobs:
            print("   No jobs to process (all already completed)")
            return []

        print(f"   Generated {len(queued_jobs)} prompts")
        print(f"[INFO] Prompt generation: {time.time() - phase_start:.2f}s")

        # PHASE 2: EXECUTE ALL AI REQUESTS WITH CONTINUOUS QUEUING
        print(f"\n[INFO] Queuing {len(queued_jobs)} AI requests (maintaining constant GPU load)...")
        phase_start = time.time()

        results = self._execute_queued_requests(
            queued_jobs,
            ai_executor,
            progress_callback,
            checkpoint_manager,
            checkpoint_stage,
            failure_tracker,
            failure_stage,
            llama_client,
            temperature,
            max_tokens,
            json_schema,
        )

        print(f"[INFO] AI execution (GPU): {time.time() - phase_start:.2f}s")

        # PHASE 3: MAP RESULTS BACK TO JOBS
        print(f"\n[INFO] Mapping results back to jobs...")
        phase_start = time.time()

        processed_jobs = self._merge_results(
            queued_jobs,
            results,
            result_merger
        )

        print(f"   Processed {len(processed_jobs)} jobs successfully", flush=True)
        print(f"[INFO] Result merging: {time.time() - phase_start:.2f}s", flush=True)

        return processed_jobs

    def _prepare_prompts(
        self,
        jobs: List[Dict[str, Any]],
        prompt_generator: Callable[[Dict[str, Any]], str],
        checkpoint_manager,
        checkpoint_stage: str,
    ) -> List[QueuedJob]:
        """
        Pre-generate all prompts for the entire batch

        This is done synchronously before any AI execution to:
        1. Minimize delay between AI requests
        2. Filter out already-processed jobs early
        3. Catch prompt generation errors before GPU processing

        Args:
            jobs: List of job dictionaries
            prompt_generator: Function to create prompt from job
            checkpoint_manager: Optional CheckpointManager
            checkpoint_stage: Stage name for checkpoint filtering

        Returns:
            List of QueuedJob objects with pre-generated prompts
        """
        queued_jobs = []

        # Get already-processed URLs if checkpoint available
        processed_urls = set()
        if checkpoint_manager and checkpoint_stage:
            processed_urls = set(checkpoint_manager.get_processed_urls(checkpoint_stage))

        for idx, job in enumerate(jobs):
            job_url = job.get("job_url", "")

            # Skip if already processed
            if job_url in processed_urls:
                continue

            try:
                # Pre-generate prompt
                prompt = prompt_generator(job)

                # Create queued job
                queued_jobs.append(QueuedJob(
                    index=idx,
                    job=job,
                    prompt=prompt,
                    job_url=job_url,
                ))
            except Exception as e:
                print(f"[WARNING] Failed to generate prompt for job {idx}: {e}")
                # Record failure if tracker available
                if failure_tracker and failure_stage:
                    from .failure_tracker import ErrorType
                    failure_tracker.record_failure(
                        job,
                        failure_stage,
                        ErrorType.UNKNOWN_ERROR,
                        f"Prompt generation failed: {str(e)}"
                    )
                continue

        return queued_jobs

    def _execute_queued_requests(
        self,
        queued_jobs: List[QueuedJob],
        ai_executor: Callable[[str], Optional[Dict[str, Any]]],
        progress_callback: Optional[Callable],
        checkpoint_manager,
        checkpoint_stage: str,
        failure_tracker,
        failure_stage: str,
        llama_client = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[int, Optional[Dict[str, Any]]]:
        """
        Execute all AI requests with continuous queuing using async batch mode

        This is the critical GPU load management phase. ALL requests are submitted
        to llama-server simultaneously using async HTTP, allowing the server to
        maintain constant GPU load by processing them from its internal queue.

        CRITICAL: All post-processing (checkpoints, progress, failure tracking)
        is deferred until AFTER all GPU work completes to maintain constant load.

        Args:
            queued_jobs: List of QueuedJob objects with pre-generated prompts
            ai_executor: Function to execute AI request (fallback if llama_client not provided)
            progress_callback: Optional progress callback
            checkpoint_manager: Optional CheckpointManager
            checkpoint_stage: Stage name for checkpointing
            failure_tracker: Optional FailureTracker
            failure_stage: Stage name for failure tracking
            llama_client: Optional LlamaClient instance for async batch mode
            temperature: Temperature for AI generation (required if llama_client provided)
            max_tokens: Max tokens for AI generation (required if llama_client provided)
            json_schema: JSON schema for AI generation (required if llama_client provided)

        Returns:
            Dictionary mapping job index to AI result (None on failure)
        """
        results = {}

        # Collect post-processing work to do AFTER GPU batch completes
        checkpoint_queue = []  # [(job_url, success)]
        failure_queue = []     # [(job, error_msg)]
        progress_queue = []    # [(job_index, job)]

        # Use strict batch processing - only max_workers requests in flight at a time
        print(f"   Processing {len(queued_jobs)} jobs in batches of {self.max_workers}", flush=True)

        def execute_single_request(queued_job: QueuedJob) -> Tuple[int, Optional[Dict[str, Any]], QueuedJob]:
            """Execute AI request for a single queued job"""
            try:
                result = ai_executor(queued_job.prompt)
                return (queued_job.index, result, queued_job)
            except Exception as e:
                return (queued_job.index, None, queued_job)

        # Process in explicit batches - NEVER more than max_workers in flight
        total_jobs = len(queued_jobs)
        completed_count = 0  # Track overall progress across batches

        for batch_start in range(0, total_jobs, self.max_workers):
            batch_end = min(batch_start + self.max_workers, total_jobs)
            batch_jobs = queued_jobs[batch_start:batch_end]
            batch_num = batch_start // self.max_workers + 1
            total_batches = (total_jobs + self.max_workers - 1) // self.max_workers

            print(f"   [Batch {batch_num}/{total_batches}] Processing jobs {batch_start+1}-{batch_end} of {total_jobs}...", flush=True)

            # Submit ONLY this batch to executor and wait for ALL to complete
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                batch_futures = [executor.submit(execute_single_request, job) for job in batch_jobs]

                # Wait for this batch to complete before starting next
                for future in as_completed(batch_futures):
                    job_idx, result, queued_job = future.result()
                    results[job_idx] = result
                    completed_count += 1

                    if result:
                        checkpoint_queue.append((queued_job.job_url, True))
                    else:
                        checkpoint_queue.append((queued_job.job_url, False))
                        failure_queue.append((queued_job.job, "AI executor returned None or exception occurred"))

                    progress_queue.append((job_idx, queued_job.job))

                    # Report progress immediately after each job completes
                    if progress_callback:
                        progress_callback(completed_count, total_jobs, queued_job.job)

            print(f"   [Batch {batch_num}/{total_batches}] Complete", flush=True)

        # POST-PROCESSING PHASE: Do all I/O and tracking AFTER GPU work completes
        print(f"\n[INFO] Processing batch results...")

        # 1. Update checkpoints in bulk
        if checkpoint_manager and checkpoint_stage:
            successful_urls = [url for url, success in checkpoint_queue if success and url]
            for url in successful_urls:
                checkpoint_manager.mark_job_completed(checkpoint_stage, url)

        # 2. Record failures in bulk
        if failure_tracker and failure_stage:
            from .failure_tracker import ErrorType
            for job, error_msg in failure_queue:
                failure_tracker.record_failure(
                    job,
                    failure_stage,
                    ErrorType.UNKNOWN_ERROR,
                    error_msg
                )

        # Note: Progress is now reported immediately after each job completes (above)
        # so no deferred progress reporting needed here

        return results

    def _merge_results(
        self,
        queued_jobs: List[QueuedJob],
        results: Dict[int, Optional[Dict[str, Any]]],
        result_merger: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge AI results back into original jobs

        Args:
            queued_jobs: Original queued jobs
            results: Dictionary mapping job index to AI result
            result_merger: Function to merge result into job

        Returns:
            List of processed jobs (same order as queued_jobs)
        """
        processed_jobs = []

        for queued_job in queued_jobs:
            result = results.get(queued_job.index)

            if result:
                # Merge successful result
                processed_job = result_merger(queued_job.job, result)
                processed_jobs.append(processed_job)
            else:
                # Add job with failure state
                # Let the caller handle failure state (they know the expected schema)
                processed_job = result_merger(queued_job.job, None)
                processed_jobs.append(processed_job)

        return processed_jobs


# Factory function for easy usage
def create_batch_queue_processor(
    max_workers: int = 4,
    queue_delay_ms: int = 50,
) -> BatchQueueProcessor:
    """
    Create a batch queue processor instance

    Args:
        max_workers: Number of concurrent threads
        queue_delay_ms: Delay between request submissions (0 = immediate)

    Returns:
        BatchQueueProcessor instance
    """
    return BatchQueueProcessor(
        max_workers=max_workers,
        queue_delay_ms=queue_delay_ms,
    )


if __name__ == "__main__":
    import json

    print("Testing BatchQueueProcessor...")

    # Mock functions for testing
    def mock_prompt_generator(job):
        """Generate mock prompt from job"""
        return f"Analyze this job: {job['title']}"

    def mock_ai_executor(prompt):
        """Simulate AI execution with delay"""
        time.sleep(0.1)  # Simulate processing time
        return {"score": 85, "reasoning": "Good match"}

    def mock_result_merger(job, result):
        """Merge result into job"""
        if result:
            return {**job, **result}
        else:
            return {**job, "score": 0, "reasoning": "Failed"}

    # Test data
    test_jobs = [
        {"job_url": f"http://example.com/job{i}", "title": f"Job {i}"}
        for i in range(10)
    ]

    # Create processor
    processor = BatchQueueProcessor(max_workers=4, queue_delay_ms=50)

    # Process batch
    print(f"\nProcessing {len(test_jobs)} test jobs...")

    def progress(current, total, job):
        print(f"[{current}/{total}] Processed: {job['title']}")

    results = processor.process_batch(
        jobs=test_jobs,
        prompt_generator=mock_prompt_generator,
        ai_executor=mock_ai_executor,
        result_merger=mock_result_merger,
        progress_callback=progress,
    )

    print(f"\n[SUCCESS] Processed {len(results)} jobs")
    print(f"Sample result: {json.dumps(results[0], indent=2)}")
    print("\nTest complete!")
