# aioboinc

[![Test](https://github.com/hectorespert/aioboinc/actions/workflows/test.yml/badge.svg)](https://github.com/hectorespert/aioboinc/actions/workflows/test.yml)
[![Coverage](https://raw.githubusercontent.com/hectorespert/aioboinc/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/hectorespert/aioboinc/blob/python-coverage-comment-action-data/htmlcov/index.html)
[![PyPI](https://img.shields.io/pypi/v/aioboinc)](https://pypi.org/project/aioboinc/)

A small package to talk to a [BOINC](https://boinc.berkeley.edu/) client from Python using asyncio,
based on the [BOINC GUI RPC Protocol](https://github.com/BOINC/boinc/wiki/GuiRpcProtocol).
It is meant for monitoring and controlling a BOINC client and does not cover the whole protocol.
It has no dependencies outside the standard library.

This is a maintained fork of [nielstron/pyboinc](https://github.com/nielstron/pyboinc), which was
never published to PyPI. What differs from upstream is listed in the [changelog](CHANGELOG.md).

### Coming from `pyboinc`

The package is imported as `aioboinc`, not `pyboinc`, so moving over starts with a rename of the
imports:

```python
from aioboinc import Mode, init_rpc_client
```

Since 0.4.0 errors are raised rather than returned. `authorize()` raises `BOINCAuthError` for a
wrong password instead of returning `False`, and so does a request that needs it first. The
[changelog](CHANGELOG.md) lists the rest.

## Installation

```
pip install aioboinc
```

## Usage

```python
import asyncio

from aioboinc import BOINCAuthError, Mode, RPCClient

IP_BOINC = "127.0.0.1"
PASSWORD_BOINC = "example_password"


async def main():
    # Leaving the block closes the connection, even on an error. A host that cannot be reached
    # raises BOINCConnectionError; see Errors below for the rest.
    async with RPCClient(IP_BOINC, PASSWORD_BOINC) as rpc_client:
        # Connecting does not authenticate. Do it before anything else: without it BOINC refuses
        # to change anything, and to answer queries from another host, with BOINCAuthError.
        try:
            await rpc_client.authorize()
        except BOINCAuthError:
            raise SystemExit("Wrong password") from None

        print(await rpc_client.get_cc_status())
        print(await rpc_client.get_project_status())

        # Get the last three messages
        c = await rpc_client.get_message_count()
        print(await rpc_client.get_messages(c - 3))

        # Get the tasks
        results = await rpc_client.get_results()
        print(results)

        # Suspend a task and resume it
        if results:
            task = (results[0]["project_url"], results[0]["name"])
            print(await rpc_client.suspend_result(*task))
            print(await rpc_client.resume_result(*task))

        # Stop computing for an hour, then go back to what was configured.
        # A duration of 0, the default, makes the change permanent.
        print(await rpc_client.set_run_mode(Mode.NEVER, 3600))


asyncio.run(main())
```

## Methods

`init_rpc_client(host, password=None, port=31416, timeout=30.0)` connects to the BOINC client on
`host` and returns an `RPCClient`. `async with RPCClient(host, password=None, port=31416,
timeout=30.0) as client:` does the same, and closes the connection when the block ends, even on
an error; `async with` on a client from `init_rpc_client()` closes it too. `timeout` is the seconds to connect, and to get each reply
afterwards; `None` waits forever. `password` is the one in `gui_rpc_auth.cfg`, in the BOINC data
directory.

BOINC listens on IPv4 only, so `host` is a name, resolved to its IPv4 addresses, or an IPv4
address. An IPv6 address raises `BOINCConnectionError`.

To manage the connection:

| Method | Does |
| --- | --- |
| `authorize(password=None)` | Authorizes the connection. Needed for the requests that change something, and for every request from another host |
| `connect()` | Connects again, after the connection was dropped or closed. Call `authorize()` next |
| `close()` | Closes the connection |
| `connected` | Whether there is a connection |

To read the state of the BOINC client:

| Method | Returns |
| --- | --- |
| `exchange_versions()` | The version of the BOINC client, as a dict with `major`, `minor` and `release` |
| `get_cc_status()` | Its modes, why it is suspended, and the state of its network, as a dict |
| `get_daily_xfer_history()` | The bytes uploaded and downloaded each day, newest first, as a list of dicts with `when`, a `date`, `up` and `down` |
| `get_disk_usage()` | The disk space each project uses, under `project`, and the totals of the disk, in bytes |
| `get_file_transfers()` | A list of the uploads and downloads |
| `get_host_info()` | The description of the host: CPU, memory, disk, operating system, GPUs |
| `get_message_count()` | The sequence number of the newest message of the event log |
| `get_messages(seqno=0, translatable=False)` | A list of the messages newer than `seqno` |
| `get_newer_version()` | The newest version of the BOINC client, under `newer_version`, `""` when the one running is the newest, and the page to download it from, under `download_url`. BOINC asks the BOINC website first, so it may take seconds |
| `get_notices(seqno=0)` | The notices newer than `seqno`, as a dict with `notices`, a list, and `refresh`, `True` when the list is complete and replaces the notices got before. It needs `authorize()` even locally |
| `get_notices_public(seqno=0)` | The same, without the private notices, and without `authorize()` |
| `get_old_results()` | A list of the tasks reported and deleted in the last hour, which `get_results()` no longer has |
| `get_project_status()` | A list of the projects, as `Project` objects, importable from `aioboinc`, that compare equal to their URL |
| `get_results(active_only=False)` | A list of the tasks; with `active_only=True`, only those started and not finished |
| `get_statistics()` | The credit of the user and of the host for each day, as a list with a dict for each project, with its `master_url` and its `daily_statistics` |

The replies are dicts and lists keyed by the names of the elements BOINC sends, described in the
[protocol](https://github.com/BOINC/boinc/wiki/GuiRpcProtocol#requests-and-replies). Numbers come
as `int` or `float`, flags as `bool`, times as `datetime` in UTC, or `None` when they are not set,
the days of `get_daily_xfer_history()` as `date`,
and the CPU and elapsed times of a task, and the time so far and left of a transfer, as
`timedelta`. Other durations, such as the `*_mode_delay` of `get_cc_status()` or the backoffs, are
`float` seconds. States and reasons are enums importable from `aioboinc`, which compare equal to
their number: the modes of `get_cc_status()` are a `Mode`, its suspend reasons a `SuspendReason`
and `network_status` a `NetworkStatus`; the `state` of a task is a `ResultState`, and its
`active_task_state` and `scheduler_state` an `ActiveTaskState` and a `SchedulerState`; the `pri` of
a message is a `MessagePriority`, the `sched_rpc_pending` of a project a `RpcReason`, and the
`docker_type` of the host a `DockerType`. A number the enum does not have, from a newer BOINC
client, comes as an `int`. The type depends on the element, and an
element the parser does not know comes as a `str`. What a project sends once for each resource,
such as CPU or NVIDIA, is a dict by the name of the resource, as `rsc_backoff_time`, or a list of
the names, as `no_rsc_apps`.

To control it, after `authorize()`. Each returns `True` when BOINC answers with success:

| Method | Does |
| --- | --- |
| `suspend_result(project_url, name)` | Suspends a task. `project_url` and `name` are those of a task from `get_results()` |
| `resume_result(project_url, name)` | Resumes a suspended task |
| `abort_result(project_url, name)` | Aborts a task. It cannot be undone |
| `update_project(project)` | Contacts a project now, to report the tasks done and ask for work. `project` is a `Project` from `get_project_status()` or its master URL |
| `suspend_project(project)` | Suspends a project: its tasks are not computed nor transferred |
| `resume_project(project)` | Resumes a suspended project |
| `no_new_tasks(project)` | Stops asking a project for work; the tasks it has are still computed |
| `allow_new_tasks(project)` | Asks a project for work again |
| `reset_project(project)` | Aborts the tasks of a project and deletes its files. It cannot be undone |
| `detach_project(project)` | Detaches from a project, losing its tasks. It cannot be undone |
| `detach_project_when_done(project)` | Detaches from a project once its tasks are done and reported, asking it for no more |
| `dont_detach_project_when_done(project)` | Cancels `detach_project_when_done()` |
| `retry_file_transfer(project_url, name)` | Retries an upload or a download now. `project_url` and `name` are those of a transfer from `get_file_transfers()` |
| `abort_file_transfer(project_url, name)` | Aborts an upload or a download; the tasks that need the file fail. It cannot be undone |
| `set_run_mode(mode, duration=0)` | Sets when BOINC computes: `Mode.ALWAYS`, `Mode.AUTO`, `Mode.NEVER`, or `Mode.RESTORE` to end a temporary mode. A `duration` in seconds makes it temporary |
| `set_gpu_mode(mode, duration=0)` | The same for the GPU |
| `set_network_mode(mode, duration=0)` | The same for the network |
| `network_available()` | Retries now the network communication BOINC has deferred |
| `set_language(language)` | Sets the language BOINC sends to the projects, such as `"es"` |
| `quit()` | Stops the BOINC client on the host |

Each method has a docstring with the details: `help(RPCClient.get_disk_usage)`.

## Errors

Every error is a `BOINCError`, and all of them can be imported from `aioboinc`:

| Error | Raised when | The connection |
| --- | --- | --- |
| `BOINCAuthError` | The password is wrong or missing, or the request needs `authorize()` first | Is kept, except when BOINC rejects the password |
| `BOINCCommandError` | BOINC answers the request with an error, such as `no such result` | Is kept, except in `authorize()` |
| `BOINCConnectionError` | The host cannot be reached, or the connection is lost | Is dropped |
| `BOINCTimeoutError` | The host does not answer within the timeout | Is dropped |
| `BOINCProtocolError` | What answers is not a BOINC client: its reply is not XML, is empty, or is not the one to the request, such as `<cc_status>` to `get_cc_status()` | Is dropped |

`BOINCTimeoutError` and `BOINCProtocolError` are also `BOINCConnectionError`, so catching that one
covers every lost connection. `BOINCConnectionError` is also a `ConnectionError`, and
`BOINCTimeoutError` a `TimeoutError`. `BOINCClientError` is another name for `BOINCError`, kept
from before 0.4.0.

When the connection is dropped, `connected` is `False`: call `connect()` and `authorize()` again
to go on.

## Development

```
python -m unittest discover -s tests -t .
```

The tests talk to a fake BOINC client on a local socket; no BOINC installation is needed.

To see what the tests cover, run them under [coverage.py](https://coverage.readthedocs.io/):

```
pip install coverage
coverage run -m unittest discover -s tests -t .
coverage report
```

CI fails below 95 %, and every pull request gets a comment with what it changes.

The code is linted with [ruff](https://docs.astral.sh/ruff/) and its types are checked with
[mypy](https://mypy-lang.org/). CI requires both to pass:

```
pip install ruff mypy
ruff check .
mypy
```

## License

MIT, see [LICENSE](LICENSE). Copyright of the original work remains with its author.
