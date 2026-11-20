"""
Client making requests to RPC server
managing authentication etc
"""

import asyncio
import xml.etree.ElementTree as ET
from enum import Enum
from hashlib import md5

from ._parse import Project, parse_generic
from ._raw_client import DEFAULT_TIMEOUT, GUI_RPC_DEFAULT_PORT, _RPCClientRaw
from ._tag import Tag


class BOINCClientError(Exception):
    pass


class Mode(Enum):
    ALWAYS = Tag.ALWAYS
    NEVER = Tag.NEVER
    AUTO = Tag.AUTO
    RESTORE = Tag.RESTORE


async def init_rpc_client(
    # timeout is not a limit on this call, which asyncio.timeout() around it would replace, but
    # the one the client keeps for connecting and for every request afterwards.
    host: str, password=None, port=GUI_RPC_DEFAULT_PORT, timeout: float | None = DEFAULT_TIMEOUT,  # noqa: ASYNC109
):
    """
    Creates RPC Client and initiates connection to RPC Server
    timeout is the seconds to connect, and to get each reply, before raising TimeoutError.
    None waits forever.
    """
    c = RPCClient(host, password, port, timeout)
    await c.connect()
    return c


def _append_project_element(root: ET.Element, project_url: Project | str, name):
    url = ET.SubElement(root, Tag.PROJECT_URL)
    url.text = str(project_url)
    name_e = ET.SubElement(root, Tag.NAME)
    name_e.text = name


