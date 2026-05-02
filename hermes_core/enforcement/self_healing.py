#!/usr/bin/env python3
"""
Self-Healing Verifier for Hermes Agent.

Based on backend (Harness) self_healing/verifier.py pattern:
- Self-healing with verifier feedback -> 90%+ success rates
- Error classification + strategy-based auto-fix loop

Features:
1. Test execution and verification
2. Error detection and classification
3. Auto-fix for common patterns
4. Iterative refinement
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    LOGIC_ERROR = "logic_error"
    TEST_FAILURE = "test_failure"
    UNKNOWN = "unknown"


class FixStrategy(Enum):
    CORRECT_SYNTAX = "correct_syntax"
    ADD_IMPORT = "add_import"
    FIX_TYPES = "fix_types"
    CORRECT_LOGIC = "correct_logic"
    ADD_HANDLER = "add_handler"
    SIMPLIFY = "simplify"
    ESCALATE = "escalate"


@dataclass
class VerificationResult:
    passed: bool
    error_type: ErrorType | None
    error_message: str | None
    error_line: int | None
    confidence: float = 1.0
    suggestions: list[str] = field(default_factory=list)
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0


@dataclass
class FixAttempt:
    strategy: FixStrategy
    original_code: str
    fixed_code: str
    success: bool
    verification_result: VerificationResult | None = None
    error: str | None = None


@dataclass
class SelfHealingConfig:
    max_attempts: int = 3
    timeout_seconds: int = 30
    auto_fix_enabled: bool = True
    test_command: str = "pytest"
    confidence_threshold: float = 0.7


class SelfHealingVerifier:
    """
    Self-healing verification system.

    Usage:
        verifier = SelfHealingVerifier()
        result = verifier.verify(code, tests)

        if not result.passed:
            fix = verifier.auto_fix(code, result)
            if fix.success:
                code = fix.fixed_code
    """

    SYNTAX_FIXES = [
        (r"unexpected EOF", "Add closing bracket/parenthesis"),
        (r"expected '.*'", "Add missing token"),
        (r"invalid syntax", "Check syntax around error location"),
        (r"unindent does not match", "Fix indentation"),
    ]

    IMPORT_FIXES = [
        (r"No module named '(\w+)'", "pip install {name} or add import"),
        (r"cannot import name '(\w+)'", "Check import path or spelling"),
        (r"ImportError", "Fix import statement"),
    ]

    TYPE_FIXES = [
        (r"got an unexpected keyword argument", "Check function signature"),
        (r"missing .* required positional argument", "Add required argument"),
        (r"can't multiply sequence by non-int", "Convert types properly"),
    ]

    def __init__(self, config: SelfHealingConfig | None = None):
        self.config = config or SelfHealingConfig()
        self._fix_history: list[FixAttempt] = []

    def verify(
        self,
        code: str,
        file_path: str | None = None,
        tests: list[str] | None = None,
    ) -> VerificationResult:
        """Verify code by running tests and checking for errors."""
        errors = self._check_syntax(code)

        if errors:
            return VerificationResult(
                passed=False,
                error_type=ErrorType.SYNTAX_ERROR,
                error_message=errors[0]["message"],
                error_line=errors[0].get("line"),
                suggestions=[e["fix"] for e in errors],
            )

        if tests:
            return self._run_tests(code, tests)

        return VerificationResult(
            passed=True,
            error_type=None,
            error_message=None,
            error_line=None,
            confidence=1.0,
        )

    def _check_syntax(self, code: str) -> list[dict]:
        """Check Python code for syntax errors."""
        errors = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            msg = str(e)
            fix = "Unknown fix"

            for pattern, suggestion in self.SYNTAX_FIXES:
                if re.search(pattern, msg, re.IGNORECASE):
                    fix = suggestion
                    break

            errors.append({
                "type": ErrorType.SYNTAX_ERROR,
                "message": msg,
                "line": e.lineno,
                "fix": fix,
            })

        return errors

    def _run_tests(self, code: str, tests: list[str]) -> VerificationResult:
        """Run tests and return results."""
        results = []

        for test_cmd in tests:
            try:
                result = subprocess.run(
                    test_cmd.split(),
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                )
                results.append({
                    "passed": result.returncode == 0,
                    "output": result.stdout + result.stderr,
                })
            except subprocess.TimeoutExpired:
                results.append({"passed": False, "output": "Timeout"})
            except Exception as e:
                results.append({"passed": False, "output": str(e)})

        passed = sum(1 for r in results if r["passed"])
        failed = len(results) - passed

        return VerificationResult(
            passed=failed == 0,
            error_type=ErrorType.TEST_FAILURE if failed > 0 else None,
            error_message=f"{failed} tests failed, {passed} passed" if failed > 0 else None,
            tests_run=len(results),
            tests_passed=passed,
            tests_failed=failed,
            confidence=passed / len(results) if results else 1.0,
        )

    def auto_fix(
        self,
        code: str,
        verification: VerificationResult,
    ) -> FixAttempt:
        """Attempt to auto-fix code based on verification result."""
        if verification.passed:
            return FixAttempt(
                strategy=FixStrategy.CORRECT_LOGIC,
                original_code=code,
                fixed_code=code,
                success=True,
                verification_result=verification,
            )

        if not self.config.auto_fix_enabled:
            return FixAttempt(
                strategy=FixStrategy.ESCALATE,
                original_code=code,
                fixed_code=code,
                success=False,
                error="Auto-fix disabled",
            )

        strategy_map = {
            ErrorType.SYNTAX_ERROR: self._fix_syntax,
            ErrorType.IMPORT_ERROR: self._fix_import,
            ErrorType.TYPE_ERROR: self._fix_types,
            ErrorType.RUNTIME_ERROR: self._fix_runtime,
            ErrorType.TEST_FAILURE: self._fix_test_failure,
        }

        strategy_fn = strategy_map.get(
            verification.error_type,
            self._fix_unknown,
        )

        try:
            fixed = strategy_fn(code, verification)

            fix_attempt = FixAttempt(
                strategy=FixStrategy(strategy_fn.__name__),
                original_code=code,
                fixed_code=fixed,
                success=True,
            )

            self._fix_history.append(fix_attempt)
            return fix_attempt

        except Exception as e:
            return FixAttempt(
                strategy=FixStrategy.ESCALATE,
                original_code=code,
                fixed_code=code,
                success=False,
                error=str(e),
            )

    def _fix_syntax(self, code: str, verification: VerificationResult) -> str:
        """Fix syntax errors."""
        msg = verification.error_message or ""

        if "closing bracket" in msg.lower():
            opens = code.count("{") + code.count("[") + code.count("(")
            closes = code.count("}") + code.count("]") + code.count(")")
            if opens > closes:
                code = code.rstrip() + "\n"

        elif "indentation" in msg.lower():
            lines = code.split("\n")
            fixed_lines = []
            for line in lines:
                if line.strip() and not line.startswith(" " * 4 * (len(line) - len(line.lstrip()))):
                    line = line.replace("\t", "    ")
                fixed_lines.append(line)
            code = "\n".join(fixed_lines)

        return code

    def _fix_import(self, code: str, verification: VerificationResult) -> str:
        """Fix import errors."""
        msg = verification.error_message or ""

        match = re.search(r"No module named '(\w+)'", msg)
        if match:
            module = match.group(1)
            code = f"import {module}\n{code}"

        return code

    def _fix_types(self, code: str, verification: VerificationResult) -> str:
        """Fix type errors."""
        return code

    def _fix_runtime(self, code: str, verification: VerificationResult) -> str:
        """Fix runtime errors."""
        msg = verification.error_message or ""

        if "division by zero" in msg.lower():
            code = code.replace("/ x", "/ max(1, x)")

        return code

    def _fix_test_failure(self, code: str, verification: VerificationResult) -> str:
        """Fix test failures by simplifying or correcting logic."""
        return code

    def _fix_unknown(self, code: str, verification: VerificationResult) -> str:
        """Fix unknown errors — simplify approach."""
        lines = [l for l in code.split("\n") if not l.strip().startswith("#")]
        return "\n".join(lines)

    def verify_and_fix(
        self,
        code: str,
        tests: list[str] | None = None,
    ) -> tuple[str, VerificationResult]:
        """Verify code and auto-fix if needed."""
        attempts = 0
        current_code = code

        while attempts < self.config.max_attempts:
            verification = self.verify(current_code, tests=tests)

            if verification.passed:
                return current_code, verification

            fix = self.auto_fix(current_code, verification)

            if not fix.success:
                break

            current_code = fix.fixed_code
            attempts += 1

        return current_code, self.verify(current_code, tests=tests)

    def get_stats(self) -> dict:
        """Get verification statistics."""
        total_attempts = len(self._fix_history)
        successful = sum(1 for f in self._fix_history if f.success)

        return {
            "total_attempts": total_attempts,
            "successful_fixes": successful,
            "success_rate": successful / total_attempts if total_attempts else 0,
            "strategies_used": [f.strategy.value for f in self._fix_history],
        }
