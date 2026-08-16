import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from .database import clear_corrections, init_db, list_corrections, save_correction
from .llm import MODEL_ID, correct_text, is_llm_ready
from .schemas import CorrectionRequest, CorrectionResponse, HealthResponse


app = FastAPI(title=os.getenv("APP_NAME", "EngTutor API"))

origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_id=MODEL_ID, llm_ready=is_llm_ready())


@app.get("/api/corrections", response_model=list[CorrectionResponse])
def get_history(limit: int = 50) -> list[CorrectionResponse]:
    return list_corrections(limit=limit)


@app.post("/api/corrections", response_model=CorrectionResponse)
def create_correction(request: CorrectionRequest) -> CorrectionResponse:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required.")

    correction = correct_text(text)
    return save_correction(correction)


@app.delete("/api/corrections", status_code=204)
def delete_history() -> None:
    clear_corrections()
