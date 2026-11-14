"""
Tests for the RPC client against a fake BOINC client

The fake speaks just enough of the GUI RPC framing to record what was sent and answer with a canned
reply, so nothing here needs a real BOINC client or the network.
"""

import asyncio
import unittest
from hashlib import md5

from aioboinc import init_rpc_client
from aioboinc.rpc_client import BOINCClientError, Mode, RPCClient

from .fixtures import web_state

END_OF_MESSAGE = b"\x03"
ENCODING = "ISO-8859-1"
SUCCESS = "<boinc_gui_rpc_reply><success/></boinc_gui_rpc_reply>"


def _unwrap(request: str) -> str:
    """Strip the request envelope, leaving the element the caller built"""
    prefix, suffix = "<boinc_gui_rpc_request>", "</boinc_gui_rpc_request>"
    assert request.startswith(prefix) and request.endswith(suffix), request
    return request[len(prefix):-len(suffix)]


class FakeBoinc:
    """
    Answers every request with the next reply in `replies`, or `default` once they run out
    """

    def __init__(self, replies=(), default=SUCCESS):
        self.replies = list(replies)
        self.default = default
        self.requests = []
        self.disconnected = asyncio.Event()
        self._server = None

    async def start(self):
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self._server.sockets[0].getsockname()[1]

    async def stop(self):
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader, writer):
        try:
            while True:
                try:
                    message = await reader.readuntil(END_OF_MESSAGE)
                except (asyncio.IncompleteReadError, ConnectionError):
                    break
                self.requests.append(_unwrap(str(message[:-1], encoding=ENCODING)))
                reply = self.replies.pop(0) if self.replies else self.default
                writer.write(bytes(reply, encoding=ENCODING) + END_OF_MESSAGE)
                await writer.drain()
        finally:
            self.disconnected.set()
            writer.close()


class RPCClientTestCase(unittest.IsolatedAsyncioTestCase):

    replies = ()

    async def asyncSetUp(self):
        self.boinc = FakeBoinc(self.replies)
        port = await self.boinc.start()
        self.addAsyncCleanup(self.boinc.stop)
        self.client = await init_rpc_client("127.0.0.1", "secret", port)
        self.addAsyncCleanup(self.client.close)


class SetModeTest(RPCClientTestCase):

    async def test_set_run_mode_sends_the_duration(self):
        self.assertIs(await self.client.set_run_mode(Mode.NEVER, 60), True)
        self.assertEqual(
            self.boinc.requests, ["<set_run_mode><never/><duration>60</duration></set_run_mode>"]
        )

    async def test_set_network_mode_sends_the_duration(self):
        self.assertIs(await self.client.set_network_mode(Mode.ALWAYS, 3600), True)
        self.assertEqual(
            self.boinc.requests,
            ["<set_network_mode><always/><duration>3600</duration></set_network_mode>"],
        )

    async def test_set_gpu_mode_sends_the_duration(self):
        self.assertIs(await self.client.set_gpu_mode(Mode.AUTO, 1.5), True)
        self.assertEqual(
            self.boinc.requests, ["<set_gpu_mode><auto/><duration>1.5</duration></set_gpu_mode>"]
        )

    async def test_duration_defaults_to_permanent(self):
        await self.client.set_run_mode(Mode.RESTORE)
        self.assertEqual(
            self.boinc.requests, ["<set_run_mode><restore/><duration>0</duration></set_run_mode>"]
        )


class AuthorizeTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1234.5678</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><authorized/></boinc_gui_rpc_reply>",
    )

    async def test_answers_the_nonce_with_its_salted_hash(self):
        self.assertIs(await self.client.authorize(), True)
        expected = md5(b"1234.5678secret").hexdigest()
        self.assertEqual(
            self.boinc.requests,
            ["<auth1/>", "<auth2><nonce_hash>{}</nonce_hash></auth2>".format(expected)],
        )

    async def test_without_a_password_sends_nothing(self):
        self.client.password = None
        self.assertIs(await self.client.authorize(), False)
        self.assertEqual(self.boinc.requests, [])


class RejectedAuthorizeTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1234.5678</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><unauthorized/></boinc_gui_rpc_reply>",
    )

    async def test_wrong_password_returns_false(self):
        self.assertIs(await self.client.authorize(), False)


class UnauthorizedTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><unauthorized/></boinc_gui_rpc_reply>",)

    async def test_control_request_returns_false(self):
        self.assertIs(await self.client.set_run_mode(Mode.NEVER), False)


class ErrorTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><error>no such result</error></boinc_gui_rpc_reply>",)

    async def test_control_request_raises(self):
        with self.assertRaisesRegex(BOINCClientError, "no such result"):
            await self.client.suspend_result("https://example.org/", "task_0")
        self.assertEqual(
            self.boinc.requests,
            [
                "<suspend_result><project_url>https://example.org/</project_url>"
                "<name>task_0</name></suspend_result>"
            ],
        )


class QueryTest(RPCClientTestCase):

    replies = (web_state.cc_status,)

    async def test_get_cc_status_parses_numbers(self):
        status = await self.client.get_cc_status()
        self.assertEqual(self.boinc.requests, ["<get_cc_status/>"])
        self.assertEqual(status["task_mode"], 2)
        self.assertEqual(status["task_mode_delay"], 0.0)


class CloseTest(RPCClientTestCase):

    async def test_close_hangs_up(self):
        await self.client.close()
        await asyncio.wait_for(self.boinc.disconnected.wait(), timeout=5)
        self.assertFalse(self.client.connected)

    async def test_close_twice_is_harmless(self):
        await self.client.close()
        await self.client.close()

    async def test_request_after_close_raises(self):
        await self.client.close()
        with self.assertRaises(ConnectionError):
            await self.client.get_cc_status()

    async def test_can_connect_again_after_close(self):
        await self.client.close()
        await self.client.connect()
        self.assertIs(await self.client.set_run_mode(Mode.AUTO), True)


class NeverConnectedTest(unittest.IsolatedAsyncioTestCase):

    async def test_close_is_harmless(self):
        await RPCClient("127.0.0.1").close()

    async def test_request_raises(self):
        with self.assertRaises(ConnectionError):
            await RPCClient("127.0.0.1").get_cc_status()


if __name__ == "__main__":
    unittest.main()
