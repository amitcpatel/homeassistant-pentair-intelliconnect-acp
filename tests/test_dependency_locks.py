"""Dependency and key-scope guards (HOM-4828).

These tests are deliberately offline: they read repo files and installed
package metadata only. No network call is made and no key value is printed.
"""

from __future__ import annotations

import ast
from importlib import metadata
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "pentair_pool"
MANIFEST = json.loads((COMPONENT / "manifest.json").read_text())
PACKAGE_JSON = json.loads((ROOT / "package.json").read_text())
LOCK = json.loads((ROOT / "package-lock.json").read_text())

# First patched version for every advisory reported in HOM-4824 / HOM-4828.
PATCHED_FLOOR = {
    "@github/copilot": "1.0.43",  # GHSA-9ccr-r5hg-74gf
    "js-yaml": "4.3.2",  # GHSA-2883/52cp/5p4m/h67p (highest 4.x fix)
    "katex": "0.18.2",  # GHSA-238p-pmpm-9mq7
    "linkify-it": "5.0.2",  # GHSA-22p9-wv53-3rq4, GHSA-v245-v573-v5vm
    "markdown-it": "15.0.3",  # GHSA-253c/6v5v/gfr2/r7fv/vfgh (15.x fix)
    "smol-toml": "1.9.0",  # GHSA-7w5x/r4xh/v3rj (highest fix)
    # HOM-6003: GHSA-gg6h-894w-4m9c, affected >=2.2.0 <2.8.7. markdownlint
    # 0.42.0 pins 2.8.6 exactly, so package.json overrides it (to 2.9.1, the
    # version upstream markdownlint moved to in e862edfa).
    "re2js": "2.8.7",
}


def _ver(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("-", maxsplit=1)[0].split("."))


def _locked_versions(name: str) -> list[str]:
    suffix = f"node_modules/{name}"
    return [
        entry["version"] for path, entry in LOCK["packages"].items() if path == suffix or path.endswith("/" + suffix)
    ]


@pytest.mark.unit
@pytest.mark.parametrize(("name", "floor"), sorted(PATCHED_FLOOR.items()))
def test_lockfile_has_no_vulnerable_versions(name: str, floor: str) -> None:
    """Every locked copy of a flagged package is at or above its fix."""
    versions = _locked_versions(name)
    assert versions, f"{name} missing from package-lock.json"
    for version in versions:
        assert _ver(version) >= _ver(floor), f"{name} {version} < {floor}"


@pytest.mark.unit
def test_re2js_override_is_exact_and_patched() -> None:
    """The re2js override stays exact, patched, and is what the lock resolves.

    Guards against someone dropping the override when bumping markdownlint
    while markdownlint still pins a vulnerable re2js.
    """
    spec = PACKAGE_JSON["overrides"]["re2js"]
    assert spec[0].isdigit(), f"re2js override is not exact: {spec}"
    assert _ver(spec) >= _ver(PATCHED_FLOOR["re2js"])
    assert _locked_versions("re2js") == [spec]


@pytest.mark.unit
def test_dev_tool_pins_are_exact() -> None:
    """Dev tooling stays pinned exactly so the lockfile is reproducible."""
    for name, spec in PACKAGE_JSON["devDependencies"].items():
        assert spec[0].isdigit(), f"{name} is not pinned exactly: {spec}"


@pytest.mark.unit
def test_manifest_pins_pycognito_exactly() -> None:
    """The HA runtime requirement is one exact pin, not an open range."""
    reqs = MANIFEST["requirements"]
    assert len(reqs) == 1
    assert reqs[0].startswith("pycognito==")


@pytest.mark.unit
def test_manifest_pin_matches_tested_home_assistant() -> None:
    """The pin equals what the installed (tested) HA release ships with.

    HA's hass-nabucasa pins pycognito exactly, so a different pin would make
    HA's installer fight its own constraints at integration load.
    """
    pytest.importorskip("homeassistant")
    pinned = MANIFEST["requirements"][0].split("==", 1)[1]
    assert metadata.version("pycognito") == pinned
    nabucasa_reqs = metadata.requires("hass-nabucasa") or []
    assert f"pycognito=={pinned}" in [r.replace(" ", "") for r in nabucasa_reqs]


@pytest.mark.unit
def test_unauth_app_key_is_only_used_for_detect_user() -> None:
    """API_KEY_UNAUTH stays scoped to the unauthenticated pre-auth probe.

    The value is a vendor application key for the public detectUser
    endpoint, not a user credential. This guard fails if it ever spreads
    to authenticated calls, which would change that classification.
    """
    users = sorted(
        {
            f"{path.relative_to(ROOT)}:{func.name}"
            for path in COMPONENT.rglob("*.py")
            for func in ast.walk(ast.parse(path.read_text()))
            if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(func)
            if isinstance(node, ast.Name) and node.id == "API_KEY_UNAUTH"
        }
    )
    assert users == ["custom_components/pentair_pool/api/client.py:async_detect_user"]

    const_src = (COMPONENT / "const.py").read_text()
    assert "/unauth/" in const_src.split("DETECT_USER_URL", 1)[1].splitlines()[0]
