# models/dictionary_entity.py
from typing import List, Optional
from enum import Enum
from sqlmodel import SQLModel, Field, Column, JSON

class DictionaryType(str, Enum):
    CLIENT = "client"
    OPERATOR = "operator"
    BOTH = "both"

class DictionaryBase(SQLModel):
    name: str = Field(
        index=True,
        nullable=False
    )
    type: str = Field(
        default=DictionaryType.BOTH, index=True
    )
    phrases: List[str] = Field(
        sa_column=Column(JSON), default_factory=list
    )
    description: Optional[str] = Field(
        default=None
    )
    color: Optional[str] = Field(default="#CCCCCC")

class DictionaryEntity(DictionaryBase, table=True):
    __tablename__ = "dictionaries"
    id: Optional[int] = Field(
        default=None,
        index=True,
        primary_key=True
    )

class DictionaryCreate(DictionaryBase):
    pass

class DictionaryRead(DictionaryBase):
    id: int

class DictionaryUpdate(SQLModel):
    name: Optional[str] = None
    type: Optional[DictionaryType] = None
    phrases: Optional[List[str]] = None
    description: Optional[str] = None
    color: Optional[str] = None

