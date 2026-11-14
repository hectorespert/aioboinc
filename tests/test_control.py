"""
Tests for the requests that change something on the BOINC client
"""

from aioboinc._parse import Project

from .fake_boinc import RPCClientTestCase

TASK = ("https://example.org/", "task_0")
TASK_XML = "<project_url>https://example.org/</project_url><name>task_0</name>"


class TaskControlTest(RPCClientTestCase):

    async def test_abort_result(self):
        self.assertIs(await self.client.abort_result(*TASK), True)
        self.assertEqual(self.boinc.requests, ["<abort_result>" + TASK_XML + "</abort_result>"])

    async def test_suspend_result(self):
        self.assertIs(await self.client.suspend_result(*TASK), True)
        self.assertEqual(
            self.boinc.requests, ["<suspend_result>" + TASK_XML + "</suspend_result>"]
        )

    async def test_resume_result(self):
        self.assertIs(await self.client.resume_result(*TASK), True)
        self.assertEqual(self.boinc.requests, ["<resume_result>" + TASK_XML + "</resume_result>"])

    async def test_a_task_can_be_named_by_the_project_a_query_returned(self):
        project = Project(master_url="https://example.org/")
        await self.client.suspend_result(project, "task_0")
        self.assertEqual(
            self.boinc.requests, ["<suspend_result>" + TASK_XML + "</suspend_result>"]
        )


class ClientControlTest(RPCClientTestCase):

    async def test_quit(self):
        self.assertIs(await self.client.quit(), True)
        self.assertEqual(self.boinc.requests, ["<quit/>"])

    async def test_network_available(self):
        self.assertIs(await self.client.network_available(), True)
        self.assertEqual(self.boinc.requests, ["<network_available/>"])

    async def test_set_language(self):
        self.assertIs(await self.client.set_language("es"), True)
        self.assertEqual(
            self.boinc.requests, ["<set_language><language>es</language></set_language>"]
        )


class DetailedReplyTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><status>3</status></boinc_gui_rpc_reply>",)

    async def test_a_reply_that_is_not_a_plain_success_is_handed_back(self):
        reply = await self.client.network_available()
        self.assertEqual((reply.tag, reply.text), ("status", "3"))
