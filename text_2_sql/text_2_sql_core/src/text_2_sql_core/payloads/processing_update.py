from pydantic import BaseModel


class ProcessingUpdate(BaseModel):
    title: str
    message: str
