from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from database.database import write_session
from entities.enums.recording_task_status import RecordingTaskStatus
from entities.recording_entity import RecordingEntity
from models.recording_models import RecordingPost
from models.success_response import SuccessResponse

recordings = APIRouter(
    prefix='/recordings',
    tags=['recordings']
)


@recordings.get('/{record_id}')
def get_recording(
        record_id: int
):
    with write_session() as sess:
        record = sess.get(RecordingEntity, record_id)
        if not record:
            return SuccessResponse(success=False)
        else:
            return SuccessResponse(data=record)


@recordings.post('')
def add_recording(
        model: RecordingPost
):
    with write_session() as sess:
        existing: RecordingEntity|None = sess.exec(
            select(RecordingEntity).where(RecordingEntity.path == model.path)
        ).first()
        if not existing:
            record = RecordingEntity(
                path=model.path,
                recognize_status=RecordingTaskStatus.NEW.value,
                analysis_status = RecordingTaskStatus.NEW.value,
            )
            sess.add(record)
            return SuccessResponse(
                data=record,
            )
        else:
            if (
                    existing.recognize_status == RecordingTaskStatus.FINISHED.value
                    and existing.analysis_status == RecordingTaskStatus.FINISHED.value
            ):
                existing.recognize_status = RecordingTaskStatus.NEW.value
                existing.analysis_status = RecordingTaskStatus.NEW.value
                sess.add(existing)
                return SuccessResponse(
                    data=existing
                )
        return SuccessResponse(
            success=False
        )

