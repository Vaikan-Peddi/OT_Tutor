# OT Socratic Tutor

A local RAG-powered Socratic tutoring system for Occupational Therapy anatomy content.  
No GPU required. ChromaDB runs locally. LLM inference runs via Groq API (free tier).

## Project Structure

```
ot_tutor/
├── data/                      ← place openstax_anatomy.pdf here
├── db/                        ← ChromaDB persists here (git-ignored)
├── src/
│   ├── config.py              ← all settings, paths, env vars
│   ├── llm.py                 ← provider-agnostic LLM wrapper (Groq / OpenAI / Anthropic)
│   ├── ingest.py              ← PDF → chunks → embeddings → ChromaDB
│   ├── retriever.py           ← retrieve_context()
│   ├── agents/
│   │   ├── analyzer.py        ← silent JSON analysis agent
│   │   ├── tutor.py           ← Socratic tutor (speaks to student)
│   │   └── manager.py         ← QuestionSession + orchestration
│   └── eval/
│       ├── retrieval_eval.py  ← 15-question retrieval quality eval
│       └── ragas_eval.py      ← faithfulness + answer relevance
├── main.py                    ← interactive chat
├── run_ingest.py              ← one-time DB build
├── run_eval.py                ← run evals
├── .env.example               ← copy to .env and fill keys
└── requirements.txt
```

## Setup

```bash
# 1. Clone / unzip the project
cd ot_tutor

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — add your GROQ_API_KEY (get one free at console.groq.com)

# 5. Add the PDF
# Place openstax_anatomy.pdf in data/

# 6. Build ChromaDB (run ONCE; takes a few minutes on CPU)
python run_ingest.py

# 7. Start the tutor
python main.py
```

## Chat Commands

| Command    | Effect                                              |
|------------|-----------------------------------------------------|
| `/reveal`  | Show the direct answer (unlocks after 3 turns)      |
| `/new`     | Force-start a new question session                  |
| `/status`  | Print current session summary                       |
| `/quit`    | Exit                                                |

## Accessibility

- Browser-based **Speech-to-Text**: click the microphone button in the chat input to dictate questions or answers.
- Browser-based **Text-to-Speech**: click the speaker button on assistant responses and mastery summaries to hear them read aloud.

## Switching LLM Provider

Edit `.env`:

```
# Groq (default, free)
ACTIVE_PROVIDER=groq
ACTIVE_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=...

# OpenAI
ACTIVE_PROVIDER=openai
ACTIVE_MODEL=gpt-4o-mini
OPENAI_API_KEY=...

# Anthropic
ACTIVE_PROVIDER=anthropic
ACTIVE_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=...
```

## Running Evals

```bash
# Retrieval quality (15 questions, no transcripts needed)
python run_eval.py

# Also run RAGAS faithfulness eval (requires eval_transcripts.json)
python run_eval.py --ragas
```

Results are saved to `eval_results/`.

## Notes

- **No GPU needed.** Embedding (`all-MiniLM-L6-v2`) and ChromaDB retrieval are CPU-friendly.
- The first ingest (chunking + embedding the full PDF) takes ~5–10 min on CPU. Subsequent runs load ChromaDB instantly.
- ChromaDB persists to `db/chroma_db/` — delete this folder and re-run `run_ingest.py` to rebuild.
