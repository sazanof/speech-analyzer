from typing import Annotated

from fastapi import APIRouter, Depends

tags = APIRouter(
    prefix='/tags',
    tags=['tags']
)


@tags.get('')
def get_tags(

):
    return {}