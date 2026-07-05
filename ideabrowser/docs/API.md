# API Reference

Base path: `/api/v1`. Interactive docs (Swagger UI) at `/docs` when the
server is running. All bodies are JSON. Errors use standard HTTP codes:
`404` unknown resource, `409` conflict/illegal state transition, `422`
validation failure.

## Ideas

| Method | Path | Purpose |
|---|---|---|
| GET | `/ideas` | Searchable database. Query: `q`, `category`, `status`, `min_score`, `sort=score\|newest`, `limit`, `offset` |
| POST | `/ideas` | Submit an idea — full analysis (validation + 4 frameworks) runs on intake; returns the complete report |
| GET | `/ideas/daily` | Today's featured idea (auto-selects best unfeatured idea once per day) |
| GET | `/ideas/{slug}` | Full interactive report: idea, validation, frameworks, keywords, signals, competitors, trends |
| POST | `/ideas/{id}/revalidate` | Re-run validation + frameworks (new snapshot; history preserved) |

## Trends

| Method | Path | Purpose |
|---|---|---|
| GET | `/trends` | List trends ranked by momentum (filter: `category`) |
| POST | `/trends/{id}/refresh` | Recompute momentum/stage from keyword telemetry |
| POST | `/trends/{id}/generate-idea` | AI-generate one fully analyzed idea seeded by this trend |

## Users, personalization, workspace

| Method | Path | Purpose |
|---|---|---|
| POST | `/users` | Register (roles: founder / operator / sponsor) |
| GET/PUT | `/users/{id}/profile` | Founder profile: skills, interests, capital, hours, risk appetite |
| GET | `/users/{id}/recommendations` | Ideas ranked by quality (55%) blended with founder fit (45%) |
| GET | `/users/{id}/founder-fit/{idea_id}` | Fit score with matched skills, gaps, rationale |
| GET/POST | `/users/{id}/workspace` | Saved ideas with stage tracking |
| PATCH | `/users/{id}/workspace/{item}` | Move stage (`saved → researching → validating → building → launched`) / edit notes |

## Chat (AI analyst)

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat/sessions` | Open a conversation, optionally grounded on one idea (`idea_id`) |
| GET | `/chat/sessions/{id}` | Session with message history |
| POST | `/chat/sessions/{id}/messages` | Send a message; returns the assistant's reply. Grounded sessions embed the idea's full analysis into the system prompt |

## AdBooker

| Method | Path | Purpose |
|---|---|---|
| POST/GET | `/adbooker/newsletters` | Create / list newsletters |
| POST/GET | `/adbooker/newsletters/{id}/placements` | Manage sellable ad formats |
| GET | `/adbooker/newsletters/{id}/slots` | Availability calendar (`start`, `end`, `available_only`); slots materialize on demand |
| GET | `/adbooker/newsletters/{id}/pricing-suggestions` | AI pricing per slot with factor breakdown; `?apply=true` writes prices |
| GET | `/adbooker/newsletters/{id}/dashboard` | Operator analytics: occupancy, revenue, status funnel, CTR, upcoming sends |
| GET | `/adbooker/slots/{id}/prediction` | Impressions/clicks forecast with confidence + drivers |
| POST | `/adbooker/slots/{id}/book` | Reserve a slot → booking in `awaiting_assets` |
| GET | `/adbooker/bookings/{id}` | Booking with assets + payment ledger |
| POST | `/adbooker/bookings/{id}/assets` | Upload creative; AI review attaches automatically |
| POST | `/adbooker/assets/{id}/review` | Operator approve/reject (`decision`, `feedback`) |
| POST | `/adbooker/bookings/{id}/pay` | Charge via the configured gateway; booking → `confirmed` |
| POST | `/adbooker/bookings/{id}/deliver` | Mark sent + record realized performance |
| POST | `/adbooker/bookings/{id}/complete` | Close out |
| POST | `/adbooker/bookings/{id}/cancel` | Cancel pre-delivery; auto-refund if paid |

### Sponsor booking walkthrough

```bash
# 1. browse availability
curl "localhost:8000/api/v1/adbooker/newsletters/1/slots?available_only=true"

# 2. book a slot
curl -X POST localhost:8000/api/v1/adbooker/slots/41/book \
  -H 'content-type: application/json' \
  -d '{"sponsor_id": 3, "brand_name": "Acme", "contact_email": "ads@acme.com"}'

# 3. upload creatives (headline, body_copy, landing_url required)
curl -X POST localhost:8000/api/v1/adbooker/bookings/1/assets \
  -H 'content-type: application/json' \
  -d '{"kind": "headline", "content": "Ship dashboards 3x faster"}'
# ... booking auto-advances to awaiting_approval once required kinds are in

# 4. operator approves each asset  →  awaiting_payment
# 5. pay                            →  confirmed
curl -X POST localhost:8000/api/v1/adbooker/bookings/1/pay
```
