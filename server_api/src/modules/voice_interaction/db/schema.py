from pydantic import BaseModel


class SpeechRequest(BaseModel):
    session_id: str
