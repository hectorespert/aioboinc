"""
Tests for connecting, authorizing, changing modes and closing
"""

import asyncio
import unittest
from hashlib import md5
from unittest import mock

from aioboinc.rpc_client import BOINCClientError, Mode, RPCClient

from .fake_boinc import NO_REPLY, Late, RPCClientTestCase
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
        await asyncio.gather(self.client.authorize("first"), self.client.authorize("second"))
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
        with self.assertRaisesRegex(ConnectionError, "invalid response"):
            await self.client.get_cc_status()
        # Whatever answered is not a BOINC client, so there is no point in going on talking to it
        self.assertFalse(self.client.connected)


class TimeoutTest(RPCClientTestCase):

    timeout = 0.1
    replies = (Late(web_state.seqno, 0.5), web_state.cc_status)

    async def test_a_late_reply_raises_timeout_error(self):
        with self.assertRaisesRegex(TimeoutError, "127.0.0.1 did not reply within 0.1 seconds"):
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
            self.assertRaisesRegex(TimeoutError, "connect to 192.0.2.1 within 0.1 seconds"),
        ):
            await client.connect()
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
        with self.assertRaises(ConnectionError):
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
        with self.assertRaises(ConnectionError):
            await RPCClient("127.0.0.1").get_cc_status()

    async def test_receiving_raises(self):
        with self.assertRaises(ConnectionError):
            await RPCClient("127.0.0.1")._raw_client.receive()


if __name__ == "__main__":
    unittest.main()
