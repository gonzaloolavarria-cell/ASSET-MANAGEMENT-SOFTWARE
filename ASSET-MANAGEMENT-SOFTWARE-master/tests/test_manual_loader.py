"""Tests for tools/engines/manual_loader.py — equipment manual document loader."""

import json
from pathlib import Path

import pytest

from tools.engines.manual_loader import (
    ManualSection,
    _title_from_filename,
    _validate_equipment_type_id,
    build_chat_system_prompt,
    estimate_tokens,
    format_equipment_context,
    get_equipment_type_names,
    list_available_equipment_types,
    load_equipment_context,
    load_equipment_library_context,
    load_manual_files,
)


# ════════════════════════════════════════════════════════════════════════
# SECTION 1: UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════


class TestEstimateTokens:

    def test_empty_string(self):
        assert estimate_tokens("") == 1  # minimum 1

    def test_short_string(self):
        result = estimate_tokens("Hello world")
        assert result >= 1
        assert result <= 10

    def test_longer_text(self):
        text = "a" * 4000
        result = estimate_tokens(text)
        assert result == 1000  # 4000 / 4

    def test_returns_int(self):
        assert isinstance(estimate_tokens("test"), int)


class TestTitleFromFilename:

    def test_pdf_name(self):
        assert _title_from_filename(Path("maintenance-manual.pdf")) == "Maintenance Manual"

    def test_underscores(self):
        assert _title_from_filename(Path("troubleshooting_guide.txt")) == "Troubleshooting Guide"

    def test_md_extension(self):
        assert _title_from_filename(Path("sample-manual.md")) == "Sample Manual"


