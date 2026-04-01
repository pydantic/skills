---
name: pydantic-validation
description: >
  Expert guidance on Pydantic v2 models, validators, serialization, and schema generation.
  Use when the user imports pydantic, defines BaseModel subclasses, encounters ValidationError,
  asks about field validators, model configuration, JSON Schema, or migrating from Pydantic v1.
  Also use when the user asks about data validation, type coercion, or serialization in Python.
license: MIT
metadata:
  version: "1.0.0"
  author: pydantic
---

# Pydantic v2 Validation Skill

Pydantic is a Python library for data validation using type annotations. This skill provides patterns, best practices, and debugging guidance for Pydantic v2.

## When to Use This Skill

Invoke this skill when:
- User imports `pydantic`, defines `BaseModel` subclasses, or uses `TypeAdapter`
- User encounters a `ValidationError` and needs help debugging it
- User asks about field validators, model validators, or custom types
- User wants to generate or customize JSON Schema from models
- User is migrating from Pydantic v1 to v2
- User asks about data validation, serialization, or type coercion in Python

Do **not** use this skill for:
- Pydantic AI agents (`pydantic_ai`) — use the pydantic-ai skill instead
- Logfire observability — use the logfire skill instead
- General Python development unrelated to data validation

## Core Concepts

### Model Definition

```python
from pydantic import BaseModel, Field, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(strict=False, frozen=False)

    name: str
    age: int = Field(ge=0, le=150, description="User age in years")
    email: str | None = None
```

- Use type annotations for field types — Pydantic infers validation from them
- Use `Field(...)` only when you need constraints (`ge`, `le`, `min_length`, `pattern`) or metadata (`description`, `alias`)
- Set `model_config = ConfigDict(...)` for model-level behavior — only when non-default behavior is needed

### Validation Modes

Pydantic validates in three modes:

| Mode | Method | Input | Notes |
|---|---|---|---|
| **Python** | `Model(...)`, `model_validate(data)` | dict, model instance, or dataclass | Default mode |
| **JSON** | `model_validate_json(json_str)` | JSON string or bytes | Faster than `json.loads` + `model_validate` (single Rust pass) |
| **Strings** | `model_validate_strings(data)` | dict with all string values | Useful for form data, query params |

**Performance tip:** Prefer `model_validate_json()` over `json.loads()` + `model_validate()` — it skips the intermediate Python dict and validates directly from JSON in Rust.

### Validator Types

| Decorator | Mode | When it runs | Use case |
|---|---|---|---|
| `@field_validator('x', mode='before')` | Before Pydantic parsing | Before type coercion | Coerce raw input (e.g., string → int) |
| `@field_validator('x', mode='after')` | After Pydantic parsing | After type coercion | Business rules on typed value |
| `@field_validator('x', mode='plain')` | Replaces Pydantic parsing | Instead of default validation | Full custom type handling |
| `@field_validator('x', mode='wrap')` | Wraps Pydantic parsing | Around default validation | Most flexible — receives `handler` callable |
| `@model_validator(mode='before')` | Before all field validation | Before any parsing | Transform raw input dict |
| `@model_validator(mode='after')` | After all field validation | After full model is built | Cross-field validation |
| `@model_validator(mode='wrap')` | Wraps full model validation | Around all validation | Full control over model construction |

```python
from pydantic import BaseModel, field_validator, model_validator


class Order(BaseModel):
    item: str
    quantity: int
    price_cents: int

    @field_validator('quantity', mode='after')
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('quantity must be positive')
        return v

    @model_validator(mode='after')
    def total_must_be_reasonable(self) -> 'Order':
        total = self.quantity * self.price_cents
        if total > 100_000_00:  # $100,000
            raise ValueError('order total exceeds maximum')
        return self
```

