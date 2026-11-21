"""
Tests for the requests that read from the BOINC client

The replies are the ones in fixtures/web_state.py, captured from a real client.
"""

from datetime import UTC, date, datetime, timedelta

from aioboinc import (
    ActiveTaskState,
    DockerType,
    MessagePriority,
    Mode,
    NetworkStatus,
    Project,
    ResultState,
    RpcReason,
    SchedulerState,
    SuspendReason,
)

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


class AcctMgrInfoTest(RPCClientTestCase):

    # As handle_acct_mgr_info() in client/gui_rpc_server_ops.cpp writes it, with an account manager
    # that needs a cookie
    replies = (
        """<boinc_gui_rpc_reply>
<acct_mgr_info>
   <acct_mgr_url>https://bam.boincstats.com/</acct_mgr_url>
   <acct_mgr_name>BAM!</acct_mgr_name>
   <have_credentials/>
   <cookie_required/>
   <cookie_failure_url>https://bam.boincstats.com/login</cookie_failure_url>
</acct_mgr_info>
</boinc_gui_rpc_reply>""",
    )

    async def test_returns_the_account_manager(self):
        self.assertEqual(
            await self.client.get_acct_mgr_info(),
            {
                "acct_mgr_url": "https://bam.boincstats.com/",
                "acct_mgr_name": "BAM!",
                "have_credentials": True,
                "cookie_required": True,
                "cookie_failure_url": "https://bam.boincstats.com/login",
            },
        )
        self.assertEqual(self.boinc.requests, ["<acct_mgr_info/>"])


class NoAcctMgrTest(RPCClientTestCase):

    replies = (
        """<boinc_gui_rpc_reply>
<acct_mgr_info>
   <acct_mgr_url></acct_mgr_url>
   <acct_mgr_name></acct_mgr_name>
</acct_mgr_info>
</boinc_gui_rpc_reply>""",
    )

    async def test_the_url_and_name_are_empty_and_the_flags_false(self):
        self.assertEqual(
            await self.client.get_acct_mgr_info(),
            {
                "acct_mgr_url": "",
                "acct_mgr_name": "",
                "have_credentials": False,
                "cookie_required": False,
            },
        )


class CcStatusTest(RPCClientTestCase):

    replies = (web_state.cc_status,)

    async def test_every_mode_is_a_mode(self):
        status = await self.client.get_cc_status()
        for mode in ("task_mode", "gpu_mode", "network_mode"):
            with self.subTest(mode):
                self.assertIs(status[mode], Mode.AUTO)
                self.assertIs(status[f"{mode}_perm"], Mode.AUTO)

    async def test_the_reasons_and_the_network_are_enums(self):
        status = await self.client.get_cc_status()
        self.assertIs(status["task_suspend_reason"], SuspendReason.TIME_OF_DAY)
        self.assertIs(status["gpu_suspend_reason"], SuspendReason.NOT_SUSPENDED)
        self.assertIs(status["network_suspend_reason"], SuspendReason.NOT_SUSPENDED)
        self.assertIs(status["network_status"], NetworkStatus.WANT_DISCONNECT)

    async def test_a_member_is_still_its_number(self):
        status = await self.client.get_cc_status()
        self.assertEqual(status["task_suspend_reason"], 8)
        self.assertFalse(status["gpu_suspend_reason"])


class CcStatusUnknownReasonTest(RPCClientTestCase):

    # A newer BOINC client may add a reason
    replies = (
        web_state.cc_status.replace(
            "<task_suspend_reason>8</task_suspend_reason>",
            "<task_suspend_reason>4200</task_suspend_reason>",
        ),
    )

    async def test_a_value_the_enum_does_not_have_is_an_int(self):
        status = await self.client.get_cc_status()
        self.assertIs(type(status["task_suspend_reason"]), int)
        self.assertEqual(status["task_suspend_reason"], 4200)


class CcStatusFlagsTest(RPCClientTestCase):

    replies = (web_state.cc_status,)

    async def test_flags_are_flags(self):
        status = await self.client.get_cc_status()
        self.assertIs(status["ams_password_error"], False)
        # BOINC sends it only when it is set
        self.assertIs(status["manager_must_quit"], False)
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


