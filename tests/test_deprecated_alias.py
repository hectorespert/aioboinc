"""
Tests for pyboinc, the deprecated alias of aioboinc
"""

import importlib
import sys
import unittest
import warnings


def _forget_pyboinc():
    for name in [n for n in sys.modules if n == "pyboinc" or n.startswith("pyboinc.")]:
        del sys.modules[name]


class DeprecatedAliasTest(unittest.TestCase):

    def setUp(self):
        _forget_pyboinc()
        self.addCleanup(_forget_pyboinc)

    def _import(self, name):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            module = importlib.import_module(name)
        return module, [w for w in caught if issubclass(w.category, DeprecationWarning)]

    def test_importing_pyboinc_warns_and_names_the_replacement(self):
        _, caught = self._import("pyboinc")
        self.assertEqual(len(caught), 1)
        self.assertIn("import aioboinc instead", str(caught[0].message))

    def test_importing_a_submodule_warns_too(self):
        _, caught = self._import("pyboinc.rpc_client")
        self.assertEqual(len(caught), 1)

    def test_the_warning_points_at_the_importing_code(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import pyboinc  # noqa: F401
        self.assertEqual(caught[0].filename, __file__)

    def test_modules_are_the_same_objects_not_copies(self):
        import aioboinc
        import aioboinc.rpc_client
        pyboinc, _ = self._import("pyboinc")
        rpc_client, _ = self._import("pyboinc.rpc_client")
        self.assertIs(pyboinc.init_rpc_client, aioboinc.init_rpc_client)
        self.assertIs(rpc_client, aioboinc.rpc_client)
        self.assertIs(rpc_client.Mode, aioboinc.rpc_client.Mode)
        self.assertIs(rpc_client.BOINCClientError, aioboinc.rpc_client.BOINCClientError)

    def test_every_module_has_an_alias(self):
        self._import("pyboinc")
        for name in ("_constants", "_parse", "_raw_client", "_tag", "rpc_client"):
            with self.subTest(name):
                self.assertIs(
                    importlib.import_module("pyboinc." + name),
                    importlib.import_module("aioboinc." + name),
                )

    def test_aioboinc_alone_does_not_warn(self):
        for name in [n for n in sys.modules if n == "aioboinc" or n.startswith("aioboinc.")]:
            self.addCleanup(sys.modules.__setitem__, name, sys.modules.pop(name))
        _, caught = self._import("aioboinc.rpc_client")
        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