class TestValidateEquipmentTypeId:

    def test_valid_id(self):
        _validate_equipment_type_id("ET-SAG-MILL")  # no error

    def test_valid_alphanumeric(self):
        _validate_equipment_type_id("ET123")  # no error

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_equipment_type_id("")

    def test_path_traversal_dots(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_equipment_type_id("../etc/passwd")

    def test_path_traversal_slash(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_equipment_type_id("foo/bar")

    def test_path_traversal_backslash(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_equipment_type_id("foo\\bar")

    def test_invalid_characters(self):
        with pytest.raises(ValueError, match="must match"):
            _validate_equipment_type_id("!invalid")

    def test_starts_with_dash(self):
        with pytest.raises(ValueError, match="must match"):
            _validate_equipment_type_id("-invalid")


# ════════════════════════════════════════════════════════════════════════
# SECTION 2: EQUIPMENT LIBRARY LOADING
# ════════════════════════════════════════════════════════════════════════


class TestLoadEquipmentLibraryContext:

    def test_loads_sag_mill(self):
        sections = load_equipment_library_context("ET-SAG-MILL")
        assert len(sections) >= 1
        assert all(isinstance(s, ManualSection) for s in sections)

    def test_sag_mill_has_specifications(self):
        sections = load_equipment_library_context("ET-SAG-MILL")
        titles = [s.title for s in sections]
        assert "Technical Specifications" in titles

    def test_sag_mill_has_components(self):
        sections = load_equipment_library_context("ET-SAG-MILL")
        titles = [s.title for s in sections]
        assert "Sub-Assemblies & Components" in titles

    def test_specifications_contain_power(self):
        sections = load_equipment_library_context("ET-SAG-MILL")
        specs = next(s for s in sections if s.title == "Technical Specifications")
        assert "8500" in specs.content  # typical_power_kw

    def test_components_contain_failure_modes(self):
        sections = load_equipment_library_context("ET-SAG-MILL")
        comp_section = next(s for s in sections if "Components" in s.title)
        assert "DEGRADES" in comp_section.content or "failure" in comp_section.content.lower()

    def test_unknown_type_returns_empty(self):
        sections = load_equipment_library_context("ET-NONEXISTENT")
        assert sections == []

    def test_source_is_equipment_library(self):
        sections = load_equipment_library_context("ET-SAG-MILL")
        for s in sections:
            assert s.source == "equipment-library"

    def test_token_estimates_positive(self):
        sections = load_equipment_library_context("ET-SAG-MILL")
        for s in sections:
            assert s.token_estimate > 0


class TestGetEquipmentTypeNames:

    def test_returns_dict(self):
        names = get_equipment_type_names()
        assert isinstance(names, dict)

    def test_contains_sag_mill(self):
        names = get_equipment_type_names()
        assert "ET-SAG-MILL" in names
        assert names["ET-SAG-MILL"] == "SAG Mill"

    def test_has_15_types(self):
        names = get_equipment_type_names()
        assert len(names) == 15


# ════════════════════════════════════════════════════════════════════════
# SECTION 3: MANUAL FILE LOADING
# ════════════════════════════════════════════════════════════════════════


class TestLoadManualFiles:

    def test_loads_txt_file(self, tmp_path):
        eq_dir = tmp_path / "ET-TEST"
        eq_dir.mkdir()
        (eq_dir / "manual.txt").write_text("Test content here.", encoding="utf-8")
        sections = load_manual_files("ET-TEST", tmp_path)
        assert len(sections) == 1
        assert sections[0].content == "Test content here."
        assert sections[0].title == "Manual"

    def test_loads_md_file(self, tmp_path):
        eq_dir = tmp_path / "ET-TEST"
        eq_dir.mkdir()
        (eq_dir / "troubleshooting-guide.md").write_text("# Troubleshooting\nStep 1...", encoding="utf-8")
        sections = load_manual_files("ET-TEST", tmp_path)
        assert len(sections) == 1
        assert "Troubleshooting" in sections[0].content

    def test_loads_shared_files(self, tmp_path):
        eq_dir = tmp_path / "ET-TEST"
        eq_dir.mkdir()
        (eq_dir / "manual.txt").write_text("Equipment manual", encoding="utf-8")
        shared_dir = tmp_path / "_shared"
        shared_dir.mkdir()
        (shared_dir / "safety.txt").write_text("Safety procedures", encoding="utf-8")
        sections = load_manual_files("ET-TEST", tmp_path)
        assert len(sections) == 2
        titles = [s.title for s in sections]
        assert "[Shared] Safety" in titles

    def test_missing_directory_returns_empty(self, tmp_path):
        sections = load_manual_files("ET-NONEXISTENT", tmp_path)
        assert sections == []

    def test_missing_manuals_dir_returns_empty(self):
        sections = load_manual_files("ET-TEST", Path("/nonexistent/path"))
        assert sections == []

    def test_ignores_unsupported_extensions(self, tmp_path):
        eq_dir = tmp_path / "ET-TEST"
        eq_dir.mkdir()
        (eq_dir / "image.png").write_bytes(b"\x89PNG")
        (eq_dir / "manual.txt").write_text("Content", encoding="utf-8")
        sections = load_manual_files("ET-TEST", tmp_path)
        assert len(sections) == 1

    def test_skips_empty_files(self, tmp_path):
        eq_dir = tmp_path / "ET-TEST"
        eq_dir.mkdir()
        (eq_dir / "empty.txt").write_text("", encoding="utf-8")
        (eq_dir / "real.txt").write_text("Content", encoding="utf-8")
        sections = load_manual_files("ET-TEST", tmp_path)
        assert len(sections) == 1

    def test_source_includes_type_id(self, tmp_path):
        eq_dir = tmp_path / "ET-TEST"
        eq_dir.mkdir()
        (eq_dir / "manual.txt").write_text("Content", encoding="utf-8")
        sections = load_manual_files("ET-TEST", tmp_path)
        assert sections[0].source == "ET-TEST/manual.txt"

    def test_loads_real_sample_manual(self):
        """Load the sample SAG Mill manual from the actual data directory."""
        sections = load_manual_files("ET-SAG-MILL")
        # Should find at least the sample-manual.md
        assert len(sections) >= 1
        titles = [s.title for s in sections]
        assert any("Sample Manual" in t for t in titles)


# ════════════════════════════════════════════════════════════════════════
# SECTION 4: COMBINED CONTEXT LOADING
# ════════════════════════════════════════════════════════════════════════


class TestLoadEquipmentContext:

    def test_combines_library_and_manuals(self, tmp_path):
        eq_dir = tmp_path / "ET-SAG-MILL"
        eq_dir.mkdir()
        (eq_dir / "extra.txt").write_text("Extra info", encoding="utf-8")
        sections = load_equipment_context("ET-SAG-MILL", tmp_path)
        sources = [s.source for s in sections]
        assert "equipment-library" in sources
        assert "ET-SAG-MILL/extra.txt" in sources

    def test_library_only_when_no_manuals(self):
        sections = load_equipment_context("ET-SAG-MILL", Path("/nonexistent"))
        assert len(sections) >= 1
        assert all(s.source == "equipment-library" for s in sections)

    def test_truncation_respects_max_tokens(self, tmp_path):
        eq_dir = tmp_path / "ET-SAG-MILL"
        eq_dir.mkdir()
        # Create a file with ~10K tokens (40K chars)
        (eq_dir / "huge.txt").write_text("x" * 40000, encoding="utf-8")
        sections = load_equipment_context("ET-SAG-MILL", tmp_path, max_tokens=5000)
        total = sum(s.token_estimate for s in sections)
        assert total <= 5000


# ════════════════════════════════════════════════════════════════════════
# SECTION 5: FORMATTING
# ════════════════════════════════════════════════════════════════════════


class TestFormatEquipmentContext:

    def test_wraps_in_tags(self):
        sections = [ManualSection("test.txt", "Test Section", "Content here", 10)]
        result = format_equipment_context(sections)
        assert result.startswith("<equipment_manual>")
        assert result.endswith("</equipment_manual>")

    def test_includes_source_comment(self):
        sections = [ManualSection("test.txt", "Test", "Content", 10)]
        result = format_equipment_context(sections)
        assert "<!-- source: test.txt -->" in result

    def test_includes_title_as_heading(self):
        sections = [ManualSection("test.txt", "My Title", "Content", 10)]
        result = format_equipment_context(sections)
        assert "## My Title" in result

    def test_empty_sections_return_empty_string(self):
        assert format_equipment_context([]) == ""

    def test_multiple_sections(self):
        sections = [
            ManualSection("a.txt", "Section A", "Content A", 10),
            ManualSection("b.txt", "Section B", "Content B", 10),
        ]
        result = format_equipment_context(sections)
        assert "Section A" in result
        assert "Section B" in result


# ════════════════════════════════════════════════════════════════════════
# SECTION 6: AVAILABLE TYPES LISTING
# ════════════════════════════════════════════════════════════════════════


class TestListAvailableEquipmentTypes:

    def test_lists_directories(self, tmp_path):
        (tmp_path / "ET-SAG-MILL").mkdir()
        (tmp_path / "ET-BALL-MILL").mkdir()
        (tmp_path / "_shared").mkdir()
        result = list_available_equipment_types(tmp_path)
        assert result == ["ET-BALL-MILL", "ET-SAG-MILL"]

    def test_excludes_shared_and_hidden(self, tmp_path):
        (tmp_path / "ET-PUMP").mkdir()
        (tmp_path / "_shared").mkdir()
        (tmp_path / ".hidden").mkdir()
        result = list_available_equipment_types(tmp_path)
        assert result == ["ET-PUMP"]

    def test_missing_dir_returns_empty(self):
        result = list_available_equipment_types(Path("/nonexistent"))
        assert result == []

    def test_real_manuals_dir(self):
        """Check the actual data/manuals directory has ET-SAG-MILL."""
        result = list_available_equipment_types()
        assert "ET-SAG-MILL" in result


# ════════════════════════════════════════════════════════════════════════
# SECTION 7: SYSTEM PROMPT BUILDING
# ════════════════════════════════════════════════════════════════════════


class TestBuildChatSystemPrompt:

    def test_returns_list_of_dicts(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL")
        assert isinstance(blocks, list)
        assert all(isinstance(b, dict) for b in blocks)

    def test_has_three_blocks(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL")
        assert len(blocks) == 3

    def test_all_blocks_have_type_text(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL")
        for b in blocks:
            assert b["type"] == "text"

    def test_base_instructions_block(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL")
        base = blocks[0]
        assert "equipment manual assistant" in base["text"].lower()
        assert "cache_control" not in base  # base is NOT cached

    def test_context_block_has_cache_control(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL")
        context = blocks[1]
        assert "cache_control" in context
        assert context["cache_control"] == {"type": "ephemeral"}

    def test_context_block_has_equipment_manual_tags(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL")
        context = blocks[1]
        assert "<equipment_manual>" in context["text"]

    def test_session_block_has_date(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL")
        session = blocks[2]
        assert "Date:" in session["text"]

    def test_session_block_includes_tag_when_provided(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL", equipment_tag="BRY-SAG-ML-001")
        session = blocks[2]
        assert "BRY-SAG-ML-001" in session["text"]

    def test_session_block_notes_no_manuals(self):
        blocks = build_chat_system_prompt("ET-SAG-MILL", manuals_dir=Path("/nonexistent"))
        session = blocks[-1]
        assert "No manual files found" in session["text"]

    def test_unknown_type_still_returns_blocks(self):
        """Even with unknown type, should return at least base + session blocks."""
        blocks = build_chat_system_prompt("ET-NONEXISTENT", manuals_dir=Path("/nonexistent"))
        assert len(blocks) >= 2
        # The base instructions should still be present
        assert "equipment manual assistant" in blocks[0]["text"].lower()