class DailyXferHistoryTest(RPCClientTestCase):

    # As DAILY_XFER_HISTORY::write_xml() in client/net_stats.cpp writes it, newest first
    replies = (
        """<boinc_gui_rpc_reply>
<daily_xfers>
<dx>
   <when>20778</when>
   <up>1756975929.000000</up>
   <down>1268207794.000000</down>
</dx>
<dx>
   <when>20777</when>
   <up>1531476955.000000</up>
   <down>2092898794.000000</down>
</dx>
</daily_xfers>
</boinc_gui_rpc_reply>""",
    )

    async def test_returns_every_day(self):
        history = await self.client.get_daily_xfer_history()
        self.assertEqual(self.boinc.requests, ["<get_daily_xfer_history/>"])
        self.assertEqual(
            history,
            [
                {"when": date(2026, 11, 21), "up": 1756975929.0, "down": 1268207794.0},
                {"when": date(2026, 11, 20), "up": 1531476955.0, "down": 2092898794.0},
            ],
        )


class NoDailyXferHistoryTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply>\n<daily_xfers>\n</daily_xfers>\n</boinc_gui_rpc_reply>",)

    async def test_returns_an_empty_list(self):
        self.assertEqual(await self.client.get_daily_xfer_history(), [])


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
        self.assertIs(info["coprocs"]["NVIDIA"]["have_opencl"], True)
        self.assertIs(info["coprocs"]["NVIDIA"]["have_cuda"], True)
        self.assertIs(info["wsl_available"], False)

    async def test_numbers_are_numbers(self):
        info = await self.client.get_host_info()
        self.assertEqual(info["timezone"], 7200)
        self.assertEqual(info["n_usable_coprocs"], 1)

    async def test_when_the_benchmarks_ran_is_a_time(self):
        info = await self.client.get_host_info()
        self.assertEqual(info["p_calculated"], datetime.fromtimestamp(1586431995.189977, UTC))

    async def test_the_properties_of_a_gpu_are_numbers(self):
        gpu = (await self.client.get_host_info())["coprocs"]["NVIDIA"]
        self.assertEqual(gpu["available_ram"], 4167041024.0)
        self.assertEqual(gpu["totalGlobalMem"], 4294967295.0)
        self.assertEqual(gpu["warpSize"], 32)
        self.assertEqual(gpu["clockRate"], 1708500)
        self.assertEqual(gpu["pci_info"]["bus_id"], 1)


class HostInfoWithOtherCoprocessorsTest(RPCClientTestCase):

    # As COPROC_INTEL::write_xml() and COPROC::write_xml() in lib/coproc.cpp write them, the second
    # for a kind of coprocessor BOINC has no element of its own for
    replies = (
        """<boinc_gui_rpc_reply>
<host_info>
    <coprocs>
<coproc_intel_gpu>
   <count>1</count>
   <name>Intel(R) UHD Graphics 630</name>
</coproc_intel_gpu>
<coproc>
   <type>Some vendor GPU</type>
   <count>2</count>
   <peak_flops>0.000000</peak_flops>
</coproc>
    </coprocs>
</host_info>
</boinc_gui_rpc_reply>
""",
        "<boinc_gui_rpc_reply>\n<host_info>\n    <coprocs>\n    </coprocs>\n</host_info>\n</boinc_gui_rpc_reply>",
    )

    async def test_each_is_under_the_name_of_its_resource(self):
        coprocs = (await self.client.get_host_info())["coprocs"]
        self.assertEqual(list(coprocs), ["intel_gpu", "Some vendor GPU"])
        self.assertEqual(coprocs["Some vendor GPU"]["count"], 2)

    async def test_no_coprocessors_is_an_empty_dict(self):
        await self.client.get_host_info()
        self.assertEqual((await self.client.get_host_info())["coprocs"], {})
