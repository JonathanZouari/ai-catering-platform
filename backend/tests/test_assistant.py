"""Phase 4: the AI ordering assistant (docs/AI_AGENT_DESIGN.md §6). Claude is faked: the safety
lives in the services, so it is tested without a model."""

import copy
import json
import uuid

import anthropic
import pytest
from anthropic.types.beta import BetaMessage

from app.agents import assistant, tools
from app.core.config import get_settings
from tests.conftest import AUTH, token
from tests.test_customer_orders import fixed_today, menu, setup  # noqa: F401
from tests.test_submit import draft_with_item, outbox  # noqa: F401

pytestmark = pytest.mark.usefixtures("supabase")


def msg(stop, *blocks):
    return BetaMessage.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": list(blocks),
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )


def say(text):
    return msg("end_turn", {"type": "text", "text": text})


def call(name, args=None, id_="toolu_1"):
    return {"type": "tool_use", "id": id_, "name": name, "input": args or {}}


THINKING = {"type": "thinking", "thinking": "", "signature": "sig-abc"}


class FakeClaude:
    """Plays a script of responses; records every request."""

    def __init__(self):
        self.script, self.requests = [], []
        self.beta = self.messages = self

    def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def tool_results(self, n=-1):
        """The tool_result blocks sent in request n, parsed."""
        last = self.requests[n]["messages"][-1]["content"]
        return [(json.loads(b["content"]), b["is_error"]) for b in last]


