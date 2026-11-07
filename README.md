# sheets-sync

[![CI](https://github.com/Trysac/u153-sheets-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u153-sheets-sync/actions/workflows/ci.yml)

Schema-driven one-way sync of keyed records into a Google Sheets tab: pure diff plan with A1 ranges, typed cell serialisation and a port for the API.

## The Problem

Teams typically push database rows into a spreadsheet by clearing and rewriting the whole tab. This approach destroys manual columns, burns API quota and risks formula injection if user text is interpreted as formulas. This library computes a minimal, deterministic update plan from a schema and applies it through a `SheetsPort`, keeping the core logic tested without Google.

## Installation

`pip install sheets-sync` (Requires Python >= 3.10, no runtime dependencies).

## Usage

```python
from sheets_sync import Column, SheetSchema, plan_sync

schema = SheetSchema((Column("id", "str", key=True), Column("name", "str")))
values = [["id", "name"], ["1", "Old"]]
records = [{"id": "1", "name": "New"}]
plan = plan_sync(schema, "Stock", values, records)
print(f"Updates: {len(plan.updates)}, Appends: {len(plan.appends)}")
```

## Public API Summary

- **Column(name, kind, key=False)**: Defines a column with types 'str', 'int', 'decimal', 'bool', 'date'.
- **SheetSchema(columns)**: Validates 1-702 columns, unique names, and exactly one key.
- **plan_sync(...)**: Generates a `SyncPlan` (updates, appends, unchanged, cleared).
- **sync(port, ...)**: Reads existing sheet, plans, and applies minimal updates.
- **SheetsPort**: Protocol for `read_values`, `batch_update`, and `append_rows`.

### Errors

Raises `SyncError` with codes: `invalid_schema`, `invalid_range`, `header_mismatch`, `duplicate_key`, `invalid_value`, `too_many_rows`.

## Why not gspread-dataframe?

`gspread-dataframe` performs bulk sheet rewrites and requires heavy dependencies like pandas. `sheets-sync` computes a minimal, deterministic keyed diff, uses only the standard library, and is fully testable offline.

[See Security Model](docs/SECURITY.md)