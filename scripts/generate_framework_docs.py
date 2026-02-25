#!/usr/bin/env python3
"""Generate framework and provider documentation pages from source files."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
FRAMEWORK_EXAMPLES_DIR = REPO_ROOT / "examples" / "frameworks"
FRAMEWORKS_DIR = DOCS_ROOT / "frameworks"
FRAMEWORK_OUTPUTS_DIR = FRAMEWORKS_DIR / "_outputs"
FRAMEWORKS_INDEX = DOCS_ROOT / "frameworks.md"
PROVIDERS_SOURCE_DIR = REPO_ROOT / "src" / "batchling" / "providers"
PROVIDER_EXAMPLES_DIR = REPO_ROOT / "examples" / "providers"
PROVIDERS_DIR = DOCS_ROOT / "providers"
PROVIDER_NOTES_DIR = PROVIDERS_DIR / "_notes"
PROVIDER_OUTPUTS_DIR = PROVIDERS_DIR / "_outputs"
PROVIDERS_INDEX = DOCS_ROOT / "providers.md"
MKDOCS_CONFIG = REPO_ROOT / "mkdocs.yml"
EXAMPLE_SUFFIX = "_example.py"
NAV_GENERATED_INDENT = "      "
AUTO_FRAMEWORK_NAV_BEGIN = f"{NAV_GENERATED_INDENT}# BEGIN AUTO-GENERATED FRAMEWORK NAV"
AUTO_FRAMEWORK_NAV_END = f"{NAV_GENERATED_INDENT}# END AUTO-GENERATED FRAMEWORK NAV"
AUTO_PROVIDER_NAV_BEGIN = f"{NAV_GENERATED_INDENT}# BEGIN AUTO-GENERATED PROVIDER NAV"
AUTO_PROVIDER_NAV_END = f"{NAV_GENERATED_INDENT}# END AUTO-GENERATED PROVIDER NAV"
PROVIDER_SKIP_FILES = {"__init__.py", "base.py"}
DISPLAY_NAME_OVERRIDES = {
    "langchain": "LangChain",
    "openai": "OpenAI",
    "litellm": "LiteLLM",
    "xai": "XAI",
}
PROVIDER_PRICING_NOTE_TITLE = "Check model support and batch pricing"
PROVIDER_PRICING_NOTE_BODY = (
    "Before sending batches, review the provider's official pricing page for supported "
    "models and batch pricing details."
)
PROVIDER_API_KEY_NOTE_TITLE = "API key required"  # pragma: allowlist secret
PROVIDER_API_KEY_NOTE_BODY = (
    "Set `{api_key_env_var}` in `.env` or ensure it is already loaded in your "
    "environment variables before running batches."
)


@dataclass(frozen=True)
class Framework:
    """A framework discovered from examples."""

    slug: str

    @property
    def display_name(self) -> str:
        """Return a human-friendly framework name."""
        override = DISPLAY_NAME_OVERRIDES.get(self.slug)
        if override is not None:
            return override

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

    @property
    def output_filename(self) -> str:
        """Return the framework output filename."""
        return f"{self.slug}.md"

    @property
    def output_path(self) -> Path:
        """Return the framework output file path."""
        return FRAMEWORK_OUTPUTS_DIR / self.output_filename

    @property
    def has_output(self) -> bool:
        """Return whether a framework output file exists."""
        return self.output_path.exists()

    @property
    def output_snippet_path(self) -> str:
        """Return the snippet include path for framework output."""
        return f"docs/frameworks/_outputs/{self.output_filename}"


@dataclass(frozen=True)
class Provider:
    """A provider discovered from provider modules."""

    slug: str
    batchable_endpoints: tuple[str, ...]

    @property
    def display_name(self) -> str:
        """Return a human-friendly provider name."""
        override = DISPLAY_NAME_OVERRIDES.get(self.slug)
        if override is not None:
            return override

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
        """Return the provider example filename."""
        return f"{self.slug}{EXAMPLE_SUFFIX}"

    @property
    def has_example(self) -> bool:
        """Return whether a provider example file exists."""
        example_path = PROVIDER_EXAMPLES_DIR / self.example_filename
        return example_path.exists()

    @property
    def notes_filename(self) -> str:
        """Return the provider notes filename."""
        return f"{self.slug}.md"

    @property
    def notes_path(self) -> Path:
        """Return the provider notes file path."""
        return PROVIDER_NOTES_DIR / self.notes_filename

    @property
    def has_notes(self) -> bool:
        """Return whether a provider notes file exists."""
        return self.notes_path.exists()

    @property
    def notes_snippet_path(self) -> str:
        """Return the snippet include path for provider notes."""
        return f"docs/providers/_notes/{self.notes_filename}"

    @property
    def output_filename(self) -> str:
        """Return the provider output filename."""
        return f"{self.slug}.md"

    @property
    def output_path(self) -> Path:
        """Return the provider output file path."""
        return PROVIDER_OUTPUTS_DIR / self.output_filename

    @property
    def has_output(self) -> bool:
        """Return whether a provider output file exists."""
        return self.output_path.exists()

    @property
    def output_snippet_path(self) -> str:
        """Return the snippet include path for provider output."""
        return f"docs/providers/_outputs/{self.output_filename}"

    @property
    def api_key_env_var(self) -> str:
        """Return the provider API key environment variable name."""
        return f"{self.slug.upper()}_API_KEY"


def discover_frameworks() -> list[Framework]:
    """Discover tested frameworks from example filenames.

    Returns
    -------
    list[Framework]
        Frameworks extracted from files matching ``*_example.py``.
    """
    if not FRAMEWORK_EXAMPLES_DIR.exists():
        return []

    frameworks: list[Framework] = []

    for path in sorted(FRAMEWORK_EXAMPLES_DIR.glob(pattern=f"*{EXAMPLE_SUFFIX}")):
        slug = path.name[: -len(EXAMPLE_SUFFIX)]
        frameworks.append(Framework(slug=slug))

    return frameworks


def extract_batchable_endpoints(*, provider_file: Path) -> tuple[str, ...]:
    """Extract ``batchable_endpoints`` from a provider module.

    Parameters
    ----------
    provider_file : Path
        Provider module path.

    Returns
    -------
    tuple[str, ...]
        Declared batchable endpoints, or an empty tuple when unavailable.
    """
    tree = ast.parse(provider_file.read_text(encoding="utf-8"))

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        for class_node in node.body:
            if isinstance(class_node, ast.Assign):
                targets = [
                    target.id for target in class_node.targets if isinstance(target, ast.Name)
                ]
                if "batchable_endpoints" not in targets:
                    continue
                return _extract_string_sequence(node=class_node.value)

            if isinstance(class_node, ast.AnnAssign):
                if not isinstance(class_node.target, ast.Name):
                    continue
                if class_node.target.id != "batchable_endpoints" or class_node.value is None:
                    continue
                return _extract_string_sequence(node=class_node.value)

    return ()


def _extract_string_sequence(*, node: ast.AST) -> tuple[str, ...]:
    """Extract a tuple of strings from an AST tuple/list literal.

    Parameters
    ----------
    node : ast.AST
        AST node to inspect.

    Returns
    -------
    tuple[str, ...]
        Extracted string values.
    """
    if not isinstance(node, ast.Tuple | ast.List):
        return ()

    values: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant):
            continue
        if not isinstance(element.value, str):
            continue
        values.append(element.value)

    return tuple(values)


def discover_providers() -> list[Provider]:
    """Discover providers from provider modules.

    Returns
    -------
    list[Provider]
        Providers found in ``src/batchling/providers``.
    """
    providers: list[Provider] = []

    for path in sorted(PROVIDERS_SOURCE_DIR.glob(pattern="*.py")):
        if path.name in PROVIDER_SKIP_FILES:
            continue

        slug = path.stem
        endpoints = extract_batchable_endpoints(provider_file=path)
        providers.append(Provider(slug=slug, batchable_endpoints=endpoints))

    return providers


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
    lines = [
        f"# {framework.display_name}",
        "",
        f"Here's an example showing how to use `batchling` with {framework.display_name}:",
        "",
        "```python",
        f'--8<-- "examples/frameworks/{framework.example_filename}"',
        "```",
    ]

    if framework.has_output:
        lines.extend(["", "Output:", "", f'--8<-- "{framework.output_snippet_path}"'])

    lines.append("")
    return "\n".join(lines)


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
        "Below are the frameworks we tested that we are sure are compatible with `batchling`, along with examples of how to use `batchling` with them:",
        "",
    ]

    for framework in frameworks:
        lines.append(f"- [{framework.display_name}](frameworks/{framework.slug}.md)")

    lines.append("")
    return "\n".join(lines)


def render_provider_page(*, provider: Provider) -> str:
    """Render a provider detail page.

    Parameters
    ----------
    provider : Provider
        Provider metadata used to render the page.

    Returns
    -------
    str
        Markdown content for the provider page.
    """
    lines = [
        f"# {provider.display_name}",
        "",
        f"`batchling` is compatible with {provider.display_name} through any [supported framework](../frameworks.md){{ data-preview }}",
        "",
        f"The following endpoints are made batch-compatible by {provider.display_name}:",
        "",
    ]

    if provider.batchable_endpoints:
        for endpoint in provider.batchable_endpoints:
            lines.append(f"- `{endpoint}`")
    else:
        lines.append("- _No declared `batchable_endpoints` found in the provider file._")

    lines.extend(
        [
            "",
            f'!!! warning "{PROVIDER_PRICING_NOTE_TITLE}"',
            f"    {PROVIDER_PRICING_NOTE_BODY}",
        ]
    )

    if provider.has_notes:
        lines.extend(["", f'--8<-- "{provider.notes_snippet_path}"'])

    if provider.has_example:
        lines.extend(
            [
                "",
                "## Example Usage",
                "",
                f'!!! note "{PROVIDER_API_KEY_NOTE_TITLE}"',
                f"    {PROVIDER_API_KEY_NOTE_BODY.format(api_key_env_var=provider.api_key_env_var)}",
                "",
                f"Here's an example showing how to use `batchling` with {provider.display_name}:",
                "",
            ]
        )
        lines.extend(
            [
                "```python",
                f'--8<-- "examples/providers/{provider.example_filename}"',
                "```",
            ]
        )
        if provider.has_output:
            lines.extend(
                [
                    "",
                    "Output:",
                    "",
                    f'--8<-- "{provider.output_snippet_path}"',
                ]
            )

    lines.append("")
    return "\n".join(lines)


def render_providers_index(*, providers: list[Provider]) -> str:
    """Render the providers index page.

    Parameters
    ----------
    providers : list[Provider]
        Providers to list.

    Returns
    -------
    str
        Markdown content for ``docs/providers.md``.
    """
    lines = [
        "# Providers",
        "",
        "`batchling` is compatible with most providers exposing a Batch API.",
        "",
        "The following providers are supported by `batchling`:",
        "",
    ]

    for provider in providers:
        lines.append(f"- [{provider.display_name}](providers/{provider.slug}.md)")

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


def render_mkdocs_framework_nav(*, frameworks: list[Framework]) -> list[str]:
    """Render generated framework nav entries for ``mkdocs.yml``.

    Parameters
    ----------
    frameworks : list[Framework]
        Frameworks to include under the Frameworks nav section.

    Returns
    -------
    list[str]
        YAML lines including line endings.
    """
    return [
        f"{NAV_GENERATED_INDENT}- {framework.display_name}: frameworks/{framework.slug}.md\n"
        for framework in frameworks
    ]


def render_mkdocs_provider_nav(*, providers: list[Provider]) -> list[str]:
    """Render generated provider nav entries for ``mkdocs.yml``.

    Parameters
    ----------
    providers : list[Provider]
        Providers to include under the Providers nav section.

    Returns
    -------
    list[str]
        YAML lines including line endings.
    """
    return [
        f"{NAV_GENERATED_INDENT}- {provider.display_name}: providers/{provider.slug}.md\n"
        for provider in providers
    ]


def update_mkdocs_nav_block(
    *, begin_marker: str, end_marker: str, replacement_lines: list[str]
) -> None:
    """Update an auto-generated nav subsection in ``mkdocs.yml``.

    Parameters
    ----------
    begin_marker : str
        Start marker line.
    end_marker : str
        End marker line.
    replacement_lines : list[str]
        Generated YAML lines to inject between markers.

    Raises
    ------
    ValueError
        If generation markers are missing or invalid in ``mkdocs.yml``.
    """
    lines = MKDOCS_CONFIG.read_text(encoding="utf-8").splitlines(keepends=True)
    begin_index: int | None = None
    end_index: int | None = None

    for index, line in enumerate(lines):
        if line.rstrip("\n") == begin_marker:
            begin_index = index
        if line.rstrip("\n") == end_marker:
            end_index = index

    if begin_index is None or end_index is None or begin_index >= end_index:
        raise ValueError("Could not find valid auto-generated nav markers in mkdocs.yml.")

    updated_lines = lines[: begin_index + 1] + replacement_lines + lines[end_index:]
    MKDOCS_CONFIG.write_text("".join(updated_lines), encoding="utf-8")


def update_mkdocs_nav(*, frameworks: list[Framework], providers: list[Provider]) -> None:
    """Update auto-generated framework and provider nav entries in ``mkdocs.yml``.

    Parameters
    ----------
    frameworks : list[Framework]
        Frameworks to include in the generated nav subsection.
    providers : list[Provider]
        Providers to include in the generated nav subsection.
    """
    update_mkdocs_nav_block(
        begin_marker=AUTO_FRAMEWORK_NAV_BEGIN,
        end_marker=AUTO_FRAMEWORK_NAV_END,
        replacement_lines=render_mkdocs_framework_nav(frameworks=frameworks),
    )
    update_mkdocs_nav_block(
        begin_marker=AUTO_PROVIDER_NAV_BEGIN,
        end_marker=AUTO_PROVIDER_NAV_END,
        replacement_lines=render_mkdocs_provider_nav(providers=providers),
    )


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


def clean_stale_provider_pages(*, providers: list[Provider]) -> None:
    """Delete generated provider pages that no longer have a provider source file.

    Parameters
    ----------
    providers : list[Provider]
        Current provider set used to preserve expected pages.
    """
    expected_paths = {PROVIDERS_DIR / f"{provider.slug}.md" for provider in providers}

    if not PROVIDERS_DIR.exists():
        return

    for path in PROVIDERS_DIR.glob(pattern="*.md"):
        if path in expected_paths:
            continue

        path.unlink()


def generate_docs() -> None:
    """Generate framework and provider docs from source files."""
    frameworks = discover_frameworks()
    providers = discover_providers()

    write_text(path=FRAMEWORKS_INDEX, content=render_frameworks_index(frameworks=frameworks))
    write_text(path=PROVIDERS_INDEX, content=render_providers_index(providers=providers))

    for framework in frameworks:
        page_path = FRAMEWORKS_DIR / f"{framework.slug}.md"
        page_content = render_framework_page(framework=framework)
        write_text(path=page_path, content=page_content)

    for provider in providers:
        page_path = PROVIDERS_DIR / f"{provider.slug}.md"
        page_content = render_provider_page(provider=provider)
        write_text(path=page_path, content=page_content)

    clean_stale_framework_pages(frameworks=frameworks)
    clean_stale_provider_pages(providers=providers)
    update_mkdocs_nav(frameworks=frameworks, providers=providers)


if __name__ == "__main__":
    generate_docs()
