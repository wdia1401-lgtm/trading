"""End-to-end API smoke tests exercising the main user journeys over HTTP."""


def _create_user(client, email="api@x.com", role="founder") -> int:
    r = client.post("/api/v1/users", json={"email": email, "name": "API User", "role": role})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ai_backend"] == "deterministic"


def test_submit_idea_runs_full_analysis(client):
    r = client.post(
        "/api/v1/ideas",
        json={
            "title": "Inventory Copilot for Restaurants",
            "category": "b2b-saas",
            "problem_statement": "Restaurants throw away 10% of stock because ordering is guesswork.",
            "solution_overview": "Forecast demand from POS data and auto-draft supplier orders.",
            "business_model": {"model": "saas", "price_point_usd": 149,
                               "revenue_streams": [{"name": "Pro", "kind": "subscription"}]},
        },
    )
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["validation"]["overall_score"] > 0
    assert len(report["frameworks"]) == 4
    slug = report["idea"]["slug"]

    # searchable database
    r = client.get("/api/v1/ideas", params={"q": "restaurants"})
    assert any(i["slug"] == slug for i in r.json())

    # detail + daily
    assert client.get(f"/api/v1/ideas/{slug}").status_code == 200
    daily = client.get("/api/v1/ideas/daily")
    assert daily.status_code == 200
    assert daily.json()["idea"]["slug"] == slug  # only idea in db -> featured


def test_workspace_and_personalization(client):
    user_id = _create_user(client)
    idea = client.post(
        "/api/v1/ideas",
        json={
            "title": "Field Notes AI",
            "problem_statement": "Field technicians lose critical notes across jobs and tools.",
            "solution_overview": "Voice-first notes that auto-file against work orders.",
        },
    ).json()["idea"]

    r = client.put(
        f"/api/v1/users/{user_id}/profile",
        json={"skills": ["python"], "interests": ["ai-tools"], "capital_available_usd": 10000},
    )
    assert r.status_code == 200

    r = client.get(f"/api/v1/users/{user_id}/recommendations")
    assert r.status_code == 200 and len(r.json()) >= 1
    assert "blended_score" in r.json()[0]

    r = client.get(f"/api/v1/users/{user_id}/founder-fit/{idea['id']}")
    assert r.status_code == 200
    assert 0 <= r.json()["score"] <= 100

    r = client.post(f"/api/v1/users/{user_id}/workspace", json={"idea_id": idea["id"]})
    assert r.status_code == 201
    item_id = r.json()["id"]
    r = client.patch(f"/api/v1/users/{user_id}/workspace/{item_id}", params={"stage": "validating"})
    assert r.json()["stage"] == "validating"


def test_chat_grounded_on_idea(client):
    user_id = _create_user(client, "chat@x.com")
    idea = client.post(
        "/api/v1/ideas",
        json={
            "title": "Compliance Bot",
            "problem_statement": "Small lenders cannot keep up with regulatory change velocity.",
            "solution_overview": "Automated policy-to-regulation mapping with cited findings.",
        },
    ).json()["idea"]

    session = client.post("/api/v1/chat/sessions", json={"user_id": user_id, "idea_id": idea["id"]})
    assert session.status_code == 201
    sid = session.json()["id"]
    r = client.post(f"/api/v1/chat/sessions/{sid}/messages", json={"content": "What is the biggest risk?"})
    assert r.status_code == 201
    assert r.json()["role"] == "assistant"
    assert len(r.json()["content"]) > 40

    history = client.get(f"/api/v1/chat/sessions/{sid}").json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"]


def test_adbooker_end_to_end(client):
    operator = _create_user(client, "op@api.com", role="operator")
    sponsor = _create_user(client, "sp@api.com", role="sponsor")

    nl = client.post(
        "/api/v1/adbooker/newsletters",
        json={"operator_id": operator, "name": "API Weekly", "niche": "devtools",
              "audience_size": 20000, "open_rate": 0.5, "click_rate": 0.03,
              "send_days": [0, 1, 2, 3, 4]},
    )
    assert nl.status_code == 201, nl.text
    nl_id = nl.json()["id"]

    pt = client.post(
        f"/api/v1/adbooker/newsletters/{nl_id}/placements",
        json={"name": "Main Sponsor", "base_price_cents": 60000, "ctr_multiplier": 1.5},
    )
    assert pt.status_code == 201

    slots = client.get(f"/api/v1/adbooker/newsletters/{nl_id}/slots",
                       params={"available_only": True}).json()
    assert slots, "calendar should materialize bookable slots"
    slot_id = slots[0]["id"]

    prediction = client.get(f"/api/v1/adbooker/slots/{slot_id}/prediction").json()
    assert prediction["predicted_impressions"] == 10000  # 20k x 0.5 open rate

    booking = client.post(
        f"/api/v1/adbooker/slots/{slot_id}/book",
        json={"sponsor_id": sponsor, "brand_name": "Testly", "contact_email": "sp@api.com"},
    )
    assert booking.status_code == 201
    b_id = booking.json()["id"]

    # double-booking the same slot is rejected
    dup = client.post(
        f"/api/v1/adbooker/slots/{slot_id}/book",
        json={"sponsor_id": sponsor, "brand_name": "Other", "contact_email": "o@api.com"},
    )
    assert dup.status_code == 409

    for kind, content in [
        ("headline", "Get your builds 3x faster"),
        ("body_copy", "Testly runs your suite on 64 cores with smart sharding. Teams cut CI from 40 to 12 minutes."),
        ("landing_url", "https://testly.example.com"),
    ]:
        r = client.post(f"/api/v1/adbooker/bookings/{b_id}/assets",
                        json={"kind": kind, "content": content})
        assert r.status_code == 201
        assert "score" in r.json()["ai_review"]

    booking_state = client.get(f"/api/v1/adbooker/bookings/{b_id}").json()
    assert booking_state["status"] == "awaiting_approval"

    for asset in booking_state["assets"]:
        r = client.post(f"/api/v1/adbooker/assets/{asset['id']}/review",
                        json={"decision": "approved"})
        assert r.status_code == 200

    pay = client.post(f"/api/v1/adbooker/bookings/{b_id}/pay")
    assert pay.status_code == 200
    assert pay.json()["status"] == "succeeded"

    # paying twice is an illegal transition -> 409
    assert client.post(f"/api/v1/adbooker/bookings/{b_id}/pay").status_code == 409

    deliver = client.post(f"/api/v1/adbooker/bookings/{b_id}/deliver",
                          json={"impressions": 9800, "clicks": 300, "conversions": 21})
    assert deliver.status_code == 200 and deliver.json()["status"] == "delivered"
    assert client.post(f"/api/v1/adbooker/bookings/{b_id}/complete").json()["status"] == "completed"

    dash = client.get(f"/api/v1/adbooker/newsletters/{nl_id}/dashboard").json()
    assert dash["bookings_by_status"].get("completed") == 1
    assert dash["revenue_confirmed_cents"] == 60000
    assert dash["avg_ctr"] > 0

    pricing = client.get(f"/api/v1/adbooker/newsletters/{nl_id}/pricing-suggestions").json()
    assert pricing and all("suggested_price_cents" in p for p in pricing)
