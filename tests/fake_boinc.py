"""
A fake BOINC client to test against

It speaks just enough of the GUI RPC framing to record what was sent and answer with a canned
reply, so no test needs a real BOINC client or the network.
"""

import asyncio
import unittest

from aioboinc import init_rpc_client

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
