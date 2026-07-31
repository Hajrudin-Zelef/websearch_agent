"""
Serveur FastAPI minimal — un seul endpoint POST /chat.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from agent import run_agent

app = FastAPI(title="WebSearch Agent")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    answer = run_agent(req.message)
    return ChatResponse(response=answer)


@app.get("/health")
async def health():
    return {"status": "ok"}
