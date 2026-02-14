"""
Text processing utilities for DayZ server management.

Common text operations like secret masking, parsing, and string manipulation.
"""

import re


def mask_password_in_config(content: str) -> str:
    """
    Mask password fields in configuration text.

    Replaces any value after '=' with "******" for lines containing 'password'.

    Args:
        content: Configuration file content

    Returns:
        Configuration with passwords masked

    Examples:
        >>> mask_password_in_config('hostname="Test"\\npassword="secret123"')
        'hostname="Test"\\npassword="******"'
    """
    return "\n".join(
        re.sub(r'(=\s*)".*?"', r'\\1"******"', line)
        if re.search(r"password", line, re.IGNORECASE)
        else line
        for line in content.splitlines()
    )


def mask_username(username: str) -> str:
    """
    Mask username for display (show first and last char only).

    Args:
        username: Username to mask

    Returns:
        Masked username (e.g., "a***e" for "alice")

    Examples:
        >>> mask_username("alice")
        'a***e'
        >>> mask_username("ab")
        'ab'
        >>> mask_username("a")
        'a'
    """
    if len(username) > 2:
        return username[0] + "*" * (len(username) - 2) + username[-1]
    return username


def extract_mod_name_from_meta(content: str) -> str | None:
    """
    Extract mod name from meta.cpp content.

    Args:
        content: Contents of meta.cpp file

    Returns:
        Mod name if found, None otherwise

    Examples:
        >>> extract_mod_name_from_meta('name = "My Cool Mod";')
        'My Cool Mod'
    """
    if match := re.search(r'name\s*=\s*"([^"]+)"', content):
        return match.group(1)
    return None


def extract_template_from_config(content: str) -> str | None:
    """
    Extract mission template from serverDZ.cfg content.

    Args:
        content: Server configuration file content

    Returns:
        Template name if found, None otherwise

    Examples:
        >>> extract_template_from_config('template = "dayzOffline.chernarusplus";')
        'dayzOffline.chernarusplus'
    """
    if match := re.search(r'template\s*=\s*"([^"]+)"', content):
        return match.group(1)
    return None


def parse_steam_username(content: str) -> str:
    """
    Parse Steam username from config content.

    Handles formats:
    - steamlogin=username
    - username (plain)

    Args:
        content: Config file content or username string

    Returns:
        Parsed username or "anonymous" if invalid

    Examples:
        >>> parse_steam_username("steamlogin=testuser")
        'testuser'
        >>> parse_steam_username("testuser")
        'testuser'
        >>> parse_steam_username("")
        'anonymous'
    """
    content = content.strip()
    if not content:
        return "anonymous"

    if "=" in content:
        return content.split("=", 1)[1].strip()

    parts = content.split()
    return parts[0] if parts else "anonymous"


def build_workshop_url(mod_id: str) -> str:
    """
    Build Steam Workshop URL for a mod ID.

    Args:
        mod_id: Workshop mod ID

    Returns:
        Full Steam Workshop URL

    Examples:
        >>> build_workshop_url("1234567890")
        'https://steamcommunity.com/sharedfiles/filedetails/?id=1234567890'
    """
    return f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
