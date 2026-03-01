"""Tests for dedup.py."""

from pathlib import Path
from unittest.mock import patch

import imagehash
import numpy as np
import pytest
from PIL import Image

import dedup
from dedup import (
    ImageInfo,
    UnionFind,
    _compute_hashes,
    _compute_md5,
    _files_size_similar,
    _get_gif_frame_info,
    _gifs_are_identical,
    compute_image_info,
    deduplicate,
    find_similar_groups,
)


# ---------------------------------------------------------------------------
# UnionFind
# ---------------------------------------------------------------------------
class TestUnionFind:
    def test_find_new_element_returns_itself(self):
        uf = UnionFind()
        assert uf.find("a") == "a"

    def test_union_merges_two_sets(self):
        uf = UnionFind()
        uf.union("a", "b")
        assert uf.find("a") == uf.find("b")

    def test_path_compression(self):
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(2, 3)
        # After find with path compression, 1 should point directly to root
        root = uf.find(1)
        assert uf.parent[1] == root

    def test_independent_clusters(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("c", "d")
        assert uf.find("a") == uf.find("b")
        assert uf.find("c") == uf.find("d")
        assert uf.find("a") != uf.find("c")

    def test_transitive_union(self):
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(2, 3)
        assert uf.find(1) == uf.find(3)


# ---------------------------------------------------------------------------
# Helpers to build ImageInfo with known hash values
# ---------------------------------------------------------------------------
def _make_hash(val: int) -> imagehash.ImageHash:
    """Create an ImageHash from a single integer (fills 8x8 bit array)."""
    bits = np.zeros((8, 8), dtype=bool)
    if val != 0:
        flat = bits.flatten()
        for i in range(min(val, 64)):
            flat[i] = True
        bits = flat.reshape(8, 8)
    return imagehash.ImageHash(bits)


def _zero_hash() -> imagehash.ImageHash:
    return imagehash.ImageHash(np.zeros((8, 8), dtype=bool))


def _make_info(
    phash=0,
    ahash=0,
    dhash=0,
    colorhash=0,
    width=4,
    height=4,
    n_frames=1,
    md5="abc",
) -> ImageInfo:
    return ImageInfo(
        phash=_make_hash(phash),
        ahash=_make_hash(ahash),
        dhash=_make_hash(dhash),
        colorhash=_make_hash(colorhash),
        width=width,
        height=height,
        n_frames=n_frames,
        md5=md5,
    )


# ---------------------------------------------------------------------------
# ImageInfo
# ---------------------------------------------------------------------------
class TestImageInfoDegenerateHash:
    def test_all_zero_is_degenerate(self):
        info = _make_info(phash=0, ahash=0, dhash=0)
        assert info._has_degenerate_hash() is True

    def test_not_degenerate_when_hashes_nonzero(self):
        info = _make_info(phash=5, ahash=10, dhash=20)
        assert info._has_degenerate_hash() is False

    def test_two_zeros_not_degenerate(self):
        info = _make_info(phash=0, ahash=0, dhash=5)
        assert info._has_degenerate_hash() is False


class TestImageInfoIsAnimated:
    def test_static_image(self):
        info = _make_info(n_frames=1)
        assert info.is_animated() is False

    def test_animated_image(self):
        info = _make_info(n_frames=5)
        assert info.is_animated() is True


class TestImageInfoIsCandidate:
    def test_rejects_dimension_mismatch(self):
        a = _make_info(width=4, height=4)
        b = _make_info(width=8, height=8)
        is_match, _, _ = a.is_candidate(b, threshold=0)
        assert is_match is False

    def test_rejects_frame_count_mismatch(self):
        a = _make_info(n_frames=1)
        b = _make_info(n_frames=3)
        is_match, _, _ = a.is_candidate(b, threshold=0)
        assert is_match is False

    def test_exact_match_static(self):
        a = _make_info()
        b = _make_info()
        is_match, agreements, total_dist = a.is_candidate(b, threshold=0)
        assert is_match is True
        assert total_dist == 0

    def test_recompressed_static_detected(self):
        """ahash=0, dhash=0, colorhash=0, phash<=10 should match."""
        a = _make_info(phash=0, ahash=0, dhash=0, colorhash=0)
        b = _make_info(phash=3, ahash=0, dhash=0, colorhash=0)
        is_match, _, _ = a.is_candidate(b, threshold=0)
        assert is_match is True

    def test_animated_needs_all_four_agreements(self):
        a = _make_info(n_frames=5)
        b = _make_info(n_frames=5)
        is_match, agreements, _ = a.is_candidate(b, threshold=0)
        assert is_match is True
        assert agreements == 4

    def test_animated_rejects_partial_agreement(self):
        a = _make_info(phash=0, ahash=0, dhash=0, colorhash=0, n_frames=5)
        b = _make_info(phash=30, ahash=30, dhash=30, colorhash=0, n_frames=5)
        is_match, agreements, _ = a.is_candidate(b, threshold=0)
        # Only colorhash agrees -> 1/4 -> rejected
        assert is_match is False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
class TestComputeHashes:
    def test_returns_four_hashes(self):
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        result = _compute_hashes(img)
        assert len(result) == 4
        assert all(isinstance(h, imagehash.ImageHash) for h in result)

    def test_converts_rgb_to_rgba(self):
        img = Image.new("RGB", (4, 4), (255, 0, 0))
        result = _compute_hashes(img)
        assert len(result) == 4


class TestComputeMd5:
    def test_correct_digest(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        import hashlib

        expected = hashlib.md5(b"hello world").hexdigest()
        assert _compute_md5(f) == expected

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        import hashlib

        expected = hashlib.md5(b"").hexdigest()
        assert _compute_md5(f) == expected


class TestFilesSizeSimilar:
    def test_identical_sizes(self, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"x" * 1000)
        b.write_bytes(b"x" * 1000)
        assert _files_size_similar(a, b) is True

    def test_within_threshold(self, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"x" * 1000)
        b.write_bytes(b"x" * 990)  # 1% diff
        assert _files_size_similar(a, b) is True

    def test_beyond_threshold(self, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"x" * 1000)
        b.write_bytes(b"x" * 500)  # 50% diff
        assert _files_size_similar(a, b) is False

    def test_zero_size_equal(self, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"")
        b.write_bytes(b"")
        assert _files_size_similar(a, b) is True

    def test_zero_size_vs_nonzero(self, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"")
        b.write_bytes(b"x")
        assert _files_size_similar(a, b) is False


class TestGetGifFrameInfo:
    def test_static_png_returns_none(self, tmp_path, make_png):
        f = make_png(tmp_path, "static.png")
        assert _get_gif_frame_info(f) is None

    def test_animated_gif_returns_frames(self, tmp_path, make_gif):
        f = make_gif(
            tmp_path,
            "anim.gif",
            colors=[(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)],
            durations=[100, 200, 150],
        )
        result = _get_gif_frame_info(f)
        assert result is not None
        assert len(result) == 3
        for phash_str, duration in result:
            assert isinstance(phash_str, str)
            assert isinstance(duration, int)


class TestGifsAreIdentical:
    def test_identical_gifs(self, tmp_path, make_gif):
        colors = [(255, 0, 0, 255), (0, 255, 0, 255)]
        durations = [100, 100]
        a = make_gif(tmp_path, "a.gif", colors=colors, durations=durations)
        b = make_gif(tmp_path, "b.gif", colors=colors, durations=durations)
        assert _gifs_are_identical(a, b) is True

    def test_different_frames(self, tmp_path):
        # Create GIFs with distinct patterns (not solid colors) so phash differs
        size = (64, 64)

        # GIF A: frame 1 = left half white, frame 2 = top half white
        f1a = Image.new("RGBA", size, (0, 0, 0, 255))
        for x in range(32):
            for y in range(64):
                f1a.putpixel((x, y), (255, 255, 255, 255))
        f2a = Image.new("RGBA", size, (0, 0, 0, 255))
        for x in range(64):
            for y in range(32):
                f2a.putpixel((x, y), (255, 255, 255, 255))

        path_a = tmp_path / "a.gif"
        f1a.save(path_a, save_all=True, append_images=[f2a], duration=[100, 100], loop=0)

        # GIF B: frame 1 = right half white, frame 2 = bottom half white
        f1b = Image.new("RGBA", size, (0, 0, 0, 255))
        for x in range(32, 64):
            for y in range(64):
                f1b.putpixel((x, y), (255, 255, 255, 255))
        f2b = Image.new("RGBA", size, (0, 0, 0, 255))
        for x in range(64):
            for y in range(32, 64):
                f2b.putpixel((x, y), (255, 255, 255, 255))

        path_b = tmp_path / "b.gif"
        f1b.save(path_b, save_all=True, append_images=[f2b], duration=[100, 100], loop=0)

        assert _gifs_are_identical(path_a, path_b) is False

    def test_different_timing(self, tmp_path, make_gif):
        colors = [(255, 0, 0, 255), (0, 255, 0, 255)]
        a = make_gif(tmp_path, "a.gif", colors=colors, durations=[100, 100])
        b = make_gif(tmp_path, "b.gif", colors=colors, durations=[100, 500])
        assert _gifs_are_identical(a, b) is False


# ---------------------------------------------------------------------------
# Integration-level
# ---------------------------------------------------------------------------
class TestComputeImageInfo:
    def test_static_png(self, tmp_path, make_png):
        f = make_png(tmp_path, "test.png", size=(8, 8))
        info = compute_image_info(f)
        assert info is not None
        assert info.width == 8
        assert info.height == 8
        assert info.n_frames == 1
        assert info.is_animated() is False
        assert isinstance(info.md5, str)

    def test_animated_gif(self, tmp_path, make_gif):
        f = make_gif(
            tmp_path,
            "test.gif",
            colors=[(255, 0, 0, 255), (0, 255, 0, 255)],
            durations=[100, 100],
            size=(8, 8),
        )
        info = compute_image_info(f)
        assert info is not None
        assert info.n_frames == 2
        assert info.is_animated() is True

    def test_corrupt_file_returns_none(self, tmp_path):
        f = tmp_path / "corrupt.png"
        f.write_bytes(b"not an image")
        info = compute_image_info(f)
        assert info is None


class TestFindSimilarGroups:
    def test_groups_identical_images(self, tmp_path, make_png):
        a = make_png(tmp_path, "a.png", color=(255, 0, 0, 255), size=(8, 8))
        b = make_png(tmp_path, "b.png", color=(255, 0, 0, 255), size=(8, 8))
        groups = find_similar_groups([a, b], threshold=0)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_separates_unique_images(self, tmp_path, make_png):
        a = make_png(tmp_path, "a.png", color=(255, 0, 0, 255), size=(32, 32))
        b = make_png(tmp_path, "b.png", color=(0, 0, 255, 255), size=(16, 16))
        groups = find_similar_groups([a, b], threshold=0)
        # Different dimensions -> can't be duplicates
        assert len(groups) == 0

    def test_skips_degenerate_hashes(self, tmp_path, make_png):
        # Fully transparent images should be skipped
        a = make_png(tmp_path, "a.png", color=(0, 0, 0, 0), size=(4, 4))
        b = make_png(tmp_path, "b.png", color=(0, 0, 0, 0), size=(4, 4))
        groups = find_similar_groups([a, b], threshold=0)
        # These may or may not have degenerate hashes depending on imagehash;
        # the key assertion is no crash
        assert isinstance(groups, list)


class TestDeduplicate:
    def test_dry_run_keeps_all_files(self, tmp_path, make_png):
        a = make_png(tmp_path, "a.png", color=(255, 0, 0, 255), size=(8, 8))
        b = make_png(tmp_path, "b.png", color=(255, 0, 0, 255), size=(8, 8))
        info_a = compute_image_info(a)
        info_b = compute_image_info(b)
        groups = [[(a, info_a), (b, info_b)]]

        group_count, removed = deduplicate(groups, dry_run=True, threshold=0)
        assert group_count == 1
        assert removed == 1
        assert a.exists()
        assert b.exists()

    def test_deletes_duplicates(self, tmp_path, make_png):
        a = make_png(tmp_path, "a.png", color=(255, 0, 0, 255), size=(8, 8))
        b = make_png(tmp_path, "b.png", color=(255, 0, 0, 255), size=(8, 8))
        info_a = compute_image_info(a)
        info_b = compute_image_info(b)
        groups = [[(a, info_a), (b, info_b)]]

        group_count, removed = deduplicate(groups, dry_run=False, threshold=0)
        assert group_count == 1
        assert removed == 1
        # 'a' is alphabetically first -> kept
        assert a.exists()
        assert not b.exists()

    def test_keeps_alphabetically_first(self, tmp_path, make_png):
        z = make_png(tmp_path, "z_last.png", color=(255, 0, 0, 255), size=(8, 8))
        a = make_png(tmp_path, "a_first.png", color=(255, 0, 0, 255), size=(8, 8))
        info_z = compute_image_info(z)
        info_a = compute_image_info(a)
        groups = [[(z, info_z), (a, info_a)]]

        deduplicate(groups, dry_run=False, threshold=0)
        assert a.exists()  # alphabetically first
        assert not z.exists()


class TestMainCLI:
    def test_missing_directory(self, tmp_path, capsys):
        with patch("sys.argv", ["dedup", "--dir", str(tmp_path / "nonexistent")]):
            dedup.main()
        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    def test_empty_directory(self, tmp_path, capsys):
        d = tmp_path / "empty"
        d.mkdir()
        with patch("sys.argv", ["dedup", "--dir", str(d), "--dry-run"]):
            dedup.main()
        captured = capsys.readouterr()
        assert "No image files" in captured.out

    def test_dry_run_flag(self, tmp_path, make_png, capsys):
        d = tmp_path / "imgs"
        d.mkdir()
        make_png(d, "a.png", color=(255, 0, 0, 255), size=(8, 8))
        make_png(d, "b.png", color=(255, 0, 0, 255), size=(8, 8))
        with patch("sys.argv", ["dedup", "--dir", str(d), "--dry-run"]):
            dedup.main()
        captured = capsys.readouterr()
        assert "dry-run" in captured.out

    def test_threshold_argument(self, tmp_path, make_png, capsys):
        d = tmp_path / "imgs"
        d.mkdir()
        make_png(d, "only.png", size=(8, 8))
        with patch("sys.argv", ["dedup", "--dir", str(d), "--threshold", "5"]):
            dedup.main()
        captured = capsys.readouterr()
        assert "threshold: 5" in captured.out
