---
name: debug-validation-error
description: Debug a Pydantic ValidationError by analyzing its structured error output
---

# Debug Pydantic ValidationError

Analyze a Pydantic `ValidationError` and identify the root cause.

## Workflow

1. **Get the structured error output**: If the user has a `ValidationError`, call `.errors()` on it to get the list of error dicts. Each dict has `loc`, `msg`, `type`, `input`, and optionally `ctx`.

2. **Analyze each error**:
   - `loc` — the field path (e.g., `('address', 'zip_code')` for nested models). Trace this to the model definition.
   - `type` — the error type. Common types:
     - `missing` — required field not provided
     - `int_parsing`, `str_type` — type coercion failed
     - `value_error` — raised from `ValueError` in a validator
     - `assertion_error` — from `assert` in a validator (**convert to `ValueError`**)
   - `input` — the actual value that failed. Check if it's the right type or if coercion is needed.
   - `ctx` — constraint context (e.g., `{'ge': 0}` for `greater_than_equal` errors).

3. **Trace to source**: Find the model definition and the specific field or validator causing the error. Check:
   - Is the field type annotation correct?
   - Is there a `@field_validator` with the wrong `mode=`?
   - Is the input data in the expected format?

4. **Suggest the minimal fix**:
   - If the input is wrong: show how to fix the input data
   - If coercion is needed: add a `@field_validator('field', mode='before')` to transform the input
   - If `assertion_error`: convert `assert` to `raise ValueError(...)`
   - If a required field is missing: add a default value or make the field `Optional`

5. **Check for v1/v2 migration issues**: If the code uses `@validator`, `parse_obj`, `.dict()`, or `class Config:`, flag these as v1 patterns and suggest the v2 equivalents.
