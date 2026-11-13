# Changelog

## 0.1.0

First release on PyPI, as `aioboinc`. It is [nielstron/pyboinc](https://github.com/nielstron/pyboinc)
at its last commit (`f8a31de`, 2022-10-16) plus:

- **Fixed** `set_run_mode()`, `set_network_mode()` and `set_gpu_mode()`. All three raised `TypeError`
  before sending anything, so none of them could ever have worked. The duration is now sent, so a
  temporary change is temporary.
- **Added** `RPCClient.close()`. The connection was never closed, which leaked a socket for every
  client created.
- Tests run against a fake BOINC client instead of needing a real one on `localhost`.
- Requires Python 3.10 or later.
