"""
Tests for connecting, authorizing, changing modes and closing
"""

import asyncio
import errno
import socket
import unittest
from hashlib import md5
from unittest import mock

import aioboinc
from aioboinc import (
    BOINCAuthError,
    BOINCClientError,
    BOINCCommandError,
    BOINCConnectionError,
    BOINCError,
    BOINCProtocolError,
    BOINCTimeoutError,
    Mode,
    RPCClient,
    init_rpc_client,
)

from .fake_boinc import HANG_UP, NO_REPLY, FakeBoinc, HangUpMidway, Late, RPCClientTestCase, Split
from .fixtures import web_state


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
            ["<auth1/>", f"<auth2><nonce_hash>{expected}</nonce_hash></auth2>"],
        )

    async def test_a_password_given_later_replaces_the_first(self):
        self.assertIs(await self.client.authorize("other"), True)
        expected = md5(b"1234.5678other").hexdigest()
        self.assertEqual(
            self.boinc.requests[1], f"<auth2><nonce_hash>{expected}</nonce_hash></auth2>"
        )
        self.assertEqual(self.client.password, "other")

    async def test_without_a_password_raises_and_sends_nothing(self):
        self.client.password = None
        with self.assertRaisesRegex(BOINCAuthError, "No password"):
            await self.client.authorize()
        self.assertEqual(self.boinc.requests, [])
        self.assertTrue(self.client.connected)


class RejectedAuthorizeTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1234.5678</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><unauthorized/></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><nonce>1</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><authorized/></boinc_gui_rpc_reply>",
    )

    async def test_wrong_password_raises_auth_error(self):
        with self.assertRaisesRegex(BOINCAuthError, "127.0.0.1 rejected the password"):
            await self.client.authorize()

    async def test_wrong_password_drops_the_connection(self):
        # BOINC hangs up after it, so the next try needs a new connection
        with self.assertRaises(BOINCAuthError):
            await self.client.authorize()
        self.assertFalse(self.client.connected)
        await asyncio.wait_for(self.boinc.disconnected.wait(), timeout=5)
        await self.client.connect()
        self.assertIs(await self.client.authorize("right"), True)


class UnencodablePasswordTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><nonce>2</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><authorized/></boinc_gui_rpc_reply>",
    )

    async def test_a_failure_after_auth1_drops_the_connection(self):
        # A lone surrogate cannot be encoded, so this fails after auth1, before auth2
        with self.assertRaises(UnicodeEncodeError):
            await self.client.authorize("\ud800")
        self.assertFalse(self.client.connected)
        await self.client.connect()
        self.assertIs(await self.client.authorize("right"), True)


class Auth1ErrorTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><error>no</error></boinc_gui_rpc_reply>",)

    async def test_an_error_instead_of_the_nonce_raises(self):
        with self.assertRaisesRegex(BOINCCommandError, "no"):
            await self.client.authorize()
        self.assertFalse(self.client.connected)


class Auth1WithoutNonceTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><nonce/></boinc_gui_rpc_reply>",)

    async def test_a_reply_without_the_nonce_raises(self):
        with self.assertRaisesRegex(BOINCProtocolError, "did not answer auth1 with a nonce"):
            await self.client.authorize()
        self.assertFalse(self.client.connected)


class Auth2UnexpectedTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><success/></boinc_gui_rpc_reply>",
    )

    async def test_a_reply_other_than_authorized_raises(self):
        with self.assertRaisesRegex(BOINCProtocolError, "did not answer auth2 with authorized"):
            await self.client.authorize()
        self.assertFalse(self.client.connected)


class UnauthorizedTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><unauthorized/></boinc_gui_rpc_reply>",)

    async def test_control_request_raises_auth_error(self):
        with self.assertRaisesRegex(BOINCAuthError, "call authorize"):
            await self.client.set_run_mode(Mode.NEVER)

    async def test_query_raises_auth_error(self):
        # Instead of an empty answer
        with self.assertRaises(BOINCAuthError):
            await self.client.get_project_status()

    async def test_the_connection_is_kept(self):
        # BOINC lets the first refusal go, so authorize() can follow on the same connection
        with self.assertRaises(BOINCAuthError):
            await self.client.get_cc_status()
        self.assertTrue(self.client.connected)


class ErrorTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><error>no such result</error></boinc_gui_rpc_reply>",)

    async def test_control_request_raises(self):
        with self.assertRaisesRegex(BOINCCommandError, "no such result"):
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


class ConcurrentRequestsTest(RPCClientTestCase):

    replies = (web_state.seqno, web_state.cc_status)

    async def test_requests_made_at_once_each_get_their_own_reply(self):
        count, status = await asyncio.gather(
            self.client.get_message_count(), self.client.get_cc_status()
        )
        self.assertEqual(self.boinc.requests, ["<get_message_count/>", "<get_cc_status/>"])
        self.assertEqual(count, 47)
        self.assertEqual(status["task_mode"], 2)


class ConcurrentAuthorizeTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1234.5678</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><authorized/></boinc_gui_rpc_reply>",
        web_state.seqno,
    )

    async def test_no_request_slips_in_between_the_two_steps(self):
        authorized, count = await asyncio.gather(
            self.client.authorize(), self.client.get_message_count()
        )
        self.assertEqual(
            [r.split(">")[0] + ">" for r in self.boinc.requests],
            ["<auth1/>", "<auth2>", "<get_message_count/>"],
        )
        self.assertIs(authorized, True)
        self.assertEqual(count, 47)


class ConcurrentAuthorizeWithOtherPasswordsTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><authorized/></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><nonce>2</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><unauthorized/></boinc_gui_rpc_reply>",
    )

    async def test_each_call_answers_with_its_own_password(self):
        first, second = await asyncio.gather(
            self.client.authorize("first"), self.client.authorize("second"), return_exceptions=True
        )
        self.assertIs(first, True)
        self.assertIsInstance(second, BOINCAuthError)
        self.assertEqual(
            self.boinc.requests,
            [
                "<auth1/>",
                f"<auth2><nonce_hash>{md5(b'1first').hexdigest()}</nonce_hash></auth2>",
                "<auth1/>",
                f"<auth2><nonce_hash>{md5(b'2second').hexdigest()}</nonce_hash></auth2>",
            ],
        )
        # The last call to finish leaves its password for the next authorize() without one
        self.assertEqual(self.client.password, "second")


class InvalidReplyTest(RPCClientTestCase):

    replies = ("<html/>",)

    async def test_a_reply_without_the_envelope_raises(self):
        with self.assertRaisesRegex(BOINCProtocolError, "invalid reply"):
            await self.client.get_cc_status()
        # Whatever answered is not a BOINC client, so there is no point in going on talking to it
        self.assertFalse(self.client.connected)


class EmptyReplyTest(RPCClientTestCase):

    # What BOINC sends before hanging up on an auth1 it did not expect
    replies = ("<boinc_gui_rpc_reply>\n</boinc_gui_rpc_reply>",)

    async def test_an_empty_reply_raises(self):
        with self.assertRaisesRegex(BOINCProtocolError, "invalid reply"):
            await self.client.get_cc_status()
        self.assertFalse(self.client.connected)


class MalformedReplyTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><cc_status>",)

    async def test_a_reply_that_is_not_xml_raises(self):
        with self.assertRaisesRegex(BOINCProtocolError, "invalid reply"):
            await self.client.get_cc_status()
        self.assertFalse(self.client.connected)


class HangUpInsteadOfReplyTest(RPCClientTestCase):

    replies = (HANG_UP,)

    async def test_a_host_that_hangs_up_raises_connection_error(self):
        with self.assertRaisesRegex(BOINCConnectionError, "127.0.0.1 closed the connection"):
            await self.client.get_cc_status()
        self.assertFalse(self.client.connected)


class WrongReplyTest(RPCClientTestCase):

    # Every request gets <success/>, the default of the fake BOINC: the reply to a request that
    # changes something, not to a query
    QUERIES = {
        "exchange_versions": "server_version",
        "get_cc_status": "cc_status",
        "get_disk_usage": "disk_usage_summary",
        "get_file_transfers": "file_transfers",
        "get_host_info": "host_info",
        "get_message_count": "seqno",
        "get_messages": "msgs",
        "get_notices": "notices",
        "get_notices_public": "notices",
        "get_project_status": "projects",
        "get_results": "results",
        "get_statistics": "statistics",
    }

    async def test_a_query_answered_with_another_reply_raises_and_drops_the_connection(self):
        for query, reply_tag in self.QUERIES.items():
            with self.subTest(query=query):
                await self.client.connect()
                with self.assertRaisesRegex(BOINCProtocolError, f"with success, not {reply_tag}$"):
                    await getattr(self.client, query)()
                self.assertFalse(self.client.connected)


