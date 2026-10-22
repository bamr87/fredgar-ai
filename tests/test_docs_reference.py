"""The generated reference in docs/reference/ must match the source (UPS-DOC-05).

`tools/gen_reference.py` renders the API route table from the DRF router and the
management-command table from each command's `help` and `add_arguments`. This test
re-renders both and fails when a committed file is stale; the fix is always
`python3 tools/gen_reference.py --write`, never a hand edit.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _generator():
    spec = importlib.util.spec_from_file_location(
        "gen_reference", ROOT / "tools" / "gen_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_reference_is_current():
    stale = _generator().stale(ROOT)
    assert not stale, (
        f"stale generated reference: {', '.join(map(str, stale))} — "
        "run `python3 tools/gen_reference.py --write` and commit the result"
    )


def test_every_command_and_route_is_listed():
    gen = _generator()
    commands = gen.render_commands()
    for path in (ROOT / "src").glob("*/management/commands/*.py"):
        if not path.name.startswith("_"):
            assert f"| `{path.stem}` |" in commands, path
    routes = gen.render_routes()
    for needle in ("`/api/v1/health/`", "`/api/v1/companies/{pk}/sync-submissions/`"):
        assert needle in routes
