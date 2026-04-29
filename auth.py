"""Authentication helpers for Miso Gallery."""

from __future__ import annotations

import os
import secrets
from functools import wraps
from typing import Literal

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash
from authlib.integrations.flask_client import OAuth

AuthMode = Literal["none", "local", "oidc"]

AUTH_TYPE = os.environ.get("AUTH_TYPE", "local").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
LLM_API_KEYS = [key.strip() for key in os.environ.get("LLM_API_KEYS", "").split(",") if key.strip()]

# OIDC Configuration
OIDC_ENABLED = os.environ.get("OIDC_ENABLED", "").strip().lower() == "true"
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "").strip()
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "").strip()
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "").strip()
OIDC_CALLBACK_URL = os.environ.get("OIDC_CALLBACK_URL", "").strip()

oauth = OAuth()


def configure_oauth(app):
    """Configure OAuth with OIDC provider if enabled."""
    if not is_oidc_configured():
        return

    # Authentik-compatible defaults
    issuer_url = OIDC_ISSUER.rstrip("/")
    if "/.well-known/openid-configuration" in issuer_url:
        issuer_url = issuer_url.replace("/.well-known/openid-configuration", "")

    oauth.init_app(app)
    oauth.register(
        name="oidc",
        client_id=OIDC_CLIENT_ID,
        client_secret=OIDC_CLIENT_SECRET,
        server_metadata_url=f"{issuer_url}/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile email",
        },
    )


def is_oidc_configured() -> bool:
    """Check if OIDC is properly configured."""
    return bool(OIDC_ENABLED and OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET)


def resolved_auth_mode() -> AuthMode:
    """Resolve effective auth mode based on configured env vars."""
    if AUTH_TYPE == "none":
        return "none"

    if AUTH_TYPE == "oidc" or is_oidc_configured():
        return "oidc"

    # default/local
    if ADMIN_PASSWORD:
        return "local"
    return "none"


def is_auth_enabled() -> bool:
    return resolved_auth_mode() != "none"


def is_authenticated() -> bool:
    return bool(session.get("authenticated"))


def is_api_key_auth_enabled() -> bool:
    return bool(LLM_API_KEYS)


def _bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


def verify_api_key(token: str) -> bool:
    if not token or not LLM_API_KEYS:
        return False
    return any(secrets.compare_digest(token, configured) for configured in LLM_API_KEYS)


def verify_local_password(password: str) -> bool:
    """Verify local password.

    Supports plaintext and hashed formats for migration:
    - plaintext: ADMIN_PASSWORD=mysecret
    - hashed: ADMIN_PASSWORD=pbkdf2:sha256:... or scrypt:...
    """
    if not ADMIN_PASSWORD:
        return False

    stored = ADMIN_PASSWORD
    if stored.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored, password)
    return password == stored


def require_auth(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        if not is_auth_enabled():
            return view_fn(*args, **kwargs)
        if is_authenticated():
            return view_fn(*args, **kwargs)
        return redirect(url_for("login", next=request.path))

    return wrapper


def require_api_key(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        if verify_api_key(_bearer_token()):
            return view_fn(*args, **kwargs)
        if is_authenticated():
            return view_fn(*args, **kwargs)
        if not is_api_key_auth_enabled():
            return jsonify({"error": "LLM API keys are not configured"}), 403
        return jsonify({"error": "Bearer token required"}), 401

    return wrapper


def get_oidc_label() -> str:
    """Get a display name for the OIDC provider."""
    label = os.environ.get("OIDC_ISSUER_LABEL", "").strip()
    if label:
        return label
    provider_name = os.environ.get("OIDC_PROVIDER_NAME", "").strip()
    if provider_name:
        return provider_name
    if OIDC_ISSUER:
        # Extract domain from issuer URL
        return OIDC_ISSUER.replace("https://", "").replace("http://", "").split("/")[0]
    return "OIDC"