class HostInfoWithRepeatedElementsTest(RPCClientTestCase):

    # As HOST_INFO::write() in lib/hostinfo.cpp writes them: the OpenCL properties of the CPU for
    # each OpenCL platform, and on Windows the WSL distributions
    replies = (
        """<boinc_gui_rpc_reply>
<host_info>
    <wsl>
        <distro>
            <distro_name>Ubuntu</distro_name>
            <os_name>Ubuntu</os_name>
            <os_version>24.04</os_version>
            <wsl_version>2</wsl_version>
        </distro>
        <distro>
            <distro_name>boinc-buda-runner</distro_name>
            <os_name>Ubuntu</os_name>
            <os_version>22.04</os_version>
            <wsl_version>2</wsl_version>
            <distro_version>3</distro_version>
            <wsl_gpu>
                <name>NVIDIA GeForce RTX 3060</name>
                <has_cuda/>
                <has_opencl/>
            </wsl_gpu>
            <wsl_gpu>
                <name>Intel(R) UHD Graphics</name>
                <has_opencl/>
            </wsl_gpu>
        </distro>
    </wsl>
<opencl_cpu_prop>
   <platform_vendor>Intel(R) Corporation</platform_vendor>
   <opencl_cpu_info>
      <name>Intel(R) Core(TM) i7</name>
   </opencl_cpu_info>
</opencl_cpu_prop>
<opencl_cpu_prop>
   <platform_vendor>The pocl project</platform_vendor>
   <opencl_cpu_info>
      <name>pthread-Intel(R) Core(TM) i7</name>
   </opencl_cpu_info>
</opencl_cpu_prop>
</host_info>
</boinc_gui_rpc_reply>
""",
        "<boinc_gui_rpc_reply>\n<host_info>\n    <wsl>\n    </wsl>\n</host_info>\n</boinc_gui_rpc_reply>",
    )

    async def test_every_wsl_distribution_is_there(self):
        info = await self.client.get_host_info()
        self.assertEqual([d["distro_name"] for d in info["wsl"]], ["Ubuntu", "boinc-buda-runner"])

    async def test_the_version_of_a_distribution_is_a_number(self):
        info = await self.client.get_host_info()
        self.assertEqual(info["wsl"][1]["distro_version"], 3)

    async def test_every_gpu_of_a_distribution_is_there(self):
        info = await self.client.get_host_info()
        self.assertEqual(
            info["wsl"][1]["wsl_gpu"],
            [
                {"name": "NVIDIA GeForce RTX 3060", "has_cuda": True, "has_opencl": True},
                {"name": "Intel(R) UHD Graphics", "has_opencl": True},
            ],
        )

    async def test_every_opencl_platform_of_the_cpu_is_there(self):
        info = await self.client.get_host_info()
        self.assertEqual(
            [p["platform_vendor"] for p in info["opencl_cpu_prop"]],
            ["Intel(R) Corporation", "The pocl project"],
        )

    async def test_no_wsl_distribution_is_an_empty_list_and_no_platform_is_no_key(self):
        await self.client.get_host_info()
        info = await self.client.get_host_info()
        self.assertEqual(info["wsl"], [])
        self.assertNotIn("opencl_cpu_prop", info)


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

    async def test_the_gpus_are_by_resource(self):
        # The names of the resources in rsc_backoff_time of a project, among others
        self.assertEqual(list((await self.client.get_host_info())["coprocs"]), ["ATI", "apple_gpu"])

    async def test_flags_of_a_gpu_are_flags(self):
        coprocs = (await self.client.get_host_info())["coprocs"]
        amd, apple = coprocs["ATI"], coprocs["apple_gpu"]
        self.assertIs(amd["have_cal"], False)
        self.assertIs(amd["have_opencl"], True)
        self.assertIs(apple["have_metal"], True)
        self.assertIs(apple["have_opencl"], False)

    async def test_properties_of_a_gpu_are_numbers(self):
        coprocs = (await self.client.get_host_info())["coprocs"]
        amd, apple = coprocs["ATI"], coprocs["apple_gpu"]
        self.assertEqual(
            [amd[p] for p in ("localRAM", "engineClock", "wavefrontSize", "numberOfSIMD", "target")],
            [8192, 2100, 64, 36, 0],
        )
        self.assertIs(amd["doublePrecision"], True)
        self.assertEqual([apple["ncores"], apple["metal_support"]], [8, 7])

    async def test_the_type_of_docker_is_a_docker_type(self):
        self.assertIs((await self.client.get_host_info())["docker_type"], DockerType.PODMAN)


