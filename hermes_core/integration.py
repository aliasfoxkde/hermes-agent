#!/usr/bin/env python3
"""
Hermes Core Integration Layer — Wires hermes_core modules into the agent loop.

This module is the SINGLE integration point for all hermes_core functionality.
It exposes lazy-initialized singletons and integration functions that run_agent.py
calls at specific points in the agent lifecycle.

Integration Points in run_agent.py:
  1. Session init  → hermes_core_integration.init_session(session_id)
  2. Tool result  → hermes_core_integration.on_tool_result(tool_name, result, args)
  3. Code error    → hermes_core_integration.on_code_error(code, error, file_path)
  4. API call      → hermes_core_integration.on_api_call(provider, latency_ms, success, error)
  5. Pre-response  → hermes_core_integration.on_pre_response(messages, final_response)
  6. Session end   → hermes_core_integration.shutdown()

Philosophy: Template + AI-for-gaps > pure AI.
  Every hermes_core module uses deterministic patterns. AI fills in the gaps.
  This makes Hermes more reliable, faster, and more resilient.
"""

from __future__ import annotations

import ast
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Lazy-loaded singletons ──────────────────────────────────────────────────

_health_checker = None
_quality_gate_runner = None
_self_healing_verifier = None
_request_classifier = None
_evolution_orchestrator = None
_pattern_library = None
_zero_tolerance_enforcement = None
_initialized = False
_session_id: Optional[str] = None


def _lazy_init():
    """Lazily initialize all hermes_core singletons. Called once per session."""
    global _health_checker, _quality_gate_runner, _self_healing_verifier
    global _request_classifier, _evolution_orchestrator, _pattern_library
    global _zero_tolerance_enforcement, _initialized

    if _initialized:
        return

    # Health monitor (lazy, non-fatal)
    try:
        from hermes_core.health.health_monitor import get_health_checker
        _health_checker = get_health_checker()
    except Exception as e:
        logger.debug("Health monitor unavailable: %s", e)
        _health_checker = None

    # Quality gate runner
    try:
        from hermes_core.quality.gates import QualityGateRunner
        _quality_gate_runner = QualityGateRunner()
    except Exception as e:
        logger.debug("Quality gate runner unavailable: %s", e)
        _quality_gate_runner = None

    # Self-healing verifier
    try:
        from hermes_core.enforcement.self_healing import SelfHealingVerifier
        _self_healing_verifier = SelfHealingVerifier()
    except Exception as e:
        logger.debug("Self-healing verifier unavailable: %s", e)
        _self_healing_verifier = None

    # Request classifier
    try:
        from hermes_core.classification.classifier import RequestClassifier
        _request_classifier = RequestClassifier()
    except Exception as e:
        logger.debug("Request classifier unavailable: %s", e)
        _request_classifier = None

    # Evolution orchestrator (lazy, non-fatal)
    try:
        from hermes_core.evolution.orchestrator import get_evolution_orchestrator
        _evolution_orchestrator = get_evolution_orchestrator()
    except Exception as e:
        logger.debug("Evolution orchestrator unavailable: %s", e)
        _evolution_orchestrator = None

    # Pattern library
    try:
        from hermes_core.patterns.library import get_pattern_library
        _pattern_library = get_pattern_library()
    except Exception as e:
        logger.debug("Pattern library unavailable: %s", e)
        _pattern_library = None

    # Zero-tolerance enforcement (lazy)
    try:
        from hermes_core.enforcement.zero_tolerance import get_zero_tolerance_enforcement
        _zero_tolerance_enforcement = get_zero_tolerance_enforcement
    except Exception as e:
        logger.debug("Zero-tolerance enforcement unavailable: %s", e)
        _zero_tolerance_enforcement = None

    _initialized = True


# ── Session lifecycle ────────────────────────────────────────────────────────


def init_session(session_id: Optional[str] = None) -> None:
    """Called once at session start. Initializes all hermes_core systems."""
    global _session_id
    _session_id = session_id
    _lazy_init()
    logger.info("[HermesCore] Session initialized (session=%s)", session_id[:8] if session_id else None)


