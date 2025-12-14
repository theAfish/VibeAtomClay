from pydantic import BaseModel

class CreateSessionRequest(BaseModel):
    pass  # No body needed for creation

class CreateSessionResponse(BaseModel):
    user_id: str
    session_id: str

class SendMessageRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class SendMessageResponse(BaseModel):
    response: str
