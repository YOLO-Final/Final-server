from pydantic import BaseModel


class RagQuery(BaseModel):
    question: str
