from enum import StrEnum
from typing import Dict, Optional, List

from pydantic import Field, BaseModel


class ConversationMatchType(StrEnum):
    EXACT = 'exact'
    FUZZY = 'fuzzy'
    PARTIAL = 'partial'


class ConversationHighlight(BaseModel):
    phrase: str
    start_pos: int
    end_pos: int
    dictionary_id: int
    dictionary_name: str
    match_type: str


class ConversationAnalysis(BaseModel):
    matched_phrases: Dict[int, List[str]] = {}
    rude_words: List[str] = []
    greetings: List[str] = []
    other_matches: Dict[str, List[str]] = {}
    highlights: List[ConversationHighlight] = []
    text_with_highlights: Optional[str] = None


class ConversationModel(BaseModel):
    recording_id: int
    speaker: str
    text: str
    text_with_highlights: Optional[str] = None
    start_time: float
    end_time: float
    analysis: ConversationAnalysis

class ConversationIdModel(ConversationModel):
    id:int
