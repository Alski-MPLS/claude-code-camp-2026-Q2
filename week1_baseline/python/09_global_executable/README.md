# Step 9 — Global Executable

Package BOUKENSHA as an installable distribution so the `boukensha` command works from anywhere on your machine.

## What this step adds

- `[project.scripts]` in `pyproject.toml` — declares the `boukensha` console-script entry point, pointing at `boukensha_loader:main`
- `src/boukensha_loader.py` — resolves *which step folder* to load from, then boots the REPL
- `src/boukensha/` — step 8's package, bundled as the default

## Install

```bash
cd 09_global_executable
uv tool install --editable .
```

After that, `boukensha` is on your `$PATH` and works from any directory. (Prefer to try it without a global install first? `uv run boukensha` from this directory does the same thing.)

## Switching steps with BOUKENSHA_PATH

The loader resolves in this order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `BOUKENSHA_PATH` env var | `BOUKENSHA_PATH=~/Sites/boukensha/python/08_the_repl_loop boukensha` |
| 2 | `~/.boukensharc` file | `echo ~/Sites/boukensha/python/08_the_repl_loop > ~/.boukensharc` |
| 3 | Bundled default | just run `boukensha` |

`BOUKENSHA_PATH` must point to a step folder that contains `src/boukensha/__init__.py`.

## Running a specific step

```bash
# step 8 (interactive REPL)
BOUKENSHA_PATH=~/Sites/boukensha/python/08_the_repl_loop boukensha

# step 7 doesn't have a REPL — the loader tells you how to run it instead
BOUKENSHA_PATH=~/Sites/boukensha/python/07_the_run_dsl boukensha
# => boukensha: the step at .../07_the_run_dsl does not support the interactive REPL
#    Run its examples directly, e.g.: python .../07_the_run_dsl/examples/*.py
```

## Debug mode

```bash
BOUKENSHA_DEBUG=1 boukensha
# => [boukensha] loading from: /path/to/step/src
```

## The key idea

The distribution is just a **wrapper and a default**. All the teaching material stays in the numbered step folders exactly as it was. `boukensha_loader.py` doesn't copy or symlink anything — it just knows where to look, and dynamically imports whichever `boukensha` package it finds there.

## Running the tests

```sh
cd week1_baseline/python/09_global_executable
uv sync --group dev
uv run pytest tests/ -v
```
