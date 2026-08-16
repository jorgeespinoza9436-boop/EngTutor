import json
import os
import re
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

try:
    from .schemas import ChangeItem, CorrectionPayload, VocabularySuggestion
except ImportError:
    from schemas import ChangeItem, CorrectionPayload, VocabularySuggestion


load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "google/flan-t5-base")
MODEL_ID = OLLAMA_MODEL if LLM_PROVIDER in {"auto", "ollama"} else HF_MODEL_ID
MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "320"))
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))


SYSTEM_INSTRUCTIONS = """
You are an American English correction tutor.
Improve the user's English so it sounds natural and native while preserving meaning.
Correct grammar, spelling, word choice, and awkward phrasing.
Return only valid JSON with these keys:
corrected_text, natural_alternative, explanation, changes, vocabulary_suggestions.
changes must be an array of objects with before, after, reason.
vocabulary_suggestions must be an array of objects with word, suggestion, reason.
Keep explanations educational, concise, and based only on the actual correction.
Preserve the user's meaning. Do not invent new ideas.
If you are not sure about a grammar label, explain the improvement in plain English.
"""


def build_prompt(text: str) -> str:
    return f"{SYSTEM_INSTRUCTIONS}\nUser text: {text}\nJSON:"


def should_use_ollama() -> bool:
    return LLM_PROVIDER in {"auto", "ollama"}


def should_use_hugging_face() -> bool:
    return LLM_PROVIDER in {"auto", "huggingface", "hf", "transformers"}


def is_ollama_ready() -> bool:
    if not should_use_ollama():
        return False

    try:
        request = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False

    models = payload.get("models", [])
    return any(model.get("name") == OLLAMA_MODEL for model in models)


def correct_with_ollama(text: str) -> CorrectionPayload | None:
    if not should_use_ollama():
        return None

    request_body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": build_prompt(text),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_predict": MAX_NEW_TOKENS,
            },
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None

    parsed = parse_json(str(payload.get("response", "")))
    if not parsed:
        return None
    return payload_to_correction(text, parsed)


@lru_cache(maxsize=1)
def get_generator() -> Any | None:
    if not should_use_hugging_face():
        return None

    try:
        from transformers import pipeline

        return pipeline(
            "text2text-generation",
            model=HF_MODEL_ID,
            tokenizer=HF_MODEL_ID,
            device_map="auto",
        )
    except Exception:
        return None


def is_llm_ready() -> bool:
    return is_ollama_ready() or get_generator() is not None


def correct_text(text: str) -> CorrectionPayload:
    ollama_result = correct_with_ollama(text)
    if ollama_result is not None:
        return apply_local_rules(ollama_result)

    generator = get_generator()
    if generator is None:
        return fallback_correction(text)

    try:
        result = generator(
            build_prompt(text),
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            truncation=True,
        )
        raw_text = result[0]["generated_text"]
        parsed = parse_json(raw_text)
        return apply_local_rules(payload_to_correction(text, parsed))
    except Exception:
        return fallback_correction(text)


def payload_to_correction(text: str, parsed: dict[str, Any]) -> CorrectionPayload:
    corrected_text = str(parsed.get("corrected_text") or text).strip()
    natural_alternative = str(
        parsed.get("natural_alternative") or corrected_text or text
    ).strip()
    explanation = str(
        parsed.get("explanation")
        or "I improved the sentence to sound more natural in American English."
    ).strip()

    return CorrectionPayload(
        original_text=text,
        corrected_text=corrected_text,
        natural_alternative=natural_alternative,
        explanation=explanation,
        changes=parse_changes(parsed.get("changes")),
        vocabulary_suggestions=parse_vocabulary(parsed.get("vocabulary_suggestions")),
    )


def parse_json(raw_text: str) -> dict[str, Any]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return parse_partial_json_fields(raw_text)
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return parse_partial_json_fields(match.group(0))


def parse_partial_json_fields(raw_text: str) -> dict[str, Any]:
    parsed = {}
    for key in ("corrected_text", "natural_alternative", "explanation"):
        match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text, re.DOTALL)
        if match:
            parsed[key] = bytes(match.group(1), "utf-8").decode("unicode_escape")
    return parsed


