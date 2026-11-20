"""
Tests for the requests that read from the BOINC client

The replies are the ones in fixtures/web_state.py, captured from a real client.
"""

from datetime import datetime

from aioboinc._parse import Project

from .fake_boinc import RPCClientTestCase
from .fixtures import web_state

NO_RESULTS = "<boinc_gui_rpc_reply><results>\n</results></boinc_gui_rpc_reply>"


class ExchangeVersionsTest(RPCClientTestCase):

    replies = (web_state.server_version,)

    async def test_returns_the_version_as_numbers(self):
        self.assertEqual(
            await self.client.exchange_versions(), {"major": 7, "minor": 16, "release": 3}
        )
        self.assertEqual(self.boinc.requests, ["<exchange_versions/>"])


class DiskUsageTest(RPCClientTestCase):

    replies = (web_state.disk_usage_summary,)

    async def test_returns_the_usage_of_each_project(self):
        usage = await self.client.get_disk_usage()
        self.assertEqual(self.boinc.requests, ["<get_disk_usage/>"])
        self.assertEqual(
            usage["project"],
            [
                {"master_url": "https://csgrid.org/csg/", "disk_usage": 0.0},
                {"master_url": "http://www.gpugrid.net/", "disk_usage": 344319715.0},
            ],
        )

    async def test_returns_the_totals_of_the_disk(self):
        usage = await self.client.get_disk_usage()
        self.assertEqual(usage["d_total"], 30376042496.0)
        self.assertEqual(usage["d_free"], 23042801664.0)
        self.assertEqual(usage["d_boinc"], 422143.0)
        self.assertEqual(usage["d_allowed"], 15188021248.0)


class DiskUsageWithoutProjectsTest(RPCClientTestCase):

    replies = (
        "<boinc_gui_rpc_reply><disk_usage_summary>"
        "<d_total>100.000000</d_total><d_free>40.000000</d_free>"
        "<d_boinc>0.000000</d_boinc><d_allowed>50.000000</d_allowed>"
        "</disk_usage_summary></boinc_gui_rpc_reply>",
    )

    async def test_returns_no_projects_and_the_totals(self):
        self.assertEqual(
            await self.client.get_disk_usage(),
            {"project": [], "d_total": 100.0, "d_free": 40.0, "d_boinc": 0.0, "d_allowed": 50.0},
        )


class FileTransfersTest(RPCClientTestCase):

    replies = (web_state.file_transfers,)

    async def test_no_transfers_is_an_empty_list(self):
        self.assertEqual(await self.client.get_file_transfers(), [])
        self.assertEqual(self.boinc.requests, ["<get_file_transfers/>"])


class HostInfoTest(RPCClientTestCase):

    replies = (web_state.host_info,)

    async def test_returns_the_host_description(self):
        info = await self.client.get_host_info()
        self.assertEqual(self.boinc.requests, ["<get_host_info/>"])
        self.assertEqual(info["domain_name"], "localhost.localdomain")
        self.assertEqual(info["p_ncpus"], 4)
        self.assertEqual(info["p_vendor"], "AuthenticAMD")

    async def test_an_empty_text_is_an_empty_string(self):
        info = await self.client.get_host_info()
        self.assertEqual(info["ip_addr"], "")

    async def test_a_flag_is_false_when_0_and_true_when_1(self):
        info = await self.client.get_host_info()
        self.assertIs(info["p_vm_extensions_disabled"], False)
        self.assertIs(info["coprocs"][0]["have_opencl"], True)


class MessageCountTest(RPCClientTestCase):

    replies = (web_state.seqno,)

    async def test_returns_a_number(self):
        self.assertEqual(await self.client.get_message_count(), 47)
        self.assertEqual(self.boinc.requests, ["<get_message_count/>"])


