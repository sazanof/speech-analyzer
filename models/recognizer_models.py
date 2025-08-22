from typing import List

from pydantic import BaseModel
# Pydantic модели для структурирования данных
class Utterance(BaseModel):
    speaker: str  # "Оператор" или "Клиент"
    text: str
    start_time: float
    end_time: float


class ConversationAnalysis(BaseModel):
    utterances: List[Utterance]
    duration: float