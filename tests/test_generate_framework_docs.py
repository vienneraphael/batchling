"""Tests for scripts/generate_framework_docs.py."""

import importlib.util
import sys
import typing as t
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_framework_docs.py"


def load_generator_module() -> t.Any:
    """
    Load ``scripts/generate_framework_docs.py`` as an importable module.

    Returns
    -------
    Any
        Loaded module instance.
    """
    spec = importlib.util.spec_from_file_location(
        name="generate_framework_docs",
        location=SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec=spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module=module)
    return module


def test_render_provider_page_includes_notes_after_endpoints(tmp_path: Path) -> None:
    """
    Ensure provider notes are injected after the endpoint list.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used to stage provider notes.

    Returns
    -------
    None
        This test asserts generated markdown layout.
    """
    module = load_generator_module()
    notes_dir = tmp_path / "_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_file = notes_dir / "openai.md"
    note_file.write_text(data="Use this provider with explicit model names.\n", encoding="utf-8")
    module.PROVIDER_NOTES_DIR = notes_dir

    provider = module.Provider(slug="openai", batchable_endpoints=("/v1/responses",))
    content = module.render_provider_page(provider=provider)

    note_include = '--8<-- "docs/providers/_notes/openai.md"'
    endpoint_line = "- `/v1/responses`"
    example_heading = "Here's an example showing how to use `batchling` with OpenAI:"

    assert note_include in content
    assert content.index(note_include) > content.index(endpoint_line)
    assert content.index(note_include) < content.index(example_heading)


def test_render_provider_page_skips_notes_when_file_is_missing(tmp_path: Path) -> None:
    """
    Ensure no notes snippet is included when a provider note file does not exist.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used as provider notes root.

    Returns
    -------
    None
        This test asserts note omission.
    """
    module = load_generator_module()
    notes_dir = tmp_path / "_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    module.PROVIDER_NOTES_DIR = notes_dir

    provider = module.Provider(slug="openai", batchable_endpoints=("/v1/responses",))
    content = module.render_provider_page(provider=provider)

    assert '--8<-- "docs/providers/_notes/openai.md"' not in content
