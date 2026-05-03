# OT Tutor

A Socratic tutoring system for Occupational Therapy students built at the University at Buffalo. Students ask anatomy and clinical questions; the tutor guides them to the answer through hints rather than giving it directly. After the session, a mastery summary and a mistake-revision quiz reinforce weak spots.

---

## How It Works

### Tutoring Pipeline

Every student question goes through a fixed pipeline managed by `ManagerAgent`:

| Turn | Phase | What happens |
|------|-------|--------------|
| 1 | `tutoring` | RAG retrieves relevant passages. `Initializer` extracts the direct answer, clinical scenario, and hint questions (stored immutably for the session). `Tutor` gives **Hint 1** — no answer, no spoilers. |
| 2 | `tutoring` | `Analyzer` scores the student's attempt. `Tutor` gives **Hint 2** targeting the gap. |
| 3 | `reveal` | `Tutor` states the full answer directly, then presents a clinical scenario for the student to reason through. |
| 4+ | `assessment` | `Analyzer` scores clinical reasoning. `Tutor` gives structured feedback (FEEDBACK / CLINICAL PEARL / NEXT STEP). |
| Mastery button | `mastery` | `MasteryAgent` generates a full session summary. Unlocks after turn 4. |

### Agent Roles

| Agent | File | Role |
|-------|------|------|
| **ManagerAgent** | `src/agents/manager.py` | Orchestrates the full pipeline; owns `QuestionSession` state |
| **Initializer** | `src/agents/analyzer.py` | One-time RAG knowledge extraction per session |
| **Analyzer** | `src/agents/analyzer.py` | Per-turn scoring: `proximity_score` (0–100), `answer_quality`, `mistake_excerpt` |
| **Tutor** | `src/agents/tutor.py` | The only agent that speaks to the student; adapts message by phase |
| **MasteryAgent** | `src/agents/mastery.py` | Final session summary using session statistics and recorded mistakes |
| **RapportAgent** | `src/agents/rapport.py` | Generates the opening greeting for each session |
| **VisionAgent** | `src/agents/vision.py` | Identifies uploaded anatomical images via Gemini Vision |

### RAG Knowledge Base

Textbook content is chunked and embedded into a local ChromaDB collection. On each new question, the top-4 passages are retrieved and passed to the Initializer.

- Source PDF: `data/openstax_anatomy.pdf`
- Vector store: `db/chroma_db/`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Chunk size: 512 tokens, 50-token overlap

---

## Project Structure

