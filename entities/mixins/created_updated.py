from datetime import datetime
from sqlmodel import Field


class TimeStampMixin:
    created: datetime = Field(default_factory=datetime.now, nullable=False)

    updated: datetime | None = Field(default_factory=datetime.now, nullable=False)

