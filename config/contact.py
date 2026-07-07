from __future__ import annotations

import os


APP_VERSION = "1.0.17"
DEFAULT_CONTACT_EMAIL = "pplee0300@snu.ac.kr"


def get_contact_email() -> str:
    for variable in ("CROSSREF_MAILTO", "BLUEPRINT_CONTACT_EMAIL"):
        value = os.environ.get(variable, "").strip()
        if value:
            return value
    return DEFAULT_CONTACT_EMAIL


def build_blueprint_user_agent(version: str | None = None) -> str:
    return f"BluePrintReboot/{version or APP_VERSION} (mailto:{get_contact_email()})"
