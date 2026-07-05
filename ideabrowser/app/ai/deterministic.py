"""Offline AI backend: seeded heuristics that mimic the Claude provider.

Everything is derived deterministically from the input text (via a stable
hash), so the platform demos identically on every machine and tests never
flake. Output shapes match the Anthropic provider exactly.
"""

import hashlib
import re

from ..schemas.ai import AnalysisNarrative, CreativeReview, IdeaDraft, RevenueStream


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def _pick(options: list, seed: int, salt: int = 0):
    return options[(seed + salt) % len(options)]


_CATEGORIES = ["ai-tools", "fintech", "health", "climate", "creator-economy", "devtools", "b2b-saas"]
_MODELS = ["saas", "marketplace", "usage-based api", "productized service"]
_CHANNELS = [
    ["SEO content engine", "founder-led LinkedIn", "niche newsletters"],
    ["Product Hunt launch", "community partnerships", "cold outbound"],
    ["YouTube tutorials", "affiliate program", "integration marketplaces"],
]


class DeterministicProvider:
    name = "deterministic"

    # ------------------------------------------------------------- ideas
    def draft_idea(self, context: str) -> IdeaDraft:
        seed = _seed(context)
        topic = context.strip().split("\n")[0][:80] or "an emerging niche"
        tam = 500_000_000 + (seed % 20) * 250_000_000
        difficulty = 3 + seed % 6
        return IdeaDraft(
            title=f"{topic.title()} Copilot",
            tagline=f"An AI-native workflow layer for {topic.lower()}",
            category=_pick(_CATEGORIES, seed),
            problem_statement=(
                f"Teams working on {topic.lower()} still stitch together spreadsheets, "
                "manual research, and generic tools; the work is slow, error-prone, and "
                "the domain knowledge is locked in a few heads."
            ),
            solution_overview=(
                f"A focused product that automates the core {topic.lower()} workflow "
                "end-to-end: ingest the relevant data sources, apply domain-tuned AI "
                "analysis, and deliver decision-ready outputs where the team already works."
            ),
            why_now=(
                "Model quality crossed the usefulness threshold for this domain in the "
                "last 18 months, incumbent tooling has not adapted, and buyers are "
                "actively budgeting for AI workflow consolidation."
            ),
            target_segments=[f"{topic.lower()} operators", "agencies", "in-house teams at SMBs"],
            audience_needs=["save hours of manual work", "defensible accuracy", "easy adoption"],
            tam_usd=tam,
            sam_usd=tam // 8,
            som_usd=tam // 80,
            cagr_pct=8.0 + seed % 14,
            business_model=_pick(_MODELS, seed, 1),
            revenue_streams=[
                RevenueStream(name="Pro subscription", kind="subscription", pricing="$49-199/mo"),
                RevenueStream(name="Team plan", kind="subscription", pricing="$500+/mo"),
                RevenueStream(name="API access", kind="usage", pricing="metered"),
            ],
            price_point_usd=49 + (seed % 4) * 50,
            gtm_channels=_pick(_CHANNELS, seed, 2),
            first_100_customers=(
                "Hand-recruit from the three most active online communities in the niche; "
                "trade white-glove onboarding for testimonials and case studies."
            ),
            difficulty_1_10=difficulty,
            time_to_mvp_weeks=4 + difficulty * 2,
            required_skills=["product", "full-stack engineering", "prompt/ML engineering", "growth"],
            capital_needed_usd=15_000 + difficulty * 10_000,
        )

    # ---------------------------------------------------------- analysis
    def analyze_idea(self, idea_context: str, scores: dict[str, float]) -> AnalysisNarrative:
        avg = sum(scores.values()) / len(scores) if scores else 50.0
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best = [k.replace("_", " ") for k, _ in ranked[:2]]
        worst = [k.replace("_", " ") for k, _ in ranked[-2:]]
        if avg >= 80:
            verdict = "exceptional"
        elif avg >= 68:
            verdict = "strong"
        elif avg >= 55:
            verdict = "promising"
        elif avg >= 42:
            verdict = "risky"
        else:
            verdict = "weak"
        title = idea_context.strip().split("\n")[0]
        return AnalysisNarrative(
            verdict=verdict,
            narrative=(
                f"{title} scores {avg:.0f}/100 overall. The strongest case for it rests on "
                f"{best[0]} and {best[1]}; the case against centers on {worst[1]} and "
                f"{worst[0]}. Treat the weakest dimension as the first validation "
                "experiment rather than a reason to pass."
            ),
            top_strengths=[f"High {b} relative to comparable ideas" for b in best],
            top_risks=[f"Underpowered {w} — needs de-risking before committing" for w in worst],
            next_steps=[
                f"Design a one-week experiment that stress-tests {worst[1]}",
                "Interview 10 people in the primary target segment",
                "Ship a landing-page smoke test and measure conversion to waitlist",
            ],
        )

    # ---------------------------------------------------------- creative
    def review_creative(self, kind: str, content: str, audience: str) -> CreativeReview:
        suggestions: list[str] = []
        score = 60
        words = content.split()
        if kind in ("headline", "cta") and len(words) > 12:
            suggestions.append("Tighten to under 12 words; front-load the benefit.")
            score -= 10
        if kind == "body_copy" and len(words) < 25:
            suggestions.append("Add one concrete proof point (metric, customer, outcome).")
            score -= 5
        if not re.search(r"\b(you|your)\b", content, re.IGNORECASE):
            suggestions.append("Address the reader directly ('you/your') to lift engagement.")
            score -= 5
        if kind == "cta" and not re.search(r"\b(get|start|try|book|join|claim)\b", content, re.IGNORECASE):
            suggestions.append("Lead the CTA with an action verb (Get, Start, Try...).")
            score -= 10
        if re.search(r"\d", content):
            score += 10  # concrete numbers convert better
        if not suggestions:
            suggestions.append(f"Solid as-is; consider an A/B variant tuned to {audience}.")
            score += 10
        improved = content if not suggestions else f"{content.rstrip('.')} — built for {audience}."
        return CreativeReview(score=max(0, min(100, score)), suggestions=suggestions, improved_version=improved)

    # -------------------------------------------------------------- chat
    def chat(self, system: str, history: list[dict[str, str]]) -> str:
        question = history[-1]["content"] if history else ""
        # Surface the grounded context (idea facts embedded in the system prompt)
        facts = [ln.strip("- ") for ln in system.splitlines() if ln.strip().startswith("-")][:4]
        fact_text = " ".join(facts) if facts else "the idea's core analysis"
        return (
            f"Here's my read on \"{question.strip()[:120]}\": based on {fact_text} — "
            "the honest answer is to weigh the strongest demand signal against the "
            "hardest execution constraint. Run the cheapest experiment that could "
            "change your mind, and revisit the validation report's weakest dimension "
            "before committing resources. Ask me for a specific breakdown (market, "
            "competition, GTM, or execution) and I'll go deeper."
        )
