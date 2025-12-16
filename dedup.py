#!/usr/bin/env python3
"""Find and remove duplicate emoji files using perceptual hashing."""

import argparse
import hashlib
from pathlib import Path
from dataclasses import dataclass

import imagehash
from PIL import Image

EXTENSIONS = (".png", ".gif", ".jpg", ".jpeg")

# Number of hash algorithms that must agree for images to be considered similar
MIN_HASH_AGREEMENT = 4

# Maximum file size difference ratio for duplicates (e.g., 0.05 = 5% difference allowed)
MAX_SIZE_DIFF_RATIO = 0.02


@dataclass
class ImageInfo:
    """Container for image metadata and hashes."""

    phash: imagehash.ImageHash
    ahash: imagehash.ImageHash
    dhash: imagehash.ImageHash
    colorhash: imagehash.ImageHash
    width: int
    height: int
    n_frames: int  # 1 for static images
    md5: str  # File content hash for exact duplicate detection

    def _has_degenerate_hash(self) -> bool:
        """Check if this image has degenerate (all-zero) hashes, indicating mostly transparent content."""
        zero_hash = "0000000000000000"
        # If 3+ hashes are all zeros, the image is likely mostly transparent
        zero_count = sum(1 for h in [str(self.phash), str(self.ahash), str(self.dhash)] if h == zero_hash)
        return zero_count >= 3

    def is_candidate(self, other: "ImageInfo", threshold: int) -> tuple[bool, int, int]:
        """
        Check if two images are candidate duplicates based on metadata and hashes.
        Returns (is_candidate, agreements, total_distance).

        This is a fast pre-filter. GIFs require additional frame verification.
        """
        # Dimensions must match exactly
        if self.width != other.width or self.height != other.height:
            return False, 0, 999

        # Frame count must match for animated images
        if self.n_frames != other.n_frames:
            return False, 0, 999

        # Calculate perceptual hash distances
        distances = [
            self.phash - other.phash,
            self.ahash - other.ahash,
            self.dhash - other.dhash,
            self.colorhash - other.colorhash,
        ]
        total_distance = sum(distances)
        agreements = sum(1 for d in distances if d <= threshold)

        # For static images: detect re-compressed/re-exported duplicates
        # Require identical structure AND color, with small perceptual variance:
        # - aHash=0 AND dHash=0 AND colorHash=0 AND pHash <= 10
        # - OR all 4 hashes match exactly (total_distance = 0)
        if self.n_frames == 1:
            phash_dist = self.phash - other.phash
            ahash_dist = self.ahash - other.ahash
            dhash_dist = self.dhash - other.dhash
            chash_dist = self.colorhash - other.colorhash
            # Identical structure + color, small perceptual variance = re-compressed image
            if ahash_dist == 0 and dhash_dist == 0 and chash_dist == 0 and phash_dist <= 10:
                return True, agreements, total_distance
            # All hashes match exactly
            if total_distance == 0:
                return True, agreements, total_distance
            return False, agreements, total_distance

        # For animated images: require all 4 hashes to agree (will be verified by frame check)
        return agreements >= MIN_HASH_AGREEMENT, agreements, total_distance

    def is_animated(self) -> bool:
        """Check if this is an animated image (multiple frames)."""
        return self.n_frames > 1