def shutdown() -> None:
    """Called at session end. Clean shutdown of all hermes_core systems."""
    global _health_checker, _initialized, _session_id
    if _health_checker is not None:
        try:
            _health_checker.stop()
        except Exception:
            pass
    _initialized = False
    _session_id = None
    logger.info("[HermesCore] Session shut down")


# ── Health Monitor ──────────────────────────────────────────────────────────


def on_api_call(
    provider: str,
    latency_ms: float,
    success: bool,
    error: str = "",
) -> None:
    """Called after each API call. Tracks latency and failure for circuit breaker."""
    if _health_checker is None:
        return
    try:
        _health_checker.record_request(provider, latency_ms, success, error)
    except Exception as e:
        logger.debug("Health monitor record_request failed: %s", e)


def is_provider_available(provider: str) -> bool:
    """Check if a provider's circuit breaker is closed. Used for routing decisions."""
    if _health_checker is None:
        return True
    try:
        metrics = _health_checker.get_metrics(provider)
        if metrics is None:
            return True
        return metrics.is_available()
    except Exception:
        return True  # Fail open


def get_provider_health_summary() -> dict[str, Any]:
    """Get a summary of all provider health for debugging."""
    if _health_checker is None:
        return {}
    try:
        all_metrics = _health_checker.get_all_metrics()
        return {
            name: {
                "status": m.status.value,
                "circuit_open": m.circuit_open,
                "avg_latency_ms": round(m.avg_latency_ms, 1),
                "p95_latency_ms": round(m.p95_latency_ms, 1),
                "error_rate": round(m.error_rate, 3),
                "total_requests": m.total_requests,
            }
            for name, m in all_metrics.items()
        }
    except Exception:
        return {}


# ── Quality Gates ────────────────────────────────────────────────────────────


# Tools whose results should trigger quality gate checks
_QUALITY_GATED_TOOLS = frozenset([
    "write_file", "patch", "terminal", "execute_code",
])


