"""Steam ID resolution utilities.

Provides functions to resolve Steam usernames to Steam64 IDs and vice versa
using available methods.

Note: This module has limitations with vanity URLs that require the Steam Web API,
which needs an API key. For vanity URLs, users should:
1. Visit their Steam profile
2. Right-click -> View Page Source
3. Search for "OpenID" or just copy the numeric ID from the profile URL
4. Use that Steam64 ID directly
"""

import re

import requests


def _try_api_lookup(query: str) -> tuple[bool, str | None, str]:
    """Try looking up via SteamID.io API (limited support).

    Returns:
        Tuple of (success: bool, steam64_id: str | None, message: str)
    """
    try:
        # Try direct API endpoint (may not work for all queries)
        response = requests.get(
            "https://steamid.io/api/lookup/",
            params={"input": query},
            timeout=5,
            headers={"User-Agent": "DayZ-Server-Manager"},
        )
        response.raise_for_status()

        # The API response is likely JSON or has specific format
        text = response.text

        # Try to find Steam64 ID in various formats
        patterns = [
            r'"steamid64"\s*:\s*"?(\d{17})"?',
            r'<span\s+id=["\']?steamid64["\']?\s*>\s*(\d{17})\s*</span>',
            r'href="https://steamid\.io/lookup/(\d{17})"',
            r'data-steamid64="(\d{17})"',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                steam64 = match.group(1)
                return True, steam64, f"API resolved to Steam64 ID: {steam64}"

        return False, None, "API lookup completed but could not extract Steam64 ID"

    except Exception as e:
        return False, None, f"API lookup failed: {str(e)}"


def resolve_username_to_steam64(username: str) -> tuple[bool, str | None, str]:
    """Resolve a Steam username to a Steam64 ID.

    Supports:
    - Direct Steam64 IDs (extracts from URLs or validates raw ID)
    - Profile URLs with Steam64 ID (extracts directly)
    - Vanity URLs (attempts API lookup with limitations)
    - Usernames (attempts API lookup with limitations)

    Args:
        username: Steam community username, Steam64 ID, or profile URL

    Returns:
        Tuple of (success: bool, steam64_id: str | None, message: str)
    """
    username = username.strip()
    if not username:
        return False, None, "Username cannot be empty"

    try:
        # First, try to extract a Steam64 ID directly from the input
        # Pattern 1: Direct URL with profiles ID
        profiles_match = re.search(r"steamcommunity\.com/profiles/(\d+)", username)
        if profiles_match:
            steam64 = profiles_match.group(1)
            is_valid, message = validate_steam64_id(steam64)
            if is_valid:
                return True, steam64, f"Extracted Steam64 ID from profile URL: {steam64}"
            return False, None, f"Invalid Steam64 ID in URL: {steam64}"

        # Pattern 2: Raw Steam64 ID (17 digits)
        if re.match(r"^\d{17}$", username):
            is_valid, message = validate_steam64_id(username)
            if is_valid:
                return True, username, f"Valid Steam64 ID: {username}"
            return False, None, message

        # Pattern 3: Extract vanity URL from Steam community URL
        vanity_match = re.search(r"steamcommunity\.com/id/([a-zA-Z0-9_-]+)", username)
        vanity_name = vanity_match.group(1) if vanity_match else username.split("/")[-1].rstrip("/")

        # Try API lookup for vanity URLs
        success, steam64, api_message = _try_api_lookup(username)
        if success and steam64:
            return True, steam64, api_message

        # Provide helpful message for vanity URL failures
        return (
            False,
            None,
            f"Could not resolve vanity URL '{vanity_name}'. "
            f"Tip: You can find your Steam64 ID by visiting your Steam profile, "
            f"right-clicking, selecting 'View Page Source', and searching for a 17-digit number starting with 7656119. "
            f"Then paste that number directly.",
        )

    except requests.RequestException as e:
        return False, None, f"Network error resolving username: {str(e)}"
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

    # Steam64 IDs usually start with 7656 for user accounts
    if not steam64_id.startswith("7656"):
        return (
            False,
            f"Invalid Steam64 ID prefix (should usually start with 7656, got {steam64_id[:7]})",
        )

    return True, f"Valid Steam64 ID: {steam64_id}"
