# routes/dictionaries.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from database.database import write_session
from entities.dictionary_entity import DictionaryEntity, DictionaryCreate, DictionaryRead, DictionaryUpdate, DictionaryType

dictionaries = APIRouter(prefix="/dictionaries", tags=["dictionaries"])

def get_db():
    with write_session() as session:
        yield session

@dictionaries.post("", response_model=DictionaryRead)
def create_dictionary(
        dictionary: DictionaryCreate,
        session: Session = Depends(get_db)
):
    db_dict = DictionaryEntity.model_validate(
        dictionary.model_dump()
    )
    session.add(db_dict)
    session.commit()
    session.refresh(db_dict)
    return db_dict


@dictionaries.get("", response_model=List[DictionaryRead])
def read_dictionaries(session: Session = Depends(get_db)):
    dictionaries = session.exec(select(DictionaryEntity)).all()
    return dictionaries


@dictionaries.get("/{dict_id}", response_model=DictionaryRead)
def read_dictionary(dict_id: int, session: Session = Depends(get_db)):
    dictionary = session.get(DictionaryEntity, dict_id)
    if not dictionary:
        raise HTTPException(status_code=404, detail="Dictionary not found")
    return dictionary


@dictionaries.patch("/{dict_id}", response_model=DictionaryRead)
def update_dictionary(dict_id: int, dictionary: DictionaryUpdate, session: Session = Depends(get_db)):
    db_dict = session.get(DictionaryEntity, dict_id)
    if not db_dict:
        raise HTTPException(status_code=404, detail="Dictionary not found")

    dict_data = dictionary.model_dump(exclude_unset=True)
    for key, value in dict_data.items():
        setattr(db_dict, key, value)

    session.add(db_dict)
    session.commit()
    session.refresh(db_dict)
    return db_dict


@dictionaries.delete("/{dict_id}")
def delete_dictionary(dict_id: int, session: Session = Depends(get_db)):
    dictionary = session.get(DictionaryEntity, dict_id)
    if not dictionary:
        raise HTTPException(status_code=404, detail="Dictionary not found")
    session.delete(dictionary)
    session.commit()
    return {"ok": True}