class MessagesTest(RPCClientTestCase):

    replies = (web_state.msgs,)

    async def test_returns_every_message_parsed(self):
        messages = await self.client.get_messages()
        self.assertEqual(self.boinc.requests, ["<get_messages><seqno>0</seqno></get_messages>"])
        self.assertEqual(len(messages), 47)
        first = messages[0]
        self.assertEqual(first["seqno"], 1)
        self.assertEqual(first["pri"], 1)
        self.assertEqual(
            first["body"], "Starting BOINC client version 7.16.3 for x86_64-suse-linux-gnu"
        )
        self.assertEqual(first["time"], datetime.fromtimestamp(1586722353))

    async def test_a_message_from_the_client_itself_has_no_project(self):
        messages = await self.client.get_messages()
        self.assertEqual(messages[0]["project"], "")

    async def test_asks_from_a_sequence_number_and_for_translatable_text(self):
        await self.client.get_messages(44, translatable=True)
        self.assertEqual(
            self.boinc.requests, ["<get_messages><seqno>44</seqno><translatable/></get_messages>"]
        )


class ProjectStatusTest(RPCClientTestCase):

    replies = (web_state.projects,)

    async def test_returns_a_project_for_each_one_attached(self):
        projects = await self.client.get_project_status()
        self.assertEqual(self.boinc.requests, ["<get_project_status/>"])
        self.assertEqual(
            [str(p) for p in projects], ["https://csgrid.org/csg/", "http://www.gpugrid.net/"]
        )
        self.assertEqual(projects[0].project_name, "Citizen Science Grid")

    async def test_a_flag_sent_as_an_empty_element_is_true(self):
        project = (await self.client.get_project_status())[0]
        self.assertIs(project.dont_use_dcf, True)

    async def test_counters_that_look_like_flags_are_numbers(self):
        project = (await self.client.get_project_status())[0]
        # The BOINC client sends the reason for a pending scheduler request, not just whether there
        # is one, so 0 has to stay a number rather than become False.
        for counter in ("sched_rpc_pending", "send_time_stats_log", "send_job_log"):
            with self.subTest(counter):
                self.assertIs(type(getattr(project, counter)), int)

    async def test_a_project_compares_equal_to_its_url(self):
        project = (await self.client.get_project_status())[0]
        self.assertEqual(project, "https://csgrid.org/csg/")
        self.assertEqual(project, Project(master_url="https://csgrid.org/csg/"))
        self.assertNotEqual(project, "http://www.gpugrid.net/")
        self.assertTrue(repr(project).startswith("<Project https://csgrid.org/csg/, {"))

    async def test_a_project_can_be_a_dict_key_or_a_set_member(self):
        csgrid, gpugrid = await self.client.get_project_status()
        self.assertEqual({csgrid, gpugrid, Project(master_url="https://csgrid.org/csg/")}, {csgrid, gpugrid})
        tasks = {csgrid: 3, gpugrid: 1}
        self.assertEqual(tasks["http://www.gpugrid.net/"], 1)
        self.assertIn("https://csgrid.org/csg/", {csgrid})


class ResultsTest(RPCClientTestCase):

    replies = (web_state.results,)

    async def test_returns_every_task_parsed(self):
        results = await self.client.get_results()
        self.assertEqual(self.boinc.requests, ["<get_results/>"])
        self.assertEqual(len(results), 2)
        task = results[0]
        self.assertEqual(task["name"], "2ffeA01_379_3-TONI_MDADpr4sf-5-10-RND0805_0")
        self.assertEqual(task["version_num"], 210)
        self.assertEqual(task["project_url"], "http://www.gpugrid.net/")
        self.assertIsInstance(task["project_url"], Project)

    async def test_a_flag_is_true_when_present_and_missing_when_not(self):
        task = (await self.client.get_results())[0]
        self.assertIs(task["report_immediately"], True)
        self.assertNotIn("ready_to_report", task)

    async def test_can_ask_for_active_tasks_only(self):
        await self.client.get_results(active_only=True)
        self.assertEqual(self.boinc.requests, ["<get_results><active_only/></get_results>"])


class NoResultsTest(RPCClientTestCase):

    replies = (NO_RESULTS,)

    async def test_no_tasks_is_an_empty_list(self):
        self.assertEqual(await self.client.get_results(), [])


class NoResultsSelfClosingTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><results/></boinc_gui_rpc_reply>",)

    async def test_no_tasks_is_an_empty_list(self):
        self.assertEqual(await self.client.get_results(), [])