**Key rules:**
- Always use `@field_validator` (not v1's `@validator`) with explicit `mode=`
- **Never use `assert`** in validators — assertions are skipped with `python -O`. Use `raise ValueError(...)` instead.
- Field validators must be `@classmethod` and return the validated value
- Model validators with `mode='after'` receive the model instance (`self`), not a dict

### ValidationError Structure

```python
from pydantic import BaseModel, ValidationError

try:
    User(name=123, age="not a number")
except ValidationError as e:
    print(e.errors())      # List of error dicts
    print(e.error_count())  # Number of errors
    print(str(e))           # Human-readable summary
```

Each error dict contains:
- `loc` — field path as a tuple (e.g., `('address', 'zip_code')` for nested models)
- `msg` — human-readable error message
- `type` — error type string (e.g., `'int_parsing'`, `'value_error'`, `'missing'`)
- `input` — the actual value that failed validation
- `ctx` — extra context (e.g., `{'ge': 0}` for constraint errors)

**Error types to know:**
- `value_error` — raised from `ValueError` in a validator
- `assertion_error` — from `assert` in a validator (**avoid** — skipped with `-O` flag)
- `missing` — required field not provided
- `int_parsing`, `str_type`, etc. — type coercion failures
- Custom: use `PydanticCustomError('error_type', 'message {var}', {'var': val})`

### TypeAdapter

For validating types that aren't BaseModel subclasses:

```python
from pydantic import TypeAdapter

# Instantiate ONCE at module level — not inside functions
UserListAdapter = TypeAdapter(list[User])

users = UserListAdapter.validate_python([{"name": "Alice", "age": 30}])
json_bytes = UserListAdapter.dump_json(users)
schema = UserListAdapter.json_schema()
```

**Performance:** `TypeAdapter.__init__` builds the validation schema. Instantiating inside a function rebuilds it on every call. Always define at module level.

### Serialization

```python
user = User(name="Alice", age=30)

user.model_dump()                          # → dict
user.model_dump(exclude_none=True)         # omit None fields
user.model_dump(include={'name'})          # only specified fields
user.model_dump(by_alias=True)             # use field aliases

user.model_dump_json()                     # → JSON string (fast, via Rust)
user.model_dump_json(indent=2)             # pretty-printed JSON
```

Custom serialization with `@field_serializer`:

```python
from pydantic import BaseModel, field_serializer
from datetime import datetime


class Event(BaseModel):
    timestamp: datetime

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()
```

### JSON Schema

```python
# Output schema (after serialization transforms)
schema = User.model_json_schema()

# Validation-mode schema (what the model accepts as input)
schema = User.model_json_schema(mode='validation')

# Serialization-mode schema (what model_dump/model_dump_json produces)
schema = User.model_json_schema(mode='serialization')
```

These can differ when custom serializers change the output type. Use `mode='validation'` for API request schemas, `mode='serialization'` for API response schemas.

### Settings Management

```python
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    model_config = ConfigDict(env_prefix='APP_')

    database_url: str
    debug: bool = False
    port: int = 8000
```

`pydantic-settings` reads from environment variables, `.env` files, and other sources. Install separately: `pip install pydantic-settings`.

## Common Gotchas

These are mistakes that agents commonly make with Pydantic. Getting these wrong produces silent failures or confusing errors.

- **`@validator` is v1 — use `@field_validator`**: The v1 `@validator` decorator still works but is deprecated. Always use `@field_validator` with explicit `mode=`.
- **`assert` in validators is dangerous**: `assert` statements are removed when Python runs with `-O` (optimize). This silently disables your validation. Use `raise ValueError(...)`.
- **`model_validate` vs constructor**: `Model(**data)` and `Model.model_validate(data)` behave identically for dicts. Use `model_validate` when the input might be a model instance or when you want `from_attributes=True`.
- **`from_attributes=True` for ORM objects**: Set `model_config = ConfigDict(from_attributes=True)` when validating SQLAlchemy, Django, or other ORM instances. Without it, `model_validate(orm_obj)` fails.
- **Forward references need `model_rebuild()`**: If model A references model B which is defined later, call `A.model_rebuild()` after both are defined. Don't use v1's `update_forward_refs()`.
- **`TypeAdapter` in a loop**: Instantiating `TypeAdapter` inside a function or loop rebuilds the schema every time. Define it at module level.
- **`model_dump()` vs `dict()`**: In v2, `dict(model)` still works but is deprecated. Use `model.model_dump()`.

## v1 to v2 Migration

| v1 | v2 |
|---|---|
| `@validator('field')` | `@field_validator('field', mode='before'/'after')` |
| `@root_validator` | `@model_validator(mode='before'/'after')` |
| `parse_raw_as(Type, data)` | `TypeAdapter(Type).validate_json(data)` |
| `parse_obj_as(Type, data)` | `TypeAdapter(Type).validate_python(data)` |
| `.parse_raw(data)` | `.model_validate_json(data)` |
| `.parse_obj(data)` / `.from_orm(obj)` | `.model_validate(data)` (set `from_attributes=True`) |
| `.json()` | `.model_dump_json()` |
| `.dict()` | `.model_dump()` |
| `.schema()` | `.model_json_schema()` |
| `update_forward_refs()` | `model_rebuild()` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `Field(regex=...)` | `Field(pattern=...)` |
| `constr(min_length=1)` | `Annotated[str, Field(min_length=1)]` |
