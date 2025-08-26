from fastapi import APIRouter
from sqlmodel import select, asc

from database.database import write_session
from entities.conversation_entity import ConversationEntity
from models.conversation_model import ConversationHighlight, ConversationModel
from models.success_response import SuccessResponse

conversations = APIRouter(
    prefix='/conversations',
    tags=['conversations']
)


@conversations.get('/{record_id}', response_model=SuccessResponse)
def get_recording(
        record_id: int
):
    with write_session() as sess:
        conversations_orm: list[ConversationEntity] = sess.exec(
            select(ConversationEntity)
            .where(ConversationEntity.recording_id == record_id)
            .order_by(asc(ConversationEntity.id))
            .order_by(asc(ConversationEntity.start_time))
        ).all()
        if not conversations_orm:
            return SuccessResponse(success=False)
        else:
            return SuccessResponse(
                data=[
                    ConversationModel.model_validate(c.model_dump()) for c in conversations_orm
                ]
            )


@conversations.get('/{record_id}/dictionaries', response_model=SuccessResponse)
def get_recording(
        record_id: int
):
    with write_session() as sess:
        conversations_orm: list[ConversationEntity] = sess.exec(
            select(ConversationEntity)
            .where(ConversationEntity.recording_id == record_id)
            .order_by(asc(ConversationEntity.id))
            .order_by(asc(ConversationEntity.start_time))
        ).all()
        conversation_dictionaries: list[ConversationHighlight] = []
        if not conversations_orm:
            return SuccessResponse(success=False)
        else:
            _all = [ConversationModel.model_validate(c.model_dump()) for c in conversations_orm]
            for conversation in _all:
                if len(conversation.analysis.highlights) > 0:
                    for h in conversation.analysis.highlights:
                        founded = False
                        for d in conversation_dictionaries:
                            if d.dictionary_id == h.dictionary_id:
                                founded = True
                        if not founded:
                           conversation_dictionaries.append(h)
            return SuccessResponse(data=conversation_dictionaries)