class UnionFind:
    """Union-Find data structure for clustering similar images."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px != py:
            self.parent[px] = py


def _compute_hashes(img: Image.Image) -> tuple[imagehash.ImageHash, ...]:
    """Compute all hash types for a single image/frame."""
    # Convert to RGBA to handle transparency consistently
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return (
        imagehash.phash(img),
        imagehash.average_hash(img),
        imagehash.dhash(img),
        imagehash.colorhash(img),
    )


def _compute_md5(path: Path) -> str:
    """Compute MD5 hash of file contents."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _get_gif_frame_info(path: Path) -> list[tuple[str, int]] | None:
    """
    Get perceptual hash and duration for each frame of a GIF.
    Returns list of (hash_string, duration_ms) tuples, or None if not a multi-frame image.
    """
    try:
        with Image.open(path) as img:
            n_frames = getattr(img, "n_frames", 1)
            if n_frames <= 1:
                return None

            frame_info = []
            for i in range(n_frames):
                img.seek(i)
                frame = img.copy()
                if frame.mode != "RGBA":
                    frame = frame.convert("RGBA")
                duration = img.info.get("duration", 0)
                frame_info.append((str(imagehash.phash(frame)), duration))
            return frame_info
    except Exception:
        return None


def _gifs_are_identical(path1: Path, path2: Path) -> bool:
    """
    Compare two GIFs frame-by-frame to check if they have identical content AND timing.
    Returns True only if all frames and durations match.
    """
    info1 = _get_gif_frame_info(path1)
    info2 = _get_gif_frame_info(path2)

    # If either isn't a multi-frame GIF, fall back to MD5 comparison
    if info1 is None or info2 is None:
        return _compute_md5(path1) == _compute_md5(path2)

    # Frame counts must match
    if len(info1) != len(info2):
        return False

    # All frames AND durations must match
    return info1 == info2


def compute_image_info(path: Path) -> ImageInfo | None:
    """
    Compute image metadata and perceptual hashes.
    For animated GIFs, samples middle frame to avoid blank first-frame issues.
    Returns None if image can't be processed.
    """
    try:
        md5 = _compute_md5(path)

        with Image.open(path) as img:
            width, height = img.size
            n_frames = getattr(img, "n_frames", 1)
            is_animated = getattr(img, "is_animated", False)

            if not is_animated:
                hashes = _compute_hashes(img)
            else:
                # For animated images, use middle frame for hashing
                middle_frame = n_frames // 2
                try:
                    img.seek(middle_frame)
                    hashes = _compute_hashes(img.copy())
                except EOFError:
                    img.seek(0)
                    hashes = _compute_hashes(img)

            return ImageInfo(
                phash=hashes[0],
                ahash=hashes[1],
                dhash=hashes[2],
                colorhash=hashes[3],
                width=width,
                height=height,
                n_frames=n_frames,
                md5=md5,
            )

    except Exception as e:
        print(f"  Warning: Could not process {path.name}: {e}")
        return None


def _files_size_similar(path1: Path, path2: Path) -> bool:
    """Check if two files have similar sizes (within MAX_SIZE_DIFF_RATIO)."""
    size1 = path1.stat().st_size
    size2 = path2.stat().st_size
    if size1 == 0 or size2 == 0:
        return size1 == size2
    ratio = abs(size1 - size2) / max(size1, size2)
    return ratio <= MAX_SIZE_DIFF_RATIO


def _verify_duplicate_pair(
    path_i: Path, info_i: ImageInfo, path_j: Path, info_j: ImageInfo, threshold: int
) -> bool:
    """
    Verify if two candidate images are true duplicates.
    For animated GIFs, compares frames and timing. For static images, perceptual match is sufficient.
    """
    # For animated images, verify frame-by-frame including timing
    if info_i.is_animated() and info_j.is_animated():
        return _gifs_are_identical(path_i, path_j)

    # For static images, perceptual hash agreement is sufficient
    # (handles re-compressed/re-exported duplicates with different file sizes)
    return True


