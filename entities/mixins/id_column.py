from sqlmodel import Field
from sqlmodel import SQLModel


class IdColumnMixin(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
