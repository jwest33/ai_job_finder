"""
Adaptive rate limiter with heuristic patterns for web scraping.

Implements multiple strategies to avoid rate limiting:
- Adaptive base delay that increases on 429s and recovers on success
- Gaussian jitter for human-like timing patterns
- Request velocity tracking to preemptively throttle
- Circuit breaker pattern for consecutive failures
- Response time monitoring for early warning signs
- Thread-safe for concurrent scraping
"""

import random
import time
import math
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class RateLimiterStats:
    """Statistics for monitoring rate limiter behavior"""
    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    total_wait_time: float = 0.0
    circuit_breaker_trips: int = 0
    session_rotations: int = 0


# Global registry for shared rate limiters (one per site)
_global_rate_limiters: Dict[str, "AdaptiveRateLimiter"] = {}
_global_registry_lock = threading.Lock()

# Global semaphores for serializing requests per site (one request at a time)
_global_request_semaphores: Dict[str, threading.Semaphore] = {}


def get_request_semaphore(site_name: str) -> threading.Semaphore:
    """
    Get a semaphore that limits concurrent requests to a site.

    This ensures only ONE request can be in-flight at a time per site,
    preventing concurrent scrapers from overwhelming the target.
    """
    with _global_registry_lock:
        if site_name not in _global_request_semaphores:
            _global_request_semaphores[site_name] = threading.Semaphore(1)
        return _global_request_semaphores[site_name]


def get_shared_rate_limiter(site_name: str, **kwargs) -> "AdaptiveRateLimiter":
    """
    Get or create a shared rate limiter for a specific site.

    This ensures all scraper instances for the same site share one rate limiter,
    preventing concurrent requests from overwhelming the target.

    Args:
        site_name: The site name (e.g., "glassdoor", "indeed")
        **kwargs: Arguments to pass to AdaptiveRateLimiter if creating new

    Returns:
        Shared AdaptiveRateLimiter instance for the site
    """
    with _global_registry_lock:
        if site_name not in _global_rate_limiters:
            _global_rate_limiters[site_name] = AdaptiveRateLimiter(**kwargs)
            print(f"[RATE] Created shared rate limiter for {site_name}")
        return _global_rate_limiters[site_name]


