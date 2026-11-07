# Architecture & Design Decisions

## Overview

`sheets_sync` provides pure diff computation and synchronization of keyed records into a single Google Sheets tab.

### Components

1. **Schema & Serialization (`Column`, `SheetSchema`, `serialize`)**:
   - Maps typed Python data (`str`, `int`, `decimal.Decimal`, `bool`, `datetime.date`) into canonical Google Sheets string representations.
   - Enforces cell character limits (`<= 50,000` chars) and strictly rejects booleans masquerading as integers or decimals.
   - Rejects non-finite decimals (`NaN`, `Infinity`).
   - Strict 1-702 column limits, unique non-empty column names, and exactly one designated primary key column.

2. **A1 Notation & Title Quoting (`column_letter`, `escape_sheet_title`)**:
   - Bijective base-26 column conversion: 1 -> `A`, 26 -> `Z`, 27 -> `AA`, 702 -> `ZZ`, 703 -> `AAA`, 18278 -> `ZZZ`.
   - Sheet titles are quoted with single quotes, inner single quotes doubled (e.g. `O'Brien` -> `'O''Brien'`).

3. **Plan Computation (`plan_sync`)**:
   - Validates that sheet header matches expected schema columns.
   - Identifies changed rows and generates `RangeUpdate` objects sorted ascending by sheet row number.
   - Detects new rows and queues them in `appends` while preserving record insertion order.
   - If `delete_missing=True`, clears sheet rows whose keys are no longer present in input records.
   - Rejects duplicate keys in both sheet and incoming records.

4. **Execution Protocol (`SheetsPort`, `sync`)**:
   - Pure port pattern allowing callers to wire any Google API client or in-memory stub.
   - Writes are executed using `value_input_option="RAW"` to prevent formula injection.
