from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel

class SuccessResponse(BaseModel):
    success: bool = True
    data: Union[None,Any] = None
    timestamp: datetime = datetime.now()