class MessagesTest(RPCClientTestCase):

    replies = (web_state.msgs,)

    async def test_returns_every_message_parsed(self):
        messages = await self.client.get_messages()
        self.assertEqual(self.boinc.requests, ["<get_messages><seqno>0</seqno></get_messages>"])
        self.assertEqual(len(messages), 47)
        first = messages[0]
        self.assertEqual(first["seqno"], 1)
        self.assertIs(first["pri"], MessagePriority.INFO)
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


def inner(reply, tag):
    # The element of a captured reply, as text, to build another reply with
    start = reply.index(f"<{tag}>")
    end = reply.rindex(f"</{tag}>") + len(f"</{tag}>")
    return reply[start:end]


# As CLIENT_STATE::write_state_gui() in client/cs_statefile.cpp writes it: the host, the network
# and time statistics, then each project followed by its apps, app versions, workunits and tasks,
# and last the client, its platforms and the global preferences
STATE = (
    "<boinc_gui_rpc_reply>\n<client_state>\n"
    + inner(web_state.host_info, "host_info")
    + """
<have_cuda/>
<net_stats>
    <bwup>584580387.616399</bwup>
    <avg_up>1057412043.172964</avg_up>
    <avg_time_up>1795027437.639985</avg_time_up>
    <bwdown>6103516.654512</bwdown>
    <avg_down>1968170055.966415</avg_down>
    <avg_time_down>1795027298.713402</avg_time_down>
</net_stats>
<time_stats>
    <on_frac>0.999</on_frac>
    <connected_frac>-1.000000</connected_frac>
    <cpu_and_network_available_frac>0.998</cpu_and_network_available_frac>
    <active_frac>0.997</active_frac>
    <gpu_active_frac>0.996</gpu_active_frac>
    <client_start_time>1795000000.000000</client_start_time>
    <total_start_time>1600000000.000000</total_start_time>
    <total_duration>195000000.000000</total_duration>
    <total_active_duration>194000000.000000</total_active_duration>
    <total_gpu_active_duration>193000000.000000</total_gpu_active_duration>
    <now>1795027500.000000</now>
    <previous_uptime>3600.000000</previous_uptime>
    <session_active_duration>27000.000000</session_active_duration>
    <session_gpu_active_duration>26000.000000</session_gpu_active_duration>
</time_stats>
"""
    + inner(web_state.projects, "project").split("</project>")[0]
    + """</project>
<app>
    <name>period_search</name>
    <user_friendly_name>Period Search Application</user_friendly_name>
    <non_cpu_intensive>0</non_cpu_intensive>
</app>
<app_version>
    <app_name>period_search</app_name>
    <version_num>10222</version_num>
    <platform>x86_64-pc-linux-gnu</platform>
    <plan_class>opencl_101_amd_linux</plan_class>
    <file_ref>
        <file_name>period_search_10222_linux_opencl_x64</file_name>
        <main_program/>
    </file_ref>
    <file_ref>
        <file_name>libOpenCL.so</file_name>
        <open_name>libOpenCL.so.1</open_name>
        <copy_file/>
    </file_ref>
    <avg_ncpus>0.010000</avg_ncpus>
    <flops>39683185388.323620</flops>
    <coproc>
        <type>ATI</type>
        <count>0.500000</count>
    </coproc>
    <dont_throttle/>
</app_version>
<workunit>
    <name>ps_261115_input_6651_108</name>
    <app_name>period_search</app_name>
    <version_num>10222</version_num>
    <rsc_fpops_est>8319704636358.558594</rsc_fpops_est>
    <rsc_fpops_bound>831970463635855.875000</rsc_fpops_bound>
    <rsc_memory_bound>64000000.000000</rsc_memory_bound>
    <rsc_disk_bound>100000000.000000</rsc_disk_bound>
    <command_line>
--device 0
    </command_line>
    <file_ref>
        <file_name>ps_261115_input_6651_108</file_name>
        <open_name>period_search_in</open_name>
    </file_ref>
<job_keywords>
<keyword>
   <name>Astronomy</name>
   <description>Astronomy and astrophysics</description>
   <parent>0</parent>
   <level>0</level>
   <category>0</category>
</keyword>
</job_keywords>
</workunit>
"""
    + inner(web_state.results, "result").split("</result>")[0]
    + """</result>
<platform_name>x86_64-pc-linux-gnu</platform_name>
<core_client_major_version>8</core_client_major_version>
<core_client_minor_version>2</core_client_minor_version>
<core_client_release>9</core_client_release>
<executing_as_daemon>1</executing_as_daemon>
<platform>x86_64-pc-linux-gnu</platform>
<platform>i686-pc-linux-gnu</platform>
<global_preferences>
   <source_project>https://example.org/</source_project>
   <mod_time>1794000000.000000</mod_time>
   <battery_charge_min_pct>90.000000</battery_charge_min_pct>
   <battery_max_temperature>40.000000</battery_max_temperature>
   <run_on_batteries>0</run_on_batteries>
   <run_if_user_active>1</run_if_user_active>
   <run_gpu_if_user_active>1</run_gpu_if_user_active>
   <suspend_if_no_recent_input>0.000000</suspend_if_no_recent_input>
   <suspend_cpu_usage>25.000000</suspend_cpu_usage>
   <start_hour>0.000000</start_hour>
   <end_hour>0.000000</end_hour>
   <net_start_hour>0.000000</net_start_hour>
   <net_end_hour>0.000000</net_end_hour>
   <leave_apps_in_memory>1</leave_apps_in_memory>
   <confirm_before_connecting>1</confirm_before_connecting>
   <hangup_if_dialed>0</hangup_if_dialed>
   <dont_verify_images>0</dont_verify_images>
   <work_buf_min_days>0.100000</work_buf_min_days>
   <work_buf_additional_days>0.500000</work_buf_additional_days>
   <max_ncpus_pct>100.000000</max_ncpus_pct>
   <niu_max_ncpus_pct>100.000000</niu_max_ncpus_pct>
   <niu_cpu_usage_limit>100.000000</niu_cpu_usage_limit>
   <niu_suspend_cpu_usage>50.000000</niu_suspend_cpu_usage>
   <cpu_scheduling_period_minutes>60.000000</cpu_scheduling_period_minutes>
   <disk_interval>60.000000</disk_interval>
   <disk_max_used_gb>0.000000</disk_max_used_gb>
   <disk_max_used_pct>90.000000</disk_max_used_pct>
   <disk_min_free_gb>1.000000</disk_min_free_gb>
   <vm_max_used_pct>75.000000</vm_max_used_pct>
   <ram_max_used_busy_pct>50.000000</ram_max_used_busy_pct>
   <ram_max_used_idle_pct>90.000000</ram_max_used_idle_pct>
   <idle_time_to_run>3.000000</idle_time_to_run>
   <max_bytes_sec_up>0.000000</max_bytes_sec_up>
   <max_bytes_sec_down>0.000000</max_bytes_sec_down>
   <cpu_usage_limit>100.000000</cpu_usage_limit>
   <daily_xfer_limit_mb>0.000000</daily_xfer_limit_mb>
   <daily_xfer_period_days>0</daily_xfer_period_days>
   <override_file_present>1</override_file_present>
   <network_wifi_only>0</network_wifi_only>
   <max_cpus>8</max_cpus>
   <day_prefs>
      <day_of_week>0</day_of_week>
      <start_hour>8.00</start_hour>
      <end_hour>20.00</end_hour>
   </day_prefs>
   <day_prefs>
      <day_of_week>6</day_of_week>
      <net_start_hour>1.00</net_start_hour>
      <net_end_hour>7.00</net_end_hour>
   </day_prefs>
</global_preferences>
<host_venue>home</host_venue>
</client_state>
</boinc_gui_rpc_reply>
"""
)


