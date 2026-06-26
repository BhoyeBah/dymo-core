# Contributing

Thanks for improving Dymo SaaS Core.

## Rules

- Keep the repository core-only.
- Do not add business modules directly to the package.
- Prefer small, focused changes with tests.
- Update documentation when public behavior changes.

## Checks

- Run `PYTHONPATH=src pytest`.
- Run `pip install -e .`.
- Run `python -m build`.
- Run `dymo-saas --help`.