class ReplyOfAnotherQueryTest(RPCClientTestCase):

    replies = (web_state.results,)

    async def test_the_reply_to_another_query_is_not_taken_for_this_one(self):
        # It parsed into a list of tasks, returned as if it were the status
        with self.assertRaisesRegex(BOINCProtocolError, "answered get_cc_status with results"):
            await self.client.get_cc_status()


class HangUpMidwayTest(RPCClientTestCase):

    replies = (HangUpMidway("<boinc_gui_rpc_reply><cc_status><task_mode>2</task_mode>"),)

    async def test_a_host_that_hangs_up_in_the_middle_of_a_reply_raises_connection_error(self):
        with self.assertRaisesRegex(BOINCConnectionError, "127.0.0.1 closed the connection"):
            await self.client.get_cc_status()
        self.assertFalse(self.client.connected)


class SplitReplyTest(RPCClientTestCase):

    # The end of message character comes on its own, last
    replies = (
        Split(
            "<boinc_gui_rpc_reply><cc_status><task_mode>2</task_mode>",
            "<gpu_mode>3</gpu_mode></cc_status></boinc_gui_rpc_reply>",
            "",
        ),
    )

    async def test_a_reply_that_comes_in_pieces_is_read_whole(self):
        status = await self.client.get_cc_status()
        self.assertEqual(status["task_mode"], 2)
        self.assertEqual(status["gpu_mode"], 3)
        self.assertTrue(self.client.connected)


class AsyncWithTest(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.boinc = FakeBoinc()
        self.port = await self.boinc.start()
        self.addAsyncCleanup(self.boinc.stop)

    async def test_connects_on_entering_and_closes_on_leaving(self):
        async with RPCClient("127.0.0.1", "secret", self.port) as client:
            self.assertTrue(client.connected)
            self.assertIs(await client.network_available(), True)
        self.assertFalse(client.connected)
        await asyncio.wait_for(self.boinc.disconnected.wait(), 5)

    async def test_closes_on_an_error_and_lets_it_through(self):
        with self.assertRaisesRegex(RuntimeError, "in the block"):
            async with RPCClient("127.0.0.1", "secret", self.port) as client:
                raise RuntimeError("in the block")
        self.assertFalse(client.connected)
        await asyncio.wait_for(self.boinc.disconnected.wait(), 5)

    async def test_a_client_from_init_rpc_client_keeps_its_connection(self):
        client = await init_rpc_client("127.0.0.1", "secret", self.port)
        # So that the fake BOINC can stop even if the block does not close it
        self.addAsyncCleanup(client.close)
        await asyncio.wait_for(self.boinc.connected.wait(), 5)
        async with client as entered:
            self.assertIs(entered, client)
            await client.network_available()
        self.assertEqual(self.boinc.connections, 1)
        self.assertFalse(client.connected)

    async def test_a_host_that_cannot_be_reached_raises_on_entering(self):
        await self.boinc.stop()
        with self.assertRaises(BOINCConnectionError):
            async with RPCClient("127.0.0.1", "secret", self.port):
                self.fail("entered the block without a connection")


class ExportsTest(unittest.TestCase):

    def test_the_names_a_caller_needs_come_from_the_package(self):
        from aioboinc import _parse, rpc_client

        self.assertIs(aioboinc.Mode, rpc_client.Mode)
        self.assertIs(aioboinc.RPCClient, rpc_client.RPCClient)
        self.assertIs(aioboinc.Project, _parse.Project)

    def test_every_exported_name_is_there(self):
        for name in aioboinc.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(aioboinc, name))


