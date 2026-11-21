"""
Client for the GUI RPC protocol of a BOINC client

init_rpc_client() connects one. Its methods make the requests, authorize() among them, and wait
for their replies. For what a reply holds, see
https://github.com/BOINC/boinc/wiki/GuiRpcProtocol#requests-and-replies
"""

import asyncio
import xml.etree.ElementTree as ET
from hashlib import md5
from typing import Any

from ._constants import Mode
from ._parse import Project, parse_generic, parse_project
from ._raw_client import DEFAULT_TIMEOUT, GUI_RPC_DEFAULT_PORT, _RPCClientRaw
from ._tag import Tag
from .exceptions import BOINCAuthError, BOINCClientError, BOINCCommandError, BOINCProtocolError

__all__ = ["BOINCClientError", "Mode", "RPCClient", "init_rpc_client"]


async def init_rpc_client(
    # timeout is not a limit on this call, which asyncio.timeout() around it would replace, but
    # the one the client keeps for connecting and for every request afterwards.
    host: str, password=None, port=GUI_RPC_DEFAULT_PORT, timeout: float | None = DEFAULT_TIMEOUT,  # noqa: ASYNC109
):
    """
    Create a client and connect it to a BOINC client

    Connecting does not authorize: call authorize() next.

    Args:
        host: Name or IPv4 address of the host the BOINC client runs on. BOINC listens on IPv4
            only, so a name is resolved to its IPv4 addresses, and an IPv6 address raises
            BOINCConnectionError.
        password: The GUI RPC password, from gui_rpc_auth.cfg in the BOINC data directory.
            authorize() uses it unless it is given another.
        port: Port the BOINC client listens on.
        timeout: Seconds to connect, and to get each reply afterwards, before raising
            BOINCTimeoutError. None waits forever.

    Returns:
        The connected RPCClient.

    Raises:
        BOINCConnectionError: The host could not be reached.
        BOINCTimeoutError: The host did not accept the connection in time.
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
    Client for the GUI RPC protocol of a BOINC client

    Made by init_rpc_client(), which connects it, or used as an async context manager, which
    connects it on entering and closes it on leaving, even on an error:

        async with RPCClient(host, password) as client:
            await client.authorize()
            ...

    Each method sends one request and waits for its reply. Requests made at once, for example with
    asyncio.gather(), wait for their turn. A reply is parsed into dicts and lists keyed by the
    names of its XML elements, and the type of each value depends on its element: numbers become
    int or float, flags bool, times datetime in UTC or None when not set, the CPU and elapsed
    times of a task and the time so far and left of a transfer timedelta, and empty texts "".
    Other durations, such as the *_mode_delay of get_cc_status() or the backoffs, are float
    seconds. An element the parser does not know stays a str. For what
    each reply holds, see
    https://github.com/BOINC/boinc/wiki/GuiRpcProtocol#requests-and-replies

    The queries need authorize() first only when the client is on another host. The requests
    that change something always do.

    Every request raises:
        BOINCAuthError: The request needs authorize() first. The connection is kept.
        BOINCCommandError: BOINC answered with an error, such as "no such result". The connection
            is kept, except in authorize().
        BOINCConnectionError: The connection could not be used or was lost, or the reply was not
            one, or not the one to the request (BOINCProtocolError), or did not come in time
            (BOINCTimeoutError). The connection is dropped: connect() and authorize() again to go
            on.

    Attributes:
        password: The password authorize() uses when it is given none.
    """

    def __init__(
        self, host: str, password=None, port=GUI_RPC_DEFAULT_PORT,
        timeout: float | None = DEFAULT_TIMEOUT,
    ):
        """
        Create a client, without connecting it: use it with async with, or call connect()

        Takes the same arguments as init_rpc_client().
        """
        self._raw_client = _RPCClientRaw(host, port, timeout)
        # One connection carries one exchange at a time: a reply has no id to match it to its
        # request, so requests made at once wait for their turn.
        self._lock = asyncio.Lock()
        self.password = password

    async def __aenter__(self) -> "RPCClient":
        # A client from init_rpc_client() is connected already, and keeps its connection
        await self.connect()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    @property
    def connected(self) -> bool:
        """
        Whether there is a connection to the BOINC client

        It is lost by closing it, and by a request that times out, is cancelled or fails on the
        way: connect() again to go on.
        """
        return self._raw_client.connected

    async def connect(self):
        """
        Connect to the BOINC client, unless already connected

        Connecting does not authorize: call authorize() next.

        Raises:
            BOINCConnectionError: The host could not be reached.
            BOINCTimeoutError: The host did not accept the connection in time.
        """
        if not self.connected:
            await self._raw_client.connect()

    async def close(self):
        """
        Close the connection to the BOINC client

        The client can be connected again afterwards.
        """
        await self._raw_client.close()

    async def authorize(self, password=None):
        """
        Authorize the connection with the GUI RPC password

        Without it BOINC refuses the requests that change something, and every request from
        another host. It lasts as long as the connection: after a new connect(), call it again.

        Args:
            password: The password to use, kept for the next calls. Without one, the last one
                given, here or to init_rpc_client(), is used.

        Returns:
            True.

        Raises:
            BOINCAuthError: There is no password, and the connection is kept; or BOINC rejected
                it, and the connection is dropped, since BOINC hangs up then: connect() again
                before trying another.
            BOINCCommandError: BOINC answered the first step with an error. The connection is
                dropped, as it is whenever authorize() stops half way, since BOINC hangs up on a
                second try on the same one: connect() again before retrying.
            BOINCConnectionError: As for any request. The connection is dropped.
        """
        # Both steps in one turn, so no other request takes the reply to either of them. The
        # password is chosen inside it too, so a call waiting for its turn cannot change it.
        async with self._lock:
            if password is not None:
                self.password = password
            if self.password is None:
                raise BOINCAuthError(f"No password to authorize at {self._raw_client.host} with")
            try:
                return await self._authorize(self.password)
            except BaseException:
                # The server hangs up after a failed authorization, and after a second auth1. So
                # whatever stops the two steps half way, the next try needs a new connection.
                self._raw_client._abort()
                raise

    async def _authorize(self, password: str):
        host = self._raw_client.host
        nonce = self._check_reply(await self._raw_client.request(ET.Element(Tag.AUTH1)))
        if nonce.tag != Tag.NONCE or nonce.text is None:
            raise BOINCProtocolError(f"{host} did not answer auth1 with a nonce")
        auth2 = ET.Element(Tag.AUTH2)
        nonce_hash = ET.SubElement(auth2, Tag.NONCE_HASH)
        salted = nonce.text + password
        nonce_hash.text = md5(bytes(salted, encoding="UTF8")).hexdigest()
        reply = await self._raw_client.request(auth2)
        if reply.tag == Tag.UNAUTHORIZED:
            raise BOINCAuthError(f"{host} rejected the password")
        if self._check_reply(reply).tag != Tag.AUTHORIZED:
            raise BOINCProtocolError(f"{host} did not answer auth2 with authorized")
        return True

    async def _request(self, req: ET.Element, reply_tag: str | None = None):
        """
        Raises BOINCAuthError if the server refuses the request for want of authorize(),
        BOINCCommandError if it answers with an error, and BOINCProtocolError if the reply is not
        reply_tag, when one is given
        """
        async with self._lock:
            reply = self._check_reply(await self._raw_client.request(req))
            if reply_tag is not None and reply.tag != reply_tag:
                # Not the reply to this request, so what comes next on the connection cannot be
                # trusted to be the reply to the next one either. Dropped while holding the lock,
                # so that no request waiting for its turn goes out on it.
                self._raw_client._abort()
                raise BOINCProtocolError(
                    f"{self._raw_client.host} answered {req.tag} with {reply.tag}, not {reply_tag}"
                )
        return reply

    @staticmethod
    def _check_reply(reply: ET.Element) -> ET.Element:
        if reply.tag == Tag.UNAUTHORIZED:
            raise BOINCAuthError("Not authorized: call authorize() with the right password first")
        elif reply.tag == Tag.ERROR:
            raise BOINCCommandError(reply.text)
        return reply

    async def _request_auth(self, req: ET.Element):
        """
        Returns:
            True if answer was a single "success" tag
            The reply if answer was a non-trivial reply
        Raises BOINCAuthError if answer was a single "unauthorized" tag, and BOINCCommandError on
        error
        """
        return self.evaluate_reply(await self._request(req))

    @staticmethod
    def evaluate_reply(reply: ET.Element):
        """
        Read the reply to a request that changes something

        Returns:
            True if the reply is success, and the reply itself otherwise.

        Raises:
            BOINCAuthError: The reply is unauthorized.
            BOINCCommandError: The reply is an error.
        """
        return True if RPCClient._check_reply(reply).tag == Tag.SUCCESS else reply

    async def exchange_versions(self):
        """
        Get the version of the BOINC client

        Returns:
            A dict with major, minor and release, such as {"major": 7, "minor": 16, "release": 3}.
        """
        req = ET.Element(Tag.EXCHANGE_VERSIONS)
        return parse_generic(await self._request(req, Tag.SERVER_VERSION))

    async def get_cc_status(self):
        """
        Get the state of the BOINC client: its modes, why it is suspended, and its network

        Returns:
            A dict, with task_mode, task_suspend_reason, gpu_mode, network_mode and network_status
            among others. The modes and their *_perm are a Mode, the suspend reasons a
            SuspendReason, NOT_SUSPENDED when it is not, and network_status a NetworkStatus.
            task_mode_delay, gpu_mode_delay and network_mode_delay are the seconds left of a
            temporary mode, as float, and 0 without one. ams_password_error, disallow_attach and simple_gui_only are
            bool, and manager_must_quit is there, True, only when an update asks the BOINC Manager
            to quit.
        """
        req = ET.Element(Tag.GET_CC_STATUS)
        return parse_generic(await self._request(req, Tag.CC_STATUS))

    async def get_disk_usage(self):
        """
        Get how much of the disk BOINC and each project use, in bytes

        Returns:
            A dict with:
                project: A list with a dict for each project, with its master_url and disk_usage.
                d_total: Size of the disk.
                d_free: Free space on the disk.
                d_boinc: Space BOINC uses, leaving the projects out.
                d_allowed: Space BOINC may use, under its preferences.
        """
        req = ET.Element(Tag.GET_DISK_USAGE)
        rep = await self._request(req, Tag.DISK_USAGE_SUMMARY)
        # The projects come as repeated <project> elements, which a dict keeps only the last of,
        # so they are gathered in a list. The totals of the disk follow them.
        res: dict[str, Any] = {Tag.PROJECT: []}
        for c in rep:
            if c.tag == Tag.PROJECT:
                res[Tag.PROJECT].append(parse_generic(c))
            else:
                res[c.tag] = parse_generic(c)
        return res

    async def get_file_transfers(self):
        """
        Get the files being uploaded or downloaded

        Returns:
            A list with a dict for each transfer, [] when there is none.
        """
        req = ET.Element(Tag.GET_FILE_TRANSFERS)
        return parse_generic(await self._request(req, Tag.FILE_TRANSFERS))

    async def get_host_info(self):
        """
        Get the description of the host: its CPU, memory, disk, operating system and GPUs

        Returns:
            A dict, with domain_name, p_ncpus, p_model, m_nbytes, os_name and coprocs among others.
            docker_type and docker_compose_type are a DockerType.
        """
        req = ET.Element(Tag.GET_HOST_INFO)
        return parse_generic(await self._request(req, Tag.HOST_INFO))

    async def get_message_count(self):
        """
        Get the sequence number of the newest message of the event log

        Returns:
            The number, an int. It is also the count of messages since the client started.
        """
        req = ET.Element(Tag.GET_MESSAGE_COUNT)
        return parse_generic(await self._request(req, Tag.SEQNO))

    async def get_messages(self, seqno=0, translatable=False):
        """
        Get the messages of the event log newer than a sequence number

        Args:
            seqno: Only the messages with a greater sequence number are returned. 0, the default,
                returns them all; get_message_count() - 3, the last three.
            translatable: Keep the _("...") markers around the text that the BOINC Manager
                translates. By default they are removed.

        Returns:
            A list with a dict for each message, oldest first, with project, pri, a
            MessagePriority, seqno, body and time. project is "" for a message from the client
            itself.
        """
        req = ET.Element(Tag.GET_MESSAGES)
        s = ET.SubElement(req, Tag.SEQNO)
        s.text = str(seqno)
        if translatable:
            ET.SubElement(req, Tag.TRANSLATABLE)
        return parse_generic(await self._request(req, Tag.MSGS))

    async def get_statistics(self):
        """
        Get the credit of the user and of the host for each day, by project, as the Statistics tab
        of the BOINC Manager draws it

        Returns:
            A list with a dict for each project, with:
                master_url: The URL of the project.
                daily_statistics: A list with a dict for each day, oldest first, with day, the
                    datetime in UTC of the midnight that begins it, and user_total_credit,
                    user_expavg_credit, host_total_credit and host_expavg_credit, as float, as
                    of the last reply of the project's scheduler that day. Only the days with a
                    reply are there, from the last save_stats_days of the BOINC configuration,
                    30 by default. When older days are dropped, the last of them is kept, dated
                    the first day of that window.
        """
        req = ET.Element(Tag.GET_STATISTICS)
        # The days come as repeated <daily_statistics> elements, which a dict keeps only the last
        # of, so they are gathered in a list.
        return [
            {
                Tag.MASTER_URL: p.findtext(Tag.MASTER_URL, ""),
                Tag.DAILY_STATISTICS: [parse_generic(d) for d in p.findall(Tag.DAILY_STATISTICS)],
            }
            for p in await self._request(req, Tag.STATISTICS)
        ]

    async def get_notices(self, seqno=0):
        """
        Get the notices newer than a sequence number, as the Notices tab of the BOINC Manager
        shows them: from the projects' news feeds, their schedulers and the client itself

        It needs authorize(), even from the host BOINC runs on; get_notices_public() does not.

        Args:
            seqno: Only the notices with a greater sequence number are returned. 0, the default,
                returns them all. Pass the greatest seqno got so far to get only the new ones.

        Returns:
            A dict with:
                refresh: True when BOINC has removed notices since the last call on this
                    connection. notices then holds all of them, to replace those got before
                    rather than be added to them.
                notices: A list with a dict for each notice, oldest first, with seqno, title,
                    description, an HTML text, create_time and arrival_time, as datetime in UTC,
                    project_name, "" for a notice of the client itself, category, client or
                    scheduler for theirs and "" for news, link and is_private.
        """
        return await self._get_notices(Tag.GET_NOTICES, seqno)

    async def get_notices_public(self, seqno=0):
        """
        Get the notices that are not private, which needs no authorize()

        Args:
            seqno: As for get_notices().

        Returns:
            As get_notices(), leaving out the notices whose is_private is True.
        """
        return await self._get_notices(Tag.GET_NOTICES_PUBLIC, seqno)

    async def _get_notices(self, tag: str, seqno):
        req = ET.Element(tag)
        s = ET.SubElement(req, Tag.SEQNO)
        s.text = str(seqno)
        notices = [parse_generic(c) for c in await self._request(req, Tag.NOTICES)]
        # When notices have been removed, BOINC sends first a notice with seqno -1, which is not
        # one, and then all of them, as RPC_CLIENT::get_notices() in lib/gui_rpc_client_ops.cpp reads
        # it.
        refresh = any(n.get(Tag.SEQNO) == -1 for n in notices)
        return {
            "refresh": refresh,
            "notices": [n for n in notices if n.get(Tag.SEQNO) != -1],
        }

    async def get_project_status(self):
        """
        Get the projects the BOINC client is attached to

        Returns:
            A list with a Project for each one. Its fields are attributes, such as project_name or
            user_total_credit, and it compares equal to its master_url. rsc_backoff_time and
            rsc_backoff_interval are a dict by resource, such as CPU or NVIDIA: the datetime until
            which the project does not ask for work for it, or None, and the seconds it backs off
            for, as float. no_rsc_apps, no_rsc_ams, no_rsc_pref and no_rsc_config are a list of the
            resources each applies to, empty when none. sched_rpc_pending is a RpcReason, NONE
            when BOINC is not to contact the project.
        """
        req = ET.Element(Tag.GET_PROJECT_STATUS)
        return [parse_project(c) for c in await self._request(req, Tag.PROJECTS)]

    async def get_results(self, active_only=False):
        """
        Get the tasks

        Args:
            active_only: Only the tasks BOINC has started and that have not finished, leaving out
                those waiting to start and those done.

        Returns:
            A list with a dict for each task, [] when there is none, with name, project_url,
            report_deadline and active_task among others. project_url is a Project, state a
            ResultState, and the active_task_state and scheduler_state of active_task an
            ActiveTaskState and a SchedulerState.
        """
        req = ET.Element(Tag.GET_RESULTS)
        if active_only:
            ET.SubElement(req, Tag.ACTIVE_ONLY)
        return parse_generic(await self._request(req, Tag.RESULTS))

    ######################################################################
    # Controlling the server
    ######################################################################

    async def abort_result(self, project_url, name):
        """
        Abort a task: BOINC stops it and reports it to its project as aborted. It cannot be undone.

        Args:
            project_url: The task's project, as a Project or its master URL, such as the
                project_url of a task from get_results().
            name: The task's name.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply().
        """
        req = ET.Element(Tag.ABORT_RESULT)
        _append_project_element(req, project_url, name)
        return await self._request_auth(req)

    async def suspend_result(self, project_url, name):
        """
        Suspend a task until resume_result()

        Args:
            project_url: The task's project, as a Project or its master URL, such as the
                project_url of a task from get_results().
            name: The task's name.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply().
        """
        req = ET.Element(Tag.SUSPEND_RESULT)
        _append_project_element(req, project_url, name)
        return await self._request_auth(req)

    async def resume_result(self, project_url, name):
        """
        Resume a task suspended by suspend_result()

        Args:
            project_url: The task's project, as a Project or its master URL, such as the
                project_url of a task from get_results().
            name: The task's name.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply().
        """
        req = ET.Element(Tag.RESUME_RESULT)
        _append_project_element(req, project_url, name)
        return await self._request_auth(req)

    async def update_project(self, project: Project | str):
        """
        Contact the project now, to report the tasks done and ask for work, as Update in the BOINC
        Manager, even if it is backed off

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_UPDATE, project)

    async def suspend_project(self, project: Project | str):
        """
        Stop computing and transferring the tasks of a project until resume_project()

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_SUSPEND, project)

    async def resume_project(self, project: Project | str):
        """
        Resume a project suspended by suspend_project()

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_RESUME, project)

    async def no_new_tasks(self, project: Project | str):
        """
        Stop asking a project for work, as No new tasks in the BOINC Manager, until
        allow_new_tasks(). The tasks it has are still computed and reported.

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_NOMOREWORK, project)

    async def allow_new_tasks(self, project: Project | str):
        """
        Ask a project for work again after no_new_tasks(), as Allow new tasks in the BOINC Manager

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_ALLOWMOREWORK, project)

    async def reset_project(self, project: Project | str):
        """
        Reset a project, as Reset project in the BOINC Manager: abort its tasks, without reporting
        them, and delete its files, which it downloads again. It stays attached. It cannot be
        undone, and the work done on its tasks is lost.

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_RESET, project)

    async def detach_project(self, project: Project | str):
        """
        Detach from a project, as Remove in the BOINC Manager: reset it and forget it. It cannot be
        undone, and the work done on its tasks is lost; to keep it, see detach_project_when_done().

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError, and so does one attached via an account manager, which only the
            account manager can detach.
        """
        return await self._project_op(Tag.PROJECT_DETACH, project)

    async def detach_project_when_done(self, project: Project | str):
        """
        Detach from a project once its tasks are done and reported, without asking it for work
        meanwhile, as no_new_tasks() does. Until then dont_detach_project_when_done() cancels it.
        A project attached via an account manager is detached after the next request to the
        account manager.

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_DETACH_WHEN_DONE, project)

    async def dont_detach_project_when_done(self, project: Project | str):
        """
        Cancel detach_project_when_done(), and ask the project for work again, as
        allow_new_tasks() does

        Args:
            project: The project, as a Project from get_project_status() or its master URL.

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project the BOINC client is not attached to raises
            BOINCCommandError.
        """
        return await self._project_op(Tag.PROJECT_DONT_DETACH_WHEN_DONE, project)

    async def retry_file_transfer(self, project_url: Project | str, name: str):
        """
        Retry an upload or a download now, as Retry Now in the BOINC Manager, ending the backoff of
        the file and of the transfers of its project

        Args:
            project_url: The transfer's project, as a Project or its master URL, such as the
                project_url of a transfer from get_file_transfers().
            name: The name of the file, such as the name of a transfer from get_file_transfers().

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project, a file or a transfer BOINC does not have raises
            BOINCCommandError.
        """
        return await self._file_transfer_op(Tag.RETRY_FILE_TRANSFER, project_url, name)

    async def abort_file_transfer(self, project_url: Project | str, name: str):
        """
        Abort an upload or a download, as Abort Transfer in the BOINC Manager. The tasks that need
        the file fail, and the work done on them is lost. It cannot be undone.

        Args:
            project_url: The transfer's project, as a Project or its master URL, such as the
                project_url of a transfer from get_file_transfers().
            name: The name of the file, such as the name of a transfer from get_file_transfers().

        Returns:
            True, or the reply when BOINC answers something other than success, as for
            evaluate_reply(). A project, a file or a transfer BOINC does not have raises
            BOINCCommandError.
        """
        return await self._file_transfer_op(Tag.ABORT_FILE_TRANSFER, project_url, name)

    async def _file_transfer_op(self, tag: str, project_url: Project | str, name: str):
        req = ET.Element(tag)
        url = ET.SubElement(req, Tag.PROJECT_URL)
        url.text = str(project_url)
        filename = ET.SubElement(req, Tag.FILENAME)
        filename.text = name
        return await self._request_auth(req)

    async def _project_op(self, tag: str, project: Project | str):
        req = ET.Element(tag)
        url = ET.SubElement(req, Tag.PROJECT_URL)
        url.text = str(project)
        return await self._request_auth(req)

    async def quit(self):
        """
        Stop the BOINC client, and with it every task

        It stops the program on the host, not this client. Starting it again has to be done on the
        host.

        Returns:
            True, or the reply when BOINC answers something other than success.
        """
        return await self._request_auth(ET.Element(Tag.QUIT))

    async def network_available(self):
        """
        Retry now the network communication BOINC has deferred, such as transfers that failed

        Returns:
            True, or the reply when BOINC answers something other than success.
        """
        return await self._request_auth(ET.Element(Tag.NETWORK_AVAILABLE))

    async def set_language(self, language: str):
        """
        Set the language of the user, which BOINC sends to the projects in its requests to them

        Args:
            language: The language, as a code such as "es". It goes in the Accept-Language header
                of those requests.

        Returns:
            True, or the reply when BOINC answers something other than success.
        """
        req = ET.Element(Tag.SET_LANGUAGE)
        a = ET.SubElement(req, Tag.LANGUAGE)
        a.text = language
        return await self._request_auth(req)

    async def set_run_mode(self, mode: Mode, duration=0):
        """
        Set when BOINC may compute

        Args:
            mode: The mode, a Mode.
            duration: Seconds the mode lasts before going back to the permanent one. 0, the
                default, makes it the permanent one.

        Returns:
            True, or the reply when BOINC answers something other than success.
        """
        req = ET.Element(Tag.SET_RUN_MODE)
        ET.SubElement(req, mode.name.lower())
        a = ET.SubElement(req, Tag.DURATION)
        a.text = str(duration)
        return await self._request_auth(req)

    async def set_network_mode(self, mode: Mode, duration=0):
        """
        Set when BOINC may use the network

        Args:
            mode: The mode, a Mode.
            duration: Seconds the mode lasts before going back to the permanent one. 0, the
                default, makes it the permanent one.

        Returns:
            True, or the reply when BOINC answers something other than success.
        """
        req = ET.Element(Tag.SET_NETWORK_MODE)
        ET.SubElement(req, mode.name.lower())
        a = ET.SubElement(req, Tag.DURATION)
        a.text = str(duration)
        return await self._request_auth(req)

    async def set_gpu_mode(self, mode: Mode, duration=0):
        """
        Set when BOINC may use the GPU

        Args:
            mode: The mode, a Mode.
            duration: Seconds the mode lasts before going back to the permanent one. 0, the
                default, makes it the permanent one.

        Returns:
            True, or the reply when BOINC answers something other than success.
        """
        req = ET.Element(Tag.SET_GPU_MODE)
        ET.SubElement(req, mode.name.lower())
        a = ET.SubElement(req, Tag.DURATION)
        a.text = str(duration)
        return await self._request_auth(req)
