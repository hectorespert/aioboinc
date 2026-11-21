"""
Tests for the requests that change something on the BOINC client
"""

from aioboinc import BOINCCommandError, Project

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


PROJECT_URL = "https://example.org/"
PROJECT_XML = "<project_url>https://example.org/</project_url>"


class ProjectControlTest(RPCClientTestCase):

    OPS = {
        "update_project": "project_update",
        "suspend_project": "project_suspend",
        "resume_project": "project_resume",
        "no_new_tasks": "project_nomorework",
        "allow_new_tasks": "project_allowmorework",
        "reset_project": "project_reset",
        "detach_project": "project_detach",
        "detach_project_when_done": "project_detach_when_done",
        "dont_detach_project_when_done": "project_dont_detach_when_done",
    }

    async def test_each_op_sends_its_request(self):
        for method, tag in self.OPS.items():
            with self.subTest(method):
                self.boinc.requests.clear()
                self.assertIs(await getattr(self.client, method)(PROJECT_URL), True)
                self.assertEqual(self.boinc.requests, [f"<{tag}>{PROJECT_XML}</{tag}>"])

    async def test_a_project_can_be_named_by_the_project_a_query_returned(self):
        await self.client.suspend_project(Project(master_url=PROJECT_URL))
        self.assertEqual(
            self.boinc.requests, ["<project_suspend>" + PROJECT_XML + "</project_suspend>"]
        )


class DetachProjectOfAccountManagerTest(RPCClientTestCase):

    # As the BOINC client answers for a project attached via an account manager
    replies = (
        "<boinc_gui_rpc_reply><error>must detach using account manager</error></boinc_gui_rpc_reply>",
    )

    async def test_raises_command_error(self):
        with self.assertRaisesRegex(BOINCCommandError, "must detach using account manager"):
            await self.client.detach_project(PROJECT_URL)


class UnknownProjectTest(RPCClientTestCase):

    # As the BOINC client answers for a project it is not attached to
    replies = ("<boinc_gui_rpc_reply><error>No such project</error></boinc_gui_rpc_reply>",)

    async def test_raises_command_error(self):
        with self.assertRaisesRegex(BOINCCommandError, "No such project"):
            await self.client.update_project("https://unknown.example.org/")


TRANSFER = ("https://example.org/", "result_0_r1_sent_0")
TRANSFER_XML = "<project_url>https://example.org/</project_url><filename>result_0_r1_sent_0</filename>"


class FileTransferControlTest(RPCClientTestCase):

    async def test_retry_file_transfer(self):
        self.assertIs(await self.client.retry_file_transfer(*TRANSFER), True)
        self.assertEqual(
            self.boinc.requests, ["<retry_file_transfer>" + TRANSFER_XML + "</retry_file_transfer>"]
        )

    async def test_abort_file_transfer(self):
        self.assertIs(await self.client.abort_file_transfer(*TRANSFER), True)
        self.assertEqual(
            self.boinc.requests, ["<abort_file_transfer>" + TRANSFER_XML + "</abort_file_transfer>"]
        )

    async def test_a_transfer_can_be_named_by_the_project_a_query_returned(self):
        await self.client.retry_file_transfer(Project(master_url=TRANSFER[0]), TRANSFER[1])
        self.assertEqual(
            self.boinc.requests, ["<retry_file_transfer>" + TRANSFER_XML + "</retry_file_transfer>"]
        )


class NoSuchTransferTest(RPCClientTestCase):

    # As the BOINC client answers for a file it has but does not transfer
    replies = ("<boinc_gui_rpc_reply><error>No such transfer waiting</error></boinc_gui_rpc_reply>",)

    async def test_raises_command_error(self):
        with self.assertRaisesRegex(BOINCCommandError, "No such transfer waiting"):
            await self.client.retry_file_transfer(*TRANSFER)


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
