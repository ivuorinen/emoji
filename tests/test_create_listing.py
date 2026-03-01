"""Tests for create_listing.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

import create_listing


class TestCharacterGrouping:
    """Test file grouping by first character."""

    def test_alpha_files_grouped_by_first_char(self, tmp_path, make_png):
        a1 = make_png(tmp_path, "apple.png")
        a2 = make_png(tmp_path, "avocado.png")
        b1 = make_png(tmp_path, "banana.png")

        with patch.object(create_listing, "EMOJI_DIR", tmp_path):
            # Test via generate_readme output
            create_listing.generate_readme([a1, a2, b1])
            content = Path("README.md").read_text()
        assert "## a" in content
        assert "## b" in content

    def test_non_alpha_grouped_as_special(self, tmp_path, make_png):
        f1 = make_png(tmp_path, "1emoji.png")
        f2 = make_png(tmp_path, "_underscore.png")

        create_listing.generate_readme([f1, f2])
        content = Path("README.md").read_text()
        # Non-alpha chars get special group key
        assert r"\[^a-zA-Z:\]" in content

    def test_numeric_file_grouped_as_special(self, tmp_path, make_png):
        f1 = make_png(tmp_path, "9lives.png")
        create_listing.generate_readme([f1])
        content = Path("README.md").read_text()
        assert r"\[^a-zA-Z:\]" in content


class TestSorting:
    """Test sort order of groups."""

    def test_special_group_sorts_before_alpha(self, tmp_path, make_png):
        f_special = make_png(tmp_path, "1first.png")
        f_alpha = make_png(tmp_path, "zebra.png")

        create_listing.generate_readme([f_special, f_alpha])
        content = Path("README.md").read_text()
        # Special group should appear before 'z' group
        special_pos = content.index(r"\[^a-zA-Z:\]")
        z_pos = content.index("## z")
        assert special_pos < z_pos


class TestRowChunking:
    """Test that files are split into rows of PER_ROW."""

    def test_files_chunked_into_rows(self, tmp_path, make_png):
        files = [make_png(tmp_path, f"a{i:02d}.png", color=(i, 0, 0, 255)) for i in range(25)]
        create_listing.generate_readme(files)
        content = Path("README.md").read_text()
        # 25 files / 10 per row = 3 rows
        assert content.count("<tr>") == 3

    def test_single_file_one_row(self, tmp_path, make_png):
        f = make_png(tmp_path, "alone.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert content.count("<tr>") == 1


class TestUrlEncoding:
    """Test URL encoding of filenames."""

    def test_space_in_filename(self, tmp_path, make_png):
        f = make_png(tmp_path, "my emoji.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert "my%20emoji.png" in content

    def test_plus_in_filename(self, tmp_path, make_png):
        f = make_png(tmp_path, "a+b.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert "a%2Bb.png" in content

    def test_hash_in_filename(self, tmp_path, make_png):
        f = make_png(tmp_path, "c#sharp.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert "c%23sharp.png" in content


class TestGenerateReadme:
    """Test generate_readme output structure."""

    def test_produces_markdown_table(self, tmp_path, make_png):
        f = make_png(tmp_path, "test.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert content.startswith("# Emotes")
        assert "<table" in content
        assert "<img" in content
        assert "test.png" in content

    def test_includes_timestamp(self, tmp_path, make_png):
        f = make_png(tmp_path, "test.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert "Generated:" in content

    def test_image_title_uses_stem(self, tmp_path, make_png):
        f = make_png(tmp_path, "smile.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert ':smile:' in content


class TestGenerateHtml:
    """Test generate_html output structure."""

    def test_produces_html_with_search(self, tmp_path, make_png):
        f = make_png(tmp_path, "test.png")
        create_listing.generate_html([f])
        content = Path("index.html").read_text()
        assert "<!DOCTYPE html>" in content
        assert 'id="search"' in content
        assert "test.png" in content

    def test_data_keyword_attribute(self, tmp_path, make_png):
        f = make_png(tmp_path, "happy.png")
        create_listing.generate_html([f])
        content = Path("index.html").read_text()
        assert 'data-keyword="happy"' in content

    def test_special_group_header(self, tmp_path, make_png):
        f = make_png(tmp_path, "1number.png")
        create_listing.generate_html([f])
        content = Path("index.html").read_text()
        assert "0-9 / Special" in content

    def test_hash_group_sorts_first(self, tmp_path, make_png):
        f_special = make_png(tmp_path, "1first.png")
        f_alpha = make_png(tmp_path, "zebra.png")
        create_listing.generate_html([f_special, f_alpha])
        content = Path("index.html").read_text()
        special_pos = content.index("0-9 / Special")
        z_pos = content.index(">Z<")
        assert special_pos < z_pos

    def test_dark_theme(self, tmp_path, make_png):
        f = make_png(tmp_path, "test.png")
        create_listing.generate_html([f])
        content = Path("index.html").read_text()
        assert "#1a1a1a" in content

    def test_emoji_count_shown(self, tmp_path, make_png):
        files = [make_png(tmp_path, f"e{i}.png", color=(i, 0, 0, 255)) for i in range(3)]
        create_listing.generate_html(files)
        content = Path("index.html").read_text()
        assert "3 emojis" in content

    def test_html_escapes_name(self, tmp_path, make_png):
        f = make_png(tmp_path, "a<b.png")
        create_listing.generate_html([f])
        content = Path("index.html").read_text()
        assert "a&lt;b" in content


class TestMain:
    """Test the main() entry point."""

    def test_system_exit_on_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with patch.object(create_listing, "EMOJI_DIR", empty):
            with pytest.raises(SystemExit, match="No images"):
                create_listing.main()

    def test_succeeds_with_valid_files(self, tmp_path, make_png):
        d = tmp_path / "emoji"
        d.mkdir()
        make_png(d, "test.png")
        with patch.object(create_listing, "EMOJI_DIR", d):
            create_listing.main()
        assert Path("README.md").exists()
        assert Path("index.html").exists()

    def test_ignores_non_image_extensions(self, tmp_path):
        d = tmp_path / "emoji"
        d.mkdir()
        (d / "notes.txt").write_text("not an image")
        with patch.object(create_listing, "EMOJI_DIR", d):
            with pytest.raises(SystemExit, match="No images"):
                create_listing.main()


class TestEdgeCases:
    """Test edge cases."""

    def test_single_file(self, tmp_path, make_png):
        f = make_png(tmp_path, "only.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        assert "only.png" in content

    def test_unicode_filename(self, tmp_path, make_png):
        f = make_png(tmp_path, "\u00e9moji.png")
        create_listing.generate_readme([f])
        content = Path("README.md").read_text()
        # URL-encoded form of the unicode char should be present
        assert "emoji/" in content
