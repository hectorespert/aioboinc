"""
The types of the replies, as TypedDict

A reply is still a dict, keyed by the names of the elements BOINC sends. These types say which keys
it has and the type of each, for an editor and a type checker, and change nothing at run time.

A key is NotRequired when BOINC writes it only sometimes; the others it has written since BOINC 7.2.
A reply may also have keys these do not list, from a newer BOINC client. A state or a reason is its
enum, or an int for a value the enum does not have yet.
"""

from typing import NotRequired, TypedDict

from ._constants import Mode, NetworkStatus, SuspendReason


class Version(TypedDict):
    """
    The version of the BOINC client, from exchange_versions()
    """

    major: int
    minor: int
    release: int


class CcStatus(TypedDict):
    """
    The state of the BOINC client, from get_cc_status()
    """

    network_status: NetworkStatus | int
    ams_password_error: bool
    task_suspend_reason: SuspendReason | int
    task_mode: Mode | int
    task_mode_perm: Mode | int
    # Seconds left of a temporary mode, 0 without one
    task_mode_delay: float
    gpu_suspend_reason: SuspendReason | int
    gpu_mode: Mode | int
    gpu_mode_perm: Mode | int
    gpu_mode_delay: float
    network_suspend_reason: SuspendReason | int
    network_mode: Mode | int
    network_mode_perm: Mode | int
    network_mode_delay: float
    disallow_attach: bool
    simple_gui_only: bool
    max_event_log_lines: int
    # Only when an update asks the BOINC Manager to quit
    manager_must_quit: NotRequired[bool]


class ProjectDiskUsage(TypedDict):
    """
    The disk space a project uses, in get_disk_usage()
    """

    master_url: str
    # Bytes
    disk_usage: float


class DiskUsage(TypedDict):
    """
    The disk space BOINC and each project use, in bytes, from get_disk_usage()
    """

    project: list[ProjectDiskUsage]
    d_total: float
    d_free: float
    d_boinc: float
    d_allowed: float
