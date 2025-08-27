from datetime import datetime

from pydantic import BaseModel, Field

from entities.enums.recording_task_status import RecordingTaskStatus
from models.recognizer_models import Utterance


class RecordingPost(BaseModel):
    path:str = Field()


class RecordingGet(BaseModel):
    id:int
    path: str
    analysis_status: RecordingTaskStatus
    recognize_status: RecordingTaskStatus
    duration:float|None = None
    conversation:list[Utterance]|None = None
    created:datetime|None
    updated:datetime|None = None
    recognize_start: datetime | None = None
    recognize_end: datetime | None  = None
    analysis_start: datetime | None  = None
    analysis_end: datetime | None  = None