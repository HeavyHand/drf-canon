from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    'PROBLEM_TYPE_BASE': '/problems/',
}


def canon_setting(name: str) -> Any:
    """
    Reads a key of the ``DRF_CANON`` setting, falling back to its default.

    Read on every call rather than cached, so ``override_settings`` works without extra wiring.
    """
    return getattr(settings, 'DRF_CANON', {}).get(name, DEFAULTS[name])
