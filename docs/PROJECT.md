# Project Record

## Objective

Schema-driven one-way sync of keyed records into a Google Sheets tab: pure diff plan with A1 ranges, typed cell serialisation and a port for the API.

## Scope

- **In-Scope**: Typed schema definitions, deterministic diff planning, A1 notation generation, RAW value serialization, the `SheetsPort` protocol, and the public synchronization API.
- **Out-of-Scope**: Authentication, two-way merging, row reordering, sheet formatting, formula evaluation, processing multiple tabs per call, and rate limiting.

## Effort Metrics

| Metric | Value |
|---|---|
| Tokens (input / output) | 342605 / 13580 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.1125 |

## Factory run u153 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | gemini-3.8-flash | yes | 4449 | 11051 | 0 | 0 | 0.0224 |
| fix-1 | gemini-3.8-flash | no | 30966 | 1076 | 0 | 81813 | 0.0334 |
| audit | gemini-3.1-flash-lite | no | 25274 | 111 | 0 | 8137 | 0.0067 |
| docs | gemini-3.1-flash-lite | no | 191966 | 1342 | 0 | 0 | 0.0500 |

Total: $0.1125. Prices: Anthropic list prices.
