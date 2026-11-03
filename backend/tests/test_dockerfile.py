"""Tests for the root Dockerfile and .dockerignore.

Verifies multi-stage layout, UID, port, no :latest pin, contract copy,
and .dockerignore contents — exactly what docs/deployment.md §image
and SPEC 9.1 describe.
"""

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"


@pytest.fixture()
def dockerfile_text() -> str:
    return DOCKERFILE.read_text()


@pytest.fixture()
def dockerignore_text() -> str:
    return DOCKERIGNORE.read_text()


class TestDockerfile:
    """Assert Dockerfile properties."""

    def test_multi_stage(self, dockerfile_text: str) -> None:
        FROM_COUNT = dockerfile_text.count("FROM ")
        assert FROM_COUNT >= 2, "Dockerfile must use multi-stage build"

    def test_user_10001(self, dockerfile_text: str) -> None:
        assert "USER 10001" in dockerfile_text

    def test_expose_8000(self, dockerfile_text: str) -> None:
        assert "EXPOSE 8000" in dockerfile_text

    def test_no_latest_tag(self, dockerfile_text: str) -> None:
        lines = dockerfile_text.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("FROM "):
                parts = stripped.split()
                # Handle: FROM image:tag, FROM image AS name, FROM image:tag AS name
                image_ref = parts[1]
                assert ":latest" not in image_ref, (
                    f"All FROM images must pin a specific tag; found :latest in {image_ref}"
                )

    def test_contract_copied(self, dockerfile_text: str) -> None:
        assert "COPY contract /contract" in dockerfile_text

    def test_uv_sync_in_builder(self, dockerfile_text: str) -> None:
        assert "uv sync --frozen" in dockerfile_text

    def test_workdir_app(self, dockerfile_text: str) -> None:
        assert "WORKDIR /app" in dockerfile_text

    def test_python_env_vars(self, dockerfile_text: str) -> None:
        assert "PYTHONDONTWRITEBYTECODE=1" in dockerfile_text
        assert "PYTHONUNBUFFERED=1" in dockerfile_text

    def test_path_venv(self, dockerfile_text: str) -> None:
        assert "/app/.venv/bin" in dockerfile_text

    def test_base_image_slim(self, dockerfile_text: str) -> None:
        """Runtime stage must be a python:3.11-slim variant."""
        lines = dockerfile_text.splitlines()
        for i, line in enumerate(lines):
            if "AS builder" in line:
                # The line after this is probably empty, find next non-empty
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line.startswith("FROM ") and "AS" not in next_line:
                        image = next_line.split()[1]
                        assert "python:" in image and "slim" in image
                        break
                break


class TestDockerignore:
    """Assert .dockerignore contents."""

    def _patterns(self, text: str) -> set[str]:
        return {
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

    def test_excludes_git(self, dockerignore_text: str) -> None:
        patterns = self._patterns(dockerignore_text)
        assert ".git" in patterns

    def test_excludes_agent(self, dockerignore_text: str) -> None:
        patterns = self._patterns(dockerignore_text)
        assert ".agent" in patterns

    def test_excludes_venv(self, dockerignore_text: str) -> None:
        patterns = self._patterns(dockerignore_text)
        assert ".venv" in patterns

    def test_excludes_tests(self, dockerignore_text: str) -> None:
        patterns = self._patterns(dockerignore_text)
        assert "tests" in patterns
