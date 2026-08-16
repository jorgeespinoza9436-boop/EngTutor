# EngTutor

EngTutor is a local English correction chatbot with:

- React mobile-first chat UI
- FastAPI backend
- SQLite correction history
- Free local LLM support through Ollama, with optional Hugging Face Transformers fallback
- Voice input, text-to-speech, native alternatives, and vocabulary suggestions

## Project Structure

```text
.
├── backend
│   ├── app
│   ├── requirements.txt
│   └── .env.example
└── frontend
    ├── src
    └── package.json
```

## Run Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Free Local LLM

The easiest free local model path is Ollama:

```bash
ollama pull llama3.2:1b
ollama serve
```

Keep this in `backend/.env`:

```text
LLM_PROVIDER=auto
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b
```

`LLM_PROVIDER=auto` tries Ollama first. If Ollama is not available, the backend tries the optional Hugging Face Transformers provider.

For local Hugging Face inference instead:

```bash
pip install -r requirements-llm.txt
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Model

The backend defaults to `llama3.2:1b` through Ollama. Change `OLLAMA_MODEL` in `backend/.env` to use another locally pulled Ollama model.

If the model is not ready yet, the API still responds with basic cleanup so the full app flow remains testable. If you use Hugging Face and `torch` is not available for your current Python version, use Python 3.11 or 3.12 for the backend virtual environment.

update my skill
