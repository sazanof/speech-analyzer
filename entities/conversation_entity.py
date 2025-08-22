from typing import Optional

from sqlmodel import Field, JSON

from entities.mixins.created_updated import TimeStampMixin
from entities.mixins.id_column import IdColumnMixin
from models.conversation_model import ConversationAnalysis


class ConversationBase:
    recording_id: Optional[int] = None
    speaker:str = Field(nullable=True, index=True)
    text:str = Field(nullable=True)
    text_with_highlights:str = Field(nullable=True)
    start_time:float = Field(nullable=True)
    end_time:float = Field(nullable=True)
    analysis: ConversationAnalysis = Field(nullable=True, default=None, sa_type=JSON)

class ConversationEntity(TimeStampMixin, ConversationBase,IdColumnMixin, table=True):
    __tablename__ = "conversations"
