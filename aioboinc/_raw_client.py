"""
Raw client for maintaining the socket connection to the BOINC server
Based on:
https://github.com/BOINC/boinc/wiki/GuiRpc
https://github.com/BOINC/boinc/wiki/GuiRpcProtocol
https://github.com/BOINC/boinc/blob/master/lib/gui_rpc_client.cpp

Note that this client is Async, based on asyncio
"""

import asyncio
import contextlib
import ipaddress
import xml.etree.ElementTree as ET
from socket import AF_INET

from .exceptions import BOINCConnectionError, BOINCError, BOINCProtocolError, BOINCTimeoutError

GUI_RPC_DEFAULT_PORT = 31416
# Seconds to connect, or to get the reply to a request, before giving up
DEFAULT_TIMEOUT = 30.0
REPLY_TAG = "boinc_gui_rpc_reply"
REQUEST_TAG = "boinc_gui_rpc_request"
END_OF_MESSAGE = b"\x03"
BOINC_ENCODING = "ISO-8859-1"


def _is_ipv6_address(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).version == 6
    except ValueError:
        return False


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
        if _is_ipv6_address(self.host):
            raise BOINCConnectionError(
                f"Could not connect to {self.host}: BOINC listens on IPv4 only"
            )
        deadline = asyncio.timeout(self.timeout)
        try:
            async with deadline:
                # The BOINC client listens on IPv4 only (init_tcp() in client/gui_rpc_server.cpp),
                # so a name is resolved to its IPv4 addresses, without trying IPv6 ones first.
                self._reader, self._writer = await asyncio.open_connection(
                    self.host, self.port, family=AF_INET, limit=1024*5000
                )
        except TimeoutError as err:
            if deadline.expired():
                raise BOINCTimeoutError(
                    f"Could not connect to {self.host} within {self.timeout} seconds"
                ) from None
            # The system gave up on the connection, which is an OSError like any other
            raise BOINCConnectionError(f"Could not connect to {self.host}: {err}") from err
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
        self._writer.write(message + END_OF_MESSAGE)
        # Wait while the buffer is full, as asyncio asks after a write. It also raises if the
        # connection is lost.
        await self._writer.drain()

    async def send(self, request: ET.Element):
        """
        Send request to RPC server
        Returns once the request is written; the system may still be sending it
        """
        req = ET.Element(REQUEST_TAG)
        req.append(request)
        req_str = ET.tostring(req, encoding=BOINC_ENCODING, xml_declaration=False, short_empty_elements=True)
        req_str = req_str.replace(b" />", b"/>")
        await self._write(req_str)

    async def _read(self) -> bytes:
        if self._reader is None:
            raise BOINCConnectionError(f"Connection to {self.host} was not opened before reading")
        return await self._reader.readuntil(separator=END_OF_MESSAGE)

    async def receive(self) -> ET.Element:
        """
        Receive the next message by the RPC server
        """
        # readuntil() reads the whole message, however many packets it comes in, ending with the end
        # of message character, or raises
        message = await self._read()
        resp_e = ET.fromstring(str(message[:-1], encoding=BOINC_ENCODING))
        if resp_e.tag != REPLY_TAG or len(resp_e) == 0:
            raise BOINCProtocolError(f"Got an invalid reply from {self.host}")
        return resp_e[0]

    async def request(self, request: ET.Element):
        """
        Send request to server and return reply
        Raises BOINCTimeoutError if the reply takes longer than the timeout, and
        BOINCConnectionError if the connection is lost, or its subclass BOINCProtocolError if the
        reply is not one. If the exchange does not finish, for those or any other reason, the
        connection is dropped: the reply may still be on its way, and the next request would read it
        as its own.
        """
        deadline = asyncio.timeout(self.timeout)
        try:
            async with deadline:
                return await self._exchange(request)
        except TimeoutError as err:
            self._abort()
            if deadline.expired():
                raise BOINCTimeoutError(
                    f"{self.host} did not reply within {self.timeout} seconds"
                ) from None
            # The system gave up on the connection, which is an OSError like any other
            raise BOINCConnectionError(f"Lost the connection to {self.host}: {err}") from err
        except BOINCError:
            self._abort()
            raise
        except EOFError as err:
            self._abort()
            raise BOINCConnectionError(f"{self.host} closed the connection") from err
        except (ET.ParseError, asyncio.LimitOverrunError) as err:
            self._abort()
            raise BOINCProtocolError(f"Got an invalid reply from {self.host}") from err
        except OSError as err:
            self._abort()
            raise BOINCConnectionError(f"Lost the connection to {self.host}: {err}") from err
        except BaseException:
            self._abort()
            raise

    async def _exchange(self, request: ET.Element):
        await self.send(request)
        return await self.receive()

