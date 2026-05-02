#!/usr/bin/env python3
"""
Pattern Library for Hermes Agent.

Reusable architectural and code patterns organized by category:
- ARCHITECTURAL: System design patterns
- CODE: Implementation patterns
- API: Interface patterns
- SECURITY: Security patterns
- TESTING: Testing patterns

Based on backend (Harness) patterns/library.py pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PatternCategory(Enum):
    ARCHITECTURAL = "architectural"
    CODE = "code"
    API = "api"
    SECURITY = "security"
    TESTING = "testing"
    ENFORCEMENT = "enforcement"


@dataclass
class HermesPattern:
    """A reusable pattern."""
    name: str
    category: PatternCategory
    description: str
    problem: str
    solution: str
    implementation: str
    examples: list[str] | None = None


class HermesPatternLibrary:
    """Library of reusable patterns for Hermes."""

    def __init__(self):
        self.patterns: dict[str, HermesPattern] = {}
        self.by_category: dict[PatternCategory, list[str]] = {
            category: [] for category in PatternCategory
        }
        self.logger = logging.getLogger(__name__)

    def load_built_in_patterns(self):
        """Load Hermes-specific built-in patterns."""

        # === ENFORCEMENT PATTERNS ===

        self.add_pattern(HermesPattern(
            name="zero-tolerance-enforcement",
            category=PatternCategory.ENFORCEMENT,
            description="Zero-tolerance enforcement against hallucinations",
            problem="AI produces mock data, placeholders, unverified claims",
            solution="AST-based detectors for mock patterns, placeholders, regression indicators",
            implementation="MockDataDetector + PlaceholderDetector + RegressionIndicatorDetector",
            examples=["EnforcementViolation dataclass", "ValidationResult.allowed flag"],
        ))

        self.add_pattern(HermesPattern(
            name="quality-gates",
            category=PatternCategory.ENFORCEMENT,
            description="Layered quality gates: coverage, style, security, docs",
            problem="No automated quality checks on generated code",
            solution="GateResult + QualityReport with PASSED/FAILED/WARNING/SKIPPED states",
            implementation="CoverageGate, StyleGate, SecurityGate, DocumentationGate",
            examples=["GateStatus.PASSED", "QualityReport.overall_score"],
        ))

        self.add_pattern(HermesPattern(
            name="self-healing-verifier",
            category=PatternCategory.ENFORCEMENT,
            description="Error classification + strategy-based auto-fix loop",
            problem="Code errors require manual debugging and fixes",
            solution="ErrorType enum maps to FixStrategy; verify_and_fix() loops up to max_attempts",
            implementation="SelfHealingVerifier.verify_and_fix()",
            examples=["FixStrategy.CORRECT_SYNTAX", "VerificationResult.passed"],
        ))

        self.add_pattern(HermesPattern(
            name="regression-indicators",
            category=PatternCategory.ENFORCEMENT,
            description="Detects agreeing, apologizing, emotional language",
            problem="AI regresses to sycophant behavior",
            solution="Regex patterns for CRITICAL/HIGH/MEDIUM regression markers",
            implementation="RegressionIndicatorDetector with REGRESSION_PATTERNS",
            examples=["agreeing_language", "apologetic_language", "unverified_fixed_claim"],
        ))

        # === ARCHITECTURAL PATTERNS ===

        self.add_pattern(HermesPattern(
            name="circuit-breaker",
            category=PatternCategory.ARCHITECTURAL,
            description="Circuit breaker pattern for provider resilience",
            problem="Cascading failures when a provider goes down",
            solution="Track failures, open circuit on threshold, attempt recovery after timeout",
            implementation="HealthMetrics.circuit_open + failure_count + recovery_timeout",
            examples=["circuit_open", "failure_count", "close_circuit()"],
        ))

        self.add_pattern(HermesPattern(
            name="health-monitor",
            category=PatternCategory.ARCHITECTURAL,
            description="Periodic health checks with p95/p99 latency tracking",
            problem="No visibility into provider/service health",
            solution="ProviderHealthChecker with deque latency samples, automatic status updates",
            implementation="ProviderHealthChecker._health_check_loop()",
            examples=["HealthMetrics.p95_latency_ms", "HealthStatus.DEGRADED"],
        ))

        self.add_pattern(HermesPattern(
            name="evolution-orchestrator",
            category=PatternCategory.ARCHITECTURAL,
            description="Observe → Analyze → Plan → Execute → Validate → Learn cycle",
            problem="No systematic self-improvement mechanism",
            solution="HermesEvolutionOrchestrator with 6-phase async pipeline",
            implementation="evolve() async method",
            examples=["EvolutionPhase.OBSERVE", "EvolutionResult.changes_made"],
        ))

        self.add_pattern(HermesPattern(
            name="request-profile",
            category=PatternCategory.ARCHITECTURAL,
            description="Request classification with requirements scaling",
            problem="Can't determine optimal routing/tool selection without analysis",
            solution="RequestType enum + RequestProfile with 1-5 scales for reasoning/coding",
            implementation="RequestClassifier._build_profile()",
            examples=["RequestType.CODING", "needs_deep_reasoning()", "is_coding_heavy()"],
        ))

        self.add_pattern(HermesPattern(
            name="template-first-engine",
            category=PatternCategory.ARCHITECTURAL,
            description="Deterministic scaffolding from pre-built templates",
            problem="AI generates scaffolding from scratch — slow and non-deterministic",
            solution="Template registry with manifest scanning; AI fills gaps only",
            implementation="ScaffoldingEngine + TemplateRegistry",
            examples=["ScaffoldPlan", "template-first", "placeholder filling"],
        ))

        # === CODE PATTERNS ===

        self.add_pattern(HermesPattern(
            name="dataclass-result",
            category=PatternCategory.CODE,
            description="Dataclass result objects with allowed/pass status",
            problem="Functions return tuples or bare values making error handling inconsistent",
            solution="Result dataclass with .allowed flag + violations list",
            implementation="ValidationResult, VerificationResult, GateResult",
            examples=["result.allowed", "result.violations", "result.add_violation()"],
        ))

        self.add_pattern(HermesPattern(
            name="global-singleton",
            category=PatternCategory.CODE,
            description="Lazy global singleton with getter function",
            problem="Module-level state initialized at import time causes circular deps",
            solution="_global_instance = None; get_instance() creates on first call",
            implementation="get_zero_tolerance_enforcement() pattern",
            examples=["_global_enforcement", "get_health_checker()"],
        ))

        self.add_pattern(HermesPattern(
            name="strategy-map",
            category=PatternCategory.CODE,
            description="Strategy dispatch via enum-to-function map",
            problem="Long if/elif chains for strategy selection",
            solution="strategy_map = {Enum.VALUE: handler_fn}; strategy_map.get(enum)",
            implementation="SelfHealingVerifier.strategy_map",
            examples=["strategy_map[error_type]", "strategy_map.get(unknown, default)"],
        ))

        # === API PATTERNS ===

        self.add_pattern(HermesPattern(
            name="openai-compatible",
            category=PatternCategory.API,
            description="OpenAI API compatible endpoint structure",
            problem="Need to support multiple LLM providers transparently",
            solution="OpenAI-compatible /v1/chat/completions format; provider-specific conversion",
            implementation="model_tools.py handles OpenAI format",
            examples=["messages=[{role, content}]", "tool_calls", "stream=true"],
        ))

        # === TESTING PATTERNS ===

        self.add_pattern(HermesPattern(
            name="change-detector-test",
            category=PatternCategory.TESTING,
            description="Tests that fail when expected data changes (bad)",
            problem="Snapshot tests break on every model release, wasting engineering time",
            solution="Test the RELATIONSHIP between data elements, not the element values",
            implementation="assert catalog_entries_have_context_length (not assert 'glm-4.7' in catalog)",
            examples=["invariant tests", "relationship tests"],
        ))

        self.add_pattern(HermesPattern(
            name="regression-indicator-test",
            category=PatternCategory.TESTING,
            description="Tests that detect enforcement regression",
            problem="Can't tell if enforcement system failed",
            solution="Test that agreeing/apologizing patterns trigger violations",
            implementation="RegressionIndicatorDetector tests",
            examples=["test_agreeing_triggers_violation", "test_apologizing_triggers_violation"],
        ))

        self.logger.info("Loaded %s patterns", len(self.patterns))

    def add_pattern(self, pattern: HermesPattern):
        """Add a pattern to the library."""
        self.patterns[pattern.name] = pattern
        self.by_category[pattern.category].append(pattern.name)

    def get_pattern(self, name: str) -> HermesPattern | None:
        """Get a pattern by name."""
        return self.patterns.get(name)

    def get_by_category(self, category: PatternCategory) -> list[HermesPattern]:
        """Get all patterns in a category."""
        names = self.by_category.get(category, [])
        return [self.patterns[n] for n in names if n in self.patterns]

    def search_patterns(self, query: str) -> list[HermesPattern]:
        """Search for patterns by query."""
        query_lower = query.lower()
        return [
            p for p in self.patterns.values()
            if query_lower in p.name.lower()
            or query_lower in p.description.lower()
            or query_lower in p.problem.lower()
        ]

    def list_all_patterns(self) -> list[HermesPattern]:
        """List all available patterns."""
        return list(self.patterns.values())


_global_pattern_library: HermesPatternLibrary | None = None


def get_pattern_library() -> HermesPatternLibrary:
    """Get or create global HermesPatternLibrary instance."""
    global _global_pattern_library
    if _global_pattern_library is None:
        _global_pattern_library = HermesPatternLibrary()
        _global_pattern_library.load_built_in_patterns()
    return _global_pattern_library
