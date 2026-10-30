# fredgar-ai tools

> Operator scripts for this repository — the generated-reference builder, the docs index and the markdown prose gate. Nothing here ships to users.

| Where | What |
| --- | --- |
| [`gen_reference.py`](gen_reference.py) | Generates `docs/reference/api-routes.md` (from the DRF router) and `docs/reference/management-commands.md` (from each command's `help` and options); `--write` or `--check`. Needs the Python requirements installed. |
| [`docs_index.py`](docs_index.py) | Regenerates the `docs/README.md` index from each document's summary line (`--write`, `--check`, `--lint`). Vendored byte-identical from the bamr87 hub — never edit it here. |
| [`unwrap-prose.py`](unwrap-prose.py) | Joins soft-wrapped prose lines so each Markdown paragraph is one line (`--check`, `--write`). Vendored from the bamr87 hub. |
