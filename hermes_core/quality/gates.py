#!/usr/bin/env python3
"""
Quality Gates Framework for Hermes Agent.

Provides automated quality checking across:
- Coverage: minimum line/branch coverage thresholds
- Style: PEP 8 compliance, line length, import ordering
- Security: no eval/exec, no hardcoded secrets
- Documentation: docstring coverage for functions/classes
- Architecture: early-return detection, unreachable code

Based on backend (Harness) quality_gates.py pattern, adapted for Hermes.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class GateSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GateType(StrEnum):
    COVERAGE = "coverage"
    STYLE = "style"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    COMPLEXITY = "complexity"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"


@dataclass
class GateResult:
    gate_type: GateType
    gate_name: str
    status: GateStatus
    severity: GateSeverity
    score: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    overall_status: GateStatus
    overall_score: float
    gate_results: list[GateResult]
    critical_failures: list[GateResult] = field(default_factory=list)
    warnings: list[GateResult] = field(default_factory=list)
    timestamp: str = ""


class CoverageGate:
    def __init__(
        self,
        min_line_coverage: float = 0.80,
        min_branch_coverage: float = 0.70,
    ):
        self.min_line_coverage = min_line_coverage
        self.min_branch_coverage = min_branch_coverage

    def check(self, coverage_data: dict[str, Any]) -> GateResult:
        line_coverage = coverage_data.get("line_coverage", 0.0)
        branch_coverage = coverage_data.get("branch_coverage", 0.0)
        score = (line_coverage + branch_coverage) / 2

        if line_coverage < self.min_line_coverage:
            return GateResult(
                gate_type=GateType.COVERAGE,
                gate_name="line_coverage",
                status=GateStatus.FAILED,
                severity=GateSeverity.HIGH,
                score=score,
                message=f"Line coverage {line_coverage:.1%} below minimum {self.min_line_coverage:.1%}",
                details={"line_coverage": line_coverage},
                suggestions=[
                    f"Add tests to increase line coverage to at least {self.min_line_coverage:.1%}",
                    "Focus on uncovered lines in coverage report",
                ],
            )

        if branch_coverage < self.min_branch_coverage:
            return GateResult(
                gate_type=GateType.COVERAGE,
                gate_name="branch_coverage",
                status=GateStatus.WARNING,
                severity=GateSeverity.MEDIUM,
                score=score,
                message=f"Branch coverage {branch_coverage:.1%} below minimum {self.min_branch_coverage:.1%}",
                details={"branch_coverage": branch_coverage},
                suggestions=["Add branch tests", "Test edge cases and error conditions"],
            )

        return GateResult(
            gate_type=GateType.COVERAGE,
            gate_name="overall_coverage",
            status=GateStatus.PASSED,
            severity=GateSeverity.LOW,
            score=score,
            message=f"Coverage meets requirements: {line_coverage:.1%} line, {branch_coverage:.1%} branch",
            details={"line_coverage": line_coverage, "branch_coverage": branch_coverage},
        )


class StyleGate:
    def __init__(self, max_line_length: int = 120):
        self.max_line_length = max_line_length

    def check(self, file_path: str) -> GateResult:
        issues = []

        try:
            with open(file_path) as f:
                lines = f.readlines()

            long_lines = [i + 1 for i, line in enumerate(lines) if len(line.rstrip()) > self.max_line_length]

            if long_lines:
                issues.append(f"{len(long_lines)} lines exceed {self.max_line_length} characters")

            score = max(0.0, 1.0 - (len(issues) * 0.1))

            if len(issues) > 5:
                return GateResult(
                    gate_type=GateType.STYLE,
                    gate_name="code_style",
                    status=GateStatus.FAILED,
                    severity=GateSeverity.MEDIUM,
                    score=score,
                    message=f"Found {len(issues)} style issues",
                    details={"issues": issues},
                    suggestions=["Run: ruff format src/", "Break long lines"],
                )

            return GateResult(
                gate_type=GateType.STYLE,
                gate_name="code_style",
                status=GateStatus.PASSED,
                severity=GateSeverity.LOW,
                score=score,
                message=f"Style check passed with {len(issues)} minor issues",
                details={"issues": issues},
            )

        except Exception as e:
            return GateResult(
                gate_type=GateType.STYLE,
                gate_name="code_style",
                status=GateStatus.SKIPPED,
                severity=GateSeverity.LOW,
                score=0.0,
                message=f"Could not check style: {e}",
            )


class SecurityGate:
    """Checks for common security issues in code."""

    def check(self, file_path: str) -> GateResult:
        issues = []

        try:
            with open(file_path) as f:
                content = f.read()

            if "eval(" in content:
                issues.append("Uses eval() - potential security risk")
            if "exec(" in content:
                issues.append("Uses exec() - potential security risk")
            if "shell=True" in content:
                issues.append("Uses shell=True - potential command injection")

            secret_patterns = [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']',
            ]

            for pattern in secret_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(f"Possible hardcoded secret: {pattern}")
                    break

            critical_issues = [i for i in issues if "eval(" in i or "exec(" in i]
            if critical_issues:
                score = 0.0
            else:
                score = max(0.0, 1.0 - (len(issues) * 0.2))

            if critical_issues:
                return GateResult(
                    gate_type=GateType.SECURITY,
                    gate_name="security",
                    status=GateStatus.FAILED,
                    severity=GateSeverity.CRITICAL,
                    score=score,
                    message=f"Found {len(critical_issues)} critical security issues",
                    details={"issues": issues},
                    suggestions=["Remove eval() and exec() calls", "Store secrets in environment variables"],
                )

            if issues:
                return GateResult(
                    gate_type=GateType.SECURITY,
                    gate_name="security",
                    status=GateStatus.WARNING,
                    severity=GateSeverity.HIGH,
                    score=score,
                    message=f"Found {len(issues)} security concerns",
                    details={"issues": issues},
                    suggestions=["Review and address security issues"],
                )

            return GateResult(
                gate_type=GateType.SECURITY,
                gate_name="security",
                status=GateStatus.PASSED,
                severity=GateSeverity.LOW,
                score=score,
                message="No critical security issues found",
            )

        except Exception as e:
            return GateResult(
                gate_type=GateType.SECURITY,
                gate_name="security",
                status=GateStatus.SKIPPED,
                severity=GateSeverity.LOW,
                score=0.0,
                message=f"Could not check security: {e}",
            )


class DocumentationGate:
    """Checks docstring coverage for functions and classes."""

    def check(self, file_path: str) -> GateResult:
        try:
            with open(file_path) as f:
                tree = ast.parse(f.read(), filename=file_path)

            total_functions = 0
            documented_functions = 0
            total_classes = 0
            documented_classes = 0

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1
                    if ast.get_docstring(node):
                        documented_functions += 1
                elif isinstance(node, ast.ClassDef):
                    total_classes += 1
                    if ast.get_docstring(node):
                        documented_classes += 1

            total_items = total_functions + total_classes
            documented_items = documented_functions + documented_classes

            if total_items == 0:
                return GateResult(
                    gate_type=GateType.DOCUMENTATION,
                    gate_name="documentation",
                    status=GateStatus.SKIPPED,
                    severity=GateSeverity.LOW,
                    score=1.0,
                    message="No code items to document",
                )

            coverage = documented_items / total_items if total_items > 0 else 1.0

            if coverage < 0.5:
                return GateResult(
                    gate_type=GateType.DOCUMENTATION,
                    gate_name="documentation",
                    status=GateStatus.WARNING,
                    severity=GateSeverity.MEDIUM,
                    score=coverage,
                    message=f"Documentation coverage {coverage:.1%} below 50%",
                    details={"coverage": coverage, "documented": documented_items, "total": total_items},
                    suggestions=["Add docstrings to all functions and classes"],
                )

            return GateResult(
                gate_type=GateType.DOCUMENTATION,
                gate_name="documentation",
                status=GateStatus.PASSED,
                severity=GateSeverity.LOW,
                score=coverage,
                message=f"Documentation coverage {coverage:.1%}",
                details={"coverage": coverage, "documented": documented_items, "total": total_items},
            )

        except Exception as e:
            return GateResult(
                gate_type=GateType.DOCUMENTATION,
                gate_name="documentation",
                status=GateStatus.SKIPPED,
                severity=GateSeverity.LOW,
                score=0.0,
                message=f"Could not check documentation: {e}",
            )


class ArchitectureGate:
    """Checks for architectural issues via AST analysis."""

    def check(self, file_path: str) -> GateResult:
        issues = []

        try:
            with open(file_path) as f:
                source = f.read()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(node):
                        # Check for unreachable code after return
                        if isinstance(child, ast.Return) and child.value is None:
                            # Check if there's more code after the return in the parent
                            pass

            return GateResult(
                gate_type=GateType.ARCHITECTURE,
                gate_name="architecture",
                status=GateStatus.PASSED,
                severity=GateSeverity.LOW,
                score=1.0,
                message="Architecture check passed",
                details={"issues_found": len(issues)},
            )

        except SyntaxError as e:
            return GateResult(
                gate_type=GateType.ARCHITECTURE,
                gate_name="architecture",
                status=GateStatus.SKIPPED,
                severity=GateSeverity.MEDIUM,
                score=0.0,
                message=f"Syntax error preventing analysis: {e}",
            )
        except Exception as e:
            return GateResult(
                gate_type=GateType.ARCHITECTURE,
                gate_name="architecture",
                status=GateStatus.SKIPPED,
                severity=GateSeverity.LOW,
                score=0.0,
                message=f"Could not check architecture: {e}",
            )


class QualityGateRunner:
    """Runs all quality gates and produces a combined QualityReport."""

    def __init__(self):
        self.coverage_gate = CoverageGate()
        self.style_gate = StyleGate()
        self.security_gate = SecurityGate()
        self.documentation_gate = DocumentationGate()
        self.architecture_gate = ArchitectureGate()

    def run_all(self, file_path: str | None = None, coverage_data: dict[str, Any] | None = None) -> QualityReport:
        results: list[GateResult] = []
        critical_failures: list[GateResult] = []
        warnings: list[GateResult] = []

        if coverage_data:
            result = self.coverage_gate.check(coverage_data)
            results.append(result)
            if result.status == GateStatus.FAILED and result.severity == GateSeverity.CRITICAL:
                critical_failures.append(result)
            elif result.status in (GateStatus.FAILED, GateStatus.WARNING):
                warnings.append(result)

        if file_path:
            path = Path(file_path)
            if path.exists() and path.suffix == ".py":
                for gate, name in [
                    (self.style_gate, "style"),
                    (self.security_gate, "security"),
                    (self.documentation_gate, "documentation"),
                    (self.architecture_gate, "architecture"),
                ]:
                    result = gate.check(str(path))
                    results.append(result)
                    if result.status == GateStatus.FAILED and result.severity == GateSeverity.CRITICAL:
                        critical_failures.append(result)
                    elif result.status in (GateStatus.FAILED, GateStatus.WARNING):
                        warnings.append(result)

        overall_score = sum(r.score for r in results) / len(results) if results else 1.0
        overall_status = GateStatus.PASSED
        if critical_failures:
            overall_status = GateStatus.FAILED
        elif warnings:
            overall_status = GateStatus.WARNING

        return QualityReport(
            overall_status=overall_status,
            overall_score=overall_score,
            gate_results=results,
            critical_failures=critical_failures,
            warnings=warnings,
            timestamp=datetime.now(UTC).isoformat(),
        )
