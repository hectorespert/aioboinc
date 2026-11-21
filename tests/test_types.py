"""
Tests that the types of the replies list the keys the replies have

The replies are the ones in fixtures/web_state.py, captured from a real client, and those the tests of
the queries write as the BOINC client does.
"""

from typing import get_type_hints, is_typeddict

import aioboinc
from aioboinc import (
    ActiveTask,
    CcStatus,
    DiskUsage,
    HostInfo,
    Project,
    ProjectDiskUsage,
    Result,
    Version,
    WslDistro,
    WslGpu,
)

from .fake_boinc import RPCClientTestCase
from .fixtures import web_state


class TypesTest(RPCClientTestCase):

    def assertMatches(self, reply, typed_dict):
        # Every key BOINC always writes is there, and every key there is listed
        self.assertLessEqual(typed_dict.__required_keys__, reply.keys())
        self.assertLessEqual(reply.keys(), typed_dict.__required_keys__ | typed_dict.__optional_keys__)


class VersionTest(TypesTest):

    replies = (web_state.server_version,)

    async def test_matches_the_reply(self):
        self.assertMatches(await self.client.exchange_versions(), Version)


class CcStatusTypeTest(TypesTest):

    replies = (
        web_state.cc_status,
        web_state.cc_status.replace(
            "</cc_status>", "   <manager_must_quit>1</manager_must_quit>\n</cc_status>"
        ),
    )

    async def test_matches_the_reply(self):
        self.assertMatches(await self.client.get_cc_status(), CcStatus)

    async def test_manager_must_quit_is_not_required(self):
        await self.client.get_cc_status()
        self.assertMatches(await self.client.get_cc_status(), CcStatus)
        self.assertIn("manager_must_quit", CcStatus.__optional_keys__)


class DiskUsageTypeTest(TypesTest):

    replies = (web_state.disk_usage_summary,)

    async def test_matches_the_reply(self):
        disk_usage = await self.client.get_disk_usage()
        self.assertMatches(disk_usage, DiskUsage)
        for project in disk_usage["project"]:
            self.assertMatches(project, ProjectDiskUsage)


class HostInfoTypeTest(TypesTest):

    replies = (
        web_state.host_info,
        # The fields a current client adds on a Windows host with a WSL distribution
        web_state.host_info.replace(
            "</host_info>",
            """    <wsl_version>2.3.26.0</wsl_version>
    <wsl>
        <distro>
            <distro_name>boinc-buda-runner</distro_name>
            <os_name>Ubuntu</os_name>
            <os_version>22.04</os_version>
            <wsl_version>2</wsl_version>
            <distro_version>3</distro_version>
            <is_default/>
            <libc_version>2.35</libc_version>
            <docker_version>4.9.3</docker_version>
            <docker_type>2</docker_type>
            <wsl_gpu>
                <name>NVIDIA GeForce RTX 3060</name>
                <has_cuda/>
            </wsl_gpu>
        </distro>
    </wsl>
    <product_name>Example PC</product_name>
    <virtualbox_version>7.0.20</virtualbox_version>
</host_info>""",
        ),
    )

    async def test_matches_the_reply(self):
        self.assertMatches(await self.client.get_host_info(), HostInfo)

    async def test_matches_the_reply_with_wsl(self):
        await self.client.get_host_info()
        info = await self.client.get_host_info()
        self.assertMatches(info, HostInfo)
        for distro in info["wsl"]:
            self.assertMatches(distro, WslDistro)
            for gpu in distro["wsl_gpu"]:
                self.assertMatches(gpu, WslGpu)


class ProjectTypeTest(TypesTest):

    replies = (web_state.projects,)

    async def test_matches_the_reply(self):
        annotations = get_type_hints(Project)
        with_default = {name for name in annotations if name in vars(Project)}
        for project in await self.client.get_project_status():
            with self.subTest(project.master_url):
                # Every field without a default is there, and every field there is annotated
                self.assertLessEqual(annotations.keys() - with_default, vars(project).keys())
                self.assertLessEqual(vars(project).keys(), annotations.keys())

    async def test_a_flag_that_is_not_sent_is_false_and_a_value_none(self):
        project = (await self.client.get_project_status())[0]
        self.assertNotIn("suspended_via_gui", vars(project))
        self.assertIs(project.suspended_via_gui, False)
        self.assertIsNone(project.download_backoff)

    async def test_a_flag_that_is_sent_is_true(self):
        # dont_use_dcf is set on the first project of the captured reply
        project = (await self.client.get_project_status())[0]
        self.assertIs(project.dont_use_dcf, True)

    def test_the_defaults_are_not_shared_mutable_values(self):
        # A list or a dict on the class would be one for every project
        for name in vars(Project):
            if not name.startswith("_"):
                with self.subTest(name):
                    self.assertNotIsInstance(getattr(Project, name), (list, dict, set))


class ResultTypeTest(TypesTest):

    replies = (web_state.results,)

    async def test_matches_the_reply(self):
        for result in await self.client.get_results():
            with self.subTest(result["name"]):
                self.assertMatches(result, Result)
                if "active_task" in result:
                    self.assertMatches(result["active_task"], ActiveTask)


class ExportedTypesTest(TypesTest):

    def test_every_type_resolves(self):
        # An annotation that names something missing fails only when it is read
        for name in aioboinc.__all__:
            obj = getattr(aioboinc, name)
            if is_typeddict(obj):
                with self.subTest(name):
                    get_type_hints(obj)
