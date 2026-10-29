# Iteration 7: emailer.send_email retry-on-429 logic (mocked httpx, no real emails) + reply integration
import os
import sys
import asyncio

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
import emailer  # noqa: E402
from fastapi import HTTPException  # noqa: E402

RATE_MSG = "Mejltjänsten har för många utskick just nu. Vänta en minut och försök igen."
SAFE_HTML = "<p>Hej, din order är bekräftad.</p>"


def _resp(status, body, headers=None):
    req = httpx.Request("POST", f"{emailer.EMAIL_BASE_URL}/api/v1/email/send")
    return httpx.Response(status, json=body, headers=headers or {}, request=req)


@pytest.fixture
def patched(monkeypatch):
    """Patches httpx.AsyncClient.post with a scripted sequence and records asyncio.sleep calls."""
    state = {"calls": 0, "sleeps": [], "seq": []}

    async def fake_post(self, url, **kw):
        r = state["seq"][min(state["calls"], len(state["seq"]) - 1)]
        state["calls"] += 1
        return r

    async def fake_sleep(s):
        state["sleeps"].append(s)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(emailer.asyncio, "sleep", fake_sleep)
    return state


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


RL = {"error": "Rate limited", "message": "email rate limit exceeded", "code": "rate_limited"}


class TestRetryLogic:
    def test_429_then_success(self, patched):
        patched["seq"] = [_resp(429, RL), _resp(202, {"id": "msg_1"})]
        rid = run(emailer.send_email(to="delivered@resend.dev", subject="Test", html=SAFE_HTML))
        assert rid == "msg_1"
        assert patched["calls"] == 2
        assert patched["sleeps"] == [2]

    def test_two_429_then_success(self, patched):
        patched["seq"] = [_resp(429, RL), _resp(429, RL), _resp(200, {"id": "msg_2"})]
        rid = run(emailer.send_email(to="delivered@resend.dev", subject="Test", html=SAFE_HTML))
        assert rid == "msg_2" and patched["calls"] == 3
        assert patched["sleeps"] == [2, 4]

    def test_all_429_raises_503_swedish(self, patched):
        patched["seq"] = [_resp(429, RL)]
        with pytest.raises(HTTPException) as ei:
            run(emailer.send_email(to="delivered@resend.dev", subject="Test", html=SAFE_HTML))
        assert ei.value.status_code == 503
        assert ei.value.detail == RATE_MSG
        assert patched["calls"] == 4  # 1 + 3 retries
        assert patched["sleeps"] == [2, 4, 8]

    def test_retry_after_header_respected_and_capped(self, patched):
        patched["seq"] = [_resp(429, RL, {"Retry-After": "60"}), _resp(429, RL, {"Retry-After": "5"}),
                          _resp(429, RL, {"Retry-After": "abc"}), _resp(202, {"id": "x"})]
        run(emailer.send_email(to="delivered@resend.dev", subject="Test", html=SAFE_HTML))
        assert patched["sleeps"] == [15, 5, 8]

    def test_422_not_retried(self, patched):
        patched["seq"] = [_resp(422, {"code": "undeliverable", "message": "bad"})]
        with pytest.raises(HTTPException) as ei:
            run(emailer.send_email(to="delivered@resend.dev", subject="Test", html=SAFE_HTML))
        assert ei.value.status_code == 502
        assert patched["calls"] == 1 and patched["sleeps"] == []

    def test_insufficient_credits_not_retried(self, patched):
        patched["seq"] = [_resp(402, {"code": "insufficient_credits"})]
        with pytest.raises(HTTPException) as ei:
            run(emailer.send_email(to="delivered@resend.dev", subject="Test", html=SAFE_HTML))
        assert ei.value.status_code == 503 and ei.value.detail == "E-post är tillfälligt otillgänglig"
        assert patched["calls"] == 1

    def test_500_not_retried(self, patched):
        patched["seq"] = [_resp(500, {"error": "boom"})]
        with pytest.raises(HTTPException) as ei:
            run(emailer.send_email(to="delivered@resend.dev", subject="Test", html=SAFE_HTML))
        assert ei.value.status_code == 502 and patched["calls"] == 1


class TestSendOrderReplyMessage:
    """server.send_order_reply surfaces 503 detail, generic text for other errors (send_email mocked)."""

    def _order(self):
        return {"id": "TEST_none", "order_number": "B0", "customer": {"email": "delivered@resend.dev", "company": "X"},
                "items": [], "replies": [], "comment": "", "created_at": "2026-01-01T00:00:00"}

    def test_rate_limit_detail_surfaced(self, monkeypatch):
        import server

        async def boom(**kw):
            raise HTTPException(503, RATE_MSG)
        monkeypatch.setattr(server, "send_email", boom)

        async def go():
            server.client.get_io_loop = asyncio.get_running_loop  # bind motor to this loop
            return await server.send_order_reply(self._order(), "Leverans torsdag")
        err = run(go())
        assert err == RATE_MSG

    def test_other_error_generic(self, monkeypatch):
        import server

        async def boom(**kw):
            raise HTTPException(502, "Kunde inte skicka e-post")
        monkeypatch.setattr(server, "send_email", boom)

        async def go():
            server.client.get_io_loop = asyncio.get_running_loop
            return await server.send_order_reply(self._order(), "Leverans torsdag")
        err = run(go())
        assert err == "Mejlet kunde inte skickas just nu. Försök igen om en stund."
