"""
Tests for the requests that read from the BOINC client

The replies are the ones in fixtures/web_state.py, captured from a real client.
"""

from datetime import UTC, datetime, timedelta

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


class CcStatusTest(RPCClientTestCase):

    replies = (web_state.cc_status,)

    async def test_every_mode_is_a_number(self):
        status = await self.client.get_cc_status()
        self.assertEqual(
            [status[mode] for mode in ("task_mode", "gpu_mode", "network_mode")], [2, 2, 2]
        )


class CcStatusFlagsTest(RPCClientTestCase):

    replies = (web_state.cc_status,)

    async def test_flags_are_flags(self):
        status = await self.client.get_cc_status()
        self.assertIs(status["ams_password_error"], False)
        self.assertIs(status["disallow_attach"], False)
        self.assertIs(status["simple_gui_only"], False)


class CcStatusFlagsSetTest(RPCClientTestCase):

    # BOINC adds manager_must_quit, as 1, only when an update asks the Manager to quit
    replies = (
        web_state.cc_status.replace(
            "<ams_password_error>0</ams_password_error>", "<ams_password_error>1</ams_password_error>"
        ).replace("</cc_status>", "   <manager_must_quit>1</manager_must_quit>\n</cc_status>"),
    )

    async def test_set_flags_are_true(self):
        status = await self.client.get_cc_status()
        self.assertIs(status["ams_password_error"], True)
        self.assertIs(status["manager_must_quit"], True)


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


class FileTransferTest(RPCClientTestCase):

    # As FILE_INFO::write_gui() and PERS_FILE_XFER::write() in the client write them, with
    # project_backoff only while the project backs off its transfers
    replies = (
        """<boinc_gui_rpc_reply>
<file_transfers>
<file_transfer>
    <project_url>http://www.gpugrid.net/</project_url>
    <project_name>GPUGRID</project_name>
    <name>result_0_r1_sent_0</name>
    <nbytes>1048576.000000</nbytes>
    <max_nbytes>10000000.000000</max_nbytes>
    <status>0</status>
    <persistent_file_xfer>
        <num_retries>2</num_retries>
        <first_request_time>1586729657.140112</first_request_time>
        <next_request_time>1586729957.140112</next_request_time>
        <time_so_far>12.500000</time_so_far>
        <last_bytes_xferred>524288.000000</last_bytes_xferred>
        <is_upload>1</is_upload>
    </persistent_file_xfer>
    <file_xfer>
        <estimated_xfer_time_remaining>30.000000</estimated_xfer_time_remaining>
        <bytes_xferred>524288.000000</bytes_xferred>
        <file_offset>0.000000</file_offset>
        <xfer_speed>41943.040000</xfer_speed>
        <url>https://www.gpugrid.net/upload</url>
    </file_xfer>
    <project_backoff>120.000000</project_backoff>
</file_transfer>
</file_transfers>
</boinc_gui_rpc_reply>
""",
    )

    async def test_numbers_are_numbers(self):
        (transfer,) = await self.client.get_file_transfers()
        self.assertEqual(transfer["nbytes"], 1048576.0)
        self.assertEqual(transfer["max_nbytes"], 10000000.0)
        self.assertEqual(transfer["status"], 0)
        self.assertEqual(transfer["project_backoff"], 120.0)
        self.assertEqual(transfer["persistent_file_xfer"]["last_bytes_xferred"], 524288.0)
        self.assertEqual(transfer["file_xfer"]["bytes_xferred"], 524288.0)
        self.assertEqual(transfer["file_xfer"]["file_offset"], 0.0)

    async def test_the_time_left_is_a_timedelta_like_the_time_so_far(self):
        (transfer,) = await self.client.get_file_transfers()
        self.assertEqual(transfer["file_xfer"]["estimated_xfer_time_remaining"], timedelta(seconds=30))
        self.assertEqual(transfer["persistent_file_xfer"]["time_so_far"], timedelta(seconds=12.5))


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
        self.assertIs(info["coprocs"][0]["have_cuda"], True)
        self.assertIs(info["wsl_available"], False)

    async def test_numbers_are_numbers(self):
        info = await self.client.get_host_info()
        self.assertEqual(info["timezone"], 7200)
        self.assertEqual(info["n_usable_coprocs"], 1)

    async def test_the_properties_of_a_gpu_are_numbers(self):
        gpu = (await self.client.get_host_info())["coprocs"][0]
        self.assertEqual(gpu["available_ram"], 4167041024.0)
        self.assertEqual(gpu["totalGlobalMem"], 4294967295.0)
        self.assertEqual(gpu["warpSize"], 32)
        self.assertEqual(gpu["clockRate"], 1708500)
        self.assertEqual(gpu["pci_info"]["bus_id"], 1)


