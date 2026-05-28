"""Optional Cube semantic-layer metadata loader.

When CUBE_URL is unset, `fetch_cube_meta()` returns an empty string and the
agent skips the metric route entirely. This keeps the project zero-dependency
out of the box.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger(__name__)


def fetch_cube_meta() -> str:
    """Return a prompt-friendly multi-line description of all cubes, or ''."""
    if not settings.cube_url:
        return ""
    try:
        headers = {}
        if settings.cube_api_secret:
            headers["Authorization"] = settings.cube_api_secret
        r = httpx.get(f"{settings.cube_url}/cubejs-api/v1/meta", headers=headers, timeout=10.0)
        r.raise_for_status()
        meta = r.json().get("cubes", [])
    except Exception as e:  # noqa: BLE001
        log.warning("Cube meta fetch failed (%s); disabling metric route.", e)
        return ""

    lines: list[str] = []
    for c in meta:
        desc = c.get("description", "")
        lines.append(f"CUBE {c['name']}{(' — ' + desc) if desc else ''}")
        for m in c.get("measures", []):
            if m.get("meta", {}).get("pii"):
                continue
            d = m.get("description", "")
            lines.append(f"  measure {m['name']} ({m.get('type', '')}){(' — ' + d) if d else ''}")
        for dim in c.get("dimensions", []):
            if dim.get("meta", {}).get("pii"):
                continue
            lines.append(f"  dimension {dim['name']} ({dim.get('type', '')})")
    return "\n".join(lines)
