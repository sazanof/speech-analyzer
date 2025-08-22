from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from classes.text_analyzer import TextAnalyzer
from database.database import write_session
from entities.dictionary_entity import DictionaryEntity
from entities.recording_entity import RecordingEntity
from models.recognizer_models import Utterance
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
        existing = sess.exec(
            select(RecordingEntity).where(RecordingEntity.path == model.path)
        ).first()
        if not existing:
            record = RecordingEntity(
                path=model.path
            )
            sess.add(record)
            return SuccessResponse(
                data=record,
            )
    return SuccessResponse(success=False)
