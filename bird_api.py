"""Bird.com WhatsApp API integration module."""

import os
from typing import Any

import aiohttp

from logger import logger


BIRD_API_BASE_URL = "https://api.bird.com"


class BirdAPIError(Exception):
    """Raised when the Bird.com API returns an error response."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"Bird API error {status}: {message}")


class BirdAPIClient:
    """
    Async HTTP client for the Bird.com WhatsApp Messaging API.

    Environment variables used:
        BIRD_API_KEY       - API access key
        BIRD_WORKSPACE_ID  - Bird workspace identifier
        BIRD_CHANNEL_ID    - WhatsApp channel identifier
    """

    def __init__(
        self,
        api_key: str | None = None,
        workspace_id: str | None = None,
        channel_id: str | None = None,
        base_url: str = BIRD_API_BASE_URL,
    ) -> None:
        self.api_key = api_key or os.environ["BIRD_API_KEY"]
        self.workspace_id = workspace_id or os.environ["BIRD_WORKSPACE_ID"]
        self.channel_id = channel_id or os.environ["BIRD_CHANNEL_ID"]
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return (or create) the shared aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"AccessKey {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_template_message(
        self,
        recipient_phone: str,
        template_id: str,
        template_language: str = "en",
        template_variables: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Send a pre-approved WhatsApp template message via Bird.com.

        Args:
            recipient_phone: E.164 formatted phone number (e.g. '+14155552671').
            template_id: Bird.com / WhatsApp template identifier.
            template_language: ISO language code for the template (default 'en').
            template_variables: Ordered list of variable values for the template body.

        Returns:
            Parsed JSON response dict from Bird.com.

        Raises:
            BirdAPIError: If the API returns a non-2xx status code.
        """
        session = await self._get_session()

        # Build template components
        components: list[dict[str, Any]] = []
        if template_variables:
            parameters = [
                {"type": "text", "text": v} for v in template_variables
            ]
            components.append({"type": "body", "parameters": parameters})

        payload: dict[str, Any] = {
            "receiver": {
                "contacts": [
                    {
                        "identifierValue": recipient_phone,
                        "identifierKey": "phonenumber",
                    }
                ]
            },
            "template": {
                "projectId": template_id,
                "version": "latest",
                "locale": template_language,
                "variables": {
                    str(i): v
                    for i, v in enumerate(template_variables or [])
                },
            },
        }

        url = (
            f"{self.base_url}/workspaces/{self.workspace_id}"
            f"/channels/{self.channel_id}/messages"
        )

        logger.info(
            "Sending WhatsApp template message to %s via Bird.com (template=%s)",
            recipient_phone,
            template_id,
        )

        async with session.post(url, json=payload) as response:
            body = await response.json(content_type=None)

            if response.status >= 400:
                error_message = body.get("message", str(body))
                logger.error(
                    "Bird API error %d for %s: %s",
                    response.status,
                    recipient_phone,
                    error_message,
                )
                raise BirdAPIError(response.status, error_message)

            logger.info(
                "Message sent successfully to %s, response status %d",
                recipient_phone,
                response.status,
            )
            return body

    async def get_message_status(self, message_id: str) -> dict[str, Any]:
        """
        Retrieve the delivery status of a previously sent message.

        Args:
            message_id: The message ID returned by Bird.com after sending.

        Returns:
            Parsed JSON response dict containing status information.

        Raises:
            BirdAPIError: If the API returns a non-2xx status code.
        """
        session = await self._get_session()
        url = (
            f"{self.base_url}/workspaces/{self.workspace_id}"
            f"/messages/{message_id}"
        )

        async with session.get(url) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise BirdAPIError(response.status, body.get("message", str(body)))
            return body
