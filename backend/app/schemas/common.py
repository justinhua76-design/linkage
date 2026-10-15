from typing import Annotated

from pydantic import BaseModel, Field

# Finite JSON numbers only: strings such as "45", booleans, NaN and Infinity are
# rejected instead of coerced.
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class IssueOut(BaseModel):
    code: str
    field: str
    message: str
    severity: str


class ErrorEnvelope(BaseModel):
    status: str = "error"
    code: str
    message: str
    errors: list[IssueOut] = []
