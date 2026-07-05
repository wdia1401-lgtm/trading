# IdeaBrowser Reimagined

AI-powered startup idea generation & validation platform with an integrated
newsletter ad management module (**AdBooker**). API-first FastAPI backend,
pluggable Claude AI layer, deterministic offline fallback, and a bundled
interactive dashboard.

## What it does

**Idea lifecycle** — generate ideas from market trends, validate each across
seven data-grounded dimensions, apply four strategic frameworks (Value
Equation, A.C.P., Market Matrix, Value Ladder), score founder fit, serve a
daily featured idea, and chat with an AI analyst grounded on any idea's full
report.

**AdBooker** — newsletter operators manage sellable placements and a
Calendly-style slot calendar; sponsors book, upload creatives (AI-reviewed on
intake), and pay; the platform runs a strict booking state machine, dynamic
AI pricing, performance prediction, and an operator analytics dashboard.

## Quickstart

```bash
cd ideabrowser
pip install -r requirements.txt

python -m app.seed                  # demo dataset (users, ideas, newsletter, bookings)
python -m uvicorn app.main:app     # http://localhost:8000
```

- Dashboard: `http://localhost:8000/`
- OpenAPI docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Runs fully offline by default (deterministic AI backend). To enable Claude:

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # switches backend automatically
export IDEABROWSER_MODEL=claude-opus-4-8   # optional override
```

Other configuration: `IDEABROWSER_DATABASE_URL` (defaults to local SQLite;
point at PostgreSQL for production), `IDEABROWSER_PAYMENTS` (`mock` default;
`stripe` adapter slot).

## Tests

```bash
python -m pytest tests/
```

23 tests cover the framework scoring math, validation engine, booking state
machine (happy path, rejections, illegal transitions, refunds), pricing
bounds, and end-to-end API journeys.

## Layout

```
ideabrowser/
├── app/
│   ├── ai/            # provider protocol; Anthropic + deterministic backends
│   ├── api/           # FastAPI routers (thin: validate → service → commit)
│   ├── models/        # SQLAlchemy: core domain + AdBooker
│   ├── schemas/       # Pydantic contracts (API + AI structured outputs)
│   ├── services/      # domain logic: generation, validation, frameworks,
│   │   └── adbooker/  #   personalization, chat; inventory, booking,
│   │                  #   pricing, payments, insights
│   ├── main.py        # app factory
│   └── seed.py        # demo dataset
├── docs/              # ARCHITECTURE.md · DATA_MODEL.md · API.md
├── tests/
└── web/               # single-file interactive dashboard
```

## Design notes

- **Deterministic scores, AI narrative.** Dimension/framework scores are
  auditable formulas over verifiable data (comparable across ideas,
  reproducible); the LLM contributes synthesis, verdicts, and next steps.
  See `docs/ARCHITECTURE.md`.
- **Swappable AI.** All AI features route through a four-method provider
  protocol; the Claude backend uses structured outputs
  (`messages.parse` + Pydantic) so responses are schema-guaranteed.
- **State machines over flags.** Booking transitions are whitelisted in one
  table (`Booking.TRANSITIONS`); illegal moves are 409s, and cancellation
  auto-refunds through the payment gateway abstraction.