class StateTest(RPCClientTestCase):

    replies = (STATE,)

    async def test_returns_each_kind_in_its_list(self):
        state = await self.client.get_state()
        self.assertEqual(self.boinc.requests, ["<get_state/>"])
        self.assertEqual(
            {key: len(state[key]) for key in ("projects", "apps", "app_versions", "workunits", "results")},
            {"projects": 1, "apps": 1, "app_versions": 1, "workunits": 1, "results": 1},
        )
        self.assertIsInstance(state["projects"][0], Project)
        self.assertEqual(state["platforms"], ["x86_64-pc-linux-gnu", "i686-pc-linux-gnu"])
        self.assertEqual(state["host_info"]["p_ncpus"], 4)
        self.assertEqual(state["results"][0]["state"], ResultState.FILES_DOWNLOADED)

    async def test_an_app_a_version_and_a_workunit_have_their_project(self):
        state = await self.client.get_state()
        project = state["projects"][0]
        for key in ("apps", "app_versions", "workunits"):
            with self.subTest(key):
                self.assertEqual(state[key][0]["project_url"], project)
                self.assertIsInstance(state[key][0]["project_url"], Project)

    async def test_a_gpu_used_in_part_is_a_fraction(self):
        app_version = (await self.client.get_state())["app_versions"][0]
        self.assertEqual(app_version["coproc"], {"type": "ATI", "count": 0.5})

    async def test_every_file_is_there_with_its_flags(self):
        state = await self.client.get_state()
        files = state["app_versions"][0]["file_ref"]
        self.assertEqual([f["file_name"] for f in files], ["period_search_10222_linux_opencl_x64", "libOpenCL.so"])
        self.assertEqual(
            [(f["main_program"], f["copy_file"], f["optional"]) for f in files],
            [(True, False, False), (False, True, False)],
        )
        self.assertEqual(state["app_versions"][0]["is_wrapper"], False)
        self.assertEqual(state["app_versions"][0]["dont_throttle"], True)

    async def test_a_workunit_has_its_command_line_and_keywords(self):
        workunit = (await self.client.get_state())["workunits"][0]
        self.assertEqual(workunit["command_line"], "--device 0")
        self.assertEqual(workunit["rsc_fpops_est"], 8319704636358.558594)
        self.assertEqual(
            workunit["job_keywords"],
            [
                {
                    "name": "Astronomy",
                    "description": "Astronomy and astrophysics",
                    "parent": 0,
                    "level": 0,
                    "category": "0",
                }
            ],
        )

    async def test_the_client_and_its_statistics_are_typed(self):
        state = await self.client.get_state()
        self.assertEqual(
            [state["core_client_major_version"], state["core_client_minor_version"], state["core_client_release"]],
            [8, 2, 9],
        )
        self.assertIs(state["executing_as_daemon"], True)
        self.assertIs(state["have_cuda"], True)
        self.assertIs(state["have_ati"], False)
        self.assertEqual(state["net_stats"]["avg_time_up"], datetime.fromtimestamp(1795027437.639985, UTC))
        self.assertEqual(state["time_stats"]["now"], datetime.fromtimestamp(1795027500, UTC))
        self.assertEqual(state["time_stats"]["previous_uptime"], 3600.0)
        self.assertEqual(state["host_venue"], "home")

    async def test_the_global_preferences_are_typed(self):
        prefs = (await self.client.get_state())["global_preferences"]
        self.assertIs(prefs["run_on_batteries"], False)
        self.assertIs(prefs["leave_apps_in_memory"], True)
        self.assertEqual(prefs["suspend_cpu_usage"], 25.0)
        self.assertEqual(prefs["max_cpus"], 8)
        self.assertEqual(prefs["mod_time"], datetime.fromtimestamp(1794000000, UTC))
        self.assertEqual(
            prefs["day_prefs"],
            [
                {"day_of_week": 0, "start_hour": 8.0, "end_hour": 20.0},
                {"day_of_week": 6, "net_start_hour": 1.0, "net_end_hour": 7.0},
            ],
        )


