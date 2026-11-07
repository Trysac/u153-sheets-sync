# sheets-sync

[![PyPI version](https://img.shields.io/pypi/v/trysac-sheets-sync)](https://pypi.org/project/trysac-sheets-sync/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-sheets-sync)](LICENSE)
[![CI](https://github.com/Trysac/u153-sheets-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u153-sheets-sync/actions/workflows/ci.yml)

Schema-driven one-way sync of keyed records into a Google Sheets tab: pure diff plan with A1 ranges, typed cell serialisation and a port for the API

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-sheets-sync
# or
uv add trysac-sheets-sync
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import sheets_sync

# normalize() trims surrounding whitespace and lower-cases the text.
print(sheets_sync.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    sheets_sync.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