class ExceptionsTest(unittest.TestCase):

    def test_every_error_is_a_boinc_error(self):
        for error in (BOINCAuthError, BOINCCommandError, BOINCConnectionError, BOINCTimeoutError):
            self.assertTrue(issubclass(error, BOINCError), error)

    def test_the_old_name_of_the_base_still_catches_them(self):
        self.assertIs(BOINCClientError, BOINCError)

    def test_a_reply_that_is_not_from_boinc_is_a_connection_error(self):
        # So that whoever only tells auth from connection errors gets it right too
        self.assertTrue(issubclass(BOINCProtocolError, BOINCConnectionError))
        self.assertFalse(issubclass(BOINCProtocolError, TimeoutError))

    def test_connection_and_timeout_errors_are_the_builtin_ones_too(self):
        self.assertTrue(issubclass(BOINCConnectionError, ConnectionError))
        self.assertTrue(issubclass(BOINCTimeoutError, BOINCConnectionError))
        self.assertTrue(issubclass(BOINCTimeoutError, TimeoutError))
        self.assertTrue(issubclass(BOINCTimeoutError, asyncio.TimeoutError))


class TimeoutTest(RPCClientTestCase):

    timeout = 0.1
    replies = (Late(web_state.seqno, 0.5), web_state.cc_status)

    async def test_a_late_reply_raises_timeout_error(self):
        with self.assertRaisesRegex(BOINCTimeoutError, "127.0.0.1 did not reply within 0.1 seconds"):
            await self.client.get_message_count()
        self.assertFalse(self.client.connected)

    async def test_the_next_request_does_not_take_the_late_reply(self):
        with self.assertRaises(TimeoutError):
            await self.client.get_message_count()
        with self.assertRaises(ConnectionError):
            await self.client.get_cc_status()
        await self.client.connect()
        status = await self.client.get_cc_status()
        self.assertEqual(status["task_mode"], 2)


class AuthorizeTimeoutTest(RPCClientTestCase):

    timeout = 0.1
    replies = (NO_REPLY,)

    async def test_authorize_times_out_too(self):
        with self.assertRaises(TimeoutError):
            await self.client.authorize()
        self.assertFalse(self.client.connected)


class NoTimeoutTest(RPCClientTestCase):

    timeout = None
    replies = (Late(web_state.seqno, 0.2),)

    async def test_none_waits_for_the_reply(self):
        self.assertEqual(await self.client.get_message_count(), 47)


class CancelTest(RPCClientTestCase):

    replies = (NO_REPLY,)

    async def test_a_request_cancelled_while_waiting_for_its_reply_drops_the_connection(self):
        request = asyncio.create_task(self.client.get_message_count())
        await asyncio.wait_for(self.boinc.received.wait(), timeout=5)
        request.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await request
        self.assertFalse(self.client.connected)
        await asyncio.wait_for(self.boinc.disconnected.wait(), timeout=5)


class ConnectTimeoutTest(unittest.IsolatedAsyncioTestCase):

    async def test_a_host_that_does_not_answer_raises_timeout_error(self):
        async def never_connects(*args, **kwargs):
            await asyncio.Event().wait()

        client = RPCClient("192.0.2.1", timeout=0.1)
        with (
            mock.patch("asyncio.open_connection", never_connects),
            self.assertRaisesRegex(BOINCTimeoutError, "connect to 192.0.2.1 within 0.1 seconds"),
        ):
            await client.connect()
        self.assertFalse(client.connected)


class SystemTimeoutTest(unittest.IsolatedAsyncioTestCase):
    """
    The system giving up on a connection raises a TimeoutError too, which is not the client's
    timeout running out
    """

    async def test_connecting_raises_connection_error(self):
        async def system_gives_up(*args, **kwargs):
            raise OSError(errno.ETIMEDOUT, "Connection timed out")

        client = RPCClient("192.0.2.1", timeout=None)
        with (
            mock.patch("asyncio.open_connection", system_gives_up),
            self.assertRaisesRegex(BOINCConnectionError, "Could not connect to 192.0.2.1") as caught,
        ):
            await client.connect()
        self.assertNotIsInstance(caught.exception, BOINCTimeoutError)
        self.assertEqual(caught.exception.__cause__.errno, errno.ETIMEDOUT)


