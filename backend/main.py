"""
Support Chat Agent — FastAPI backend (Groq edition).

Environment variables (set in backend/.env for local, Railway dashboard for prod):
  GROQ_API_KEY    (required — get free at console.groq.com)
  MODEL           (default: llama-3.1-8b-instant)
  COMPANY_NAME    (default: "Our Company")
  BOT_NAME        (default: "Support Assistant")
  COMPANY_PERSONA (optional extra system-prompt text)
  ALLOWED_ORIGINS (comma-separated, default: *)
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from groq import AsyncGroq
from pydantic import BaseModel, field_validator

load_dotenv()

from ingest import process_file
from rag import RAGSystem

# ── Config ─────────────────────────────────────────────────────────────────────

GROQ_API_KEY    = os.environ.get("GROQ_API_KEY", "")
MODEL           = os.environ.get("MODEL", "llama-3.1-8b-instant")
COMPANY_NAME    = os.environ.get("COMPANY_NAME", "Our Company")
BOT_NAME        = os.environ.get("BOT_NAME", "Support Assistant")
COMPANY_PERSONA = os.environ.get("COMPANY_PERSONA", "")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
]

SYSTEM_PROMPT = f"""You are {BOT_NAME}, the AI customer support assistant for {COMPANY_NAME}.

{COMPANY_PERSONA}

Guidelines:
- Answer questions using the KNOWLEDGE BASE CONTEXT provided in the user message.
- Be friendly, professional, and concise.
- If the answer is not in the context, say honestly: "I don't have that information. Please reach out to our support team for further help."
- Never invent facts, pricing, or policies.
- Keep responses focused and helpful.""".strip()

MAX_FILE_BYTES    = 10 * 1024 * 1024  # 10 MB
MAX_HISTORY_TURNS = 10

# ── Lifespan ───────────────────────────────────────────────────────────────────

rag: RAGSystem | None = None
gc:  AsyncGroq  | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag, gc

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Get a free key at console.groq.com")

    rag = RAGSystem()
    gc  = AsyncGroq(api_key=GROQ_API_KEY)

    print(f"[OK] {BOT_NAME} ready  |  model={MODEL}  |  chunks={rag.count()}")
    yield


app = FastAPI(title=f"{BOT_NAME} API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Serve the widget JS file at /widget/chat-widget.js
widget_dir = Path(__file__).parent.parent / "widget"
if widget_dir.exists():
    app.mount("/widget", StaticFiles(directory=str(widget_dir)), name="widget")

# Serve the demo page at /
@app.get("/")
async def demo():
    demo_file = Path(__file__).parent.parent / "example.html"
    return FileResponse(str(demo_file))

# ── Models ─────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be empty")
        return v.strip()


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {
        "status":         "ok",
        "bot":            BOT_NAME,
        "company":        COMPANY_NAME,
        "model":          MODEL,
        "chunks_indexed": rag.count(),
        "sources":        rag.list_sources(),
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    """Stream a chat response using RAG + Groq."""

    # 1. Retrieve relevant document chunks
    context_chunks = rag.retrieve(req.message, n_results=5)

    context_block = ""
    if context_chunks:
        formatted = "\n\n---\n\n".join(
            f"[Source: {c['source']}]\n{c['content']}" for c in context_chunks
        )
        context_block = f"\n\n<knowledge_base_context>\n{formatted}\n</knowledge_base_context>"

    # 2. Build message list
    history = list(req.conversation_history[-MAX_HISTORY_TURNS:])
    history.append({
        "role":    "user",
        "content": req.message + context_block,
    })

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # 3. Stream response via Groq
    async def event_stream() -> AsyncIterator[str]:
        try:
            stream = await gc.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=1024,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    source_name: str = Form(None),
):
    """Ingest a PDF, DOCX, or TXT file into the knowledge base."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(400, "File exceeds 10 MB limit")

    try:
        chunks = process_file(content, file.filename, source_name)
        rag.add_chunks(chunks)
        return {
            "status":       "ok",
            "source":       source_name or file.filename,
            "chunks_added": len(chunks),
            "total_chunks": rag.count(),
        }
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.delete("/documents/{source_name}")
async def delete_document(source_name: str):
    """Remove all chunks for a given source from the knowledge base."""
    deleted = rag.delete_source(source_name)
    return {
        "status":         "ok",
        "source_deleted": source_name,
        "chunks_removed": deleted,
        "total_chunks":   rag.count(),
    }


@app.get("/documents")
async def list_documents():
    return {"sources": rag.list_sources(), "total_chunks": rag.count()}
