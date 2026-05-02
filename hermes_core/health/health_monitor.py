#!/usr/bin/env python3
"""
Health Monitor for Hermes Agent.

Provider health monitoring with latency tracking, p95/p99 percentiles,
circuit breaker state, and automatic failover.

Based on backend (Harness) monitoring/health.py pattern.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """Health metrics for a provider or service."""

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: datetime | None = None
    last_error: str | None = None

    # Performance
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Request tracking
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0

    # Latency samples
    latency_samples: deque = field(default_factory=lambda: deque(maxlen=100))

    # Circuit breaker
    circuit_open: bool = False
    circuit_open_since: datetime | None = None
    failure_count: int = 0

    def update_latency(self, latency_ms: float):
        """Update latency metrics with a new sample."""
        self.latency_samples.append(latency_ms)

        self.avg_latency_ms = sum(self.latency_samples) / len(self.latency_samples)

        sorted_samples = sorted(self.latency_samples)
        n = len(sorted_samples)

        if n >= 20:
            self.p95_latency_ms = sorted_samples[int(n * 0.95)]
            self.p99_latency_ms = sorted_samples[int(n * 0.99)]

    def record_success(self):
        """Record a successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.error_rate = self.failed_requests / self.total_requests if self.total_requests > 0 else 0

        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self, error: str = ""):
        """Record a failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.error_rate = self.failed_requests / self.total_requests
        self.last_error = error
        self.failure_count += 1

    def is_available(self) -> bool:
        """Check if provider is available for requests."""
        return not self.circuit_open and self.status in (
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNKNOWN,
        )

    def open_circuit(self):
        """Open the circuit breaker."""
        self.circuit_open = True
        self.circuit_open_since = datetime.now(UTC)
        logger.warning("Circuit opened for %s", self.name)

    def close_circuit(self):
        """Close the circuit breaker after recovery."""
        self.circuit_open = False
        self.circuit_open_since = None
        self.failure_count = 0
        logger.info("Circuit closed for %s", self.name)


class ProviderHealthChecker:
    """
    Health checker for Hermes providers/services.

    Performs periodic health checks and tracks performance metrics.
    """

    def __init__(
        self,
        check_interval: int = 3600,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.metrics: dict[str, HealthMetrics] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def register_service(self, name: str) -> HealthMetrics:
        """Register a service for health monitoring."""
        if name not in self.metrics:
            self.metrics[name] = HealthMetrics(name=name)
        return self.metrics[name]

    def start(self):
        """Start health checking loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._health_check_loop())

    def stop(self):
        """Stop health checking loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _health_check_loop(self):
        """Run periodic health checks."""
        while self._running:
            try:
                await self._check_all_services()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check error: %s", e)
                await asyncio.sleep(self.check_interval)

    async def _check_all_services(self):
        """Check health of all registered services."""
        for name in list(self.metrics.keys()):
            await self._check_service(name)

    async def _check_service(self, name: str):
        """Check health of a specific service."""
        metrics = self.metrics[name]
        metrics.last_check = datetime.now(UTC)

        try:
            # Record latency for the health check itself
            start = time.time()

            # Check circuit breaker recovery
            if metrics.circuit_open and metrics.circuit_open_since:
                elapsed = (datetime.now(UTC) - metrics.circuit_open_since).total_seconds()
                if elapsed >= self.recovery_timeout:
                    metrics.close_circuit()
                    await self._perform_health_check(name, metrics)
            else:
                await self._perform_health_check(name, metrics)

            latency_ms = (time.time() - start) * 1000
            metrics.update_latency(latency_ms)
            metrics.record_success()

            # Update status
            if metrics.error_rate < 0.05:
                metrics.status = HealthStatus.HEALTHY
            elif metrics.error_rate < 0.2:
                metrics.status = HealthStatus.DEGRADED
            else:
                metrics.status = HealthStatus.UNHEALTHY

            # Check circuit breaker threshold
            if metrics.failure_count >= self.failure_threshold and not metrics.circuit_open:
                metrics.open_circuit()

        except Exception as e:
            metrics.record_failure(str(e))
            metrics.status = HealthStatus.UNHEALTHY
            logger.error("Health check failed for %s: %s", name, e)

    async def _perform_health_check(self, name: str, metrics: HealthMetrics):
        """Perform the actual health check. Override for custom checks."""
        # Default: assume healthy if we got here
        pass

    def record_request(self, service_name: str, latency_ms: float, success: bool, error: str = ""):
        """Record a request result for a service."""
        if service_name not in self.metrics:
            self.register_service(service_name)

        metrics = self.metrics[service_name]
        metrics.update_latency(latency_ms)

        if success:
            metrics.record_success()
        else:
            metrics.record_failure(error)

            if metrics.failure_count >= self.failure_threshold and not metrics.circuit_open:
                metrics.open_circuit()

    def get_metrics(self, service_name: str) -> HealthMetrics | None:
        """Get metrics for a service."""
        return self.metrics.get(service_name)

    def get_all_metrics(self) -> dict[str, HealthMetrics]:
        """Get all service metrics."""
        return dict(self.metrics)


_global_health_checker: ProviderHealthChecker | None = None


def get_health_checker() -> ProviderHealthChecker:
    """Get or create global ProviderHealthChecker instance."""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = ProviderHealthChecker()
    return _global_health_checker
