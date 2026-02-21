#!/usr/bin/env python3
"""Generate framework documentation pages from example files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples" / "frameworks"
DOCS_ROOT = REPO_ROOT / "docs"
FRAMEWORKS_DIR = DOCS_ROOT / "frameworks"
FRAMEWORKS_INDEX = DOCS_ROOT / "frameworks.md"
EXAMPLE_SUFFIX = "_example.py"
GITHUB_EXAMPLES_BASE_URL = (
    "https://github.com/vienneraphael/batchling/blob/main/examples/frameworks"
)


@dataclass(frozen=True)
class Framework:
    """A framework discovered from examples."""

    slug: str

    @property
    def display_name(self) -> str:
        """Return a human-friendly framework name."""
        words = self.slug.split(sep="_")
        normalized_words: list[str] = []

        for word in words:
            if word.lower() == "ai":
                normalized_words.append("AI")
                continue

            normalized_words.append(word.capitalize())

        return " ".join(normalized_words)

    @property
    def example_filename(self) -> str:
        """Return the framework example filename."""
        return f"{self.slug}{EXAMPLE_SUFFIX}"


def discover_frameworks() -> list[Framework]:
    """Discover tested frameworks from example filenames.

    Returns
    -------
    list[Framework]
        Frameworks extracted from files matching ``*_example.py``.
    """
    if not EXAMPLES_DIR.exists():
        return []

    frameworks: list[Framework] = []

    for path in sorted(EXAMPLES_DIR.glob(pattern=f"*{EXAMPLE_SUFFIX}")):
        slug = path.name[: -len(EXAMPLE_SUFFIX)]
        frameworks.append(Framework(slug=slug))

    return frameworks


def render_framework_page(*, framework: Framework) -> str:
    """Render a framework detail page.

    Parameters
    ----------
    framework : Framework
        Framework metadata used to render the page.

    Returns
    -------
    str
        Markdown content for the framework page.
    """
    example_url = f"{GITHUB_EXAMPLES_BASE_URL}/{framework.example_filename}"
    return (
        f"# {framework.display_name}\n\n"
        f"`batchling` was tested with {framework.display_name} using this example:\n\n"
        f"- [{framework.example_filename}]({example_url})\n"
    )


def render_frameworks_index(*, frameworks: list[Framework]) -> str:
    """Render the frameworks index page.

    Parameters
    ----------
    frameworks : list[Framework]
        Frameworks to list.

    Returns
    -------
    str
        Markdown content for ``docs/frameworks.md``.
    """
    lines = [
        "# Frameworks",
        "",
        "Since it operates at the network level by intercepting select async GenAI requests, "
        "`batchling` is natively compatible with all frameworks using `httpx` or `aiohttp` as "
        "their async request engine.",
        "",
        "Below are the frameworks tested in `examples/frameworks`:",
        "",
    ]

    for framework in frameworks:
        lines.append(f"- [{framework.display_name}](frameworks/{framework.slug}.md)")

    lines.append("")
    return "\n".join(lines)


def write_text(*, path: Path, content: str) -> None:
    """Write content to a file, creating parent directories when needed.

    Parameters
    ----------
    path : Path
        File path to write.
    content : str
        Text content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def clean_stale_framework_pages(*, frameworks: list[Framework]) -> None:
    """Delete generated framework pages that no longer have an example.

    Parameters
    ----------
    frameworks : list[Framework]
        Current framework set used to preserve expected pages.
    """
    expected_paths = {FRAMEWORKS_DIR / f"{framework.slug}.md" for framework in frameworks}

    if not FRAMEWORKS_DIR.exists():
        return

    for path in FRAMEWORKS_DIR.glob(pattern="*.md"):
        if path in expected_paths:
            continue

        path.unlink()


def generate_docs() -> None:
    """Generate framework docs from available framework examples."""
    frameworks = discover_frameworks()
    write_text(path=FRAMEWORKS_INDEX, content=render_frameworks_index(frameworks=frameworks))

    for framework in frameworks:
        page_path = FRAMEWORKS_DIR / f"{framework.slug}.md"
        page_content = render_framework_page(framework=framework)
        write_text(path=page_path, content=page_content)

    clean_stale_framework_pages(frameworks=frameworks)


if __name__ == "__main__":
    generate_docs()
