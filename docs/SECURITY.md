# Security Model

## Threat Model

### Formula Injection

Standard Google Sheets API usage with `USER_ENTERED` allows strings starting with `=`, `+`, `-`, or `@` to be evaluated as spreadsheet formulas, risking data exfiltration. `sheets-sync` explicitly defends against this by enforcing `value_input_option="RAW"` in all `SheetsPort` calls. This ensures Google treats values strictly as literal strings.

## Limits and Defenses

- **Max Input**: Processing is limited to 10,000 records (`max_rows`) to prevent resource exhaustion.
- **Cell Size**: Cells exceeding 50,000 characters trigger an `invalid_value` error.
- **Logging**: Error messages truncate input representations at 200 characters to prevent credential leakage in logs.
- **Protocol**: The `SheetsPort` assumes the implementation is responsible for secure HTTPS communication; the library code itself strictly performs logic and orchestration.