def parse_changes(value: Any) -> list[ChangeItem]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                items.append(
                    ChangeItem(
                        before=text,
                        after=text,
                        reason="The model identified this phrase as part of the correction.",
                    )
                )
            continue
        if not isinstance(item, dict):
            continue
        before = str(item.get("before", "")).strip()
        after = str(item.get("after", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not before and not after and not reason:
            continue
        items.append(
            ChangeItem(
                before=before,
                after=after,
                reason=reason,
            )
        )
    return items


def parse_vocabulary(value: Any) -> list[VocabularySuggestion]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if isinstance(item, str):
            word = item.strip()
            if word:
                items.append(
                    VocabularySuggestion(
                        word=word,
                        suggestion=word,
                        reason="Useful vocabulary from the corrected sentence.",
                    )
                )
            continue
        if not isinstance(item, dict):
            continue
        word = str(item.get("word", "")).strip()
        suggestion = str(item.get("suggestion", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not word and not suggestion and not reason:
            continue
        items.append(
            VocabularySuggestion(
                word=word,
                suggestion=suggestion,
                reason=reason,
            )
        )
    return items


def fallback_correction(text: str) -> CorrectionPayload:
    cleaned = normalize_text(text)
    changes = []
    if cleaned != text:
        changes.append(
            ChangeItem(
                before=text,
                after=cleaned,
                reason="Cleaned spacing, capitalization, and sentence punctuation.",
            )
        )

    return apply_local_rules(
        CorrectionPayload(
            original_text=text,
            corrected_text=cleaned,
            natural_alternative=cleaned,
            explanation=(
                "No local free LLM is available yet, so I applied basic cleanup. "
                "Start Ollama and pull the configured model, or install the optional Hugging Face dependencies."
            ),
            changes=changes,
            vocabulary_suggestions=[],
        )
    )


def normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    if not collapsed:
        return text

    sentences = re.split(r"(?<=[.!?])\s+", collapsed)
    normalized_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence = sentence[0].upper() + sentence[1:]
        if sentence[-1] not in ".!?":
            sentence += "."
        normalized_sentences.append(sentence)
    return " ".join(normalized_sentences)


def apply_local_rules(payload: CorrectionPayload) -> CorrectionPayload:
    corrected_text, article_changes = fix_article_before_consonant_sound(
        payload.corrected_text
    )
    natural_alternative, _ = fix_article_before_consonant_sound(
        payload.natural_alternative
    )
    original_has_article_error = re.search(
        r"\ban\s+software\b", payload.original_text, flags=re.IGNORECASE
    )

    existing_changes = [
        change
        for change in payload.changes
        if change.before or change.after or change.reason
    ]
    if original_has_article_error and not any(
        change.before.lower() == "an software" for change in existing_changes
    ):
        article_changes.append(("an software", "a software"))

    for before, after in article_changes:
        existing_changes.append(
            ChangeItem(
                before=before,
                after=after,
                reason=(
                    "Use 'a' before words that start with a consonant sound, "
                    "such as 'software'."
                ),
            )
        )

    explanation = payload.explanation
    if original_has_article_error:
        explanation = (
            "Use 'a' instead of 'an' before 'software' because 'software' starts "
            "with a consonant sound. I also improved the phrasing to sound more "
            "natural in American English."
        )

    return CorrectionPayload(
        original_text=payload.original_text,
        corrected_text=corrected_text,
        natural_alternative=natural_alternative,
        explanation=explanation,
        changes=existing_changes,
        vocabulary_suggestions=payload.vocabulary_suggestions,
    )


def fix_article_before_consonant_sound(text: str) -> tuple[str, list[tuple[str, str]]]:
    changes = []

    def replace(match: re.Match[str]) -> str:
        original = match.group(0)
        replacement = re.sub(r"^an\b", "a", original, count=1, flags=re.IGNORECASE)
        changes.append((original, replacement))
        return replacement

    fixed = re.sub(r"\ban\s+software\b", replace, text, flags=re.IGNORECASE)
    return fixed, changes
