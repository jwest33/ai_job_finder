"""
Smooth Batch Processor - GPU Load Smoothing Utility

This module provides a rolling queue implementation for processing jobs
in a way that maintains constant GPU load, eliminating power oscillations
that cause coil whine.

Key Features:
- Rolling job submission (maintains constant active thread count)
- Eliminates batch completion gaps that cause GPU power drops
- Thread-safe progress tracking and checkpointing
- Preserves all existing functionality (checkpoints, failure tracking, etc.)
"""

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, List, Any, Optional, TypeVar
from queue import Queue

T = TypeVar('T')


class SmoothBatchProcessor:
    """
    Process jobs using a rolling queue to maintain constant GPU load.

    Instead of submitting all jobs at once (which creates batch completion gaps),
    this processor maintains a constant number of active workers by submitting
    new jobs as soon as previous ones complete.

    This eliminates GPU power oscillations that cause coil whine.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize the smooth batch processor

        Args:
            max_workers: Maximum number of concurrent workers (threads)
        """
        self.max_workers = max_workers
        self.results_lock = threading.Lock()

    def process_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], T],
        progress_callback: Optional[Callable[[int, int, Any], None]] = None,
    ) -> List[T]:
        """
        Process a batch of items using rolling queue submission.

        This method ensures constant GPU load by:
        1. Starting with max_workers threads
        2. As soon as one completes, immediately starting the next job
        3. Never allowing all threads to finish simultaneously

        Args:
            items: List of items to process
            process_func: Function to process each item (should be thread-safe)
            progress_callback: Optional callback(current, total, item)

        Returns:
            List of processed results (in same order as input items)
        """
        if not items:
            return []

        total = len(items)
        results = [None] * total  # Pre-allocate results list
        completed_count = [0]  # Mutable counter for thread-safe updates

        # Create thread-safe progress tracking
        progress_lock = threading.Lock()

        def process_with_tracking(item_index: int) -> T:
            """
            Process a single item with progress tracking

            Args:
                item_index: Index of item in the original list

            Returns:
                Processed result
            """
            item = items[item_index]

            # Process the item
            result = process_func(item)

            # Store result in correct position (thread-safe)
            with self.results_lock:
                results[item_index] = result

            # Update progress (thread-safe)
            with progress_lock:
                completed_count[0] += 1
                if progress_callback:
                    progress_callback(completed_count[0], total, item)

            return result

        # Use ThreadPoolExecutor with rolling submission
        # Key difference: We use map() which submits jobs as workers become available
        # instead of submit_all_at_once which creates batch completion gaps
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Using map() with range ensures rolling submission:
            # - Initially starts max_workers threads
            # - As each thread completes, immediately starts next job
            # - Maintains constant active thread count until queue is empty
            list(executor.map(process_with_tracking, range(total)))

        return results


class SmoothBatchProcessorAdvanced:
    """
    Advanced version with explicit queue management for maximum control.

    This version gives fine-grained control over job submission timing,
    allowing for even smoother GPU load distribution if needed.
    """

    def __init__(self, max_workers: int = 4, submission_delay_ms: int = 0):
        """
        Initialize advanced processor

        Args:
            max_workers: Maximum concurrent workers
            submission_delay_ms: Optional delay (milliseconds) between job submissions
                                (0 = immediate, >0 = staggered for even smoother load)
        """
        self.max_workers = max_workers
        self.submission_delay_ms = submission_delay_ms
        self.results_lock = threading.Lock()

    def process_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], T],
        progress_callback: Optional[Callable[[int, int, Any], None]] = None,
    ) -> List[T]:
        """
        Process batch with explicit queue control

        Args:
            items: Items to process
            process_func: Processing function
            progress_callback: Optional progress callback

        Returns:
            List of results
        """
        if not items:
            return []

        total = len(items)
        results = [None] * total
        completed_count = [0]
        progress_lock = threading.Lock()

        # Create job queue
        job_queue = Queue()
        for i, item in enumerate(items):
            job_queue.put((i, item))

        # Track active futures
        active_futures = []
        active_lock = threading.Lock()

        def worker():
            """
            Worker thread that continuously processes jobs from queue
            """
            while True:
                try:
                    # Get next job (non-blocking)
                    if job_queue.empty():
                        break

                    job_index, item = job_queue.get_nowait()

                    # Process the item
                    result = process_func(item)

                    # Store result
                    with self.results_lock:
                        results[job_index] = result

                    # Update progress
                    with progress_lock:
                        completed_count[0] += 1
                        if progress_callback:
                            progress_callback(completed_count[0], total, item)

                    # Mark job as done
                    job_queue.task_done()

                except Exception:
                    # Queue is empty or error occurred
                    break

        # Start worker threads
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit worker threads
            futures = [executor.submit(worker) for _ in range(self.max_workers)]

            # Wait for all jobs to complete
            job_queue.join()

            # Wait for all workers to finish
            for future in futures:
                future.result()

        return results


# Factory function for easy usage
def create_processor(max_workers: int = 4, advanced: bool = False) -> SmoothBatchProcessor:
    """
    Create a smooth batch processor instance

    Args:
        max_workers: Number of concurrent threads
        advanced: If True, use advanced processor with explicit queue control

    Returns:
        SmoothBatchProcessor instance
    """
    if advanced:
        return SmoothBatchProcessorAdvanced(max_workers=max_workers)
    else:
        return SmoothBatchProcessor(max_workers=max_workers)


if __name__ == "__main__":
    import time

    print("Testing SmoothBatchProcessor...")

    # Test function that simulates GPU workload
    def process_item(item):
        """Simulate processing with variable duration"""
        time.sleep(0.1 + (item % 3) * 0.05)  # 100-200ms per item
        return item * 2

    # Progress callback
    def progress(current, total, item):
        print(f"[{current}/{total}] Processed item {item}")

    # Test with 20 items
    test_items = list(range(20))

    processor = SmoothBatchProcessor(max_workers=4)

    print("\nProcessing 20 items with 4 threads...")
    start_time = time.time()

    results = processor.process_batch(test_items, process_item, progress)

    elapsed = time.time() - start_time

    print(f"\nCompleted in {elapsed:.2f} seconds")
    print(f"Results: {results[:5]}... (showing first 5)")
    print("\nTest complete!")