class StatisticsTest(RPCClientTestCase):

    # As PROJECT::write_statistics() in client/project.cpp writes them
    replies = (
        """<boinc_gui_rpc_reply>
<statistics>
<project_statistics>
    <master_url>https://example.org/</master_url>
    <daily_statistics>
        <day>1792627200.000000</day>
        <user_total_credit>6003209.070563</user_total_credit>
        <user_expavg_credit>9926.368779</user_expavg_credit>
        <host_total_credit>2061033.250151</host_total_credit>
        <host_expavg_credit>9809.884259</host_expavg_credit>
    </daily_statistics>
    <daily_statistics>
        <day>1792713600.000000</day>
        <user_total_credit>6010923.767445</user_total_credit>
        <user_expavg_credit>10382.212385</user_expavg_credit>
        <host_total_credit>2068683.137689</host_total_credit>
        <host_expavg_credit>10253.652183</host_expavg_credit>
    </daily_statistics>
</project_statistics>
<project_statistics>
    <master_url>https://new.example.org/</master_url>
</project_statistics>
</statistics>
</boinc_gui_rpc_reply>""",
    )

    async def test_returns_every_day_of_every_project(self):
        statistics = await self.client.get_statistics()
        self.assertEqual(self.boinc.requests, ["<get_statistics/>"])
        self.assertEqual(
            [p["master_url"] for p in statistics], ["https://example.org/", "https://new.example.org/"]
        )
        days = statistics[0]["daily_statistics"]
        self.assertEqual(
            [d["day"] for d in days],
            [datetime(2026, 10, 22, tzinfo=UTC), datetime(2026, 10, 23, tzinfo=UTC)],
        )
        self.assertEqual(
            days[1],
            {
                "day": datetime(2026, 10, 23, tzinfo=UTC),
                "user_total_credit": 6010923.767445,
                "user_expavg_credit": 10382.212385,
                "host_total_credit": 2068683.137689,
                "host_expavg_credit": 10253.652183,
            },
        )

    async def test_a_project_without_days_has_an_empty_list(self):
        self.assertEqual((await self.client.get_statistics())[1]["daily_statistics"], [])