class MessageCountTest(RPCClientTestCase):

    replies = (web_state.seqno,)

    async def test_returns_a_number(self):
        self.assertEqual(await self.client.get_message_count(), 47)
        self.assertEqual(self.boinc.requests, ["<get_message_count/>"])


class HostInfoWithAmdAndAppleGpusTest(RPCClientTestCase):

    # As COPROC_ATI::write_xml() and COPROC_APPLE::write_xml() in lib/coproc.cpp write them
    replies = (
        """<boinc_gui_rpc_reply>
<host_info>
    <coprocs>
<coproc_ati>
   <count>1</count>
   <name>Radeon RX 580</name>
   <have_cal>0</have_cal>
   <have_opencl>1</have_opencl>
   <target>0</target>
   <localRAM>8192</localRAM>
   <uncachedRemoteRAM>0</uncachedRemoteRAM>
   <cachedRemoteRAM>0</cachedRemoteRAM>
   <engineClock>2100</engineClock>
   <memoryClock>0</memoryClock>
   <wavefrontSize>64</wavefrontSize>
   <numberOfSIMD>36</numberOfSIMD>
   <doublePrecision>1</doublePrecision>
   <pitch_alignment>0</pitch_alignment>
   <surface_alignment>0</surface_alignment>
   <maxResource1DWidth>0</maxResource1DWidth>
   <maxResource2DWidth>0</maxResource2DWidth>
   <maxResource2DHeight>0</maxResource2DHeight>
</coproc_ati>
<coproc_apple_gpu>
   <count>1</count>
   <model>Apple M1</model>
   <have_metal>1</have_metal>
   <have_opencl>0</have_opencl>
   <ncores>8</ncores>
   <metal_support>7</metal_support>
</coproc_apple_gpu>
    </coprocs>
    <docker_version>27.5.1</docker_version>
    <docker_type>2</docker_type>
</host_info>
</boinc_gui_rpc_reply>
""",
    )

    async def test_flags_of_a_gpu_are_flags(self):
        amd, apple = (await self.client.get_host_info())["coprocs"]
        self.assertIs(amd["have_cal"], False)
        self.assertIs(amd["have_opencl"], True)
        self.assertIs(apple["have_metal"], True)
        self.assertIs(apple["have_opencl"], False)

    async def test_properties_of_a_gpu_are_numbers(self):
        amd, apple = (await self.client.get_host_info())["coprocs"]
        self.assertEqual(
            [amd[p] for p in ("localRAM", "engineClock", "wavefrontSize", "numberOfSIMD", "target")],
            [8192, 2100, 64, 36, 0],
        )
        self.assertIs(amd["doublePrecision"], True)
        self.assertEqual([apple["ncores"], apple["metal_support"]], [8, 7])

    async def test_the_type_of_docker_is_a_number(self):
        self.assertEqual((await self.client.get_host_info())["docker_type"], 2)


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
        self.assertEqual(first["time"], datetime(2020, 4, 12, 20, 12, 33, tzinfo=UTC))

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

    async def test_the_priority_is_a_number_and_an_unset_download_time_none(self):
        project = (await self.client.get_project_status())[0]
        self.assertEqual(project.sched_priority, 0.0)
        self.assertIsNone(project.project_files_downloaded_time)

    async def test_a_time_is_in_utc(self):
        project = (await self.client.get_project_status())[1]
        self.assertIs(project.last_rpc_time.tzinfo, UTC)

    async def test_a_time_that_is_not_set_is_none(self):
        unset, backed_off = await self.client.get_project_status()
        # BOINC sends 0 when the project has no backoff and has not asked for a next request
        self.assertIsNone(unset.min_rpc_time)
        self.assertIsNone(unset.next_rpc_time)
        self.assertEqual(backed_off.min_rpc_time, datetime.fromtimestamp(1586729657.140112, UTC))

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


