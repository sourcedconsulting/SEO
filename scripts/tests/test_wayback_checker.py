# tests/test_wayback_checker.py — stand-alone (no pytest required)
import pathlib, sys, inspect

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import wayback_checker as mod

# ── import surface ──
for attr in ("ia_available", "ia_cdx", "archive_today", "google_site",
             "format_report", "slugify", "http_get"):
    assert hasattr(mod, attr), f"missing {attr}"

# module constants
assert mod.CDX_URL.startswith("https://web.archive.org/cdx/")

# ── function signatures ──
def sig(func):
    """Return (func_name, list_of_param_names) for a top-level function."""
    params = list(inspect.signature(func).parameters)
    return (func.__name__, params)

services = {sig(getattr(mod, a))[0]: sig(getattr(mod, a))[1]
            for a in ("ia_available", "ia_cdx", "archive_today", "google_site")}

assert services["ia_available"] == ["domain"], services
assert services["ia_cdx"]       == ["domain"], services
assert services["archive_today"] == ["domain"], services
assert services["google_site"]   == ["domain"], services

# ── format_report ──
dummy_wb = {"service": "ia_available", "status": "archived", "available": True,
            "url": "https://web.archive.org/web/2025", "timestamp": "20250101",
            "http_code": 200}
dummy_gi = {"service": "google_site", "status": "not_indexed", "available": True,
            "summary": "not in Google index results"}

report = mod.format_report("https://example.com", [dummy_wb, dummy_gi])
assert "example.com" in report, repr(report)

print("All wayback_checker checks passed.")
