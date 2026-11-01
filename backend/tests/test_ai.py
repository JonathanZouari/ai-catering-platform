import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_orders import ADMIN, Shop

from app.agents.client import LLMError, get_llm
from app.agents.tools import definitions
from app.core.config import get_settings
from app.main import app


def reply(text_value="בסדר גמור"):
    block = SimpleNamespace(type="text", text=text_value)
    return SimpleNamespace(stop_reason="end_turn", content=[block])


def use(name, arguments=None):
    block = SimpleNamespace(type="tool_use", id=f"t{uuid4().hex}", name=name, input=arguments or {})
    return SimpleNamespace(stop_reason="tool_use", content=[block])


class FakeLLM:
    """Plays back a script, so the safety rules are tested without a real model."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []

    def create(self, system, tools, messages):
        self.requests.append({"system": system, "tools": tools, "messages": list(messages)})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def results(self):
        """Tool results returned to the model, parsed."""
        found = []
        for request in self.requests:
            last = request["messages"][-1]["content"]
            if isinstance(last, list):
                found.extend((json.loads(item["content"]), item["is_error"]) for item in last)
        return found


@pytest.fixture
def shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-a"))


@pytest.fixture
def other_shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-b"))


@pytest.fixture
def speak():
    def install(*script):
        llm = FakeLLM(*script)
        app.dependency_overrides[get_llm] = lambda: llm
        return llm

    return install


def send(order, message="שלום"):
    url = f"{order.url}/chat"
    return order.client.post(url, json={"message": message}, headers=order.headers)


def add_change(dish, quantity="2"):
    return {"type": "add_item", "dish_id": dish["id"], "quantity": quantity}


def propose(*changes):
    return use("propose_order_change", {"changes": list(changes), "rationale": "מתאים לאירוע"})


def proposal_for(order, llm_step, speak):
    speak(llm_step, reply())
    body = send(order).json()
    assert len(body["proposals"]) == 1, body
    return body["proposals"][0]


def post(order, proposal, action):
    url = f"{order.url}/proposals/{proposal['id']}/{action}"
    return order.client.post(url, headers=order.headers)


def seen(order):
    return order.client.get(order.url, headers=order.headers).json()


def code(response):
    return response.status_code, response.json()["error"]["code"]


def test_proposal_does_not_change_the_order(shop, speak):
    order = shop.order()
    before = seen(order)

    proposal = proposal_for(order, propose(add_change(shop.meat)), speak)

    after = seen(order)
    assert after["lines"] == [] and after["version"] == before["version"]
    assert proposal["status"] == "pending"
    assert (proposal["price_before"], proposal["price_after"]) == ("0.00", "200.00")
    assert proposal["changes"][0]["name"] == "עוף"


def test_approve_applies_exactly_once(shop, speak):
    order = shop.order()
    proposal = proposal_for(order, propose(add_change(shop.meat)), speak)

    response = post(order, proposal, "approve")

    assert response.status_code == 200
    body = response.json()
    assert body["order"]["total"] == "200.00"
    assert body["proposal"]["status"] == "approved"
    assert body["order"]["version"] == order.data["version"] + 1
    assert code(post(order, proposal, "approve")) == (409, "proposal_not_pending")
    assert seen(order)["version"] == body["order"]["version"]


def test_reject_changes_nothing(shop, speak):
    order = shop.order()
    proposal = proposal_for(order, propose(add_change(shop.meat)), speak)

    assert post(order, proposal, "reject").json()["proposal"]["status"] == "rejected"

    assert seen(order)["lines"] == []
    assert code(post(order, proposal, "approve")) == (409, "proposal_not_pending")


def test_stale_proposal_expires_and_changes_nothing(shop, speak):
    order = shop.order()
    proposal = proposal_for(order, propose(add_change(shop.meat)), speak)
    order.add(shop.dairy, "1")

    assert code(post(order, proposal, "approve")) == (409, "order_version_conflict")

    assert [line["name"] for line in seen(order)["lines"]] == ["לזניה"]
    listed = order.client.get(f"{order.url}/proposals", headers=order.headers).json()
    assert listed[0]["status"] == "expired"


def test_price_change_after_the_card_expires_it(shop, speak):
    order = shop.order()
    proposal = proposal_for(order, propose(add_change(shop.meat)), speak)
    shop.patch(f"dishes/{shop.meat['id']}", {"unit_price": "150.00"})

    assert code(post(order, proposal, "approve")) == (409, "order_version_conflict")
    assert seen(order)["lines"] == []


def test_dish_going_unavailable_fails_the_proposal(shop, speak):
    order = shop.order()
    proposal = proposal_for(order, propose(add_change(shop.meat)), speak)
    shop.patch(f"dishes/{shop.meat['id']}", {"is_available": False})

    assert code(post(order, proposal, "approve")) == (409, "dish_unavailable")
    assert seen(order)["lines"] == []


def test_new_proposal_replaces_the_pending_one(shop, speak):
    order = shop.order()
    first = proposal_for(order, propose(add_change(shop.meat)), speak)
    second = proposal_for(order, propose(add_change(shop.dairy)), speak)

    assert first["id"] != second["id"]
    assert code(post(order, first, "approve")) == (409, "proposal_not_pending")


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "add_item", "dish_id": str(uuid4()), "quantity": "1"},
        {"type": "add_item", "dish_id": "not-a-dish", "quantity": "1"},
        {"type": "set_price", "dish_id": str(uuid4()), "price": "1.00"},
        {"type": "update_details", "event_date": "2031-02-01"},
        {"type": "update_details", "delivery_fee": "0"},
        {"type": "update_details", "adults": 0, "children": 0},
    ],
)
def test_invalid_changes_become_tool_errors(shop, speak, bad):
    order = shop.order()
    llm = speak(propose(bad), reply())

    assert send(order).json()["proposals"] == []
    assert llm.results()[0][1] is True


def test_price_can_not_come_from_the_model(shop, speak):
    order = shop.order()
    change = add_change(shop.meat) | {"unit_price": "1.00"}
    llm = speak(propose(change), reply())

    assert send(order).json()["proposals"] == []
    assert llm.results()[0][1] is True


def test_another_caterers_dish_is_refused(shop, other_shop, speak):
    order = shop.order()
    llm = speak(propose(add_change(other_shop.meat)), reply())

    assert send(order).json()["proposals"] == []
    assert llm.results()[0][0]["error"] == "not_found"


def test_unavailable_dish_is_refused(shop, speak):
    shop.patch(f"dishes/{shop.meat['id']}", {"is_available": False})
    order = shop.order()
    llm = speak(propose(add_change(shop.meat)), reply())

    assert send(order).json()["proposals"] == []
    assert llm.results()[0][0]["error"] == "dish_unavailable"


def test_blocked_kashrut_mix_is_refused(shop, speak):
    shop.patch("profile", {"kashrut_mixing_rule": "block"})
    order = shop.order()
    order.add(shop.meat, "1")
    llm = speak(propose(add_change(shop.dairy)), reply())

    assert send(order).json()["proposals"] == []
    assert llm.results()[0][0]["error"] == "kashrut_mixing_blocked"


def test_guest_counts_can_change_through_a_proposal(shop, speak):
    order = shop.order()
    change = {"type": "update_details", "adults": 30, "dietary_notes": "ללא אגוזים"}
    proposal = proposal_for(order, propose(change), speak)

    assert post(order, proposal, "approve").status_code == 200

    event = seen(order)["event"]
    assert (event["adults"], event["dietary_notes"]) == (30, "ללא אגוזים")


def test_chat_and_proposals_need_the_token(shop, speak):
    order = shop.order()
    proposal = proposal_for(order, propose(add_change(shop.meat)), speak)
    url = f"{order.url}/proposals/{proposal['id']}/approve"

    assert order.client.post(url).status_code == 401
    wrong = {"X-Order-Token": "wrong"}
    assert order.client.post(url, headers=wrong).status_code == 404
    assert order.client.post(f"{order.url}/chat", json={"message": "א"}).status_code == 401
    assert seen(order)["lines"] == []


def test_one_order_can_not_touch_another_orders_proposal(shop, other_shop, speak):
    mine = shop.order()
    second = shop.order()
    foreign = other_shop.order()
    proposal = proposal_for(mine, propose(add_change(shop.meat)), speak)

    for other in (second, foreign):
        url = f"{other.url}/proposals/{proposal['id']}/approve"
        assert other.client.post(url, headers=other.headers).status_code == 404
    assert seen(mine)["lines"] == []


def test_tool_arguments_can_not_point_at_another_order(shop, other_shop, speak):
    mine = shop.order()
    other = shop.order()
    llm = speak(use("get_current_order", {"order_id": other.data["id"]}), reply())

    send(mine)

    assert llm.results()[0][1] is True


def test_approve_on_a_submitted_order_is_refused(shop, speak):
    order = shop.order()
    order.add(shop.meat)
    proposal = proposal_for(order, propose(add_change(shop.dairy)), speak)
    order.data = seen(order)
    order.store(order.submit(acknowledge_kashrut_warning=True))

    assert code(post(order, proposal, "approve")) == (409, "invalid_transition")
    assert len(seen(order)["lines"]) == 1


def test_chat_stops_after_submission(shop, speak):
    order = shop.order()
    order.add(shop.meat)
    order.store(order.submit())
    speak(reply())

    assert code(send(order)) == (409, "invalid_transition")


def test_unknown_stays_unknown(shop, speak):
    plain = shop.post(
        "dishes",
        {
            "category_id": shop.category["id"],
            "name": "מרק",
            "pricing_unit": "per_tray",
            "unit_price": "10.00",
        },
    )
    order = shop.order()
    llm = speak(
        use("get_dish_details", {"dish_id": plain["id"]}),
        reply(),
    )

    send(order)

    result = llm.results()[0][0]
    assert result["calories_per_portion"] == "unknown"
    assert result["kashrut_class"] == "unknown"
    assert result["is_vegan"] == "unknown"
    assert set(result["allergens"].values()) == {"unknown"}


def test_filter_never_counts_unknown_as_a_match(shop, speak):
    order = shop.order()
    llm = speak(use("get_available_dishes", {"vegan": True}), reply())

    send(order)

    assert llm.results()[0][0]["dishes"] == []


def test_every_tool_reads_only_this_caterer(shop, other_shop, speak):
    order = shop.order()
    llm = speak(
        use("get_menu_categories"),
        use("get_available_dishes"),
        use("get_dish_details", {"dish_id": other_shop.meat["id"]}),
        reply(),
    )

    send(order)

    results = llm.results()
    assert [c["category_id"] for c in results[0][0]["categories"]] == [shop.category["id"]]
    assert {d["dish_id"] for d in results[1][0]["dishes"]} == {shop.meat["id"], shop.dairy["id"]}
    assert results[2][1] is True


def test_private_details_never_reach_the_model(shop, speak):
    order = shop.order(
        fulfillment_type="delivery",
        time_slot_id=shop.delivery_slot["id"],
        delivery_city="חיפה",
        delivery_address="רחוב סודי 7",
    )
    order.add(shop.meat)
    llm = speak(
        use("get_current_order"),
        use("get_order_pricing"),
        use("get_quantity_recommendations"),
        use("get_kashrut_check"),
        reply(),
    )

    send(order)

    sent = json.dumps(
        [str(request) for request in llm.requests] + [result for result, _ in llm.results()],
        ensure_ascii=False,
    )
    for secret in ("דנה לוי", "050-1234567", "רחוב סודי", order.token, "access_token"):
        assert secret not in sent


def test_system_prompt_is_hebrew_and_names_the_caterer(shop, speak):
    order = shop.order()
    llm = speak(reply())

    send(order)

    assert "ענה תמיד בעברית" in llm.requests[0]["system"]
    assert "unknown" in llm.requests[0]["system"]


def test_no_approve_tool_exists():
    names = {tool["name"] for tool in definitions()}
    assert len(names) == 8
    assert not {name for name in names if "approve" in name or "submit" in name}
    assert not any("confirm" in name for name in names)


def test_conversation_history_is_kept_and_sent(shop, speak):
    order = shop.order()
    speak(reply("תשובה ראשונה"))
    send(order, "שאלה ראשונה")
    llm = speak(reply("תשובה שנייה"))
    send(order, "שאלה שנייה")

    assert [m["content"] for m in llm.requests[0]["messages"]] == [
        "שאלה ראשונה",
        "תשובה ראשונה",
        "שאלה שנייה",
    ]
    state = order.client.get(f"{order.url}/chat", headers=order.headers).json()
    assert [m["text"] for m in state["messages"]] == [
        "שאלה ראשונה",
        "תשובה ראשונה",
        "שאלה שנייה",
        "תשובה שנייה",
    ]


def test_another_orders_chat_stays_private(shop, speak):
    first = shop.order()
    second = shop.order()
    speak(reply("סוד"))
    send(first, "שאלה")

    state = second.client.get(f"{second.url}/chat", headers=second.headers).json()
    assert state["messages"] == []


def test_usage_limit_stops_chat_but_not_ordering(shop, speak, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_monthly_message_limit", 2)
    order = shop.order()
    llm = speak(reply(), reply(), reply())

    assert send(order).status_code == 200
    assert send(order).status_code == 200
    assert code(send(order)) == (429, "ai_limit_reached")

    assert len(llm.requests) == 2
    assert order.add(shop.meat)["total"] == "200.00"


def test_limit_is_per_caterer(shop, other_shop, speak, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_monthly_message_limit", 1)
    speak(reply(), reply())
    assert send(shop.order()).status_code == 200
    assert send(other_shop.order()).status_code == 200


def test_usage_rows_exist_per_caterer(shop, speak, session):
    speak(reply())
    send(shop.order())
    assert session.scalar(text("select sum(message_count) from ai_usage")) == 1


def test_one_order_can_not_spend_the_whole_allowance(shop, speak, session):
    order = shop.order()
    speak(reply())
    send(order)
    session.execute(
        text(
            "insert into ai_messages (caterer_id, conversation_id, role, content) "
            "select caterer_id, conversation_id, 'user', '{\"text\": \"א\"}' "
            "from ai_messages, generate_series(1, 100) limit 100"
        )
    )
    session.commit()
    speak(reply())

    assert code(send(order)) == (429, "ai_limit_reached")


def test_no_key_turns_chat_off_but_not_ordering(shop):
    app.dependency_overrides[get_llm] = lambda: None
    order = shop.order()

    state = order.client.get(f"{order.url}/chat", headers=order.headers).json()
    assert state["available"] is False
    assert code(send(order)) == (503, "ai_unavailable")
    assert order.add(shop.meat)["total"] == "200.00"


def test_provider_failure_saves_nothing(shop, speak):
    order = shop.order()
    speak(LLMError("RateLimitError"))

    assert code(send(order)) == (503, "ai_failed")

    state = order.client.get(f"{order.url}/chat", headers=order.headers).json()
    assert state["messages"] == []
    assert order.add(shop.meat)["total"] == "200.00"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_cut_off_turn_never_runs_its_tools(shop, speak, stop_reason):
    order = shop.order()
    partial = propose(add_change(shop.meat))
    partial.stop_reason = stop_reason
    speak(partial)

    body = send(order).json()

    assert body["proposals"] == []
    assert body["reply"]


def test_tool_loop_has_a_step_cap(shop, speak):
    order = shop.order()
    llm = speak(*[use("get_menu_categories") for _ in range(20)])

    assert send(order).status_code == 200
    assert len(llm.requests) == 8


def test_message_length_is_limited(shop, speak):
    order = shop.order()
    speak(reply())
    assert send(order, "א" * 1001).status_code == 422


def test_admin_routes_are_unaffected_by_order_tokens(shop, speak):
    order = shop.order()
    response = order.client.get(f"{ADMIN}/orders", headers=order.headers)
    assert response.status_code == 401


def test_same_dish_twice_in_a_proposal_is_refused(shop, speak):
    order = shop.order()
    order.add(shop.meat, "1")
    remove = {"type": "remove_item", "dish_id": shop.meat["id"]}
    llm = speak(propose(remove, add_change(shop.meat)), reply())

    assert send(order).json()["proposals"] == []
    assert llm.results()[0][1] is True


def test_empty_update_is_refused_and_keeps_the_pending_card(shop, speak):
    order = shop.order()
    first = proposal_for(order, propose(add_change(shop.meat)), speak)
    speak(propose({"type": "update_details"}), reply())

    assert [item["id"] for item in send(order).json()["proposals"]] == [first["id"]]


def test_quantity_too_large_to_price_becomes_a_tool_error(shop, speak):
    order = shop.order()
    llm = speak(propose(add_change(shop.meat, "99999999.00")), reply())

    response = send(order)

    assert response.status_code == 200
    assert llm.results()[0][1] is True
    assert seen(order)["lines"] == []


def test_deactivated_caterer_has_no_chat(shop, speak, session):
    order = shop.order()
    llm = speak(reply())
    session.execute(text("update caterers set is_active = false"))
    session.commit()

    assert send(order).status_code == 404
    assert llm.requests == []


def test_null_character_in_a_message_is_refused(shop, speak):
    llm = speak(reply())
    assert send(shop.order(), "א\x00ב").status_code == 422
    assert llm.requests == []
