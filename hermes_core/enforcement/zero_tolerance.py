#!/usr/bin/env python3
"""
Zero-Tolerance Enforcement for Hermes Agent.

Blocks mock/fabricated data, placeholder code, hallucinated claims,
and regression indicators (agreeing, apologizing, emotional language).

Based on backend (Harness) zero_tolerance.py pattern, adapted for CLI agent.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ViolationSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class EnforcementViolation:
    gate: str
    severity: ViolationSeverity
    message: str
    line: int | None = None
    snippet: str | None = None


@dataclass
class ValidationResult:
    allowed: bool = True
    violations: list[EnforcementViolation] = field(default_factory=list)
    warnings: list[EnforcementViolation] = field(default_factory=list)

    @property
    def total_violations(self) -> int:
        return len(self.violations) + len(self.warnings)

    def add_violation(
        self,
        gate: str,
        severity: ViolationSeverity,
        message: str,
        line: int | None = None,
        snippet: str | None = None,
    ):
        v = EnforcementViolation(gate=gate, severity=severity, message=message, line=line, snippet=snippet)
        if severity in (ViolationSeverity.CRITICAL, ViolationSeverity.HIGH):
            self.violations.append(v)
            self.allowed = False
        else:
            self.warnings.append(v)


class MockDataDetector:
    """Detects mock/fabricated data patterns."""

    MOCK_PATTERNS = [
        r"mock_|Mock_|MOCK_",
        r"placeholder|PLACEHOLDER",
        r"fake_|FAKE_",
        r"fabricat|Fabricated|FABRICATED",
        r"test_|TEST_",
        r"dummy|Dummy|DUMMY_",
    ]

    FAKE_EXAMPLES = [
        r"example\.com",
        r"fake.*@.*\.com",
        r"(john|jane) (doe|smith)",
        r"123.*street|456.*avenue",
        r"(000|111|222|123|999)-.*-.*",
    ]

    def __init__(self, source: str):
        self.source = source

    def detect(self) -> list[EnforcementViolation]:
        violations = []
        lines = self.source.split("\n")

        for line_num, line in enumerate(lines, 1):
            for pattern in self.MOCK_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(
                        EnforcementViolation(
                            gate="mock_data",
                            severity=ViolationSeverity.HIGH,
                            message=f"Mock data detected: {pattern}",
                            line=line_num,
                            snippet=line.strip(),
                        )
                    )

            if not line.strip().startswith("#"):
                for pattern in self.FAKE_EXAMPLES:
                    if re.search(pattern, line, re.IGNORECASE):
                        violations.append(
                            EnforcementViolation(
                                gate="fake_data",
                                severity=ViolationSeverity.HIGH,
                                message=f"Fake example data: {pattern}",
                                line=line_num,
                                snippet=line.strip(),
                            )
                        )

        return violations


class PlaceholderDetector:
    """Detects placeholder code patterns."""

    PATTERNS = [
        r"TODO.*implement",
        r"FIXME",
        r"XXX.*hack",
        r"NotImplementedError",
        r"pass\s*#.*TODO",
        r"return\s+None\s*#.*TODO",
        r"\{\s*#.*TODO",
        r"raise\s+Exception\([\"']not implemented",
        r"#\s*PLACEHOLDER",
        r"^\s*#\s*$",  # Empty comment line (whitespace only)
    ]

    def __init__(self, source: str):
        self.source = source

    def detect(self) -> list[EnforcementViolation]:
        violations = []
        lines = self.source.split("\n")

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") and "TODO" not in stripped:
                continue

            for pattern in self.PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(
                        EnforcementViolation(
                            gate="placeholder_code",
                            severity=ViolationSeverity.HIGH,
                            message=f"Placeholder detected: {pattern}",
                            line=line_num,
                            snippet=line.strip(),
                        )
                    )

        return violations


class RegressionIndicatorDetector:
    """Detects regression indicators: agreeing, apologizing, emotional language.

    These patterns indicate the enforcement system has failed.
    """

    REGRESSION_PATTERNS = [
        # Agreeing/apologizing
        (r"\b(you('re| are) right|I understand your|heard you|I agree)\b", "agreeing_language", ViolationSeverity.MEDIUM),
        (r"\b(sorry|apologize|my bad|mistake on my)\b", "apologetic_language", ViolationSeverity.MEDIUM),
        # Emotional language
        (r"\b(great|awesome|amazing|fantastic|wonderful)\b", "emotional_language", ViolationSeverity.LOW),
        # Unverified claims
        (r"\bthis (should|would|could) work\b", "unverified_claim", ViolationSeverity.MEDIUM),
        (r"\bfixed!\s*$", "unverified_fixed_claim", ViolationSeverity.HIGH),
        (r"\bdone!\s*$", "unverified_done_claim", ViolationSeverity.HIGH),
    ]

    def __init__(self, source: str):
        self.source = source

    def detect(self) -> list[EnforcementViolation]:
        violations = []
        lines = self.source.split("\n")

        for line_num, line in enumerate(lines, 1):
            for pattern, name, severity in self.REGRESSION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(
                        EnforcementViolation(
                            gate="regression_indicator",
                            severity=severity,
                            message=f"Regression indicator [{name}]: {pattern}",
                            line=line_num,
                            snippet=line.strip(),
                        )
                    )

        return violations


class ClaimValidator:
    """Validates that claims have context or citations."""

    UNCERTAINTY_PATTERNS = [
        (r"\b(probably|might be|could be|likely)\b", "without uncertainty marker"),
        (r"\b(I think|I believe)\b", "without explicit qualification"),
    ]

    CITATION_REQUIRED_PATTERNS = [
        (r"\b(according to|research shows|studies indicate)\b", "without citation"),
    ]

    def __init__(self, source: str):
        self.source = source

    def detect(self) -> list[EnforcementViolation]:
        violations = []
        lines = self.source.split("\n")

        for line_num, line in enumerate(lines, 1):
            if not (line.strip().startswith("#") or '"""' in line or "'''" in line):
                continue

            for pattern, hint in self.UNCERTAINTY_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    if "[uncertain]" not in line and "[source]" not in line and "[assumed]" not in line:
                        violations.append(
                            EnforcementViolation(
                                gate="hallucinated_claim",
                                severity=ViolationSeverity.MEDIUM,
                                message=f"Uncertainty {hint}",
                                line=line_num,
                                snippet=line.strip(),
                            )
                        )

            for pattern, hint in self.CITATION_REQUIRED_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    if not re.search(r"\[.*?\]", line):
                        violations.append(
                            EnforcementViolation(
                                gate="uncited_claim",
                                severity=ViolationSeverity.HIGH,
                                message=f"Claim {hint}",
                                line=line_num,
                                snippet=line.strip(),
                            )
                        )

        return violations


