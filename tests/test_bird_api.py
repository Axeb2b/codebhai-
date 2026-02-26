"""Unit tests for the Bird.com API client (bird_api.py)."""

import pytest
from aioresponses import aioresponses
from unittest.mock import patch
import os

# Set required env vars before importing module
os.environ.setdefault("BIRD_API_KEY", "test_api_key")
os.environ.setdefault("BIRD_WORKSPACE_ID", "ws123")
os.environ.setdefault("BIRD_CHANNEL_ID", "ch456")

from bird_api import BirdAPIClient, BirdAPIError  # noqa: E402


WORKSPACE_ID = "ws123"
CHANNEL_ID = "ch456"
MESSAGES_URL = (
    f"https://api.bird.com/workspaces/{WORKSPACE_ID}/channels/{CHANNEL_ID}/messages"
)


@pytest.fixture
def client():
    return BirdAPIClient(
        api_key="test_key",
        workspace_id=WORKSPACE_ID,
        channel_id=CHANNEL_ID,
    )


@pytest.mark.asyncio
async def test_send_template_message_success(client):
    """A 200 response should return the parsed JSON body."""
    response_body = {"id": "msg-001", "status": "accepted"}

    with aioresponses() as mock:
        mock.post(MESSAGES_URL, status=200, payload=response_body)
        result = await client.send_template_message(
            recipient_phone="+14155552671",
            template_id="tmpl_hello",
            template_language="en",
            template_variables=["Alice"],
        )

    assert result["id"] == "msg-001"
    assert result["status"] == "accepted"
    await client.close()


@pytest.mark.asyncio
async def test_send_template_message_no_variables(client):
    """Sending without template variables should still succeed."""
    response_body = {"id": "msg-002"}

    with aioresponses() as mock:
        mock.post(MESSAGES_URL, status=201, payload=response_body)
        result = await client.send_template_message(
            recipient_phone="+14155552671",
            template_id="tmpl_hello",
        )

    assert result["id"] == "msg-002"
    await client.close()


@pytest.mark.asyncio
async def test_send_template_message_api_error(client):
    """A 4xx response should raise BirdAPIError."""
    response_body = {"message": "Invalid template"}

    with aioresponses() as mock:
        mock.post(MESSAGES_URL, status=400, payload=response_body)
        with pytest.raises(BirdAPIError) as exc_info:
            await client.send_template_message(
                recipient_phone="+14155552671",
                template_id="tmpl_bad",
            )

    assert exc_info.value.status == 400
    assert "Invalid template" in exc_info.value.message
    await client.close()


@pytest.mark.asyncio
async def test_send_template_message_server_error(client):
    """A 5xx response should raise BirdAPIError."""
    with aioresponses() as mock:
        mock.post(MESSAGES_URL, status=500, payload={"message": "Internal error"})
        with pytest.raises(BirdAPIError) as exc_info:
            await client.send_template_message(
                recipient_phone="+14155552671",
                template_id="tmpl_hello",
            )

    assert exc_info.value.status == 500
    await client.close()


@pytest.mark.asyncio
async def test_get_message_status_success(client):
    """get_message_status should return parsed JSON on success."""
    msg_id = "msg-999"
    status_url = f"https://api.bird.com/workspaces/{WORKSPACE_ID}/messages/{msg_id}"
    response_body = {"id": msg_id, "status": "delivered"}

    with aioresponses() as mock:
        mock.get(status_url, status=200, payload=response_body)
        result = await client.get_message_status(msg_id)

    assert result["status"] == "delivered"
    await client.close()


@pytest.mark.asyncio
async def test_get_message_status_not_found(client):
    """get_message_status should raise BirdAPIError for 404."""
    msg_id = "bad-id"
    status_url = f"https://api.bird.com/workspaces/{WORKSPACE_ID}/messages/{msg_id}"

    with aioresponses() as mock:
        mock.get(status_url, status=404, payload={"message": "Not found"})
        with pytest.raises(BirdAPIError) as exc_info:
            await client.get_message_status(msg_id)

    assert exc_info.value.status == 404
    await client.close()


@pytest.mark.asyncio
async def test_close_session(client):
    """close() should close the underlying session."""
    # Trigger session creation
    await client._get_session()
    assert client._session is not None
    assert not client._session.closed

    await client.close()
    assert client._session.closed


def test_bird_api_error_str():
    """BirdAPIError should contain status and message in string representation."""
    err = BirdAPIError(403, "Forbidden")
    assert "403" in str(err)
    assert "Forbidden" in str(err)
