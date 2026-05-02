"""Hermes Core — Self-Evolving Intelligence Layer

Inspired by backend (Harness) architecture:
- Zero-tolerance enforcement: hallucination guard, mock/placeholder detection
- Quality gates: coverage, style, security, documentation
- Self-healing verifier: error classification + auto-fix loop
- Request classifier: routes by type (CODING/REASONING/ARCHITECTURE/etc.)
- Health monitor: latency tracking, p95/p99, circuit breaker
- Evolution orchestrator: observe → analyze → plan → execute → validate
- Pattern library: reusable ARCH/CODE/API/SEC/TESTING patterns
- Scaffolding engine: template-first file generation
"""

from hermes_core.enforcement.zero_tolerance import (
    ZeroToleranceEnforcement,
    EnforcementViolation,
    ValidationResult,
    ViolationSeverity,
    get_zero_tolerance_enforcement,
)
from hermes_core.quality.gates import (
    GateResult,
    QualityReport,
    GateStatus,
    GateSeverity,
    GateType,
    QualityGateRunner,
)
from hermes_core.classification.classifier import (
    RequestClassifier,
    RequestProfile,
    RequestType,
    classify_request,
)
from hermes_core.health.health_monitor import (
    HealthMetrics,
    ProviderHealthChecker,
    HealthStatus,
    get_health_checker,
)
from hermes_core.evolution.orchestrator import (
    HermesEvolutionOrchestrator,
    SystemObservation,
    EvolutionPlan,
    EvolutionResult,
    get_evolution_orchestrator,
)
from hermes_core.patterns.library import (
    HermesPatternLibrary,
    HermesPattern,
    PatternCategory,
    get_pattern_library,
)

__all__ = [
    # Enforcement
    "ZeroToleranceEnforcement",
    "EnforcementViolation",
    "ValidationResult",
    "ViolationSeverity",
    "get_zero_tolerance_enforcement",
    # Quality
    "GateResult",
    "QualityReport",
    "GateStatus",
    "GateSeverity",
    "GateType",
    "QualityGateRunner",
    # Classification
    "RequestClassifier",
    "RequestProfile",
    "RequestType",
    "classify_request",
    # Health
    "HealthMetrics",
    "ProviderHealthChecker",
    "HealthStatus",
    "get_health_checker",
    # Evolution
    "HermesEvolutionOrchestrator",
    "SystemObservation",
    "EvolutionPlan",
    "EvolutionResult",
    "get_evolution_orchestrator",
    # Patterns
    "HermesPatternLibrary",
    "HermesPattern",
    "PatternCategory",
    "get_pattern_library",
]