def reset_shared_rate_limiter(site_name: str) -> None:
    """Reset the shared rate limiter for a site (e.g., between scraping sessions)"""
    with _global_registry_lock:
        if site_name in _global_rate_limiters:
            _global_rate_limiters[site_name].reset()
            print(f"[RATE] Reset shared rate limiter for {site_name}")


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that uses multiple heuristics to avoid 429 errors.

    Key strategies:
    1. Adaptive delay: Increases on 429, slowly recovers on success
    2. Gaussian jitter: More natural than uniform random
    3. Velocity tracking: Monitors requests/minute
    4. Circuit breaker: Long pause after consecutive failures
    5. Response time awareness: Slows down if server seems stressed
    """

    def __init__(
        self,
        base_delay: float = 5.0,
        min_delay: float = 3.0,
        max_delay: float = 120.0,
        velocity_window: float = 60.0,
        velocity_max_requests: int = 8,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_reset_time: float = 300.0,
        jitter_std_ratio: float = 0.25,
    ):
        """
        Initialize the adaptive rate limiter.

        Args:
            base_delay: Starting delay between requests (seconds)
            min_delay: Minimum delay, even during recovery (seconds)
            max_delay: Maximum delay cap (seconds)
            velocity_window: Time window for velocity tracking (seconds)
            velocity_max_requests: Max requests allowed in velocity window
            circuit_breaker_threshold: Consecutive 429s before circuit trips
            circuit_breaker_reset_time: How long circuit breaker pauses (seconds)
            jitter_std_ratio: Standard deviation as ratio of delay for Gaussian jitter
        """
        # Thread lock for concurrent access
        self._lock = threading.RLock()

        # Delay parameters
        self.base_delay = base_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.current_delay = base_delay

        # Velocity tracking
        self.velocity_window = velocity_window
        self.velocity_max_requests = velocity_max_requests
        self.request_timestamps: deque = deque()

        # Circuit breaker
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_time = circuit_breaker_reset_time
        self.consecutive_failures = 0
        self.circuit_open_until: Optional[float] = None

        # Success tracking for recovery
        self.consecutive_successes = 0
        self.successes_needed_for_recovery = 3
        self.recovery_factor = 0.85  # Multiply delay by this on recovery

        # Jitter parameters
        self.jitter_std_ratio = jitter_std_ratio

        # Response time tracking (for preemptive slowdown)
        self.recent_response_times: deque = deque(maxlen=5)
        self.slow_response_threshold = 2000  # ms
        self.very_slow_response_threshold = 4000  # ms

        # Statistics
        self.stats = RateLimiterStats()

        # Callbacks for session rotation (list to support multiple scrapers)
        self._session_rotate_callbacks: list = []

    def register_session_rotate_callback(self, callback: callable) -> None:
        """Register a callback to be called when session rotation is needed"""
        with self._lock:
            if callback not in self._session_rotate_callbacks:
                self._session_rotate_callbacks.append(callback)

    def unregister_session_rotate_callback(self, callback: callable) -> None:
        """Unregister a session rotation callback"""
        with self._lock:
            if callback in self._session_rotate_callbacks:
                self._session_rotate_callbacks.remove(callback)

    @property
    def on_session_rotate_callback(self):
        """Deprecated: Use register_session_rotate_callback instead"""
        return None

    @on_session_rotate_callback.setter
    def on_session_rotate_callback(self, callback):
        """Deprecated: Use register_session_rotate_callback instead"""
        if callback:
            self.register_session_rotate_callback(callback)

    def _prune_old_timestamps(self) -> None:
        """Remove timestamps outside the velocity window"""
        now = time.time()
        while self.request_timestamps and now - self.request_timestamps[0] > self.velocity_window:
            self.request_timestamps.popleft()

    def _gaussian_jitter(self, delay: float) -> float:
        """
        Add Gaussian (normal distribution) jitter to delay.

        More human-like than uniform random - most values cluster
        around the mean with occasional outliers.
        """
        # Use Box-Muller transform for Gaussian random (no numpy dependency)
        u1 = random.random()
        u2 = random.random()
        z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)

        # Scale by standard deviation
        std = delay * self.jitter_std_ratio
        jitter = z * std

        # Ensure we don't go below minimum
        return max(self.min_delay, delay + jitter)

    def _check_velocity(self) -> tuple[bool, float]:
        """
        Check if we're approaching velocity limits.

        Returns:
            Tuple of (should_throttle, additional_wait_time)
        """
        self._prune_old_timestamps()

        current_count = len(self.request_timestamps)

        if current_count >= self.velocity_max_requests:
            # At limit - wait until oldest request falls out of window
            oldest = self.request_timestamps[0]
            wait_time = self.velocity_window - (time.time() - oldest) + 1
            return True, max(0, wait_time)

        # Approaching limit - add proportional slowdown
        if current_count >= self.velocity_max_requests * 0.7:
            # 70-100% of limit: add 20-50% extra delay
            ratio = current_count / self.velocity_max_requests
            extra_factor = 0.2 + (ratio - 0.7) * 1.0  # 0.2 to 0.5
            return False, self.current_delay * extra_factor

        return False, 0

    def _check_circuit_breaker(self) -> tuple[bool, float]:
        """
        Check if circuit breaker is open.

        Returns:
            Tuple of (is_open, wait_time_if_open)
        """
        if self.circuit_open_until is None:
            return False, 0

        now = time.time()
        if now < self.circuit_open_until:
            return True, self.circuit_open_until - now

        # Circuit breaker timeout passed - reset
        self.circuit_open_until = None
        self.consecutive_failures = 0
        return False, 0

    def _response_time_factor(self) -> float:
        """
        Calculate delay multiplier based on recent response times.

        Slow responses often indicate server stress - preemptively slow down.
        """
        if not self.recent_response_times:
            return 1.0

        avg_response_time = sum(self.recent_response_times) / len(self.recent_response_times)

        if avg_response_time > self.very_slow_response_threshold:
            return 1.8  # Server very stressed
        elif avg_response_time > self.slow_response_threshold:
            return 1.3  # Server somewhat stressed

        return 1.0

    def get_delay(self) -> float:
        """
        Get the recommended delay before the next request.

        Combines all heuristics:
        - Current adaptive delay
        - Velocity-based throttling
        - Response time factor
        - Gaussian jitter

        Thread-safe.

        Returns:
            Delay in seconds
        """
        with self._lock:
            # Check circuit breaker first
            circuit_open, circuit_wait = self._check_circuit_breaker()
            if circuit_open:
                # Add some jitter to circuit breaker wait too
                return self._gaussian_jitter(circuit_wait)

            # Start with current adaptive delay
            delay = self.current_delay

            # Apply response time factor
            delay *= self._response_time_factor()

            # Check velocity limits
            at_limit, velocity_wait = self._check_velocity()
            if at_limit:
                delay = max(delay, velocity_wait)
            else:
                delay += velocity_wait  # Add proportional slowdown

            # Apply Gaussian jitter
            delay = self._gaussian_jitter(delay)

            # Clamp to bounds
            return min(self.max_delay, max(self.min_delay, delay))

    def record_request(self, response_time_ms: Optional[float] = None) -> None:
        """
        Record that a request was made. Thread-safe.

        Args:
            response_time_ms: How long the request took (for response time tracking)
        """
        with self._lock:
            self.request_timestamps.append(time.time())
            self.stats.total_requests += 1

            if response_time_ms is not None:
                self.recent_response_times.append(response_time_ms)

    def on_success(self, response_time_ms: Optional[float] = None) -> None:
        """
        Record a successful request. Thread-safe.

        Slowly recovers the delay after consecutive successes.
        """
        with self._lock:
            self.request_timestamps.append(time.time())
            self.stats.total_requests += 1
            self.stats.successful_requests += 1

            if response_time_ms is not None:
                self.recent_response_times.append(response_time_ms)

            self.consecutive_failures = 0
            self.consecutive_successes += 1

            # Recovery: after N consecutive successes, reduce delay
            if self.consecutive_successes >= self.successes_needed_for_recovery:
                old_delay = self.current_delay
                self.current_delay = max(
                    self.base_delay,
                    self.current_delay * self.recovery_factor
                )
                self.consecutive_successes = 0

                if old_delay != self.current_delay:
                    print(f"[RATE] Recovered: delay {old_delay:.1f}s → {self.current_delay:.1f}s")

    def on_rate_limit(self) -> float:
        """
        Record a rate limit (429) response. Thread-safe.

        Increases delay and potentially triggers circuit breaker.

        Returns:
            Recommended wait time before retry (capped at max_delay)
        """
        with self._lock:
            self.stats.rate_limited_requests += 1
            self.consecutive_successes = 0
            self.consecutive_failures += 1

            # Increase base delay (multiplicative backoff)
            old_delay = self.current_delay
            backoff_factor = 1.5 + (self.consecutive_failures * 0.2)  # 1.5, 1.7, 1.9, ...
            self.current_delay = min(
                self.max_delay,
                self.current_delay * backoff_factor
            )

            print(f"[RATE] Rate limited! Delay {old_delay:.1f}s → {self.current_delay:.1f}s "
                  f"(consecutive: {self.consecutive_failures})")

            # Check if we need to trip circuit breaker
            if self.consecutive_failures >= self.circuit_breaker_threshold:
                self._trip_circuit_breaker()
                wait_time = self.circuit_open_until - time.time()
                # Cap circuit breaker wait at max_delay
                return min(wait_time, self.max_delay)

            # Return exponential backoff wait time for this specific retry
            wait_time = (2 ** (self.consecutive_failures - 1)) * 3  # 3, 6, 12...
            wait_time = min(wait_time, self.max_delay)  # Cap at max_delay

            # Add jitter
            return self._gaussian_jitter(wait_time)

    def _trip_circuit_breaker(self) -> None:
        """
        Trip the circuit breaker - pause before continuing.
        Note: Called within lock context from on_rate_limit.
        """
        self.stats.circuit_breaker_trips += 1

        # Use max_delay as the circuit breaker pause (capped wait)
        pause_duration = self.max_delay

        self.circuit_open_until = time.time() + pause_duration

        print(f"[RATE] Circuit breaker TRIPPED! Pausing for {pause_duration:.0f}s")

        # Trigger session rotation for all registered callbacks
        callbacks = list(self._session_rotate_callbacks)  # Copy to avoid lock issues

        for callback in callbacks:
            try:
                callback()
                self.stats.session_rotations += 1
            except Exception as e:
                print(f"[RATE] Session rotation callback failed: {e}")

    def force_cooldown(self, duration: float) -> None:
        """
        Force a cooldown period (e.g., when starting a new search). Thread-safe.

        Args:
            duration: Cooldown duration in seconds (capped at max_delay)
        """
        with self._lock:
            capped_duration = min(duration, self.max_delay)
            self.circuit_open_until = time.time() + capped_duration
            self.stats.total_wait_time += capped_duration
            print(f"[RATE] Forced cooldown: {capped_duration:.0f}s")

    def reset(self) -> None:
        """Reset the rate limiter to initial state. Thread-safe."""
        with self._lock:
            self.current_delay = self.base_delay
            self.consecutive_failures = 0
            self.consecutive_successes = 0
            self.circuit_open_until = None
            self.request_timestamps.clear()
            self.recent_response_times.clear()

    def get_stats_summary(self) -> str:
        """Get a human-readable summary of rate limiter statistics"""
        success_rate = (
            self.stats.successful_requests / self.stats.total_requests * 100
            if self.stats.total_requests > 0 else 0
        )

        return (
            f"Requests: {self.stats.total_requests} "
            f"(success: {success_rate:.1f}%, "
            f"rate-limited: {self.stats.rate_limited_requests}, "
            f"circuit trips: {self.stats.circuit_breaker_trips}, "
            f"session rotations: {self.stats.session_rotations})"
        )