NOTICE = """<notice>
   <title>Downtime on Tuesday</title>
   <description><![CDATA[
The project will be down on Tuesday.<br />
Sorry.
]]></description>
   <create_time>1792672125.000000</create_time>
   <arrival_time>1792730460.500000</arrival_time>
   <is_private>0</is_private>
   <project_name>Example@home</project_name>
   <category></category>
   <link><![CDATA[https://example.org/forum_thread.php?id=1]]></link>
   <seqno>{seqno}</seqno>
</notice>
"""


def notices_reply(*notices):
    return "<boinc_gui_rpc_reply>\n<notices>\n" + "".join(notices) + "</notices>\n</boinc_gui_rpc_reply>"


class NoticesTest(RPCClientTestCase):

    # As NOTICES::write() in client/cs_notice.cpp writes them, oldest first
    replies = (notices_reply(NOTICE.format(seqno=1), NOTICE.format(seqno=2)),)

    async def test_returns_every_notice_parsed(self):
        reply = await self.client.get_notices()
        self.assertEqual(self.boinc.requests, ["<get_notices><seqno>0</seqno></get_notices>"])
        self.assertIs(reply["refresh"], False)
        self.assertEqual([n["seqno"] for n in reply["notices"]], [1, 2])
        notice = reply["notices"][0]
        self.assertEqual(notice["title"], "Downtime on Tuesday")
        self.assertEqual(notice["description"], "The project will be down on Tuesday.<br />\nSorry.")
        self.assertEqual(notice["create_time"], datetime.fromtimestamp(1792672125, UTC))
        self.assertEqual(notice["arrival_time"], datetime.fromtimestamp(1792730460.5, UTC))
        self.assertIs(notice["is_private"], False)
        self.assertEqual(notice["project_name"], "Example@home")
        self.assertEqual(notice["category"], "")
        self.assertEqual(notice["link"], "https://example.org/forum_thread.php?id=1")

    async def test_asks_from_a_sequence_number(self):
        await self.client.get_notices(2)
        self.assertEqual(self.boinc.requests, ["<get_notices><seqno>2</seqno></get_notices>"])


class NoNoticesTest(RPCClientTestCase):

    replies = (notices_reply(),)

    async def test_returns_an_empty_list(self):
        self.assertEqual(await self.client.get_notices(5), {"refresh": False, "notices": []})


class NoticesRefreshTest(RPCClientTestCase):

    # After removing notices, BOINC sends a notice with seqno -1 and then all of them, whatever
    # the sequence number asked from
    replies = (
        notices_reply(
            NOTICE.format(seqno=-1).replace("1792672125.000000", "0.000000"),
            NOTICE.format(seqno=1),
            NOTICE.format(seqno=3),
        ),
    )

    async def test_says_so_and_leaves_out_the_marker(self):
        reply = await self.client.get_notices(3)
        self.assertIs(reply["refresh"], True)
        self.assertEqual([n["seqno"] for n in reply["notices"]], [1, 3])


