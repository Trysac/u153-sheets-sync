# Testing

## Test Coverage

The project uses `pytest` and `pytest-cov` to ensure branch coverage of the `src/sheets_sync` package is maintained at or above 80%.

## Existing Tests

- **`tests/test_sheets_sync.py`**: Contains unit tests for the core logic:
  - Validates `column_letter` bijective conversion logic (e.g., 1->A, 26->Z, 702->ZZ, 703->AAA, 18278->ZZZ).
  - Exercises the `SheetSchema` validation, including duplicate key detection and column name checks.
  - Verifies `plan_sync` logic for updates, appends, and `delete_missing` behavior.
  - Tests `serialize` with all supported types and boundary conditions (huge strings).
  - Uses `FakeSheets` (an in-memory `SheetsPort` implementation) to record calls and assert sync behavior without network access.