class ZeroToleranceEnforcement:
    """
    Zero-tolerance enforcement for Hermes agent.

    Blocks:
    - Mock/fabricated data
    - Placeholder code
    - Regression indicators (agreeing, apologizing, emotional language)
    - Hallucinated claims
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(__name__)

    def validate_code(
        self,
        source: str,
        filename: str = "code",
    ) -> ValidationResult:
        """Validate code against zero-tolerance gates."""
        result = ValidationResult(allowed=True)

        if "test" in filename.lower():
            return result

        detectors = [
            MockDataDetector(source),
            PlaceholderDetector(source),
            RegressionIndicatorDetector(source),
            ClaimValidator(source),
        ]

        for detector in detectors:
            violations = detector.detect()
            for violation in violations:
                result.add_violation(
                    gate=violation.gate,
                    severity=violation.severity,
                    message=violation.message,
                    line=violation.line,
                    snippet=violation.snippet,
                )

        if result.total_violations > 0:
            self.logger.warning(
                "Zero-tolerance enforcement: %s violations in %s",
                result.total_violations,
                filename,
            )
            for v in result.violations:
                self.logger.warning("  Line %s: [%s] %s", v.line, v.gate, v.message)

        return result

    def validate_output(self, output: str, context: str = "") -> ValidationResult:
        """Validate AI-generated output for violations."""
        result = ValidationResult(allowed=True)

        # Check for mock data indicators
        for pattern in MockDataDetector.MOCK_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                result.add_violation(
                    gate="mock_data",
                    severity=ViolationSeverity.HIGH,
                    message=f"Mock data in output: {pattern}",
                )

        # Check for placeholder indicators
        for pattern in PlaceholderDetector.PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                result.add_violation(
                    gate="placeholder_content",
                    severity=ViolationSeverity.HIGH,
                    message=f"Placeholder in output: {pattern}",
                )

        # Check regression indicators
        for pattern, name, severity in RegressionIndicatorDetector.REGRESSION_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                result.add_violation(
                    gate="regression_indicator",
                    severity=severity,
                    message=f"Regression indicator in output: {name}",
                )

        # Check for fabricated citations
        fabricated_citation_patterns = [
            r"\[https?://(?:www\.)?fakeexample\.com/.*\]",
            r"\[Source: (?!.*\.(?:com|org|edu|gov))",
            r"Source:\s*[^\s]+\.(?!(?:com|org|edu|gov))",
        ]
        for pattern in fabricated_citation_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                result.add_violation(
                    gate="fabricated_citation",
                    severity=ViolationSeverity.CRITICAL,
                    message="Fabricated citation detected",
                )

        if result.total_violations > 0:
            self.logger.warning(
                "Zero-tolerance enforcement: %s violations in output",
                result.total_violations,
            )

        return result


_global_enforcement: ZeroToleranceEnforcement | None = None


def get_zero_tolerance_enforcement(**kwargs) -> ZeroToleranceEnforcement:
    """Get or create global ZeroToleranceEnforcement instance."""
    global _global_enforcement
    if _global_enforcement is None:
        _global_enforcement = ZeroToleranceEnforcement(**kwargs)
    return _global_enforcement
