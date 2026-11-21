"""
The types of the replies, as TypedDict

A reply is still a dict, keyed by the names of the elements BOINC sends. These types say which keys
it has and the type of each, for an editor and a type checker, and change nothing at run time.

A key is NotRequired when BOINC writes it only sometimes, or did only in some versions; BOINC has
written the others since 7.8, of 2017, at the latest.
A reply may also have keys these do not list, from a newer BOINC client. A state or a reason is its
enum, or an int for a value the enum does not have yet.
"""

from datetime import datetime
from typing import Any, NotRequired, TypedDict

from ._constants import DockerType, Mode, NetworkStatus, SuspendReason


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


class WslGpu(TypedDict):
    """
    A GPU a WSL distribution sees, in the wsl of get_host_info()
    """

    name: str
    # Only when it has them
    has_cuda: NotRequired[bool]
    has_opencl: NotRequired[bool]


class WslDistro(TypedDict):
    """
    A WSL distribution of a Windows host, in the wsl of get_host_info()
    """

    distro_name: str
    os_name: str
    os_version: str
    # The number of the version of WSL it runs on, as a str: the same element is a str of the
    # version of WSL in HostInfo
    wsl_version: str
    # The version of the BOINC WSL distribution, only in that one
    distro_version: NotRequired[int]
    # Only when it is the default one
    is_default: NotRequired[bool]
    # Only when the configuration does not let BOINC use it
    disallowed: NotRequired[bool]
    libc_version: NotRequired[str]
    # Only when it has Docker or Podman
    docker_version: NotRequired[str]
    docker_type: NotRequired[DockerType | int]
    docker_compose_version: NotRequired[str]
    docker_compose_type: NotRequired[DockerType | int]
    # Only when it sees one at least
    wsl_gpu: NotRequired[list[WslGpu]]


class HostInfo(TypedDict):
    """
    The description of the host, from get_host_info()
    """

    # Seconds east of UTC of the time zone of the host
    timezone: int
    domain_name: str
    ip_addr: str
    host_cpid: str
    p_ncpus: int
    p_vendor: str
    p_model: str
    p_features: str
    # Floating point and integer operations per second of a CPU, and bytes per second of memory,
    # from the benchmarks
    p_fpops: float
    p_iops: float
    p_membw: float
    # When the benchmarks last ran, None if never
    p_calculated: datetime | None
    p_vm_extensions_disabled: bool
    # Bytes of memory, cache and swap, and of the disk
    m_nbytes: float
    m_cache: float
    m_swap: float
    d_total: float
    d_free: float
    os_name: str
    os_version: str
    n_usable_coprocs: int
    # The GPUs by the name of their resource, such as NVIDIA or ATI. Their fields depend on the
    # vendor.
    coprocs: dict[str, dict[str, Any]]
    # On Windows, with WSL: its version, whether BOINC uses the container system of WSL, wslc.exe,
    # and otherwise the distributions
    wsl_version: NotRequired[str]
    use_wslc: NotRequired[bool]
    wsl: NotRequired[list[WslDistro]]
    # Elsewhere, only when there is Docker or Podman
    docker_version: NotRequired[str]
    docker_type: NotRequired[DockerType | int]
    docker_compose_version: NotRequired[str]
    docker_compose_type: NotRequired[DockerType | int]
    # Only when known
    product_name: NotRequired[str]
    mac_address: NotRequired[str]
    virtualbox_version: NotRequired[str]
    # The OpenCL properties of the CPU, one for each OpenCL platform, only when there is one
    opencl_cpu_prop: NotRequired[list[dict[str, Any]]]
    # Before BOINC 8.2
    wsl_available: NotRequired[bool]
