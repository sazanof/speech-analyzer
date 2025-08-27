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
    recognize_status: int = Field(
        default=RecordingTaskStatus.NEW.value,
        index=True
    )
    analysis_status: int = Field(
        default=RecordingTaskStatus.NEW.value,
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

    # Хелпер-методы для удобства
    def get_recognize_status_enum(self) -> RecordingTaskStatus:
        return RecordingTaskStatus(self.recognize_status)

    def set_recognize_status_enum(self, status: RecordingTaskStatus):
        self.recognize_status = status.value

    def get_analysis_status_enum(self) -> RecordingTaskStatus:
        return RecordingTaskStatus(self.analysis_status)

    def set_analysis_status_enum(self, status: RecordingTaskStatus):
        self.analysis_status = status.value


class RecordingEntity(
    TimeStampMixin,
    RecordingEntityBase,
    IdColumnMixin,
    table=True
):
    __tablename__ = "recordings"
