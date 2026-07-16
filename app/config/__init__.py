"""
Configuration package.

Centralizes all environment-driven configuration for the application.
Nothing outside this package should read `os.environ` directly — every
setting is declared once in `settings.py` and consumed via `get_settings()`.
"""

from app.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
