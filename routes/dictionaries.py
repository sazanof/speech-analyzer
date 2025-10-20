# routes/dictionaries.py
from fastapi import APIRouter, HTTPException
from sqlmodel import select, update, col, delete
from typing import List

from database.database import write_session
from entities.dictionary_entity import DictionaryEntity, DictionaryCreate, DictionaryRead, DictionaryUpdate, DictionaryType
from entities.enums.recording_task_status import RecordingTaskStatus
from entities.recording_entity import RecordingEntity
from models.success_response import SuccessResponse

dictionaries = APIRouter(prefix="/dictionaries", tags=["dictionaries"])

def get_db():
    with write_session() as session:
        yield session

@dictionaries.post("", response_model=DictionaryRead)
def create_dictionary(
        dictionary: DictionaryCreate,
):
    with write_session() as session:
        try:
            db_dict = DictionaryEntity.model_validate(
                dictionary.model_dump()
            )
            session.add(db_dict)
            session.commit()
            session.refresh(db_dict)

            # Update all analyzed models
            # session.exec(
            #     update(RecordingEntity)
            #     .where(col(RecordingEntity.analysis_status).in_([
            #         RecordingTaskStatus.PENDING.value,
            #         RecordingTaskStatus.FAILED.value,
            #         RecordingTaskStatus.FINISHED.value,
            #     ]))
            #     .values(analysis_status=RecordingTaskStatus.NEW.value)
            # )

            return db_dict

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

@dictionaries.post("/restore", response_model=list[DictionaryRead])
def restore_all_dictionaries(
        _dictionaries: list[DictionaryCreate]
):
    with write_session() as session:
        try:
            session.exec(
                delete(DictionaryEntity)
            )
            ret = []
            for dictionary in _dictionaries:
                db_dict = DictionaryEntity.model_validate(
                    dictionary.model_dump()
                )
                session.add(db_dict)
                session.flush()
                ret.append(db_dict)
                # Update all analyzed models
                # session.exec(
                #     update(RecordingEntity)
                #     .where(col(RecordingEntity.analysis_status).in_([
                #         RecordingTaskStatus.PENDING.value,
                #         RecordingTaskStatus.FAILED.value,
                #         RecordingTaskStatus.FINISHED.value,
                #     ]))
                #     .values(analysis_status=RecordingTaskStatus.NEW.value)
                # )

            return ret
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))



@dictionaries.get("", response_model=List[DictionaryRead])
def read_dictionaries():
    with write_session() as session:
        try:
            return session.exec(select(DictionaryEntity)).all()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@dictionaries.get("/{dict_id}", response_model=DictionaryRead)
def read_dictionary(dict_id: int):
    with write_session() as session:
        try:
            dictionary = session.get(DictionaryEntity, dict_id)
            if not dictionary:
                raise HTTPException(status_code=404, detail="Dictionary not found")
            return dictionary
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@dictionaries.patch("/{dict_id}", response_model=DictionaryRead)
def update_dictionary(dict_id: int, dictionary: DictionaryUpdate):
    with write_session() as session:
        try:
            db_dict = session.get(DictionaryEntity, dict_id)
            if not db_dict:
                raise HTTPException(status_code=404, detail="Dictionary not found")

            dict_data = dictionary.model_dump(exclude_unset=True)
            for key, value in dict_data.items():
                setattr(db_dict, key, value)

            session.add(db_dict)
            session.commit()
            session.refresh(db_dict)

            # Update all analyzed models
            # session.exec(
            #     update(RecordingEntity)
            #     .where(col(RecordingEntity.analysis_status).in_([
            #         RecordingTaskStatus.PENDING.value,
            #         RecordingTaskStatus.FAILED.value,
            #         RecordingTaskStatus.FINISHED.value,
            #     ]))
            #     .values(analysis_status=RecordingTaskStatus.NEW.value)
            # )

            return db_dict
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@dictionaries.delete("/{dict_id}")
def delete_dictionary(dict_id: int):
    with write_session() as session:
        try:
            dictionary = session.get(DictionaryEntity, dict_id)
            if not dictionary:
                raise HTTPException(status_code=404, detail="Dictionary not found")
            session.delete(dictionary)
            session.commit()

            # Update all analyzed models
            # session.exec(
            #     update(RecordingEntity)
            #     .where(col(RecordingEntity.analysis_status).in_([
            #         RecordingTaskStatus.PENDING.value,
            #         RecordingTaskStatus.FAILED.value,
            #         RecordingTaskStatus.FINISHED.value,
            #     ]))
            #     .values(analysis_status=RecordingTaskStatus.NEW.value)
            # )

            return SuccessResponse()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

