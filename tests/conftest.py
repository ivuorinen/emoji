"""Shared test fixtures for emoji project tests."""

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def make_png():
    """Factory fixture: creates a small PNG image and returns its Path."""

    def _make_png(
        directory: Path,
        name: str,
        color: tuple = (255, 0, 0, 255),
        size: tuple[int, int] = (4, 4),
    ) -> Path:
        img = Image.new("RGBA", size, color)
        path = directory / name
        img.save(path, "PNG")
        return path

    return _make_png


@pytest.fixture
def make_gif():
    """Factory fixture: creates an animated GIF with multiple frames and returns its Path."""

    def _make_gif(
        directory: Path,
        name: str,
        colors: list[tuple],
        durations: list[int],
        size: tuple[int, int] = (4, 4),
    ) -> Path:
        if not colors:
            raise ValueError("colors must not be empty")
        if len(durations) != len(colors):
            raise ValueError(f"durations length ({len(durations)}) must match colors length ({len(colors)})")
        frames = [Image.new("RGBA", size, c) for c in colors]
        path = directory / name
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
        )
        return path

    return _make_gif


@pytest.fixture
def make_jpg():
    """Factory fixture: creates a small JPEG image and returns its Path."""

    def _make_jpg(
        directory: Path,
        name: str,
        color: tuple = (255, 0, 0),
        size: tuple[int, int] = (4, 4),
    ) -> Path:
        img = Image.new("RGB", size, color)
        path = directory / name
        img.save(path, "JPEG")
        return path

    return _make_jpg


@pytest.fixture
def emoji_dir(tmp_path, make_png, make_gif, make_jpg):
    """Creates a temp directory with several named test images."""
    d = tmp_path / "emoji"
    d.mkdir()
    make_png(d, "alpha.png", color=(255, 0, 0, 255))
    make_png(d, "beta.png", color=(0, 255, 0, 255))
    make_png(d, "gamma.png", color=(0, 0, 255, 255))
    make_jpg(d, "delta.jpg", color=(128, 128, 0))
    make_gif(
        d,
        "animated.gif",
        colors=[(255, 0, 0, 255), (0, 255, 0, 255)],
        durations=[100, 100],
    )
    return d
