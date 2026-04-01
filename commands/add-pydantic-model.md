---
name: add-pydantic-model
description: Scaffold a new Pydantic v2 BaseModel
---

# Add Pydantic BaseModel

Scaffold a new Pydantic v2 BaseModel for the described concept.

## Workflow

1. **Understand the model purpose**: Ask the user what data the model represents if not clear from context.

2. **Generate the model**:
   - Use type annotations for field types — prefer `str`, `int`, `float`, `bool`, `datetime`, `list[T]`, `dict[K, V]`, `T | None`
   - Use `Field(...)` only when constraints are needed (`ge`, `le`, `min_length`, `max_length`, `pattern`) or for metadata (`description`, `alias`, `examples`)
   - Add `model_config = ConfigDict(...)` only if non-default behavior is required (e.g., `frozen=True`, `from_attributes=True`, `str_strip_whitespace=True`)
   - Add a docstring explaining what the model represents

3. **Add validators only for business rules**:
   - Use `@field_validator('field', mode='after')` for business rules on typed values
   - Use `@field_validator('field', mode='before')` only when input coercion is genuinely needed
   - Use `@model_validator(mode='after')` for cross-field validation
   - **Never** use `assert` — always `raise ValueError(...)`
   - Don't add validators for things Pydantic already handles (type coercion, constraints)

4. **Follow these conventions**:
   - Import from `pydantic`, not `pydantic.v1`
   - Use `Annotated[type, Field(...)]` for constrained types shared across models
   - For API models: consider `alias` for camelCase JSON keys with snake_case Python attributes
   - For nested models: define child models before parent models, or use `model_rebuild()`
