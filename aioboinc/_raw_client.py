"""
Raw client for maintaining the socket connection to the BOINC server
Based on:
https://boinc.berkeley.edu/trac/wiki/GuiRpc
https://boinc.berkeley.edu/trac/wiki/GuiRpcProtocol
https://github.com/BOINC/boinc/blob/master/lib/gui_rpc_client.cpp

Note that this client is Async, based on asyncio
"""

import asyncio
import contextlib
import xml.etree.ElementTree as ET
from socket import AF_INET

from .exceptions import BOINCClientError, BOINCConnectionError, BOINCTimeoutError

GUI_RPC_DEFAULT_PORT = 31416
# Seconds to connect, or to get the reply to a request, before giving up
DEFAULT_TIMEOUT = 30.0
REPLY_TAG = "boinc_gui_rpc_reply"
REQUEST_TAG = "boinc_gui_rpc_request"
END_OF_MESSAGE = b"\x03"
BOINC_ENCODING = "ISO-8859-1"


class _RPCClientRaw:
    """
    Connects to the RPC server and transports whichever request and reply to and from it
    Takes and returns XML Element objects
    """

    def __init__(self, host: str, port=GUI_RPC_DEFAULT_PORT, timeout: float | None = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    @property
    def connected(self) -> bool:
        # A host that hangs up or resets the connection leaves the writer in place. A hang-up shows
        # as the end of the stream in the reader, and a reset as a transport that is closing.
        return (
            self._reader is not None
            and self._writer is not None
            and not self._reader.at_eof()
            and not self._writer.is_closing()
        )

    async def connect(self):
        # Let go of a connection the host hung up on before opening another
        self._abort()
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, family=AF_INET, limit=1024*5000),
                self.timeout,
            )
        except TimeoutError:
            raise BOINCTimeoutError(
                f"Could not connect to {self.host} within {self.timeout} seconds"
            ) from None
        except OSError as err:
            raise BOINCConnectionError(f"Could not connect to {self.host}: {err}") from err

    async def close(self):
        """
        Close the connection to the RPC server
        Safe to call more than once, or without having connected
        """
        if self._writer is None:
            return
        writer, self._reader, self._writer = self._writer, None, None
        writer.close()
        # The peer may already be gone; the socket is released either way.
        with contextlib.suppress(ConnectionError, OSError):
            await writer.wait_closed()

    def _abort(self):
        """
        Drop the connection without waiting for it to close
        """
        if self._writer is not None:
            self._writer.close()
        self._reader, self._writer = None, None

    async def _write(self, message: bytes):
        if self._writer is None:
            raise BOINCConnectionError(f"Connection to {self.host} was not opened before writing")
        await self._writer.drain()
        self._writer.write(message + END_OF_MESSAGE)

    async def send(self, request: ET.Element):
        """
        Send request to RPC server
        Returns without guarantee of having finished sending
        """
        req = ET.Element(REQUEST_TAG)
        req.append(request)
        req_str = ET.tostring(req, encoding=BOINC_ENCODING, xml_declaration=False, short_empty_elements=True)
        req_str = req_str.replace(b" />", b"/>")
        await self._write(req_str)

    async def _read(self):
        if self._reader is None:
            raise BOINCConnectionError(f"Connection to {self.host} was not opened before reading")
        return await self._reader.readuntil(separator=END_OF_MESSAGE)

    async def receive(self) -> ET.Element:
        """
        Receive the next message by the RPC server
        """
        buff = [await self._read()]
        while buff[-1][-1] != END_OF_MESSAGE[0]:
            buff.append(await self._read())
        resp = "".join(str(b, encoding=BOINC_ENCODING) for b in buff)
        # remove end of message chraracter
        resp = resp[:-1]
        # and parse xml
        resp_e = ET.fromstring(resp)
        if resp_e.tag != REPLY_TAG or len(resp_e) == 0:
            raise BOINCConnectionError(f"Got an invalid reply from {self.host}")
        return resp_e[0]

    async def request(self, request: ET.Element):
        """
        Send request to server and return reply
        Raises BOINCTimeoutError if the reply takes longer than the timeout, and
        BOINCConnectionError if the connection is lost or the reply is not one. If the exchange does
        not finish, for those or any other reason, the connection is dropped: the reply may still be
        on its way, and the next request would read it as its own.
        """
        try:
            return await asyncio.wait_for(self._exchange(request), self.timeout)
        except TimeoutError:
            self._abort()
            raise BOINCTimeoutError(
                f"{self.host} did not reply within {self.timeout} seconds"
            ) from None
        except BOINCClientError:
            self._abort()
            raise
        except EOFError as err:
            self._abort()
            raise BOINCConnectionError(f"{self.host} closed the connection") from err
        except (ET.ParseError, asyncio.LimitOverrunError) as err:
            self._abort()
            raise BOINCConnectionError(f"Got an invalid reply from {self.host}") from err
        except OSError as err:
            self._abort()
            raise BOINCConnectionError(f"Lost the connection to {self.host}: {err}") from err
        except BaseException:
            self._abort()
            raise

    async def _exchange(self, request: ET.Element):
        await self.send(request)
        return await self.receive()

