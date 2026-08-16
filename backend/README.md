# EngTutor Backend

FastAPI backend for local English correction with SQLite history and free local LLM support.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Free Local LLM

The recommended free provider is Ollama:

```bash
ollama pull llama3.2:1b
ollama serve
```

By default the backend uses `llama3.2:1b` through Ollama. You can change `OLLAMA_MODEL` in `.env` to another local Ollama model.

To enable local Hugging Face inference, install the optional LLM dependencies:

```bash
pip install -r requirements-llm.txt
```

The model runs on your machine. If Ollama is not available, `LLM_PROVIDER=auto` tries Hugging Face Transformers. The first Hugging Face startup may download model files unless they are already cached locally. If `torch` is not available for your Python version, use Python 3.11 or 3.12 for the backend virtual environment.
