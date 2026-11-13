# aioboinc

[![Test](https://github.com/hectorespert/pyboinc/actions/workflows/test.yml/badge.svg)](https://github.com/hectorespert/pyboinc/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/aioboinc)](https://pypi.org/project/aioboinc/)

A small package to talk to a [BOINC](https://boinc.berkeley.edu/) client from Python using asyncio,
based on the [BOINC GUI RPC Protocol](https://boinc.berkeley.edu/trac/wiki/GuiRpcProtocol).
It is meant for monitoring and controlling a BOINC client and does not cover the whole protocol.
It has no dependencies outside the standard library.

This is a maintained fork of [nielstron/pyboinc](https://github.com/nielstron/pyboinc), which was
never published to PyPI. The distribution is called `aioboinc`; the package you import is still
`pyboinc`, so code written against the original keeps working. What differs from upstream is listed
in the [changelog](CHANGELOG.md).

## Installation

```
pip install aioboinc
```

## Usage

```python
import asyncio

from pyboinc import init_rpc_client
from pyboinc.rpc_client import Mode

IP_BOINC = "127.0.0.1"
PASSWORD_BOINC = "example_password"


async def main():
    rpc_client = await init_rpc_client(IP_BOINC, PASSWORD_BOINC)
    try:
        # Connecting does not authenticate. Do it before anything else and check the answer:
        # without it BOINC refuses to change anything and gives incomplete answers to queries.
        if not await rpc_client.authorize():
            raise SystemExit("Wrong password")

        print(await rpc_client.get_cc_status())
        print(await rpc_client.get_project_status())

        # Get the last three messages
        c = await rpc_client.get_message_count()
        print(await rpc_client.get_messages(c - 3))

        # Get the tasks. With no tasks this is the string "\n" rather than an empty list.
        results = await rpc_client.get_results()
        print(results)

        # Suspend a task and resume it
        if isinstance(results, list) and results:
            task = (results[0]["project_url"], results[0]["name"])
            print(await rpc_client.suspend_result(*task))
            print(await rpc_client.resume_result(*task))

        # Stop computing for an hour, then go back to what was configured.
        # A duration of 0, the default, makes the change permanent.
        print(await rpc_client.set_run_mode(Mode.NEVER, 3600))
    finally:
        await rpc_client.close()


asyncio.run(main())
```

## Development

```
python -m unittest discover -s tests -t .
```

The tests talk to a fake BOINC client on a local socket; no BOINC installation is needed.

## License

MIT, see [LICENSE](LICENSE). Copyright of the original work remains with its author.
