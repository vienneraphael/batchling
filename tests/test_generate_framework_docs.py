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
    pricing_warning = '!!! warning "Check model support and batch pricing"'
    endpoint_line = "- `/v1/responses`"
    example_heading = "Here's an example showing how to use `batchling` with OpenAI:"

    assert note_include in content
    assert pricing_warning in content
    assert content.index(pricing_warning) > content.index(endpoint_line)
    assert content.index(pricing_warning) < content.index(example_heading)
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

    assert '!!! warning "Check model support and batch pricing"' in content
    assert '--8<-- "docs/providers/_notes/openai.md"' not in content


def test_render_provider_page_always_includes_pricing_note() -> None:
    """
    Ensure the pricing note is rendered even when no example exists.

    Returns
    -------
    None
        This test asserts the default provider warning callout.
    """
    module = load_generator_module()

    provider = module.Provider(slug="unknown_provider", batchable_endpoints=("/v1/responses",))
    content = module.render_provider_page(provider=provider)

    assert '!!! warning "Check model support and batch pricing"' in content
    assert "Before sending batches, review the provider's official pricing page" in content


def test_render_provider_page_includes_output_after_example_block(tmp_path: Path) -> None:
    """
    Ensure provider output snippets are injected after the example code block.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used to stage provider outputs.

    Returns
    -------
    None
        This test asserts output snippet placement.
    """
    module = load_generator_module()
    outputs_dir = tmp_path / "_outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_file = outputs_dir / "openai.md"
    output_file.write_text(data="```text\nexpected output\n```\n", encoding="utf-8")
    module.PROVIDER_OUTPUTS_DIR = outputs_dir

    provider = module.Provider(slug="openai", batchable_endpoints=("/v1/responses",))
    content = module.render_provider_page(provider=provider)

    example_include = '--8<-- "examples/providers/openai_example.py"'
    output_label = "Output:"
    output_include = '--8<-- "docs/providers/_outputs/openai.md"'

    assert output_include in content
    assert content.index(output_label) > content.index(example_include)
    assert content.index(output_include) > content.index(output_label)


def test_render_provider_page_skips_output_when_file_is_missing(tmp_path: Path) -> None:
    """
    Ensure no output snippet is included when a provider output file does not exist.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used as provider outputs root.

    Returns
    -------
    None
        This test asserts output omission.
    """
    module = load_generator_module()
    outputs_dir = tmp_path / "_outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    module.PROVIDER_OUTPUTS_DIR = outputs_dir

    provider = module.Provider(slug="openai", batchable_endpoints=("/v1/responses",))
    content = module.render_provider_page(provider=provider)

    assert "Output:" not in content
    assert '--8<-- "docs/providers/_outputs/openai.md"' not in content


def test_render_framework_page_includes_output_after_example_block(tmp_path: Path) -> None:
    """
    Ensure framework output snippets are injected after the example code block.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used to stage framework outputs.

    Returns
    -------
    None
        This test asserts output snippet placement.
    """
    module = load_generator_module()
    outputs_dir = tmp_path / "_outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_file = outputs_dir / "langchain.md"
    output_file.write_text(data="```text\nexpected output\n```\n", encoding="utf-8")
    module.FRAMEWORK_OUTPUTS_DIR = outputs_dir

    framework = module.Framework(slug="langchain")
    content = module.render_framework_page(framework=framework)

    example_include = '--8<-- "examples/frameworks/langchain_example.py"'
    output_label = "Output:"
    output_include = '--8<-- "docs/frameworks/_outputs/langchain.md"'

    assert output_include in content
    assert content.index(output_label) > content.index(example_include)
    assert content.index(output_include) > content.index(output_label)


def test_render_framework_page_skips_output_when_file_is_missing(tmp_path: Path) -> None:
    """
    Ensure no output snippet is included when a framework output file does not exist.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory used as framework outputs root.

    Returns
    -------
    None
        This test asserts output omission.
    """
    module = load_generator_module()
    outputs_dir = tmp_path / "_outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    module.FRAMEWORK_OUTPUTS_DIR = outputs_dir

    framework = module.Framework(slug="langchain")
    content = module.render_framework_page(framework=framework)

    assert "Output:" not in content
    assert '--8<-- "docs/frameworks/_outputs/langchain.md"' not in content
