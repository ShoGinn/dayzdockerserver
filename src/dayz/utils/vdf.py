"""
Valve KeyValues (VDF) minimal parser.

Designed for reading Steam config.vdf-style files: nested quoted keys with
brace-delimited objects and // comments. Values are typically quoted strings.

This implementation is intentionally lightweight and dependency-free.
"""

from __future__ import annotations

from typing import Any


def parse_kv(text: str) -> dict[str, Any]:
    """Parse Valve KeyValues text into a nested dict.

    Supports:
    - "key" "value"
    - "key" { ... }
    - // comments to end of line
    - quoted strings with \" escapes
    """

    s = text or ""
    i = 0
    n = len(s)

    def skip_ws_comments() -> None:
        nonlocal i
        while i < n:
            c = s[i]
            if c in (" ", "\t", "\r", "\n"):
                i += 1
                continue
            if c == "/" and i + 1 < n and s[i + 1] == "/":
                i += 2
                while i < n and s[i] not in ("\n", "\r"):
                    i += 1
                continue
            break

    def read_string() -> str:
        nonlocal i
        if i >= n or s[i] != '"':
            raise ValueError("Expected opening quote")
        i += 1
        out: list[str] = []
        while i < n:
            c = s[i]
            if c == "\\":
                i += 1
                if i < n:
                    out.append(s[i])
                    i += 1
                continue
            if c == '"':
                i += 1
                return "".join(out)
            out.append(c)
            i += 1
        raise ValueError("Unterminated string")

    def read_value() -> Any:
        nonlocal i
        skip_ws_comments()
        if i < n and s[i] == "{":
            i += 1
            obj: dict[str, Any] = {}
            while True:
                skip_ws_comments()
                if i >= n:
                    raise ValueError("Unterminated object")
                if s[i] == "}":
                    i += 1
                    break
                key = read_string()
                skip_ws_comments()
                val = read_value()
                obj[key] = val
                skip_ws_comments()
            return obj
        # Value as quoted string
        return read_string()

    result: dict[str, Any] = {}
    skip_ws_comments()
    while i < n:
        key = read_string()
        skip_ws_comments()
        val = read_value()
        result[key] = val
        skip_ws_comments()
    return result


def _find_accounts_block(node: dict[str, Any]) -> dict[str, Any] | None:
    """Depth-first search for an "Accounts" block anywhere in the tree."""
    if not isinstance(node, dict):
        return None
    if "Accounts" in node and isinstance(node["Accounts"], dict):
        return node["Accounts"]
    for val in node.values():
        if isinstance(val, dict):
            found = _find_accounts_block(val)
            if found is not None:
                return found
    return None


def find_first_account_name(kv: dict[str, Any]) -> str | None:
    """Find the first account name under the Accounts block.

    Expected layout:
    Accounts {
        "<username>" { "SteamID" "..." }
    }

    Some files may instead have an inner "AccountName" field; we ignore that
    and prefer the subkey name since that's the common Steam config.vdf format.
    """
    accounts = _find_accounts_block(kv)
    if isinstance(accounts, dict):
        for key, sub in accounts.items():
            if isinstance(key, str) and isinstance(sub, dict) and key.strip():
                return key.strip()
    return None


def validate_config_vdf(text: str) -> tuple[bool, str | None, str | None]:
    """Validate a Steam config.vdf-like file and return the first account name.

    Returns (ok, account_name, error_message). On success, error_message is None.
    Validation requires:
      - File parses as KeyValues
      - Contains an Accounts block
      - Accounts has at least one child object (an account)
    """
    try:
        kv = parse_kv(text)
    except Exception as e:
        return False, None, f"Invalid VDF format: {e}"

    accounts = _find_accounts_block(kv)
    if not isinstance(accounts, dict) or not accounts:
        return False, None, "VDF missing Accounts section or it is empty"

    # Ensure at least one child object exists
    has_child = any(isinstance(v, dict) for v in accounts.values())
    if not has_child:
        return False, None, "VDF Accounts section has no account entries"

    name = find_first_account_name(kv)
    if not name:
        return False, None, "Unable to determine account name from VDF"
    return True, name, None
