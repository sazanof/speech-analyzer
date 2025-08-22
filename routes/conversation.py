from fastapi import APIRouter
from sqlmodel import select, asc

from database.database import write_session
from entities.conversation_entity import ConversationEntity
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
        conversation = sess.exec(
            select(ConversationEntity)
            .where(ConversationEntity.recording_id == record_id)
            .order_by(asc(ConversationEntity.id))
            .order_by(asc(ConversationEntity.start_time))
        ).all()
        if not conversation:
            return SuccessResponse(success=False)
        else:
            return SuccessResponse(data=conversation)
