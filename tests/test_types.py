"""
Tests that the types of the replies list the keys the replies have

The replies are the ones in fixtures/web_state.py, captured from a real client, and those the tests of
the queries write as the BOINC client does.
"""

from typing import get_type_hints, is_typeddict

import aioboinc
from aioboinc import CcStatus, DiskUsage, ProjectDiskUsage, Version

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


class ExportedTypesTest(TypesTest):

    def test_every_type_resolves(self):
        # An annotation that names something missing fails only when it is read
        for name in aioboinc.__all__:
            obj = getattr(aioboinc, name)
            if is_typeddict(obj):
                with self.subTest(name):
                    get_type_hints(obj)
