"""
The numbers BOINC sends for a state or a reason, as enums

Their values are those of lib/common_defs.h in the BOINC source. The parser reads each element
named below as its enum, and as an int a value that a newer BOINC client may send and the enum does
not have yet. Being an IntEnum, a member compares equal to its number.
"""

from enum import IntEnum


class Mode(IntEnum):
    """
    When BOINC may compute, use the GPU or use the network, for set_run_mode(), set_gpu_mode()
    and set_network_mode(), and as task_mode, gpu_mode and network_mode in get_cc_status(), with
    their *_perm

    Attributes:
        ALWAYS: Always, whatever the preferences say.
        AUTO: When the preferences allow it.
        NEVER: Never.
        RESTORE: End a temporary mode early and go back to the permanent one. Without a temporary
            mode, go back to the mode before the last change. The duration is ignored.
    """

    ALWAYS = 1
    AUTO = 2
    NEVER = 3
    RESTORE = 4


class NetworkStatus(IntEnum):
    """
    Whether BOINC needs the network, as network_status in get_cc_status()
    """

    ONLINE = 0
    WANT_CONNECTION = 1
    WANT_DISCONNECT = 2
    LOOKUP_PENDING = 3


class SuspendReason(IntEnum):
    """
    Why BOINC does not compute, use the GPU or use the network, as task_suspend_reason,
    gpu_suspend_reason and network_suspend_reason in get_cc_status()

    NOT_SUSPENDED, 0, has no name in BOINC.
    """

    NOT_SUSPENDED = 0
    BATTERIES = 1
    USER_ACTIVE = 2
    USER_REQ = 4
    TIME_OF_DAY = 8
    BENCHMARKS = 16
    DISK_SIZE = 32
    CPU_THROTTLE = 64
    NO_RECENT_INPUT = 128
    INITIAL_DELAY = 256
    EXCLUSIVE_APP_RUNNING = 512
    CPU_USAGE = 1024
    NETWORK_QUOTA_EXCEEDED = 2048
    OS = 4096
    WIFI_STATE = 4097
    BATTERY_CHARGING = 4098
    BATTERY_OVERHEATED = 4099
    NO_GUI_KEEPALIVE = 4100
    PODMAN_INIT = 4101
    BATTERY_CHARGE_WAIT = 4102
    BATTERY_HEAT_WAIT = 4103


class RpcReason(IntEnum):
    """
    Why BOINC is to contact the scheduler of a project, as sched_rpc_pending in
    get_project_status()

    NONE, 0, has no name in BOINC.
    """

    NONE = 0
    USER_REQ = 1
    RESULTS_DUE = 2
    NEED_WORK = 3
    TRICKLE_UP = 4
    ACCT_MGR_REQ = 5
    INIT = 6
    PROJECT_REQ = 7


class ResultState(IntEnum):
    """
    Where a task is between its download and its upload, as state in get_results()
    """

    NEW = 0
    FILES_DOWNLOADING = 1
    FILES_DOWNLOADED = 2
    COMPUTE_ERROR = 3
    FILES_UPLOADING = 4
    FILES_UPLOADED = 5
    ABORTED = 6
    UPLOAD_FAILED = 7


class ActiveTaskState(IntEnum):
    """
    The state of the process of a task, as active_task_state in get_results()
    """

    UNINITIALIZED = 0
    EXECUTING = 1
    EXITED = 2
    WAS_SIGNALED = 3
    EXIT_UNKNOWN = 4
    ABORT_PENDING = 5
    ABORTED = 6
    COULDNT_START = 7
    QUIT_PENDING = 8
    SUSPENDED = 9
    COPY_PENDING = 10


class SchedulerState(IntEnum):
    """
    Whether BOINC runs a task, as scheduler_state in get_results()
    """

    UNINITIALIZED = 0
    PREEMPTED = 1
    SCHEDULED = 2


class MessagePriority(IntEnum):
    """
    The priority of a message of the event log, as pri in get_messages()
    """

    INFO = 1
    USER_ALERT = 2
    INTERNAL_ERROR = 3
    SCHEDULER_ALERT = 4


class DockerType(IntEnum):
    """
    Which container tool the host has, as docker_type and docker_compose_type in get_host_info()
    """

    NONE = 0
    DOCKER = 1
    PODMAN = 2
    WSLC = 3
