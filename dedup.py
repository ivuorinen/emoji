#!/usr/bin/env python3
"""Find and remove duplicate emoji files based on content hash."""

import hashlib
from collections import defaultdict
from pathlib import Path

EMOJI_DIR = Path("emoji")
EXTENSIONS = (".png", ".gif", ".jpg", ".jpeg")


def hash_file(path: Path) -> str:
    """Return SHA-256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_duplicates(files: list[Path]) -> dict[str, list[Path]]:
    """Group files by their content hash, return only groups with duplicates."""
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for file in files:
        file_hash = hash_file(file)
        by_hash[file_hash].append(file)
    return {h: paths for h, paths in by_hash.items() if len(paths) > 1}


def deduplicate(duplicates: dict[str, list[Path]]) -> tuple[int, int]:
    """Remove duplicates, keeping first alphabetically. Returns (groups, removed)."""
    total_removed = 0

    for file_hash, paths in duplicates.items():
        sorted_paths = sorted(paths, key=lambda p: p.name.lower())
        keep = sorted_paths[0]
        remove = sorted_paths[1:]

        print(f"\nDuplicate group ({len(paths)} files):")
        print(f"  KEEP: {keep.name}")
        for path in remove:
            print(f"  DELETE: {path.name}")
            path.unlink()
            total_removed += 1

    return len(duplicates), total_removed


def main():
    files = [
        f for f in EMOJI_DIR.iterdir()
        if f.suffix.lower() in EXTENSIONS
    ]

    if not files:
        print("No image files found in emoji/ folder.")
        return

    print(f"Scanning {len(files)} files...")

    duplicates = find_duplicates(files)

    if not duplicates:
        print("\nNo duplicates found.")
        return

    groups, removed = deduplicate(duplicates)

    print(f"\n--- Summary ---")
    print(f"Files scanned: {len(files)}")
    print(f"Duplicate groups: {groups}")
    print(f"Files removed: {removed}")


if __name__ == "__main__":
    main()