@pytest.fixture
def claude(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")
    monkeypatch.setattr(assistant, "get_client", lambda: fake)
    return fake


@pytest.fixture
def order(client, setup):
    """A draft with 3 trays of hummus (120 each)."""
    headers, slots = setup
    tray, kg, off = menu(client)
    url, version = draft_with_item(client, headers, slots["pickup"], tray)
    return {"headers": headers, "url": url, "chat": f"{url}/chat", **locals()}


def chat(client, o, text="תציע לי תפריט"):
    return client.post(o["chat"], json={"message": text}, headers=o["headers"])


def propose(changes, rationale="הוספתי בריסקט"):
    return call("propose_order_change", {"changes": changes, "rationale": rationale}, "toolu_p")


def test_unavailable_without_key(client, order):
    res = chat(client, order)
    assert res.status_code == 503 and res.json()["error"]["code"] == "assistant_unavailable"
    view = client.get(order["chat"], headers=order["headers"]).json()
    assert view["available"] is False and view["messages"] == []


def test_reads_then_proposes_without_touching_the_order(client, order, claude):
    o = order
    claude.script = [
        msg(
            "tool_use",
            THINKING,
            call("get_current_order", id_="toolu_a"),
            call("get_menu", id_="toolu_b"),
        ),
        msg("tool_use", propose([{"op": "add_item", "dish_id": o["kg"], "quantity": "2.5"}])),
        say('הצעתי להוסיף 2.5 ק"ג בריסקט. אפשר לאשר בכרטיס.'),
    ]
    res = chat(client, o)
    assert res.status_code == 200, res.text
    view = res.json()
    assert [(m["role"], m["text"]) for m in view["messages"]] == [
        ("user", "תציע לי תפריט"),
        ("assistant", 'הצעתי להוסיף 2.5 ק"ג בריסקט. אפשר לאשר בכרטיס.'),
    ]
    p = view["proposal"]
    assert p["proposed_by"] == "assistant" and p["status"] == "pending"
    assert (p["price_before"], p["price_after"]) == ("360.00", "909.98")
    assert [(c["op"], c["name"]) for c in p["changes"]] == [("add_item", "בריסקט")]
    assert view["remaining_today"] == 29

    # both reads ran and came back in one message, in call order
    (current, err1), (menu_out, err2) = claude.tool_results(1)
    assert not err1 and not err2
    assert current["pricing"]["total"] == "360.00" and current["event"]["adults"] == 40
    names = {d["name"]: d for d in menu_out["dishes"]}
    assert "טופו" not in names  # unavailable dishes are not on the menu
    brisket = names["בריסקט"]
    assert brisket["vegetarian"] is None and brisket["allergens"] == {}  # unknown, not "no"
    # the model's thinking block went back exactly as it came
    assert claude.requests[1]["messages"][1]["content"][0] == THINKING

    # nothing changed in the order itself
    now = client.get(o["url"], headers=o["headers"]).json()
    assert now["version"] == o["version"] and now["items"] == [
        {"dish_id": o["tray"], "quantity": "3.00"}
    ]
    request = claude.requests[0]
    assert request["model"] == "claude-sonnet-5-5" and request["system"] == assistant.SYSTEM


def test_accept_applies_once_and_keeps_the_draft(client, order, claude, outbox):
    o = order
    claude.script = [
        msg("tool_use", propose([{"op": "set_quantity", "dish_id": o["tray"], "quantity": "5"}])),
        say("שיניתי ל-5 מגשים."),
    ]
    p = chat(client, o).json()["proposal"]
    url = f"{o['url']}/proposals/{p['id']}"
    res = client.post(f"{url}/accept", headers=o["headers"])
    assert res.status_code == 200 and res.json()["status"] == "accepted"
    now = client.get(o["url"], headers=o["headers"]).json()
    assert now["status"] == "draft" and now["version"] == o["version"] + 1
    assert now["items"] == [{"dish_id": o["tray"], "quantity": "5.00"}]
    assert now["total"] is None  # prices stay live until submission
    pricing = client.get(f"{o['url']}/pricing", headers=o["headers"]).json()
    assert pricing["total"] == "600.00"

    again = client.post(f"{url}/accept", headers=o["headers"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "proposal_not_pending"
    assert outbox == []  # assistant proposals email nobody
    mine = client.get("/api/me/orders", headers=o["headers"]).json()
    assert mine[0]["has_pending_proposal"] is False


def test_decline_and_stale_proposals_change_nothing(client, order, claude):
    o = order
    first = [{"op": "remove_item", "dish_id": o["tray"], "quantity": None}]
    claude.script = [msg("tool_use", propose(first)), say("הסרתי.")]
    p = chat(client, o).json()["proposal"]
    res = client.post(
        f"{o['url']}/proposals/{p['id']}/decline", json={"note": "לא"}, headers=o["headers"]
    )
    assert res.json()["status"] == "declined"
    assert client.get(o["url"], headers=o["headers"]).json()["version"] == o["version"]

    claude.script = [
        msg("tool_use", propose([{"op": "add_item", "dish_id": o["kg"], "quantity": "1"}])),
        say("הוספתי."),
    ]
    p = chat(client, o).json()["proposal"]
    # the customer edits the order meanwhile: the proposal no longer fits
    edit = {"quantity": "4", "version": o["version"]}
    client.put(f"{o['url']}/items/{o['tray']}", json=edit, headers=o["headers"])
    res = client.post(f"{o['url']}/proposals/{p['id']}/accept", headers=o["headers"])
    assert res.status_code == 409 and res.json()["error"]["code"] == "proposal_expired"
    now = client.get(o["url"], headers=o["headers"]).json()
    assert now["items"] == [{"dish_id": o["tray"], "quantity": "4.00"}]


def test_a_new_proposal_replaces_the_open_one(client, order, claude):
    o = order
    claude.script = [
        msg("tool_use", propose([{"op": "set_quantity", "dish_id": o["tray"], "quantity": "4"}])),
        say("4."),
        msg("tool_use", propose([{"op": "set_quantity", "dish_id": o["tray"], "quantity": "6"}])),
        say("6."),
    ]
    first = chat(client, o).json()["proposal"]
    second = chat(client, o, "בעצם 6").json()["proposal"]
    assert second["id"] != first["id"] and second["changes"][0]["to_quantity"] == "6"
    listed = client.get(f"{o['url']}/proposals", headers=o["headers"]).json()
    assert {x["id"]: x["status"] for x in listed} == {
        first["id"]: "cancelled",
        second["id"]: "pending",
    }


def test_bad_proposals_go_back_to_the_model_as_errors(client, order, claude):
    o = order
    claude.script = [
        msg(
            "tool_use",
            propose([{"op": "add_item", "dish_id": o["off"], "quantity": "10"}]),
        ),
        msg(
            "tool_use", propose([{"op": "add_item", "dish_id": str(uuid.uuid4()), "quantity": "1"}])
        ),
        msg("tool_use", propose([{"op": "add_item", "dish_id": o["kg"], "quantity": None}])),
        msg("tool_use", propose([{"op": "set_quantity", "dish_id": o["tray"], "quantity": "1"}])),
        msg("tool_use", call("drop_tables")),
        say("לא הצלחתי."),
    ]
    view = chat(client, o).json()
    codes = [claude.tool_results(n)[0] for n in range(1, 6)]
    assert [(out["error"]["code"], err) for out, err in codes] == [
        ("dish_unavailable", True),
        ("dish_unavailable", True),
        ("invalid_arguments", True),
        ("below_minimum", True),
        ("unknown_tool", True),
    ]
    assert view["proposal"] is None
    assert client.get(o["url"], headers=o["headers"]).json()["version"] == o["version"]


def test_scope_access_and_limits(client, order, claude):
    o = order
    # no tool lets the model name an order: it is bound from the request
    assert all("order" not in json.dumps(t["input_schema"]) for t in tools.TOOLS)

    stranger = token(uuid.uuid4(), email="eve@example.com")
    client.put("/api/me", json={"full_name": "איב", "phone": "050-9999999"}, headers=stranger)
    assert client.post(o["chat"], json={"message": "היי"}, headers=stranger).status_code == 404
    assert client.get(o["chat"], headers=stranger).status_code == 404
    assert client.post(o["chat"], json={"message": "היי"}).status_code == 401
    assert claude.requests == []

    limit = {"child_portion": "0.75", "lead_days": 3, "assistant_daily_limit": 1}
    client.put("/api/admin/settings", json=limit, headers=AUTH)
    claude.script = [say("שלום!")]
    assert chat(client, o, "שלום").json()["remaining_today"] == 0
    res = chat(client, o, "עוד שאלה")
    assert res.status_code == 429 and res.json()["error"]["code"] == "assistant_limit"

    limit["assistant_daily_limit"] = 30
    client.put("/api/admin/settings", json=limit, headers=AUTH)
    version = client.get(o["url"], headers=o["headers"]).json()["version"]
    client.post(f"{o['url']}/submit", json={"version": version}, headers=o["headers"])
    res = chat(client, o, "תוסיף עוד")
    assert res.status_code == 409 and res.json()["error"]["code"] == "invalid_transition"


def test_failures_leave_a_usable_history(client, order, claude):
    o = order
    claude.script = [
        msg("tool_use", call("get_menu")),
        anthropic.APIConnectionError(request=None),
    ]
    res = chat(client, o)
    assert res.status_code == 502 and res.json()["error"]["code"] == "assistant_failed"

    claude.script = [msg("refusal")]
    view = chat(client, o, "שוב").json()
    assert view["messages"][-1] == {"role": "assistant", "text": assistant.FALLBACK_REPLY}
    # the failed turn stored only the customer's message: no tool call without its result
    sent = claude.requests[-1]["messages"]
    assert [m["role"] for m in sent] == ["user", "user"]
    assert all(b["type"] == "text" for m in sent for b in m["content"])

    claude.script = [msg("tool_use", call("get_menu"))] * assistant.MAX_ROUNDS
    view = chat(client, o, "ושוב").json()
    assert view["messages"][-1]["text"] == assistant.FALLBACK_REPLY


def test_submitting_expires_the_open_proposal(client, order, claude):
    o = order
    claude.script = [
        msg("tool_use", propose([{"op": "set_quantity", "dish_id": o["tray"], "quantity": "4"}])),
        say("4."),
    ]
    p = chat(client, o).json()["proposal"]
    client.post(f"{o['url']}/submit", json={"version": o["version"]}, headers=o["headers"])
    listed = client.get(f"{o['url']}/proposals", headers=o["headers"]).json()
    assert [(x["id"], x["status"]) for x in listed] == [(p["id"], "expired")]
    order_id = o["url"].rsplit("/", 1)[1]
    assert client.post(f"/api/admin/orders/{order_id}/approve", headers=AUTH).status_code == 200
