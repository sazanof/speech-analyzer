from datetime import datetime

from sqlmodel import Field

from entities.enums.recording_task_status import RecordingTaskStatus
from entities.mixins.created_updated import TimeStampMixin
from entities.mixins.id_column import IdColumnMixin
from sqlalchemy import JSON

from models.recognizer_models import Utterance


class RecordingEntityBase:
    path: str = Field(
        nullable=False,
        index=True,
        unique=True,
    ),
    recognize_status: RecordingTaskStatus = Field(
        default=RecordingTaskStatus.NEW,
        index=True
    )
    analysis_status: RecordingTaskStatus = Field(
        default=RecordingTaskStatus.NEW,
        index=True
    )
    duration: float = Field(
        nullable=True
    )
    conversation: list[Utterance] = Field(
        sa_type=JSON,
        default=None,
        nullable=True
    )

    recognize_start: datetime | None = Field(nullable=True)
    recognize_end: datetime | None = Field(nullable=True)

    analysis_start: datetime | None = Field(nullable=True)
    analysis_end: datetime | None = Field(nullable=True)


class RecordingEntity(
    TimeStampMixin,
    RecordingEntityBase,
    IdColumnMixin,
    table=True
):
    __tablename__ = "recordings"