class SystemTimeoutOnRequestTest(RPCClientTestCase):

    timeout = None

    async def test_a_request_raises_connection_error(self):
        async def system_gives_up(request):
            raise OSError(errno.ETIMEDOUT, "Connection timed out")

        with (
            mock.patch.object(self.client._raw_client, "_exchange", system_gives_up),
            self.assertRaisesRegex(BOINCConnectionError, "Lost the connection to 127.0.0.1") as caught,
        ):
            await self.client.get_cc_status()
        self.assertNotIsInstance(caught.exception, BOINCTimeoutError)
        self.assertEqual(caught.exception.__cause__.errno, errno.ETIMEDOUT)
        self.assertFalse(self.client.connected)


class ConnectRefusedTest(unittest.IsolatedAsyncioTestCase):

    async def test_a_port_nobody_listens_on_raises_connection_error(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        client = RPCClient("127.0.0.1", port=port)
        with self.assertRaisesRegex(BOINCConnectionError, "Could not connect to 127.0.0.1") as caught:
            await client.connect()
        self.assertIsInstance(caught.exception.__cause__, ConnectionRefusedError)
        self.assertFalse(client.connected)


class ConnectIPv6Test(unittest.IsolatedAsyncioTestCase):

    async def test_an_ipv6_address_raises_connection_error_without_trying(self):
        client = RPCClient("::1")
        with (
            mock.patch("asyncio.open_connection") as open_connection,
            self.assertRaisesRegex(BOINCConnectionError, "BOINC listens on IPv4 only"),
        ):
            await client.connect()
        open_connection.assert_not_called()
        self.assertFalse(client.connected)


class ConnectTest(RPCClientTestCase):

    async def test_connecting_twice_keeps_the_same_connection(self):
        await self.client.connect()
        self.assertIs(await self.client.set_run_mode(Mode.AUTO), True)
        self.assertFalse(self.boinc.disconnected.is_set())


class CloseTest(RPCClientTestCase):

    async def test_close_hangs_up(self):
        await self.client.close()
        await asyncio.wait_for(self.boinc.disconnected.wait(), timeout=5)
        self.assertFalse(self.client.connected)

    async def test_close_survives_a_peer_that_is_already_gone(self):
        writer = self.client._raw_client._writer

        async def reset():
            raise ConnectionResetError()

        with mock.patch.object(writer, "wait_closed", reset):
            await self.client.close()
        self.assertFalse(self.client.connected)

    async def test_close_twice_is_harmless(self):
        await self.client.close()
        await self.client.close()

    async def test_request_after_close_raises(self):
        await self.client.close()
        with self.assertRaises(BOINCConnectionError):
            await self.client.get_cc_status()

    async def test_can_connect_again_after_close(self):
        await self.client.close()
        await self.client.connect()
        self.assertIs(await self.client.set_run_mode(Mode.AUTO), True)


class HungUpTest(RPCClientTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.drop()
        # The client learns about it once the event loop passes it on
        for _ in range(500):
            if not self.client.connected:
                break
            await asyncio.sleep(0.01)

    async def drop(self):
        await self.boinc.hang_up()

    async def test_the_client_is_no_longer_connected(self):
        self.assertFalse(self.client.connected)

    async def test_a_request_raises_connection_error(self):
        with self.assertRaises(BOINCConnectionError):
            await self.client.get_cc_status()

    async def test_connect_opens_a_new_connection(self):
        old = self.client._raw_client._writer
        await self.client.connect()
        self.assertTrue(self.client.connected)
        self.assertTrue(old.is_closing())
        self.assertIs(await self.client.set_run_mode(Mode.AUTO), True)


class ResetTest(HungUpTest):

    async def drop(self):
        self.boinc.reset()


class NeverConnectedTest(unittest.IsolatedAsyncioTestCase):

    async def test_close_is_harmless(self):
        await RPCClient("127.0.0.1").close()

    async def test_request_raises(self):
        with self.assertRaisesRegex(BOINCConnectionError, "not opened before writing"):
            await RPCClient("127.0.0.1").get_cc_status()

    async def test_receiving_raises(self):
        with self.assertRaisesRegex(BOINCConnectionError, "not opened before reading"):
            await RPCClient("127.0.0.1")._raw_client.receive()


if __name__ == "__main__":
    unittest.main()
