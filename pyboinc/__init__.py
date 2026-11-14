"""
Deprecated alias of aioboinc, the name this package had before it was published

Importing it works exactly as before and warns once. Every module is the aioboinc module of the
same name rather than a copy, so `pyboinc.rpc_client.Mode is aioboinc.rpc_client.Mode` and code
that mixes both names keeps working.
"""

import sys
import warnings

import aioboinc
from aioboinc import _constants, _parse, _raw_client, _tag, rpc_client
from aioboinc import init_rpc_client  # noqa: F401

warnings.warn(
    "The pyboinc package is deprecated and will be removed in a future release of aioboinc; "
    "import aioboinc instead",
    DeprecationWarning,
    stacklevel=2,
)

for _module in (_constants, _parse, _raw_client, _tag, rpc_client):
    sys.modules[_module.__name__.replace(aioboinc.__name__, __name__, 1)] = _module
del _module
