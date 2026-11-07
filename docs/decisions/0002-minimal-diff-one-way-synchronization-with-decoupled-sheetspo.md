# Minimal diff one-way synchronization with decoupled SheetsPort and RAW input

Status: accepted (generated, pending human review)

## Context

Traditional spreadsheet synchronization approaches overwrite entire tabs or rely on heavy dependencies like pandas and gspread. Overwriting wipes non-synchronized manual columns, exhausts API quota rapidly, and creates formula-injection vulnerabilities when user data beginning with '=', '+', or '-' is interpreted as formulas.

## Decision

We implemented sheets_sync as a pure-standard-library diff engine. It generates precise single-row A1 RangeUpdate operations and appends for new keys, applying all writes through a SheetsPort protocol strictly configured with value_input_option='RAW'. Google Sheet titles are safely quoted and inner quotes escaped. Trailing empty rows are trimmed, and schema keys are strictly enforced.

## Consequences

The library runs fully offline for planning and testing without any Google cloud dependencies or mock network layers. Users obtain deterministic, minimal batch update operations while preventing spreadsheet formula injection.