class NoticesPublicTest(RPCClientTestCase):

    replies = (notices_reply(NOTICE.format(seqno=1)),)

    async def test_asks_for_the_public_ones(self):
        reply = await self.client.get_notices_public(0)
        self.assertEqual(
            self.boinc.requests, ["<get_notices_public><seqno>0</seqno></get_notices_public>"]
        )
        self.assertEqual([n["seqno"] for n in reply["notices"]], [1])


class OldResultsTest(RPCClientTestCase):

    # As print_old_results() in client/result.cpp writes them
    replies = (
        """<boinc_gui_rpc_reply>
<old_results>
    <old_result>
         <project_url>https://example.org/</project_url>
         <result_name>ps_261115_input_6462_9_0</result_name>
         <app_name>period_search</app_name>
         <exit_status>0</exit_status>
         <elapsed_time>207.615999</elapsed_time>
         <cpu_time>0.945063</cpu_time>
         <completed_time>1792730000.000000</completed_time>
         <create_time>1792733600.500000</create_time>
    </old_result>
</old_results>
</boinc_gui_rpc_reply>""",
    )

    async def test_returns_every_task_parsed(self):
        old_results = await self.client.get_old_results()
        self.assertEqual(self.boinc.requests, ["<get_old_results/>"])
        self.assertEqual(
            old_results,
            [
                {
                    "project_url": "https://example.org/",
                    "result_name": "ps_261115_input_6462_9_0",
                    "app_name": "period_search",
                    "exit_status": 0,
                    "elapsed_time": timedelta(seconds=207.615999),
                    "cpu_time": timedelta(seconds=0.945063),
                    "completed_time": datetime.fromtimestamp(1792730000, UTC),
                    "create_time": datetime.fromtimestamp(1792733600.5, UTC),
                }
            ],
        )
        self.assertIsInstance(old_results[0]["project_url"], Project)


class NoOldResultsTest(RPCClientTestCase):

    replies = ("<boinc_gui_rpc_reply>\n<old_results>\n</old_results>\n</boinc_gui_rpc_reply>",)

    async def test_returns_an_empty_list(self):
        self.assertEqual(await self.client.get_old_results(), [])
class NewerVersionTest(RPCClientTestCase):

    # As handle_get_newer_version() in client/gui_rpc_server_ops.cpp writes it: two elements, not
    # one with both
    replies = (
        "<boinc_gui_rpc_reply>\n<newer_version>8.2.11</newer_version>\n"
        "<download_url>https://boinc.berkeley.edu/download.php</download_url>\n</boinc_gui_rpc_reply>",
        "<boinc_gui_rpc_reply>\n<newer_version></newer_version>\n"
        "<download_url>https://boinc.berkeley.edu/download.php</download_url>\n</boinc_gui_rpc_reply>",
    )

    async def test_returns_the_version_and_where_to_download_it(self):
        self.assertEqual(
            await self.client.get_newer_version(),
            {"newer_version": "8.2.11", "download_url": "https://boinc.berkeley.edu/download.php"},
        )
        self.assertEqual(self.boinc.requests, ["<get_newer_version/>"])

    async def test_the_version_is_empty_when_there_is_no_newer_one(self):
        await self.client.get_newer_version()
        self.assertEqual((await self.client.get_newer_version())["newer_version"], "")


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
        for counter in ("send_time_stats_log", "send_job_log"):
            with self.subTest(counter):
                self.assertIs(type(getattr(project, counter)), int)

    async def test_a_pending_scheduler_request_is_its_reason(self):
        project = (await self.client.get_project_status())[0]
        # The BOINC client sends the reason for a pending scheduler request, not just whether there
        # is one, so 0 is a reason rather than False.
        self.assertIs(project.sched_rpc_pending, RpcReason.NONE)

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

    async def test_the_states_are_enums(self):
        task = (await self.client.get_results())[0]
        self.assertIs(task["state"], ResultState.FILES_DOWNLOADED)
        self.assertIs(task["active_task"]["active_task_state"], ActiveTaskState.UNINITIALIZED)
        self.assertIs(task["active_task"]["scheduler_state"], SchedulerState.PREEMPTED)

    async def test_a_flag_is_true_when_present_and_false_when_not(self):
        task = (await self.client.get_results())[0]
        self.assertIs(task["report_immediately"], True)
        self.assertIs(task["ready_to_report"], False)
        self.assertIs(task["active_task"]["needs_shmem"], False)

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
