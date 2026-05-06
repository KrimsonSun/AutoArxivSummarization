"""FastAPI server (handoff §13.2).

Run with:
    uvicorn src.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from src.config.loader import load_config
from src.pipeline import OneVisionPipeline
from src.schemas.summary import FinalSummary
from src.utils.logging import configure_logging, get_logger

_config = load_config("config/default.yaml")
configure_logging(level=_config.logging.level, json_logs=_config.logging.json_logs)
log = get_logger("server")

_pipeline: OneVisionPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline
    _pipeline = OneVisionPipeline(_config)
    log.info("server_ready")
    yield


app = FastAPI(title="RefinedSummarization — Multi-Agent Debate Summarizer", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/summarize", response_model=FinalSummary)
async def summarize(file: UploadFile = File(...)) -> FinalSummary:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")

    # Save the upload to a temp file so pdfplumber can seek/read.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = Path(tmp.name)
    try:
        return await _pipeline.run(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
