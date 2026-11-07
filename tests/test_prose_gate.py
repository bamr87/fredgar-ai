"""The markdown prose gate must behave the same locally as in CI (issue #118).

`CHANGELOG.md` is written by release-please and may never be edited by hand, so
every documented way to run `tools/unwrap-prose.py` has to carry the excludes
CI uses. They live once, in the Makefile's `PROSE_EXCLUDES`; the workflow and
the docs point at `make prose` / `make prose-fix`. This test fails when a doc or
the workflow goes back to a bare invocation, or when the gate stops excluding
`CHANGELOG.md` while still catching soft-wrapped prose elsewhere.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "unwrap-prose.py"
DOCUMENTED = ["AGENTS.md", "tools/README.md", ".github/workflows/markdown-oneline.yml"]

# The Docker CI image copies only src/, tests/ and data/reference/.
pytestmark = pytest.mark.skipif(
    not SCRIPT.is_file() or not (ROOT / "Makefile").is_file(),
    reason="no tools/ or Makefile in this tree (Docker CI image)",
)


def _excludes() -> list[str]:
    m = re.search(r"^PROSE_EXCLUDES\s*:=\s*(.+)$", (ROOT / "Makefile").read_text(), re.M)
    assert m, "Makefile must define PROSE_EXCLUDES"
    return [p.replace("$$", "$") for p in re.findall(r"'([^']+)'", m.group(1))]


def test_makefile_excludes_release_please_and_schema_files():
    pats = _excludes()
    assert any(re.search(p, "CHANGELOG.md") for p in pats)
    assert any(re.search(p, "docs/SCHEMA.md") for p in pats)
    assert not any(re.search(p, "docs/releasing.md") for p in pats)


def test_ci_runs_the_make_target():
    wf = (ROOT / ".github/workflows/markdown-oneline.yml").read_text()
    assert re.search(r"^\s*make prose\b", wf, re.M), "markdown-oneline must run `make prose`"


@pytest.mark.parametrize("rel", DOCUMENTED)
def test_no_documented_bare_invocation(rel):
    text = (ROOT / rel).read_text()
    bare = [
        line.strip()
        for line in text.splitlines()
        if re.search(r"unwrap-prose\.py --(check|write)", line) and "--exclude" not in line
    ]
    assert not bare, f"{rel} documents the prose gate without CI's excludes: {bare}"


def _gate(tmp_path: Path, files: dict[str, str]) -> subprocess.CompletedProcess:
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    args = [arg for p in _excludes() for arg in ("--exclude", p)]
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--check", *args],
        cwd=tmp_path, capture_output=True, text=True,
    )


def test_gate_skips_changelog_but_catches_wrapped_prose(tmp_path):
    wrapped = "A paragraph that is\nsoft wrapped across lines.\n"
    (tmp_path / "ok").mkdir()
    (tmp_path / "bad").mkdir()
    ok = _gate(tmp_path / "ok", {"CHANGELOG.md": "# Changelog\n\n" + wrapped})
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = _gate(tmp_path / "bad", {"notes.md": wrapped})
    assert bad.returncode == 1 and "notes.md" in bad.stdout, bad.stdout + bad.stderr