def on_tool_result(
    tool_name: str,
    result: str,
    args: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Called after each tool execution. Runs quality gates for file-writing tools.

    Returns a dict with gate results if quality issues were found, None otherwise.
    The caller can log or surface these results to the agent.
    """
    if _quality_gate_runner is None:
        return None

    if tool_name not in _QUALITY_GATED_TOOLS:
        return None

    if args is None:
        args = {}

    gate_results: list[dict[str, Any]] = []

    # ── write_file / patch: check the written file ──────────────────────
    if tool_name in ("write_file", "patch") and "path" in args:
        file_path = args.get("path", "")
        try:
            report = _quality_gate_runner.run_all(file_path=file_path)
            for gr in report.gate_results:
                if gr.status.value in ("failed", "warning"):
                    gate_results.append({
                        "gate": gr.gate_type.value,
                        "name": gr.gate_name,
                        "status": gr.status.value,
                        "severity": gr.severity.value,
                        "score": round(gr.score, 3),
                        "message": gr.message,
                        "suggestions": gr.suggestions,
                    })
        except Exception as e:
            logger.debug("Quality gate check failed for %s: %s", file_path, e)

    # ── terminal: check for suspicious commands ───────────────────────────
    elif tool_name == "terminal" and "command" in args:
        command = args.get("command", "")
        suspicious = _check_command_safety(command)
        if suspicious:
            gate_results.append({
                "gate": "security",
                "name": "command_safety",
                "status": "warning",
                "severity": "high",
                "score": 0.5,
                "message": f"Suspicious command pattern: {suspicious}",
                "suggestions": ["Review command for injection risks"],
            })

    if gate_results:
        # Log the most severe issue
        critical = [g for g in gate_results if g.get("severity") == "critical"]
        warning = [g for g in gate_results if g.get("severity") == "warning"]
        if critical:
            for c in critical:
                logger.warning(
                    "[HermesCore quality] %s [%s]: %s — %s",
                    tool_name, c["gate"], c["message"], args.get("path", ""),
                )
        elif warning:
            for w in warning:
                logger.info(
                    "[HermesCore quality] %s [%s]: %s — %s",
                    tool_name, w["gate"], w["message"], args.get("path", ""),
                )
        return {"gate_results": gate_results}

    return None


def _check_command_safety(command: str) -> Optional[str]:
    """Check for suspicious command patterns."""
    suspicious = [
        ("rm -rf /", "recursive root deletion"),
        ("curl | sh", "pipe to shell"),
        ("wget | sh", "wget pipe to shell"),
        ("sudo su", "privilege escalation"),
        ("chmod 777", "world-writable permissions"),
        ("> /etc/passwd", "system file overwrite"),
        ("nc -e", "netcat reverse shell"),
        ("bash -i", "interactive bash"),
        ("; shutdown", "system shutdown attempt"),
        ("&& shutdown", "system shutdown attempt"),
    ]
    cmd_lower = command.lower()
    for pattern, reason in suspicious:
        if pattern in cmd_lower:
            return reason
    return None


# ── Self-Healing ────────────────────────────────────────────────────────────


def on_code_error(
    code: str,
    error: str,
    file_path: Optional[str] = None,
) -> tuple[bool, Optional[str], Optional[dict]]:
    """Called when code execution produces an error.

    Returns (fixed, fixed_code_or_None, verification_result_or_None).
    The caller should present fixed_code to the agent for review.
    """
    if _self_healing_verifier is None:
        return False, None, None

    try:
        # Classify the error type
        error_type = _classify_error(error)
        error_line = _extract_error_line(error)

        from hermes_core.enforcement.self_healing import VerificationResult, ErrorType
        verification = VerificationResult(
            passed=False,
            error_type=error_type,
            error_message=error,
            error_line=error_line,
        )

        # Attempt auto-fix
        fixed_code, final_verification = _self_healing_verifier.verify_and_fix(
            code, tests=None
        )

        if final_verification and final_verification.passed:
            logger.info(
                "[HermesCore self-heal] Fixed %s in %s (line %s): %s → code revised",
                error_type.value if error_type else "error",
                file_path or "unknown",
                error_line or "?",
                error[:100],
            )
            return True, fixed_code, {
                "passed": final_verification.passed,
                "error_type": error_type.value if error_type else "unknown",
                "confidence": final_verification.confidence,
                "message": error,
            }

        # Failed to fix
        logger.warning(
            "[HermesCore self-heal] Could not auto-fix %s: %s",
            error_type.value if error_type else "error",
            error[:100],
        )
        return False, None, None

    except Exception as e:
        logger.debug("Self-healing failed: %s", e)
        return False, None, None


def _classify_error(error: str) -> "Optional[Any]":  # Forward ref to avoid circular
    """Classify an error string into an ErrorType."""
    from hermes_core.enforcement.self_healing import ErrorType

    error_lower = error.lower()
    if "syntaxerror" in error_lower or "unexpected eof" in error_lower:
        return ErrorType.SYNTAX_ERROR
    if "importerror" in error_lower or "modulenotfound" in error_lower:
        return ErrorType.IMPORT_ERROR
    if "typeerror" in error_lower:
        return ErrorType.TYPE_ERROR
    if "attributeerror" in error_lower or "indexerror" in error_lower:
        return ErrorType.RUNTIME_ERROR
    if "assertionerror" in error_lower or "test" in error_lower:
        return ErrorType.TEST_FAILURE
    if "nameerror" in error_lower or "undefined" in error_lower:
        return ErrorType.RUNTIME_ERROR
    return ErrorType.UNKNOWN


def _extract_error_line(error: str) -> Optional[int]:
    """Try to extract line number from error message."""
    import re
    match = re.search(r"line (\d+)", error)
    if match:
        return int(match.group(1))
    match = re.search(r"\.py:(\d+)", error)
    if match:
        return int(match.group(1))
    return None


# ── Request Classification ──────────────────────────────────────────────────


def classify_request(
    messages: list[dict],
    model: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> Optional[dict[str, Any]]:
    """Classify incoming request to determine profile.

    Returns a dict with request type and profile flags, or None if unavailable.
    Used to adjust iteration budget, compression strategy, and tool selection.
    """
    if _request_classifier is None:
        return None

    try:
        profile = _request_classifier.classify(
            messages, model=model, max_tokens=max_tokens, temperature=temperature
        )
        return {
            "request_type": profile.request_type.value,
            "requires_reasoning": profile.requires_reasoning,
            "requires_coding": profile.requires_coding,
            "needs_deep_reasoning": profile.needs_deep_reasoning(),
            "is_coding_heavy": profile.is_coding_heavy(),
            "is_architecture_task": profile.is_architecture_task(),
            "max_cost_sensitivity": profile.max_cost_sensitivity,
            "latency_tolerance_ms": profile.latency_tolerance,
        }
    except Exception as e:
        logger.debug("Request classification failed: %s", e)
        return None


# ── Enforcement / Pattern Library ───────────────────────────────────────────


def get_pattern_guidance(category: str) -> Optional[str]:
    """Get enforcement guidance from the pattern library for a given category.

    Used to provide structured guidance to the agent when enforcing
    quality gates, security checks, or architectural patterns.
    """
    if _pattern_library is None:
        return None

    try:
        from hermes_core.patterns.library import PatternCategory
        cat_map = {
            "enforcement": PatternCategory.ENFORCEMENT,
            "security": PatternCategory.SECURITY,
            "architecture": PatternCategory.ARCHITECTURAL,
            "code": PatternCategory.CODE,
            "api": PatternCategory.API,
            "testing": PatternCategory.TESTING,
        }
        pc = cat_map.get(category)
        if pc is None:
            return None

        patterns = _pattern_library.get_by_category(pc)
        if not patterns:
            return None

        # Return guidance as a structured summary
        lines = [f"--- {category.upper()} PATTERNS ({len(patterns)} available) ---"]
        for p in patterns[:5]:  # Top 5 most relevant
            lines.append(f"  [{p.name}] {p.description}")
            lines.append(f"    Problem: {p.problem}")
            lines.append(f"    Solution: {p.solution}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("Pattern library guidance failed: %s", e)
        return None


# ── Zero-Tolerance Enforcement ─────────────────────────────────────────────


def enforce_output(final_response: str) -> tuple[bool, list[dict], list[dict]]:
    """Run zero-tolerance enforcement on a final response.

    Returns (allowed, violations, warnings).
    violations: list of EnforcementViolation dicts
    warnings: list of warning dicts
    """
    if _zero_tolerance_enforcement is None:
        return True, [], []

    try:
        enforcer = _zero_tolerance_enforcement()
        result = enforcer.validate_output(final_response)
        violations = [
            {"gate": v.gate, "line": v.line, "message": v.message, "severity": v.severity.value}
            for v in result.violations
        ]
        warnings = [
            {"gate": w.gate, "message": w.message}
            for w in result.warnings
        ]
        return result.allowed, violations, warnings
    except Exception as e:
        logger.debug("Zero-tolerance enforcement failed: %s", e)
        return True, [], []


# ── Evolution Orchestrator ──────────────────────────────────────────────────


async def trigger_evolution(observations: Optional[dict[str, Any]] = None) -> None:
    """Trigger the evolution orchestrator to analyze and potentially self-improve.

    This is called asynchronously — it does not block the agent loop.
    The orchestrator runs its 6-phase cycle (Observe → Analyze → Plan →
    Execute → Validate → Learn) and may update patterns, health thresholds,
    or other hermes_core configuration based on observed behavior.
    """
    if _evolution_orchestrator is None:
        return

    try:
        import asyncio
        from hermes_core.evolution.orchestrator import SystemObservation

        obs = observations or {}
        system_obs = SystemObservation(
            session_id=_session_id or "unknown",
            timestamp=__import__("datetime").datetime.now(),
            metrics=obs.get("metrics", {}),
            patterns_used=obs.get("patterns_used", []),
            violations=obs.get("violations", []),
            tool_results=obs.get("tool_results", {}),
        )
        asyncio.create_task(_evolution_orchestrator.evolve(system_obs))
    except Exception as e:
        logger.debug("Evolution orchestrator trigger failed: %s", e)


# ── Convenience: Check all hermes_core systems ─────────────────────────────


def get_status() -> dict[str, Any]:
    """Return a dict showing which hermes_core systems are available."""
    return {
        "health_monitor": _health_checker is not None,
        "quality_gates": _quality_gate_runner is not None,
        "self_healing": _self_healing_verifier is not None,
        "request_classifier": _request_classifier is not None,
        "evolution_orchestrator": _evolution_orchestrator is not None,
        "pattern_library": _pattern_library is not None,
        "zero_tolerance": _zero_tolerance_enforcement is not None,
        "initialized": _initialized,
        "session_id": _session_id[:8] if _session_id else None,
    }
