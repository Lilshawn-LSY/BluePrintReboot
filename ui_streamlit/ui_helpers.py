from __future__ import annotations

import re
from typing import MutableMapping


def confirmation_key(action: str, item_id: str) -> str:
    action_token = _key_token(action)
    item_token = _key_token(item_id)
    return f"ui_confirm_{action_token}_{item_token}"


def request_confirmation(session_state: MutableMapping, key: str) -> None:
    session_state[key] = True


def confirmation_pending(session_state: MutableMapping, key: str) -> bool:
    return bool(session_state.get(key, False))


def clear_session_keys(session_state: MutableMapping, *keys: str) -> None:
    for key in keys:
        session_state.pop(key, None)


def _key_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value).strip()).strip("_") or "item"
