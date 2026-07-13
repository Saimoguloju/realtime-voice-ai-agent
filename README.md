# Realtime Voice AI Agent (Pipecat)

A production-shaped, real-time voice AI agent built on [Pipecat](https://github.com/pipecat-ai/pipecat):
a streaming **STT → LLM → TTS** cascade over **WebRTC**, with **function calling**,
**RAG grounding**, **persistent call transcripts**, and a **latency dashboard**
(p50/p95 per pipeline stage).

## Architecture

```
Browser (Next.js + @pipecat-ai/client-js)
   │  WebRTC (SmallWebRTC transport)
   ▼
Pipecat pipeline (Python, asyncio)
   ├── Deepgram STT        — streaming speech-to-text
   ├── Silero VAD          — turn detection / barge-in (interruptions)
   ├── OpenAI LLM (gpt-4.1) — with function calling:
   │     ├── search_knowledge_base  → RAG (OpenAI embeddings + cosine over local docs)
   │     ├── get_current_weather    → live Open-Meteo API
   │     └── get_current_time      → timezone-aware clock
   ├── Cartesia TTS        — streaming text-to-speech
   │
   ├── LatencyMetricsObserver → SQLite (per-service TTFB + processing time)
   ├── Transcript persistence → SQLite (every user/assistant turn)
   └── Whisker observer       → live pipeline debugger
   │
   ▼
Dashboard API (/api/dashboard/*) → Next.js dashboard (/dashboard)
```

## Features

| Feature | Where | What it demonstrates |
|---|---|---|
| Streaming voice pipeline | `server/bot.py` | Real-time cascade orchestration, interruption handling via VAD |
| Function calling (tools) | `server/tools.py` | LLM tool use with schemas auto-derived from signatures/docstrings |
| RAG knowledge base | `server/knowledge.py`, `server/knowledge/` | Embedding search (OpenAI `text-embedding-3-small`), disk-cached vectors |
| Call persistence | `server/storage.py` | SQLite session/transcript/metrics storage |
| Latency observability | `server/observers.py` | Per-service TTFB & processing time, p50/p95 aggregation |
| Ops dashboard | `client/src/app/dashboard/` | Call history, transcripts, latency table |
| Live pipeline debugging | Whisker | Frame-level pipeline introspection |

## Quick start

**Prereqs:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+, and API keys for
[Deepgram](https://deepgram.com), [OpenAI](https://platform.openai.com), and
[Cartesia](https://cartesia.ai) (all have free tiers/credits).

### 1. Server

```bash
cd server
uv sync
cp .env.example .env      # then add your API keys
uv run bot.py
```

### 2. Client

```bash
cd client
npm install
cp env.example .env.local
npm run dev
```

Open **http://localhost:3000**, click Connect, and talk. Try:

- *"What plans does Nimbus offer?"* → triggers the RAG knowledge-base tool
- *"What's the weather in Berlin?"* → triggers the live weather tool
- Interrupt it mid-sentence → VAD barge-in cancels TTS and yields the turn

Then open **http://localhost:3000/dashboard** to see the call transcript and
per-stage latency (p50/p95) for every session.

## Customizing the knowledge base

Drop your own markdown files into `server/knowledge/` — product docs, policies,
FAQs. They're chunked, embedded once (cached in `.embeddings_cache.json`), and
searched at call time. The demo content is a fictional SaaS FAQ.

## Latency notes

Conversational quality is dominated by perceived responsiveness. This project
measures it rather than guessing:

- Every service reports **TTFB** (time to first byte) per turn.
- The observer persists them; the dashboard aggregates **p50/p95 per stage**.
- Voice-to-voice latency ≈ STT finalization + LLM TTFB + TTS TTFB; the cascade
  streams every stage so synthesis starts before the LLM finishes.

## Project structure

```
├── server/                  # Python backend (uv-managed)
│   ├── bot.py               # Pipeline assembly, event handlers, dashboard API
│   ├── tools.py             # Function-calling tools (weather, time, RAG search)
│   ├── knowledge.py         # Embedding index over server/knowledge/*.md
│   ├── storage.py           # SQLite: sessions, transcripts, metrics
│   ├── observers.py         # Latency metrics observer
│   ├── knowledge/           # Markdown knowledge base (RAG source)
│   ├── Dockerfile           # Container image (Pipecat Cloud-ready)
│   └── pyproject.toml
├── client/                  # Next.js frontend
│   └── src/app/
│       ├── page.tsx          # Voice call UI (voice-ui-kit)
│       ├── dashboard/        # Call history + latency dashboard
│       └── api/              # Proxies to the bot server
└── README.md
```

## Deployment

The server ships with a `Dockerfile` and `pcc-deploy.toml` for
[Pipecat Cloud](https://docs.pipecat.ai/deployment/pipecat-cloud), or deploy the
container anywhere (Fly.io, AWS). The client deploys to Vercel; point
`BOT_START_URL` at your server.

## Stack

Python 3.11+ · asyncio · Pipecat 1.5 · FastAPI · Deepgram · OpenAI (LLM + embeddings) ·
Cartesia · Silero VAD · WebRTC (aiortc) · SQLite · Next.js 16 · React 19 · Tailwind 4