def find_similar_groups(
    files: list[Path], threshold: int
) -> list[list[tuple[Path, ImageInfo]]]:
    """Find groups of similar images using multi-hash consensus and union-find."""
    # Compute image info for all files
    images: list[tuple[Path, ImageInfo]] = []
    for file in files:
        info = compute_image_info(file)
        if info is not None:
            # Skip images with degenerate (all-zero) hashes - they can't be meaningfully compared
            if not info._has_degenerate_hash():
                images.append((file, info))

    if not images:
        return []

    # Use union-find to cluster similar images
    # First pass: find candidates based on hashes and metadata
    # Second pass: verify GIFs with frame comparison
    uf = UnionFind()
    for i, (path_i, info_i) in enumerate(images):
        uf.find(i)  # Initialize
        for j in range(i + 1, len(images)):
            path_j, info_j = images[j]

            # Check if candidates based on hashes/metadata
            is_candidate, _, _ = info_i.is_candidate(info_j, threshold)
            if not is_candidate:
                continue

            # For animated images, also check file size similarity
            # (static images may have different compression, so skip size check)
            if info_i.is_animated() and not _files_size_similar(path_i, path_j):
                continue

            # Verify: for GIFs, compare frames; for static, already verified by hashes
            if _verify_duplicate_pair(path_i, info_i, path_j, info_j, threshold):
                uf.union(i, j)

    # Group by cluster
    clusters: dict[int, list[tuple[Path, ImageInfo]]] = {}
    for i, (path, info) in enumerate(images):
        root = uf.find(i)
        if root not in clusters:
            clusters[root] = []
        clusters[root].append((path, info))

    # Return only groups with duplicates
    return [group for group in clusters.values() if len(group) > 1]


def deduplicate(
    groups: list[list[tuple[Path, ImageInfo]]], dry_run: bool, threshold: int
) -> tuple[int, int]:
    """Remove duplicates, keeping first alphabetically. Returns (groups, removed)."""
    total_removed = 0

    for group in groups:
        # Sort by filename alphabetically
        sorted_group = sorted(group, key=lambda x: x[0].name.lower())
        keep_path, keep_info = sorted_group[0]
        remove = sorted_group[1:]

        # Calculate agreement info for display
        agreements_info = [keep_info.is_candidate(info, threshold) for _, info in remove]
        min_agreements = min(a for _, a, _ in agreements_info)

        frames_str = f", {keep_info.n_frames} frames" if keep_info.is_animated() else ""
        print(f"\nSimilar group ({len(group)} files, {keep_info.width}x{keep_info.height}{frames_str}):")
        print(f"  KEEP: {keep_path.name}")

        for (path, info), (_, agreements, total_dist) in zip(remove, agreements_info):
            action = "WOULD DELETE" if dry_run else "DELETE"
            print(f"  {action}: {path.name} (agreements: {agreements}/4, dist: {total_dist})")
            if not dry_run:
                path.unlink()
                total_removed += 1

    if dry_run:
        return len(groups), sum(len(g) - 1 for g in groups)
    return len(groups), total_removed


def main():
    parser = argparse.ArgumentParser(
        description="Find and remove duplicate emoji files using perceptual hashing."
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=0,
        help="Similarity threshold (0=exact, default=0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show duplicates without deleting",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("emoji"),
        help="Directory to scan (default: emoji/)",
    )
    args = parser.parse_args()

    emoji_dir = args.dir
    if not emoji_dir.exists():
        print(f"Error: Directory '{emoji_dir}' does not exist.")
        return

    files = [f for f in emoji_dir.iterdir() if f.suffix.lower() in EXTENSIONS]

    if not files:
        print(f"No image files found in {emoji_dir}/ folder.")
        return

    print(f"Scanning {len(files)} files (threshold: {args.threshold})...")
    if args.dry_run:
        print("(dry-run mode - no files will be deleted)")

    groups = find_similar_groups(files, args.threshold)

    if not groups:
        print("\nNo similar images found.")
        return

    group_count, removed = deduplicate(groups, args.dry_run, args.threshold)

    print(f"\n--- Summary ---")
    print(f"Files scanned: {len(files)}")
    print(f"Similar groups: {group_count}")
    if args.dry_run:
        print(f"Files to remove: {removed}")
    else:
        print(f"Files removed: {removed}")


if __name__ == "__main__":
    main()
