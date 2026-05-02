#!/usr/bin/env python3
"""
Request Classifier for Hermes Agent.

Analyzes incoming requests to determine their type and route them appropriately.
Enables intelligent tool selection and model routing based on request profile.

Based on backend (Harness) router/classifier.py pattern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class RequestType(StrEnum):
    CODING = "coding"
    REASONING = "reasoning"
    ARCHITECTURE = "architecture"
    CONVERSATION = "conversation"
    VISION = "vision"
    TOOL_USE = "tool_use"
    SIMPLE = "simple"
    RESEARCH = "research"


@dataclass
class RequestProfile:
    request_type: RequestType
    requires_reasoning: int = 1  # 1-5 scale
    requires_coding: int = 1  # 1-5 scale
    requires_vision: bool = False
    requires_tools: bool = False
    max_cost_sensitivity: float = 1.0  # 0 (cheap) to 1 (expensive)
    latency_tolerance: int = 3000  # ms
    tokens_estimate: int = 1000

    def needs_deep_reasoning(self) -> bool:
        return self.requires_reasoning >= 4

    def is_coding_heavy(self) -> bool:
        return self.requires_coding >= 4

    def is_architecture_task(self) -> bool:
        return self.request_type == RequestType.ARCHITECTURE


class RequestClassifier:
    """Classify incoming requests to determine their profile."""

    CODING_KEYWORDS = [
        "code", "function", "class", "implement", "debug", "fix", "bug",
        "algorithm", "api", "endpoint", "database", "query", "migration",
        "refactor", "optimize", "test", "unittest", "integration",
        "file", "directory", "path", "import", "export",
    ]

    REASONING_KEYWORDS = [
        "explain", "analyze", "why", "how does", "compare", "evaluate",
        "assess", "critique", "pros", "cons", "recommend", "strategy",
        "architecture", "design", "pattern", "best practice",
        "reasoning", "logic", "thinking",
    ]

    ARCHITECTURE_KEYWORDS = [
        "architecture", "design", "system", "structure", "component",
        "module", "interface", "schema", "specification", "blueprint",
        "infrastructure", "scalability", "pattern", "framework",
        "stack", "tech stack", "architecture",
    ]

    RESEARCH_KEYWORDS = [
        "research", "find", "search", "lookup", "discover", "investigate",
        "explore", "learn about", "what is", "who is", "when did",
        "paper", "arxiv", "study", "benchmark",
    ]

    VISION_KEYWORDS = [
        "image", "picture", "photo", "screenshot", "diagram", "chart",
        "graph", "visual", "see", "look at", "extract from image",
        "screenshot", "UI", "mockup", "wireframe",
    ]

    TOOL_KEYWORDS = [
        "search", "fetch", "api call", "web", "lookup", "find",
        "execute", "run", "command", "tool", "bash", "terminal",
    ]

    def classify(
        self,
        messages: list[dict],
        model: str = "",
        stream: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> RequestProfile:
        """Classify a request based on its content and parameters."""
        all_content = self._extract_content(messages)
        request_type = self._determine_request_type(all_content, model)
        profile = self._build_profile(
            request_type, all_content, model, max_tokens, temperature
        )
        return profile

    def _extract_content(self, messages: list[dict]) -> str:
        """Extract all text content from messages."""
        content_parts = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            content_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        content_parts.append(item)
            else:
                content_parts.append(content)
        return " ".join(content_parts).lower()

    def _determine_request_type(self, content: str, model: str) -> RequestType:
        """Determine the primary type of request."""
        if any(kw in content for kw in self.VISION_KEYWORDS):
            return RequestType.VISION

        if any(kw in content for kw in self.ARCHITECTURE_KEYWORDS):
            return RequestType.ARCHITECTURE

        if any(kw in content for kw in self.RESEARCH_KEYWORDS):
            return RequestType.RESEARCH

        if any(kw in content for kw in self.CODING_KEYWORDS):
            return self._classify_coding_request(content)

        if any(kw in content for kw in self.REASONING_KEYWORDS):
            return RequestType.REASONING

        if any(kw in content for kw in self.TOOL_KEYWORDS):
            return RequestType.TOOL_USE

        return RequestType.CONVERSATION

    def _classify_coding_request(self, content: str) -> RequestType:
        """Further classify coding requests."""
        if any(kw in content for kw in self.ARCHITECTURE_KEYWORDS):
            return RequestType.ARCHITECTURE

        if re.search(r"class\s+\w+|def\s+\w+\(|import\s+\w+|async\s+def", content):
            return RequestType.CODING

        return RequestType.CODING

    def _build_profile(
        self,
        request_type: RequestType,
        content: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> RequestProfile:
        """Build a request profile based on type and analysis."""
        requires_reasoning = 1
        requires_coding = 1
        requires_vision = False
        requires_tools = False
        max_cost = 1.0
        latency = 3000
        tokens = 1000

        if request_type == RequestType.ARCHITECTURE:
            requires_reasoning = 5
            requires_coding = 4
            max_cost = 0.3
            latency = 5000
            tokens = 2000
        elif request_type == RequestType.CODING:
            requires_coding = 4
            requires_reasoning = 3
            max_cost = 0.5
            latency = 3000
            tokens = 1500
        elif request_type == RequestType.REASONING:
            requires_reasoning = 4
            requires_coding = 2
            max_cost = 0.4
            latency = 3000
            tokens = 1500
        elif request_type == RequestType.RESEARCH:
            requires_reasoning = 3
            requires_tools = True
            requires_coding = 1
            max_cost = 0.5
            latency = 3000
            tokens = 2000
        elif request_type == RequestType.VISION:
            requires_vision = True
            requires_reasoning = 3
            requires_coding = 2
            max_cost = 0.5
            latency = 5000
            tokens = 2000
        elif request_type == RequestType.TOOL_USE:
            requires_tools = True
            requires_reasoning = 3
            requires_coding = 3
            max_cost = 0.6
            latency = 5000
            tokens = 2000

        if model:
            if "architect" in model.lower():
                requires_reasoning = max(requires_reasoning, 5)
                requires_coding = max(requires_coding, 4)
            elif "coding" in model.lower():
                requires_coding = max(requires_coding, 4)
            elif "thinking" in model.lower():
                requires_reasoning = max(requires_reasoning, 4)

        if max_tokens > 4000:
            requires_reasoning = min(requires_reasoning + 1, 5)
            tokens = max_tokens

        if temperature < 0.3:
            requires_reasoning = min(requires_reasoning + 1, 5)
            requires_coding = min(requires_coding + 1, 5)

        if "complex" in content or "complicated" in content:
            requires_reasoning = min(requires_reasoning + 1, 5)
            requires_coding = min(requires_coding + 1, 5)

        if "urgent" in content or "quick" in content:
            latency = 1000
            max_cost = 0.8

        return RequestProfile(
            request_type=request_type,
            requires_reasoning=requires_reasoning,
            requires_coding=requires_coding,
            requires_vision=requires_vision,
            requires_tools=requires_tools,
            max_cost_sensitivity=max_cost,
            latency_tolerance=latency,
            tokens_estimate=tokens,
        )


def classify_request(
    messages: list[dict],
    model: str = "",
    stream: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> RequestProfile:
    """Classify a request (convenience function)."""
    classifier = RequestClassifier()
    return classifier.classify(messages, model, stream, max_tokens, temperature)
