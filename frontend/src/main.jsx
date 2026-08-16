import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Clipboard,
  Eraser,
  Loader2,
  Mic,
  Send,
  Volume2,
  Wand2,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function App() {
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const scrollRef = useRef(null);

  const recognition = useMemo(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    const instance = new SpeechRecognition();
    instance.lang = "en-US";
    instance.continuous = false;
    instance.interimResults = false;
    return instance;
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchHistory();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, isLoading]);

  useEffect(() => {
    if (!recognition) return;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join(" ");
      setInput((current) => `${current} ${transcript}`.trim());
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => {
      setIsListening(false);
      setError("Voice input is not available right now.");
    };
  }, [recognition]);

  async function fetchHealth() {
    try {
      const response = await fetch(`${API_BASE}/api/health`);
      setHealth(await response.json());
    } catch {
      setHealth(null);
    }
  }

  async function fetchHistory() {
    try {
      const response = await fetch(`${API_BASE}/api/corrections`);
      if (!response.ok) throw new Error("Could not load history.");
      const data = await response.json();
      setHistory(data.reverse());
    } catch {
      setError("Start the FastAPI backend to load correction history.");
    }
  }

  async function submitCorrection(event) {
    event.preventDefault();
    const text = input.trim();
    if (!text || isLoading) return;

    setInput("");
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/corrections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) throw new Error("Correction failed.");
      const correction = await response.json();
      setHistory((current) => [...current, correction]);
      fetchHealth();
    } catch {
      setInput(text);
      setError("I could not reach the backend. Check that FastAPI is running on port 8000.");
    } finally {
      setIsLoading(false);
    }
  }

  async function clearHistory() {
    setError("");
    try {
      await fetch(`${API_BASE}/api/corrections`, { method: "DELETE" });
      setHistory([]);
    } catch {
      setError("Could not clear history.");
    }
  }

  function startVoiceInput() {
    if (!recognition || isListening) return;
    setError("");
    setIsListening(true);
    recognition.start();
  }

  function speak(text) {
    if (!window.speechSynthesis || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  }

  return (
    <main className="appShell">
      <header className="topBar">
        <div>
          <p className="eyebrow">American English tutor</p>
          <h1>EngTutor</h1>
        </div>
        <button className="iconButton" onClick={clearHistory} title="Clear history">
          <Eraser size={18} />
        </button>
      </header>

      <section className="statusRow">
        <span className={health?.llm_ready ? "statusDot ready" : "statusDot"} />
        <span>
          {health?.llm_ready
            ? `Local model ready: ${health.model_id}`
            : "Basic mode until the local Hugging Face model is ready"}
        </span>
      </section>

      <section className="chatList" aria-live="polite">
        {history.length === 0 && (
          <div className="emptyState">
            <Wand2 size={26} />
            <p>Type a sentence or paragraph, then get a corrected and more native version.</p>
          </div>
        )}

        {history.map((item) => (
          <CorrectionCard key={item.id} item={item} onSpeak={speak} />
        ))}

        {isLoading && (
          <div className="loadingBubble">
            <Loader2 size={18} className="spin" />
            Improving your English...
          </div>
        )}
        <div ref={scrollRef} />
      </section>

      {error && <p className="errorText">{error}</p>}

      <form className="composer" onSubmit={submitCorrection}>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Write English here..."
          rows={1}
        />
        <div className="composerActions">
          <button
            type="button"
            className={isListening ? "iconButton active" : "iconButton"}
            onClick={startVoiceInput}
            disabled={!recognition}
            title="Voice input"
          >
            <Mic size={18} />
          </button>
          <button className="sendButton" disabled={!input.trim() || isLoading}>
            <Send size={18} />
          </button>
        </div>
      </form>
    </main>
  );
}

function CorrectionCard({ item, onSpeak }) {
  return (
    <article className="correctionCard">
      <div className="userBubble">
        <span>Original</span>
        <p>{item.original_text}</p>
      </div>

      <div className="assistantBubble">
        <div className="cardHeader">
          <span>Corrected</span>
          <div className="toolGroup">
            <button
              className="iconButton small"
              onClick={() => navigator.clipboard?.writeText(item.corrected_text)}
              title="Copy corrected sentence"
            >
              <Clipboard size={16} />
            </button>
            <button
              className="iconButton small"
              onClick={() => onSpeak(item.corrected_text)}
              title="Read aloud"
            >
              <Volume2 size={16} />
            </button>
          </div>
        </div>
        <p className="correctedText">{item.corrected_text}</p>

        {item.natural_alternative && (
          <div className="detailBlock">
            <span>Native alternative</span>
            <p>{item.natural_alternative}</p>
          </div>
        )}

        <div className="detailBlock">
          <span>Why</span>
          <p>{item.explanation}</p>
        </div>

        {item.changes?.length > 0 && (
          <div className="chips">
            {item.changes.map((change, index) => (
              <div className="changeChip" key={`${change.before}-${index}`}>
                <strong>{change.before}</strong>
                <span>{change.after}</span>
                <small>{change.reason}</small>
              </div>
            ))}
          </div>
        )}

        {item.vocabulary_suggestions?.length > 0 && (
          <div className="vocabList">
            <span>Vocabulary</span>
            {item.vocabulary_suggestions.map((suggestion, index) => (
              <p key={`${suggestion.word}-${index}`}>
                <strong>{suggestion.word}</strong> {"->"} {suggestion.suggestion}
                <small>{suggestion.reason}</small>
              </p>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

createRoot(document.getElementById("root")).render(<App />);
