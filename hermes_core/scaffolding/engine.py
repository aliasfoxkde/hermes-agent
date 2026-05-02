#!/usr/bin/env python3
"""
Scaffolding Engine for Hermes Agent.

Template-first file generation with progress tracking.
When a template exists, serve it deterministically. AI fills gaps only.

Based on backend (Harness) scaffolding/engine.py pattern.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ScaffoldEventType(Enum):
    API_REQUEST = "api_request"
    THINKING = "thinking"
    STRUCTURE = "structure"
    FILE_OPERATION = "file_operation"
    FILE_CREATED = "file_created"
    DOCUMENTATION = "documentation"
    SETUP_INSTRUCTION = "setup_instruction"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ScaffoldEvent:
    event_type: ScaffoldEventType
    session_id: str
    timestamp: str
    data: dict[str, Any]
    collapsed: bool = False


@dataclass
class ScaffoldFileTemplate:
    """A file template with placeholders."""
    file_path: str
    content: str
    placeholders: list[str] = field(default_factory=list)


@dataclass
class ScaffoldPlan:
    """A scaffolding plan."""
    session_id: str
    project_type: str
    file_structure: dict[str, list[str]]  # folder -> [files]
    templates: dict[str, ScaffoldFileTemplate]
    estimated_files: int = 0
    estimated_time_ms: float = 0.0


@dataclass
class ScaffoldResult:
    """Result of scaffolding generation."""
    session_id: str
    success: bool
    files_created: list[str]
    folders_created: list[str]
    placeholders: dict[str, list[str]]
    elapsed_time_ms: float
    error: str | None = None


class ScaffoldingEngine:
    """
    Template-first scaffolding engine.

    Features:
    - Deterministic output (template-first, no AI for known patterns)
    - Progress tracking via events
    - Placeholder-based for AI completion
    - <100ms for deterministic part
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._template_cache: dict[str, ScaffoldFileTemplate] = {}

    def generate_plan(
        self,
        session_id: str,
        project_type: str,
        requested_features: list[str],
    ) -> ScaffoldPlan:
        """Generate a scaffolding plan from request."""
        file_structure: dict[str, list[str]] = {}
        templates: dict[str, ScaffoldFileTemplate] = {}

        # Add standard project structure based on project type
        if project_type == "python":
            file_structure = {
                "": ["README.md", "pyproject.toml", ".gitignore"],
                "src/": ["__init__.py", "main.py"],
                "tests/": ["test_main.py"],
            }
        elif project_type == "typescript":
            file_structure = {
                "": ["README.md", "package.json", "tsconfig.json"],
                "src/": ["index.ts"],
                "tests/": ["index.test.ts"],
            }
        elif project_type == "web":
            file_structure = {
                "": ["README.md", "index.html", "styles.css", "main.js"],
            }
        else:
            file_structure = {
                "": ["README.md"],
            }

        # Count estimated files
        estimated_files = sum(len(files) for files in file_structure.values())

        return ScaffoldPlan(
            session_id=session_id,
            project_type=project_type,
            file_structure=file_structure,
            templates=templates,
            estimated_files=estimated_files,
        )

    def generate(
        self,
        plan: ScaffoldPlan,
        output_dir: str | None = None,
    ) -> ScaffoldResult:
        """Generate scaffolding from plan synchronously."""
        start_time = time.time()
        files_created: list[str] = []
        folders_created: list[str] = []
        placeholders: dict[str, list[str]] = {}

        try:
            # Create folder structure
            for folder in plan.file_structure:
                if folder and output_dir:
                    folder_path = Path(output_dir) / folder
                    folder_path.mkdir(parents=True, exist_ok=True)
                    folders_created.append(str(folder_path))

            # Generate files
            for folder, files in plan.file_structure.items():
                for file in files:
                    file_path = f"{folder}{file}"
                    files_created.append(file_path)

                    # Check for template
                    template = plan.templates.get(file_path)
                    if template:
                        placeholders[file_path] = template.placeholders

                        if output_dir:
                            content = template.content
                            full_path = Path(output_dir) / folder / file
                            full_path.parent.mkdir(parents=True, exist_ok=True)
                            full_path.write_text(content, encoding="utf-8")

            elapsed_ms = (time.time() - start_time) * 1000

            return ScaffoldResult(
                session_id=plan.session_id,
                success=True,
                files_created=files_created,
                folders_created=folders_created,
                placeholders=placeholders,
                elapsed_time_ms=elapsed_ms,
            )

        except Exception as e:
            self.logger.exception("Scaffolding error for session %s", plan.session_id)
            elapsed_ms = (time.time() - start_time) * 1000
            return ScaffoldResult(
                session_id=plan.session_id,
                success=False,
                files_created=[],
                folders_created=[],
                placeholders={},
                elapsed_time_ms=elapsed_ms,
                error=str(e),
            )
