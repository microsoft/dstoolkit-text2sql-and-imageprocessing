from pydantic import BaseModel, Field


class ProcessingUpdate(BaseModel):
    title: str | None = Field(default="Processing...")
    message: str | None = Field(default="Processing...")
