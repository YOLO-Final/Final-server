from pydantic import BaseModel


class OptimizationRequest(BaseModel):
    query: str
