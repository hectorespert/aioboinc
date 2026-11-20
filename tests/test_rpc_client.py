"""
Tests for connecting, authorizing, changing modes and closing
"""

import asyncio
import socket
import unittest
from hashlib import md5
from unittest import mock

from aioboinc import BOINCAuthError, BOINCClientError, BOINCConnectionError, BOINCTimeoutError
from aioboinc.rpc_client import Mode, RPCClient

from .fake_boinc import HANG_UP, NO_REPLY, Late, RPCClientTestCase
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


class Auth1ErrorTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><error>no</error></boinc_gui_rpc_reply>",)

    async def test_an_error_instead_of_the_nonce_raises(self):
        with self.assertRaisesRegex(BOINCClientError, "no"):
            await self.client.authorize()
        self.assertFalse(self.client.connected)


class Auth1WithoutNonceTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><nonce/></boinc_gui_rpc_reply>",)

    async def test_a_reply_without_the_nonce_raises(self):
        with self.assertRaisesRegex(BOINCConnectionError, "did not answer auth1 with a nonce"):
            await self.client.authorize()
        self.assertFalse(self.client.connected)


class Auth2UnexpectedTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><nonce>1</nonce></boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply><success/></boinc_gui_rpc_reply>",
    )

    async def test_a_reply_other_than_authorized_raises(self):
        with self.assertRaisesRegex(BOINCConnectionError, "did not answer auth2 with authorized"):
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
        with self.assertRaisesRegex(BOINCConnectionError, "invalid reply"):
            await self.client.get_cc_status()
        # Whatever answered is not a BOINC client, so there is no point in going on talking to it
        self.assertFalse(self.client.connected)


class EmptyReplyTest(RPCClientTestCase):

    # What BOINC sends before hanging up on an auth1 it did not expect
    replies = ("<boinc_gui_rpc_reply>\n</boinc_gui_rpc_reply>",)

    async def test_an_empty_reply_raises(self):
        with self.assertRaisesRegex(BOINCConnectionError, "invalid reply"):
            await self.client.get_cc_status()
        self.assertFalse(self.client.connected)


class MalformedReplyTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><cc_status>",)

    async def test_a_reply_that_is_not_xml_raises(self):
        with self.assertRaisesRegex(BOINCConnectionError, "invalid reply"):
            await self.client.get_cc_status()
        self.assertFalse(self.client.connected)


class HangUpInsteadOfReplyTest(RPCClientTestCase):

    replies = (HANG_UP,)

    async def test_a_host_that_hangs_up_raises_connection_error(self):
        with self.assertRaisesRegex(BOINCConnectionError, "127.0.0.1 closed the connection"):
            await self.client.get_cc_status()
        self.assertFalse(self.client.connected)


class ExceptionsTest(unittest.TestCase):

    def test_every_error_is_a_boinc_client_error(self):
        for error in (BOINCAuthError, BOINCConnectionError, BOINCTimeoutError):
            self.assertTrue(issubclass(error, BOINCClientError), error)

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
