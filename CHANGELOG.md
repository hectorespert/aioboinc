# Changelog

## Unreleased

- **Fixed** requests made at once on the same client, for example with `asyncio.gather()`, failing
  with `RuntimeError: readuntil() called while another coroutine is already waiting`. They now wait
  for their turn, and `authorize()` keeps its two steps together so no request takes their replies.
- **Added** a timeout, 30 seconds by default, to connect and to get each reply. Past it,
  `TimeoutError` is raised instead of waiting forever. Set it with `init_rpc_client(..., timeout=)`,
  or turn it off with `timeout=None`.
- **Fixed** a request that times out, is cancelled or fails before its reply arrives leaving that
  reply to be read by the next request as its own. The connection is now dropped instead, and
  `connected` becomes `False`: call `connect()` and `authorize()` again to go on.
- **Changed** `RPCClient.connected` to a read-only property that tells whether there is a
  connection. It stayed `True` after the connection was lost, so `connect()` did not open a new one,
  including when the BOINC client had hung up or the connection had been reset.

## 0.2.0

- **Fixed** flags that are `0` in the reply, such as `p_vm_extensions_disabled` or `have_opencl`,
  being read as `True`. Every flag was `True`, whatever its value.
- **Fixed** `sched_rpc_pending`, `send_time_stats_log` and `send_job_log` being read as flags. They
  are numbers: `sched_rpc_pending` is the reason a scheduler request is pending.
- **Fixed** an empty text, such as `team_name`, `ip_addr` or the `project` of a message from the client
  itself, being read as `True`. It is now `""`. An empty element is still `True` when it is one of
  the flags the BOINC client sends as `<flag/>`, such as `report_immediately` or
  `suspended_via_gui`.
- **Changed** an empty list, such as `get_results()` with no tasks or `get_file_transfers()` with no
  transfers, to be `[]`. It was the string `"\n"`, or `""` when the client sent it as `<results/>`.
  Code that checks for `"\n"` or `isinstance(..., list)` before using the list no longer needs to.

## 0.1.0

First release on PyPI, as `aioboinc`. It is [nielstron/pyboinc](https://github.com/nielstron/pyboinc)
at its last commit (`f8a31de`, 2022-10-16) plus:

- **Renamed** the package from `pyboinc` to `aioboinc`, to match the name it is installed by.
  Code written against the original needs its imports changed from `pyboinc` to `aioboinc`.
- **Fixed** `set_run_mode()`, `set_network_mode()` and `set_gpu_mode()`. All three raised `TypeError`
  before sending anything, so none of them could ever have worked. The duration is now sent, so a
  temporary change is temporary.
- **Fixed** a reply that does not come from a BOINC client going unnoticed when Python runs with
  `-O`, because the check was an `assert`.
- **Fixed** `Project` not being usable in a set or as a dictionary key.
- **Added** `RPCClient.close()`. The connection was never closed, which leaked a socket for every
  client created.
- Tests run against a fake BOINC client instead of needing a real one on `localhost`, and cover
  every request the client can make.
- Requires Python 3.10 or later.
