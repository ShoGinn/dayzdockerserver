#!/usr/bin/env python3
"""
Robust version extractor for DayZ Server binaries.
Handles different version formats and binary changes across builds.
"""

import re
import struct


def extract_dayz_version(binary_path: str) -> str | None:
    """
    Extract DayZ server version from binary using multiple detection strategies.

    Args:
        binary_path: Path to DayZServer binary

    Returns:
        Version string (e.g., "1.28.161464") or None if not found
    """
    try:
        with open(binary_path, "rb") as f:
            data = f.read()
    except OSError as e:
        print(f"Error reading file: {e}")
        return None

    # Strategy 1: Look for semantic version strings (most reliable)
    version = _find_version_string(data)
    if version:
        return version

    # Strategy 2: Look for version near known strings (DayZ-specific markers)
    version = _find_version_near_markers(data)
    if version:
        return version

    # Strategy 3: Look for binary-encoded version numbers
    version = _find_binary_version(data)
    if version:
        return version

    return None


def _find_version_string(data: bytes) -> str | None:
    """Find version as ASCII string using regex patterns."""

    # Pattern 1: Standard semantic versioning (x.y.z where z is a large build number)
    # DayZ typically uses format like 1.28.161464
    matches = re.findall(rb"\d+\.\d+\.\d{5,7}", data)

    candidates: list[tuple[str, int, int, int]] = []
    for match in matches:
        try:
            decoded: str = match.decode("ascii")
            parts = decoded.split(".")
            if len(parts) == 3:
                major, minor, build = map(int, parts)
                # DayZ version constraints: major 0-5, minor 0-99, build > 10000
                if 0 <= major <= 5 and 0 <= minor <= 99 and 10000 <= build <= 999999:
                    candidates.append((decoded, major, minor, build))
        except (ValueError, UnicodeDecodeError):
            continue

    if candidates:
        # Return the highest version found (most likely to be current)
        candidates.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
        return candidates[0][0]

    return None


def _find_version_near_markers(data: bytes) -> str | None:
    """Find version strings near known DayZ markers."""

    markers = [
        b"DayZ",
        b"Console version",
        b"server version",
        b"requiredBuild",
        b"requiredVersion",
    ]

    for marker in markers:
        offset = 0
        while True:
            offset = data.find(marker, offset)
            if offset == -1:
                break

            # Search in a window around the marker (±200 bytes)
            window_start = max(0, offset - 200)
            window_end = min(len(data), offset + 200)
            window = data[window_start:window_end]

            # Look for version pattern in this window
            matches = re.findall(rb"\d+\.\d+\.\d{5,7}", window)
            for match in matches:
                try:
                    decoded: str = match.decode("ascii")
                    parts = decoded.split(".")
                    if len(parts) == 3:
                        major, minor, build = map(int, parts)
                        if 0 <= major <= 5 and 0 <= minor <= 99 and 10000 <= build <= 999999:
                            return decoded
                except (ValueError, UnicodeDecodeError):
                    continue

            offset += 1

    return None


def _find_binary_version(data: bytes) -> str | None:
    """Find version encoded as binary integers."""

    # Known DayZ versions to search for (update this list as needed)
    # Format: [(major, minor, build), ...]
    known_patterns = [
        # This helps find the structure even in new versions
        (1, 28),  # Just major.minor to find the pattern
        (1, 27),
        (1, 26),
    ]

    for major, minor in known_patterns:
        # Try different encodings
        formats = [
            ("<HHI", [major, minor, 0]),  # shorts + int (little-endian)
            ("<III", [major, minor, 0]),  # all ints (little-endian)
        ]

        for fmt, values in formats:
            try:
                # Search for major.minor pattern
                pattern = struct.pack(fmt[:4], *values[:2])
                offset = data.find(pattern)

                if offset != -1:
                    # Found major.minor, now try to read the build number
                    build_offset = offset + 4 if fmt == "<HHI" else offset + 8

                    if build_offset + 4 <= len(data):
                        build = struct.unpack("<I", data[build_offset : build_offset + 4])[0]
                        if 10000 <= build <= 999999:
                            return f"{major}.{minor}.{build}"
            except struct.error:
                continue

    return None


def get_all_version_candidates(binary_path: str) -> list[str]:
    """
    Get all possible version strings found (useful for debugging).

    Returns:
        List of version strings found
    """
    try:
        with open(binary_path, "rb") as f:
            data = f.read()
    except OSError:
        return []

    matches = re.findall(rb"\d+\.\d+\.\d{5,7}", data)
    candidates = []

    for match in matches:
        try:
            decoded = match.decode("ascii")
            parts = decoded.split(".")
            if len(parts) == 3:
                major, minor, build = map(int, parts)
                if 0 <= major <= 5 and 0 <= minor <= 99 and 10000 <= build <= 999999:
                    candidates.append(decoded)
        except (ValueError, UnicodeDecodeError):
            continue

    return sorted(set(candidates))


# CLI usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract_version.py <path-to-DayZServer>")
        print("       python extract_version.py <path-to-DayZServer> --all")
        sys.exit(1)

    binary_path = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] == "--all":
        # Debug mode: show all candidates
        print("All version candidates found:")
        candidates = get_all_version_candidates(binary_path)
        for v in candidates:
            print(f"  {v}")
    else:
        # Normal mode: get best version
        version = extract_dayz_version(binary_path)
        if version:
            print(version)
        else:
            print("Version not found", file=sys.stderr)
            sys.exit(1)
