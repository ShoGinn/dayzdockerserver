"""
File system utilities for DayZ server management.

Common file operations like size calculations, cleanup categorization,
and human-readable formatting.
"""

from pathlib import Path


def get_dir_size(path: Path) -> int:
    """
    Get directory size in bytes.

    Args:
        path: Directory path to calculate size for

    Returns:
        Total size in bytes of all files in directory tree
    """
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def human_size(size_bytes: int) -> str:
    """
    Convert bytes to human-readable size string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size (e.g., "1.5 MB", "3.2 GB")

    Examples:
        >>> human_size(1024)
        '1.0 KB'
        >>> human_size(1536)
        '1.5 KB'
        >>> human_size(1073741824)
        '1.0 GB'
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes = int(size_bytes / 1024)
    return f"{size_bytes:.1f} PB"


def categorize_cleanup_file(item: Path) -> str | None:
    """
    Categorize file for cleanup based on name/extension.

    Args:
        item: File path to categorize

    Returns:
        Category name or None if not a cleanup candidate

    Categories:
        - core_dumps: core.* files
        - crash_dumps: .dmp, .mdmp files
        - log_files: .log, .rpt, .ADM files
        - temp_files: .tmp, .temp, *~ files
    """
    if item.name.startswith("core.") or item.name == "core":
        return "core_dumps"
    elif item.suffix in (".dmp", ".mdmp"):
        return "crash_dumps"
    elif item.suffix in (".log", ".rpt", ".ADM"):
        return "log_files"
    elif item.suffix in (".tmp", ".temp") or item.name.endswith("~"):
        return "temp_files"
    return None


def format_uptime(seconds: int) -> str:
    """
    Format uptime seconds as human-readable string.

    Args:
        seconds: Uptime in seconds

    Returns:
        Formatted string like "1d 05h 23m 45s"

    Examples:
        >>> format_uptime(0)
        ''
        >>> format_uptime(90)
        '0d 00h 01m 30s'
        >>> format_uptime(86400)
        '1d 00h 00m 00s'
    """
    if seconds <= 0:
        return ""

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{days}d {hours:02d}h {minutes:02d}m {secs:02d}s"
