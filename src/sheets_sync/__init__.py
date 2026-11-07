"""Schema-driven one-way sync of keyed records into a Google Sheets tab."""

from __future__ import annotations

import datetime
import decimal
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

__all__ = [
    "Column",
    "ColumnKind",
    "ErrorCode",
    "RangeUpdate",
    "SheetSchema",
    "SheetsPort",
    "SyncError",
    "SyncPlan",
    "__version__",
    "column_letter",
    "escape_sheet_title",
    "plan_sync",
    "serialize",
    "sync",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

ColumnKind = Literal["str", "int", "decimal", "bool", "date"]
ErrorCode = Literal[
    "invalid_schema",
    "invalid_range",
    "header_mismatch",
    "duplicate_key",
    "invalid_value",
    "too_many_rows",
]

MAX_CELL_CHARS = 50_000
MAX_COLUMNS = 702
MAX_COLUMN_INDEX = 18_278
MAX_INPUT_PREVIEW = 200


class SyncError(Exception):
    """Base exception raised by sheets_sync operations with a stable machine-readable code."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message: str = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


def _truncate(value: object, max_len: int = MAX_INPUT_PREVIEW) -> str:
    val_str = str(value)
    if len(val_str) > max_len:
        return val_str[:max_len] + "..."
    return val_str


@dataclass(frozen=True)
class Column:
    """Definition of a sheet column."""

    name: str
    kind: ColumnKind
    key: bool = False


@dataclass(frozen=True)
class SheetSchema:
    """Schema definition for a Google Sheet tab."""

    columns: tuple[Column, ...]

    def __post_init__(self) -> None:
        if not (1 <= len(self.columns) <= MAX_COLUMNS):
            raise SyncError(
                "invalid_schema",
                f"Schema must contain between 1 and {MAX_COLUMNS} columns, got {len(self.columns)}",
            )
        names: set[str] = set()
        key_count = 0
        for col in self.columns:
            if not isinstance(col.name, str) or not col.name.strip():
                raise SyncError("invalid_schema", "Column name must be a non-empty string")
            if col.name in names:
                raise SyncError("invalid_schema", f"Duplicate column name: '{col.name}'")
            names.add(col.name)
            if col.key:
                key_count += 1
        if key_count != 1:
            raise SyncError(
                "invalid_schema",
                f"Schema must have exactly one key column, got {key_count}",
            )

    @property
    def key_column(self) -> Column:
        for col in self.columns:
            if col.key:
                return col
        raise SyncError("invalid_schema", "No key column defined")

    @property
    def key_index(self) -> int:
        for idx, col in enumerate(self.columns):
            if col.key:
                return idx
        raise SyncError("invalid_schema", "No key column defined")


def column_letter(index: int) -> str:
    """Convert 1-based column index to A1 column letter (bijective base 26)."""
    if index < 1 or index > MAX_COLUMN_INDEX:
        raise SyncError(
            "invalid_range",
            f"Column index {index} out of valid range 1..{MAX_COLUMN_INDEX}",
        )
    result: list[str] = []
    curr = index
    while curr > 0:
        curr -= 1
        result.append(chr(ord("A") + (curr % 26)))
        curr //= 26
    return "".join(reversed(result))


def escape_sheet_title(sheet_title: str) -> str:
    """Escape a sheet title for A1 notation: always single-quoted with inner quotes doubled."""
    escaped = sheet_title.replace("'", "''")
    return f"'{escaped}'"


def serialize(column: Column, value: object) -> str:
    """Serialize a python object into Google Sheets string representation based on column type."""
    if value is None:
        if column.key:
            raise SyncError(
                "invalid_value",
                f"Key column '{column.name}' cannot be None",
            )
        return ""

    serialized: str
    kind = column.kind
    if kind == "str":
        if not isinstance(value, str):
            raise SyncError(
                "invalid_value",
                f"Column '{column.name}' expected str, got {type(value).__name__}",
            )
        serialized = value
    elif kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SyncError(
                "invalid_value",
                f"Column '{column.name}' expected int, got {type(value).__name__}",
            )
        serialized = str(value)
    elif kind == "decimal":
        if isinstance(value, bool):
            raise SyncError(
                "invalid_value",
                f"Column '{column.name}' expected decimal/int, got bool",
            )
        if isinstance(value, decimal.Decimal):
            if not value.is_finite():
                raise SyncError(
                    "invalid_value",
                    f"Column '{column.name}' decimal value must be finite",
                )
            serialized = str(value)
        elif isinstance(value, int):
            serialized = str(value)
        else:
            raise SyncError(
                "invalid_value",
                f"Column '{column.name}' expected Decimal or int, got {type(value).__name__}",
            )
    elif kind == "bool":
        if not isinstance(value, bool):
            raise SyncError(
                "invalid_value",
                f"Column '{column.name}' expected bool, got {type(value).__name__}",
            )
        serialized = "TRUE" if value else "FALSE"
    elif kind == "date":
        if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
            raise SyncError(
                "invalid_value",
                f"Column '{column.name}' expected datetime.date, got {type(value).__name__}",
            )
        serialized = value.isoformat()
    else:
        raise SyncError("invalid_schema", f"Unsupported column kind: {kind}")

    if column.key and not serialized:
        raise SyncError(
            "invalid_value",
            f"Key column '{column.name}' serialized to empty string",
        )

    if len(serialized) > MAX_CELL_CHARS:
        preview = _truncate(serialized)
        raise SyncError(
            "invalid_value",
            f"Column '{column.name}' value exceeds maximum cell limit of "
            f"{MAX_CELL_CHARS} chars: {preview}",
        )

    return serialized


@dataclass(frozen=True)
class RangeUpdate:
    """A single batch range update in A1 notation."""

    range_a1: str
    values: list[list[str]]


@dataclass(frozen=True)
class SyncPlan:
    """Result of computing a sync plan."""

    updates: list[RangeUpdate]
    appends: list[list[str]]
    unchanged: int
    cleared: int


class SheetsPort(Protocol):
    """Protocol for interacting with the Google Sheets API."""

    def read_values(self, range_a1: str) -> list[list[str]]:
        """Read a 2D grid of string values from the specified A1 range."""
        ...

    def batch_update(
        self, updates: Sequence[RangeUpdate], *, value_input_option: Literal["RAW"]
    ) -> None:
        """Update multiple ranges with RAW cell values."""
        ...

    def append_rows(
        self, range_a1: str, rows: Sequence[Sequence[str]], *, value_input_option: Literal["RAW"]
    ) -> None:
        """Append rows to the sheet with RAW cell values."""
        ...


def plan_sync(
    schema: SheetSchema,
    sheet_title: str,
    values: list[list[str]],
    records: Sequence[Mapping[str, object]],
    *,
    delete_missing: bool = False,
    max_rows: int = 10_000,
) -> SyncPlan:
    """Compute a deterministic synchronization plan between spreadsheet values and records."""
    if len(records) > max_rows:
        raise SyncError(
            "too_many_rows",
            f"Record count {len(records)} exceeds maximum of {max_rows} rows",
        )

    num_cols = len(schema.columns)
    last_col_letter = column_letter(num_cols)
    quoted_title = escape_sheet_title(sheet_title)

    # Validate header row
    if not values:
        raise SyncError("header_mismatch", "Sheet is empty, missing header row")
    header_row = values[0]
    expected_headers = [col.name for col in schema.columns]
    if len(header_row) < num_cols or [header_row[i] for i in range(num_cols)] != expected_headers:
        raise SyncError(
            "header_mismatch",
            f"Header mismatch: expected {expected_headers}, got {header_row[:num_cols]}",
        )

    # Trim trailing completely empty rows from sheet values
    data_rows = values[1:]
    while data_rows:
        last_row = data_rows[-1]
        if not last_row or all(c == "" for c in last_row):
            data_rows.pop()
        else:
            break

    key_idx = schema.key_index
    empty_row_cells = ["" for _ in range(num_cols)]

    # Parse existing sheet rows
    sheet_keys: dict[str, int] = {}
    sheet_rows_padded: dict[int, list[str]] = {}
    for offset, raw_row in enumerate(data_rows):
        sheet_row_num = offset + 2  # row 1 is header
        # Pad or slice to num_cols
        padded = list(raw_row[:num_cols]) + ["" for _ in range(max(0, num_cols - len(raw_row)))]
        key_val = padded[key_idx]
        if not key_val:
            col_name = schema.columns[key_idx].name
            raise SyncError(
                "invalid_value",
                f"Empty key in sheet row {sheet_row_num} for key column '{col_name}'",
            )
        if key_val in sheet_keys:
            raise SyncError(
                "duplicate_key",
                f"Duplicate key '{_truncate(key_val)}' found in sheet row {sheet_row_num}",
            )
        sheet_keys[key_val] = sheet_row_num
        sheet_rows_padded[sheet_row_num] = padded

    # Validate and serialize input records
    record_keys: set[str] = set()
    record_rows: list[tuple[str, list[str]]] = []
    for rec_idx, rec in enumerate(records):
        serialized_row: list[str] = []
        for col in schema.columns:
            if col.name not in rec:
                raise SyncError(
                    "invalid_value",
                    f"Record index {rec_idx} missing required column '{col.name}'",
                )
            cell_val = serialize(col, rec[col.name])
            serialized_row.append(cell_val)
        key_val = serialized_row[key_idx]
        if key_val in record_keys:
            raise SyncError(
                "duplicate_key",
                f"Duplicate record key: '{_truncate(key_val)}'",
            )
        record_keys.add(key_val)
        record_rows.append((key_val, serialized_row))

    updates_by_row: dict[int, list[list[str]]] = {}
    appends: list[list[str]] = []
    unchanged = 0
    cleared = 0
    matched_sheet_rows: set[int] = set()

    for key_val, new_cells in record_rows:
        if key_val in sheet_keys:
            sheet_row_num = sheet_keys[key_val]
            matched_sheet_rows.add(sheet_row_num)
            existing_cells = sheet_rows_padded[sheet_row_num]
            if existing_cells == new_cells:
                unchanged += 1
            else:
                updates_by_row[sheet_row_num] = [new_cells]
        else:
            appends.append(new_cells)

    if delete_missing:
        for sheet_row_num in sheet_rows_padded:
            if sheet_row_num not in matched_sheet_rows:
                updates_by_row[sheet_row_num] = [list(empty_row_cells)]
                cleared += 1

    # Sort updates by sheet row number
    sorted_updates: list[RangeUpdate] = []
    for row_num in sorted(updates_by_row.keys()):
        range_a1 = f"{quoted_title}!A{row_num}:{last_col_letter}{row_num}"
        sorted_updates.append(RangeUpdate(range_a1=range_a1, values=updates_by_row[row_num]))

    return SyncPlan(
        updates=sorted_updates,
        appends=appends,
        unchanged=unchanged,
        cleared=cleared,
    )


def sync(
    port: SheetsPort,
    schema: SheetSchema,
    sheet_title: str,
    records: Sequence[Mapping[str, object]],
    *,
    delete_missing: bool = False,
    max_rows: int = 10_000,
) -> SyncPlan:
    """Read existing sheet, compute plan, and apply minimal batch updates and row appends."""
    if len(records) > max_rows:
        raise SyncError(
            "too_many_rows",
            f"Record count {len(records)} exceeds maximum of {max_rows} rows",
        )

    num_cols = len(schema.columns)
    last_col_letter = column_letter(num_cols)
    quoted_title = escape_sheet_title(sheet_title)
    read_range = f"{quoted_title}!A1:{last_col_letter}"

    values = port.read_values(read_range)
    plan = plan_sync(
        schema=schema,
        sheet_title=sheet_title,
        values=values,
        records=records,
        delete_missing=delete_missing,
        max_rows=max_rows,
    )

    if plan.updates:
        port.batch_update(plan.updates, value_input_option="RAW")

    if plan.appends:
        append_range = f"{quoted_title}!A1"
        port.append_rows(append_range, plan.appends, value_input_option="RAW")

    return plan