class RPCClient:
    """
    For the content and structure of returned dicts refer to https://boinc.berkeley.edu/trac/wiki/GuiRpcProtocol#RequestsandReplies
    """

    def __init__(
        self, host: str, password=None, port=GUI_RPC_DEFAULT_PORT,
        timeout: float | None = DEFAULT_TIMEOUT,
    ):
        """
        Should not be called directly, use init_rpc_client
        """
        self._raw_client = _RPCClientRaw(host, port, timeout)
        # One connection carries one exchange at a time: a reply has no id to match it to its
        # request, so requests made at once wait for their turn.
        self._lock = asyncio.Lock()
        self.password = password

    @property
    def connected(self) -> bool:
        """
        Whether there is a connection to the RPC server
        It is lost by closing it, and by a request that times out, is cancelled or fails on the
        way: connect() again to go on.
        """
        return self._raw_client.connected

    async def connect(self):
        if not self.connected:
            await self._raw_client.connect()

    async def close(self):
        """
        Close the connection to the RPC server
        The client can be connected again afterwards
        """
        await self._raw_client.close()

    async def authorize(self, password=None):
        """
        Authenticate at the server with given password
        if no password provided, use previous password or password from initialization
        """
        # Both steps in one turn, so no other request takes the reply to either of them. The
        # password is chosen inside it too, so a call waiting for its turn cannot change it.
        async with self._lock:
            if password is not None:
                self.password = password
            if self.password is None:
                return False
            password = self.password
            auth1 = ET.Element(Tag.AUTH1)
            nonce = (await self._raw_client.request(auth1)).text
            auth2 = ET.Element(Tag.AUTH2)
            nonce_hash = ET.SubElement(auth2, Tag.NONCE_HASH)
            salted = nonce + password
            nonce_hash.text = md5(bytes(salted, encoding="UTF8")).hexdigest()
            return (await self._raw_client.request(auth2)).tag == Tag.AUTHORIZED

    async def _request(self, req: ET.Element):
        async with self._lock:
            return await self._raw_client.request(req)

    async def _request_auth(self, req: ET.Element):
        """
        Returns:
            True if answer was a single "success" tag
            False if answer was a single "unauthorized" tag
            The reply if answer was a non-trivial reply
        Raises a BOINCClientError on error
        """
        return self.evaluate_reply(await self._request(req))

    @staticmethod
    def evaluate_reply(reply: ET.Element):
        if reply.tag == Tag.UNAUTHORIZED:
            return False
        elif reply.tag == Tag.ERROR:
            raise BOINCClientError(reply.text)
        elif reply.tag == Tag.SUCCESS:
            return True
        else:
            return reply

    async def exchange_versions(self):
        req = ET.Element(Tag.EXCHANGE_VERSIONS)
        return parse_generic(await self._request(req))

    async def get_cc_status(self):
        req = ET.Element(Tag.GET_CC_STATUS)
        return parse_generic(await self._request(req))

    async def get_disk_usage(self):
        req = ET.Element(Tag.GET_DISK_USAGE)
        rep = await self._request(req)
        res = {Tag.PROJECT: []}
        for c in rep:
            if c.tag == Tag.PROJECT:
                res[Tag.PROJECT].append(parse_generic(c))
            else:
                parse_generic(c)
        return res

    async def get_file_transfers(self):
        req = ET.Element(Tag.GET_FILE_TRANSFERS)
        return parse_generic(await self._request(req))

    async def get_host_info(self):
        req = ET.Element(Tag.GET_HOST_INFO)
        return parse_generic(await self._request(req))

    async def get_message_count(self):
        req = ET.Element(Tag.GET_MESSAGE_COUNT)
        return parse_generic(await self._request(req))

    async def get_messages(self, seqno=0, translatable=False):
        req = ET.Element(Tag.GET_MESSAGES)
        s = ET.SubElement(req, Tag.SEQNO)
        s.text = str(seqno)
        if translatable:
            ET.SubElement(req, Tag.TRANSLATABLE)
        return parse_generic(await self._request(req))

    async def get_project_status(self):
        req = ET.Element(Tag.GET_PROJECT_STATUS)
        return [Project(**parse_generic(c)) for c in await self._request(req)]

    async def get_results(self, active_only=False):
        req = ET.Element(Tag.GET_RESULTS)
        if active_only:
            ET.SubElement(req, Tag.ACTIVE_ONLY)
        return parse_generic(await self._request(req))

    ######################################################################
    # Controlling the server
    ######################################################################

    async def abort_result(self, project_url, name):
        """
        Abort a task
        """
        req = ET.Element(Tag.ABORT_RESULT)
        _append_project_element(req, project_url, name)
        return await self._request_auth(req)

    async def suspend_result(self, project_url, name):
        """
        suspend a task
        """
        req = ET.Element(Tag.SUSPEND_RESULT)
        _append_project_element(req, project_url, name)
        return await self._request_auth(req)

    async def resume_result(self, project_url, name):
        """
        suspend a task
        """
        req = ET.Element(Tag.RESUME_RESULT)
        _append_project_element(req, project_url, name)
        return await self._request_auth(req)

    async def quit(self):
        """
        Quit the boinc client
        NOTICE: this stops the running boinc client and all computations, not the rpc client
        """
        return await self._request_auth(ET.Element(Tag.QUIT))

    async def network_available(self):
        """
        retry deferred network communication
        """
        return await self._request_auth(ET.Element(Tag.NETWORK_AVAILABLE))

    async def set_language(self, language: str):
        """
        Set language for projects
        """
        req = ET.Element(Tag.SET_LANGUAGE)
        a = ET.SubElement(req, Tag.LANGUAGE)
        a.text = language
        return await self._request_auth(req)

    async def set_run_mode(self, mode: Mode, duration=0):
        """
        set run mode for given duration
        duration = 0 means permanent change
        """
        req = ET.Element(Tag.SET_RUN_MODE)
        ET.SubElement(req, mode.value)
        a = ET.SubElement(req, Tag.DURATION)
        a.text = str(duration)
        return await self._request_auth(req)

    async def set_network_mode(self, mode: Mode, duration=0):
        """
        set network mode for given duration
        duration = 0 means permanent change
        """
        req = ET.Element(Tag.SET_NETWORK_MODE)
        ET.SubElement(req, mode.value)
        a = ET.SubElement(req, Tag.DURATION)
        a.text = str(duration)
        return await self._request_auth(req)

    async def set_gpu_mode(self, mode: Mode, duration=0):
        """
        set gpu mode for given duration
        duration = 0 means permanent change
        """
        req = ET.Element(Tag.SET_GPU_MODE)
        ET.SubElement(req, mode.value)
        a = ET.SubElement(req, Tag.DURATION)
        a.text = str(duration)
        return await self._request_auth(req)
