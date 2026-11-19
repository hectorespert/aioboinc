# Changelog

## Unreleased

- **Fixed** flags that are `0` in the reply, such as `p_vm_extensions_disabled` or `have_opencl`,
  being read as `True`. Every flag was `True`, whatever its value.
- **Fixed** `sched_rpc_pending`, `send_time_stats_log` and `send_job_log` being read as flags. They
  are numbers: `sched_rpc_pending` is the reason a scheduler request is pending.
- **Fixed** an empty text, such as `team_name`, `ip_addr` or the `project` of a message from the client
  itself, being read as `True`. It is now `""`. An empty element is still `True` when it is one of
  the flags the BOINC client sends as `<flag/>`, such as `report_immediately` or
  `suspended_via_gui`.

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