```
OT_Tutor/
├── src/
│   ├── agents/
│   │   ├── manager.py       # QuestionSession + ManagerAgent
│   │   ├── analyzer.py      # Initializer + per-turn Analyzer
│   │   ├── tutor.py         # Socratic hints, reveal, assessment responses
│   │   ├── mastery.py       # Mastery summary agent
│   │   ├── rapport.py       # Session greeting agent
│   │   └── vision.py        # Image identification (Gemini)
│   ├── config.py            # All paths, model settings, env vars
│   ├── llm.py               # LLM client wrapper (Groq / OpenAI / Anthropic)
│   ├── retriever.py         # ChromaDB RAG retrieval
│   ├── ingest.py            # PDF → ChromaDB ingestion
│   └── image_retriever.py   # Stored image matching
├── web/
│   ├── backend/
│   │   ├── app.py           # FastAPI application + router registration
│   │   ├── database.py      # SQLAlchemy engine (SQLite at db/ot_tutor.db)
│   │   ├── models.py        # ORM models: Session, Message, Attempt, Mistake
│   │   ├── agent_store.py   # In-memory agent registry (session_id → ManagerAgent)
│   │   └── routes/
│   │       ├── sessions.py  # Chat, session CRUD, mastery endpoints
│   │       ├── dashboard.py # Aggregated stats + weak spots
│   │       └── mistakes.py  # Quiz generation + mistake resolution
│   └── frontend/
│       └── src/
│           ├── pages/
│           │   ├── ChatPage.jsx       # Main chat interface
│           │   └── DashboardPage.jsx  # Student performance dashboard
│           ├── components/
│           │   ├── ChatWindow.jsx     # Message list, session header, footer
│           │   ├── MessageBubble.jsx  # User / assistant / mastery message rendering
│           │   ├── InputArea.jsx      # Text input with image upload and voice input
│           │   ├── SessionSidebar.jsx # Collapsible session history
│           │   ├── NavBar.jsx         # Top navigation bar
│           │   └── RevisionModal.jsx  # Mistake revision quiz modal
│           └── api/index.js           # Axios API client
├── db/
│   ├── ot_tutor.db          # SQLite database (auto-created on first run)
│   └── chroma_db/           # ChromaDB vector store (created by run_ingest.py)
├── data/
│   ├── openstax_anatomy.pdf # Source textbook
│   └── images_json/         # Stored anatomical image metadata
├── start.py                 # One-command launcher (backend + frontend together)
├── run_ingest.py            # Build ChromaDB from PDF (run once)
├── run_eval.py              # Evaluation scripts
└── requirements.txt         # Python dependencies
```

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Groq API key (free at [console.groq.com](https://console.groq.com)) — or OpenAI / Anthropic

### 1. Clone and install Python dependencies

```bash
git clone <repo-url>
cd OT_Tutor
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install frontend dependencies

```bash
cd web/frontend
npm install
cd ../..
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
# Required — choose one provider
ACTIVE_PROVIDER=groq
ACTIVE_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_groq_key_here

# Optional — alternative providers
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Optional — Gemini Vision for image identification
GEMINI_API_KEY=your_gemini_key_here
VISION_MODEL=gemini-2.5-flash
```

**Supported providers:**

| `ACTIVE_PROVIDER` | `ACTIVE_MODEL` examples |
|---|---|
| `groq` | `llama-3.1-8b-instant`, `llama-3.3-70b-versatile` |
| `openai` | `gpt-4o-mini`, `gpt-4o` |
| `anthropic` | `claude-3-5-haiku-20241022`, `claude-sonnet-4-6` |

### 4. Add the textbook PDF

Place `openstax_anatomy.pdf` in the `data/` directory.

### 5. Build the knowledge base (run once)

```bash
python run_ingest.py
```

This chunks the PDF, embeds it, and saves the vector store to `db/chroma_db/`. Takes ~5–10 minutes on CPU the first time. Re-run only if you swap the PDF.

### 6. Start the application

```bash
python start.py
```

This starts both servers concurrently:

- **Backend API** → `http://localhost:8000`
- **Frontend** → `http://localhost:5173`

Open `http://localhost:5173` in your browser.

---

## Running Separately

### Backend only

```bash
uvicorn web.backend.app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend only

```bash
cd web/frontend
npm run dev
```

### Production build

```bash
cd web/frontend
npm run build        # outputs to web/frontend/dist/
```

The FastAPI app serves the built frontend automatically when `web/frontend/dist/` exists — no separate frontend server needed.

---

## UI Features

### Chat

- **Session sidebar** — collapsible list of past sessions with phase indicators and scores. Click any session to resume it.
- **Phase indicator** — header shows current phase (Socratic Hints / Answer Revealed / Clinical Assessment / Mastery Complete).
- **Image upload** — click the image icon to upload an anatomical diagram. Gemini Vision identifies it; hints are framed around the diagram.
- **Voice input** — click the microphone icon to dictate using the browser's Speech Recognition API (Chrome/Edge).
- **Mastery button** — appears after turn 4. Triggers a full session summary with confetti on completion.
- **Session complete card** — after mastery, the input is locked and a completion card is shown.

### Dashboard

- **Stats** — total sessions, average assessment score, mastery completions, total attempts.
- **Weak spots** — topics where mistakes were recorded. Click any mistake excerpt to reveal the correct answer. Click **Revise →** to open a quiz modal.
- **Revision quiz modal** — 4 MCQ questions generated by the LLM targeting your specific misconceptions. After completing, click **Mark Resolved** to clear those mistakes from the weak spots list.
- **Answer quality breakdown** — bar chart of correct / partial / wrong / unanswered across all sessions.
- **Recent sessions table** — clickable rows navigate directly to the session.

---

## API Reference

All endpoints are prefixed with `/api`.

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions` | Create a new tutoring session; returns greeting |
| `GET` | `/sessions` | List all sessions |
| `GET` | `/sessions/{id}` | Get session with full message history |
| `POST` | `/sessions/{id}/chat` | Send a message (multipart: `message` + optional `image`) |
| `POST` | `/sessions/{id}/mastery` | Generate mastery summary (cached after first call) |
| `DELETE` | `/sessions/{id}` | Delete session and all associated data |

#### Chat request (multipart/form-data)

```
message: string       # student's text (may be empty for image-only)
image:   file         # optional image upload
```

#### Chat response

```json
{
  "reply": "...",
  "phase": "tutoring | reveal | assessment",
  "turn_count": 3,
  "mastery_unlocked": false,
  "mastery_done": false,
  "topic_label": "finger flexion",
  "current_score": 72.5
}
```

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/dashboard` | Returns stats, weak spots with full mistake details, quality breakdown, recent sessions |

### Mistakes / Revision

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/mistakes/quiz` | Generate 4 MCQ questions targeting specific mistakes |
| `POST` | `/mistakes/resolve` | Mark mistakes as resolved (removes from weak spots) |

#### Quiz request

```json
{ "mistake_ids": [1, 4, 7] }
```

#### Quiz response

```json
{
  "questions": [
    {
      "question": "Which muscle is primarily responsible for finger flexion?",
      "options": ["Flexor carpi radialis", "Flexor digitorum profundus", "Extensor digitorum", "Lumbricals"],
      "correct_index": 1,
      "explanation": "FDP flexes the fingers at the DIP joint and is the primary finger flexor."
    }
  ]
}
```

---

## Database Schema

SQLite at `db/ot_tutor.db`. Auto-created on first startup.

| Table | Key columns |
|-------|-------------|
| `sessions` | `id`, `phase`, `turn_count`, `mastery_unlocked`, `mastery_done`, `avg_score`, `topic_label` |
| `messages` | `session_id`, `role`, `content`, `is_mastery` |
| `attempts` | `session_id`, `turn`, `phase`, `answer_quality`, `proximity_score`, `attempt_summary` |
| `mistakes` | `session_id`, `topic`, `excerpt`, `correct_answer`, `original_question`, `resolved` |

---

## Scoring

The `proximity_score` (0–100) is computed by the Analyzer on every turn:

| Range | Meaning |
|-------|---------|
| 0–10 | No attempt or completely off-topic |
| 11–35 | Engages with topic but core facts wrong |
| 36–60 | Right area, missing key detail |
| 61–79 | Mostly correct, minor gaps |
| 80–89 | Very good, trivial omissions only |
| 90–100 | Directly stated the correct answer |

**Full-credit rule:** if the student correctly identified the core answer at any point in the conversation history, the score floors at 85 — even if the current message is off-track.

The dashboard `avg_score` uses `assessment`-phase attempts only, finalized at mastery.

---

## Evaluation

```bash
# Retrieval quality eval (15 questions)
python run_eval.py

# Also run RAGAS faithfulness eval (requires eval_transcripts.json)
python run_eval.py --ragas
```

Results are saved to `eval_results/`.

---

## Key Configuration (`src/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ACTIVE_PROVIDER` | `groq` | LLM provider: `groq`, `openai`, `anthropic` |
| `ACTIVE_MODEL` | `llama-3.1-8b-instant` | Model name for the active provider |
| `REVEAL_TURN_THRESHOLD` | `4` | Turn after which the Mastery button unlocks |
| `DEFAULT_K` | `4` | Top-k passages retrieved per RAG query |
| `CHUNK_SIZE` | `512` | Token size for PDF chunking |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `IMAGE_MATCH_THRESHOLD` | `0.55` | Cosine similarity threshold for stored image matching |

---

## Notes

- **No GPU needed.** Embedding and ChromaDB retrieval are CPU-friendly.
- Agent sessions are kept in memory (`agent_store.py`). Restarting the server clears active sessions — students will see a "Session expired" error and need to start a new session.
- The first ingest takes ~5–10 minutes on CPU. Subsequent starts load ChromaDB instantly.
- To rebuild the knowledge base: delete `db/chroma_db/` and re-run `python run_ingest.py`.
