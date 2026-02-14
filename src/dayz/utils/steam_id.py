"""Steam ID resolution utilities.

Provides functions to resolve Steam usernames to Steam64 IDs and vice versa
using publicly available Steam metadata endpoints.
"""

import re

import requests


def resolve_username_to_steam64(username: str) -> tuple[bool, str | None, str]:
    """Resolve a Steam username to a Steam64 ID.

    Uses the SteamID.io API (free, no auth required) to convert a username
    to a Steam64 ID.

    Args:
        username: Steam community username or profile URL

    Returns:
        Tuple of (success: bool, steam64_id: str | None, message: str)
    """
    username = username.strip()
    if not username:
        return False, None, "Username cannot be empty"

    try:
        # Try to extract from Steam community URL if provided
        match = re.search(r"(?:steamcommunity\.com/(?:profiles|id)/)?([a-zA-Z0-9_-]+)/?$", username)
        if not match:
            return False, None, "Invalid username or Steam profile URL format"

        clean_username = match.group(1)

        # Use SteamID.io API to resolve username
        response = requests.get(
            "https://steamid.io/lookup",
            params={"input": clean_username},
            timeout=5,
            headers={"User-Agent": "DayZ-Server-Manager"},
        )
        response.raise_for_status()

        # Parse the response to find Steam64 ID
        # The response is HTML, so we need to extract from it
        text = response.text

        # Look for commonID in the response
        # Format: <span id="steamid64">76561198...</span>
        match = re.search(r'<span id=["\']steamid64["\']\s*>\s*(\d+)\s*</span>', text)
        if match:
            steam64 = match.group(1)
            return True, steam64, f"Resolved to Steam64 ID: {steam64}"

        # Alternative pattern - check for error messages
        if "Profile not found" in text or "Invalid input" in text:
            return False, None, f"Steam profile not found for: {clean_username}"

        return False, None, "Could not resolve username to Steam64 ID"

    except requests.RequestException as e:
        return False, None, f"Failed to resolve username: {str(e)}"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"


def validate_steam64_id(steam64_id: str) -> tuple[bool, str]:
    """Validate a Steam64 ID format.

    Args:
        steam64_id: The Steam64 ID to validate

    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    steam64_id = steam64_id.strip()

    if not steam64_id.isdigit():
        return False, "Steam64 ID must contain only digits"

    if len(steam64_id) != 17:
        return False, f"Steam64 ID must be 17 digits (got {len(steam64_id)})"

    # Steam64 IDs should start with 76561198
    if not steam64_id.startswith("76561198"):
        return False, "Invalid Steam64 ID prefix (should start with 76561198)"

    return True, f"Valid Steam64 ID: {steam64_id}"