class ProjectBackoffTest(RPCClientTestCase):

    # As PROJECT::write_state() in client/project.cpp writes them, one of each per resource
    replies = (
        """<boinc_gui_rpc_reply>
<projects>
<project>
    <master_url>http://www.gpugrid.net/</master_url>
    <rsc_backoff_time>
        <name>CPU</name>
        <value>0.000000</value>
    </rsc_backoff_time>
    <rsc_backoff_interval>
        <name>CPU</name>
        <value>0.000000</value>
    </rsc_backoff_interval>
    <rsc_backoff_time>
        <name>NVIDIA</name>
        <value>1586729657.140112</value>
    </rsc_backoff_time>
    <rsc_backoff_interval>
        <name>NVIDIA</name>
        <value>600.000000</value>
    </rsc_backoff_interval>
    <no_rsc_pref>CPU</no_rsc_pref>
    <no_rsc_apps>CPU</no_rsc_apps>
    <no_rsc_apps>intel_gpu</no_rsc_apps>
</project>
</projects>
</boinc_gui_rpc_reply>
""",
    )

    async def test_each_resource_has_its_backoff(self):
        (project,) = await self.client.get_project_status()
        self.assertEqual(
            project.rsc_backoff_time,
            {"CPU": None, "NVIDIA": datetime.fromtimestamp(1586729657.140112, UTC)},
        )
        self.assertEqual(project.rsc_backoff_interval, {"CPU": 0.0, "NVIDIA": 600.0})

    async def test_each_resource_a_flag_applies_to_is_listed(self):
        (project,) = await self.client.get_project_status()
        self.assertEqual(project.no_rsc_apps, ["CPU", "intel_gpu"])
        self.assertEqual(project.no_rsc_pref, ["CPU"])
        self.assertEqual(project.no_rsc_ams, [])
        self.assertEqual(project.no_rsc_config, [])


class ProjectBackoffOfCapturedReplyTest(RPCClientTestCase):

    replies = (web_state.projects,)

    async def test_no_resource_is_lost(self):
        csgrid, gpugrid = await self.client.get_project_status()
        self.assertEqual(csgrid.rsc_backoff_time, {"CPU": None, "NVIDIA": None})
        self.assertEqual(csgrid.rsc_backoff_interval, {"CPU": 0.0, "NVIDIA": 0.0})
        self.assertEqual(csgrid.no_rsc_apps, ["NVIDIA"])
        self.assertEqual(gpugrid.no_rsc_apps, [])


class ProjectSharesAndBackoffsTest(RPCClientTestCase):

    # As PROJECT::write_state() writes them for the GUI: ams_resource_share_new only when an account
    # manager sets the share, and the backoffs, in seconds left, only while there is one
    replies = (
        """<boinc_gui_rpc_reply>
<projects>
<project>
    <master_url>http://www.gpugrid.net/</master_url>
    <disk_share>24234069469.866669</disk_share>
    <ams_resource_share_new>50.000000</ams_resource_share_new>
    <download_backoff>60.000000</download_backoff>
    <upload_backoff>90.500000</upload_backoff>
</project>
</projects>
</boinc_gui_rpc_reply>
""",
    )

    async def test_numbers_are_numbers(self):
        (project,) = await self.client.get_project_status()
        self.assertEqual(project.disk_share, 24234069469.866669)
        self.assertEqual(project.ams_resource_share_new, 50.0)
        self.assertEqual(project.download_backoff, 60.0)
        self.assertEqual(project.upload_backoff, 90.5)


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



class CompletedResultTest(RPCClientTestCase):

    # As RESULT::write_gui() and ACTIVE_TASK::write_gui() write them: completed_time only once the
    # task is done
    replies = (
        """<boinc_gui_rpc_reply>
<results>
<result>
    <name>task_1</name>
    <completed_time>1795246648.368982</completed_time>
    <active_task>
        <swap_size>1048576</swap_size>
        <virtual_size>2097152</virtual_size>
    </active_task>
</result>
</results>
</boinc_gui_rpc_reply>
""",
    )

    async def test_the_time_it_completed_is_a_time(self):
        (task,) = await self.client.get_results()
        self.assertEqual(task["completed_time"], datetime.fromtimestamp(1795246648.368982, UTC))

    async def test_the_virtual_size_is_a_number_like_the_swap_size(self):
        (task,) = await self.client.get_results()
        self.assertEqual(task["active_task"]["virtual_size"], 2097152.0)
        self.assertEqual(task["active_task"]["swap_size"], 1048576.0)

class NoResultsTest(RPCClientTestCase):

    replies = (NO_RESULTS,)

    async def test_no_tasks_is_an_empty_list(self):
        self.assertEqual(await self.client.get_results(), [])


class NoResultsSelfClosingTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply><results/></boinc_gui_rpc_reply>",)

    async def test_no_tasks_is_an_empty_list(self):
        self.assertEqual(await self.client.get_results(), [])
