import asyncio
import logging
import time
import unittest
from threading import Thread
from typing import Optional

from slack_sdk.socket_mode.request import SocketModeRequest

from slack_sdk.socket_mode.async_client import AsyncBaseSocketModeClient
from slack_sdk.socket_mode.websockets import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient
from tests.slack_sdk.socket_mode.mock_socket_mode_server import (
    start_socket_mode_server,
    socket_mode_envelopes,
)
from tests.slack_sdk.socket_mode.mock_web_api_server import (
    setup_mock_web_api_server,
    cleanup_mock_web_api_server,
)
from tests.slack_sdk_async.helpers import async_test


class TestInteractionsWebsockets(unittest.TestCase):
    logger = logging.getLogger(__name__)

    def setUp(self):
        setup_mock_web_api_server(self)
        self.web_client = AsyncWebClient(
            token="xoxb-api_test", base_url="http://localhost:8888",
        )

    def tearDown(self):
        cleanup_mock_web_api_server(self)

    @async_test
    async def test_interactions(self):
        t = Thread(target=start_socket_mode_server(3002))
        t.daemon = True
        t.start()

        received_messages = []
        received_socket_mode_requests = []

        async def message_handler(
            receiver: AsyncBaseSocketModeClient,
            message: dict,
            raw_message: Optional[str],
        ):
            self.logger.info(f"Raw Message: {raw_message}")
            received_messages.append(raw_message)

        async def socket_mode_listener(
            receiver: AsyncBaseSocketModeClient, request: SocketModeRequest,
        ):
            self.logger.info(f"Socket Mode Request: {request}")
            received_socket_mode_requests.append(request)

        client = SocketModeClient(
            app_token="xapp-A111-222-xyz",
            web_client=self.web_client,
            auto_reconnect_enabled=False,
        )
        client.message_listeners.append(message_handler)
        client.socket_mode_request_listeners.append(socket_mode_listener)

        try:
            time.sleep(1)  # wait for the server
            client.wss_uri = "ws://0.0.0.0:3002/link"
            await client.connect()
            await asyncio.sleep(1)  # wait for the message receiver

            await client.send_message("foo")
            await client.send_message("bar")
            await client.send_message("baz")

            expected = socket_mode_envelopes + ["foo", "bar", "baz"]
            expected.sort()

            count = 0
            while count < 10 and len(received_messages) < len(expected):
                await asyncio.sleep(0.2)
                count += 0.2

            received_messages.sort()
            self.assertEqual(received_messages, expected)

            self.assertEqual(
                len(socket_mode_envelopes), len(received_socket_mode_requests)
            )
        finally:
            await client.close()