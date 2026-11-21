from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from enum import IntEnum
from typing import Any
from xml.etree import ElementTree as ET

from ._constants import (
    ActiveTaskState,
    DockerType,
    MessagePriority,
    Mode,
    NetworkStatus,
    ResultState,
    RpcReason,
    SchedulerState,
    SuspendReason,
)
from ._tag import Tag

INTEGER_TAG = {
    Tag.MAJOR,
    Tag.MINOR,
    Tag.RELEASE,
    Tag.MAX_EVENT_LOG_LINES,
    Tag.SEQNO,
    Tag.RPC_SEQNO,
    Tag.USERID,
    Tag.TEAMID,
    Tag.HOSTID,
    Tag.NRPC_FAILURES,
    Tag.MASTER_FETCH_FAILURES,
    Tag.NJOBS_SUCCESS,
    Tag.NJOBS_ERROR,
    Tag.VERSION_NUM,
    Tag.EXIT_STATUS,
    Tag.APP_VERSION_NUM,
    Tag.SLOT,
    Tag.PID,
    Tag.P_NCPUS,
    Tag.VENDOR_ID,
    Tag.HALF_FP_CONFIG,
    Tag.SINGLE_FP_CONFIG,
    Tag.DOUBLE_FP_CONFIG,
    Tag.EXECUTION_CAPABILITIES,
    Tag.GLOBAL_MEM_SIZE,
    Tag.LOCAL_MEM_SIZE,
    Tag.MAX_CLOCK_FREQUENCY,
    Tag.MAX_COMPUTE_UNITS,
    Tag.NV_COMPUTE_CAPABILITY_MAJOR,
    Tag.NV_COMPUTE_CAPABILITY_MINOR,
    Tag.AMD_SIMD_INSTRUCTION_WIDTH,
    Tag.AMD_SIMD_PER_COMPUTE_UNIT,
    Tag.AMD_SIMD_WIDTH,
    Tag.NUM_RETRIES,
    Tag.SEND_TIME_STATS_LOG,
    Tag.SEND_JOB_LOG,
    Tag.TIMEZONE,
    Tag.N_USABLE_COPROCS,
    # The PCI address and properties of an NVIDIA GPU, in coprocs
    Tag.BUS_ID,
    Tag.DEVICE_ID,
    Tag.DOMAIN_ID,
    Tag.CUDAVERSION,
    Tag.DRVVERSION,
    Tag.REGSPERBLOCK,
    Tag.WARPSIZE,
    Tag.MAXTHREADSPERBLOCK,
    Tag.CLOCKRATE,
    Tag.DEVICEOVERLAP,
    Tag.MULTIPROCESSORCOUNT,
    # The properties of an AMD GPU, in coprocs
    Tag.CACHEDREMOTERAM,
    Tag.ENGINECLOCK,
    Tag.LOCALRAM,
    Tag.MAXRESOURCE1DWIDTH,
    Tag.MAXRESOURCE2DHEIGHT,
    Tag.MAXRESOURCE2DWIDTH,
    Tag.MEMORYCLOCK,
    Tag.NUMBEROFSIMD,
    Tag.PITCH_ALIGNMENT,
    Tag.SURFACE_ALIGNMENT,
    Tag.TARGET,
    Tag.UNCACHEDREMOTERAM,
    Tag.WAVEFRONTSIZE,
    # And of an Apple GPU
    Tag.NCORES,
    Tag.METAL_SUPPORT,
    # The state of a file transfer, as a number
    Tag.STATUS,
    # The version of the BOINC WSL distribution, in the wsl of get_host_info()
    Tag.DISTRO_VERSION,
    # In get_state()
    Tag.CORE_CLIENT_MAJOR_VERSION,
    Tag.CORE_CLIENT_MINOR_VERSION,
    Tag.CORE_CLIENT_RELEASE,
    # Of a keyword of a workunit
    Tag.PARENT,
    Tag.LEVEL,
    # Of the global preferences
    Tag.DAILY_XFER_PERIOD_DAYS,
    Tag.MAX_CPUS,
    Tag.DAY_OF_WEEK,
}

FLOAT_TAG = {
    Tag.TASK_MODE_DELAY,
    Tag.GPU_MODE_DELAY,
    Tag.NETWORK_MODE_DELAY,
    Tag.DISK_USAGE,
    Tag.D_TOTAL,
    Tag.D_FREE,
    Tag.D_BOINC,
    Tag.D_ALLOWED,
    Tag.USER_TOTAL_CREDIT,
    Tag.USER_EXPAVG_CREDIT,
    Tag.HOST_TOTAL_CREDIT,
    Tag.HOST_EXPAVG_CREDIT,
    Tag.REC,
    Tag.RESOURCE_SHARE,
    Tag.DESIRED_DISK_USAGE,
    Tag.DURATION_CORRECTION_FACTOR,
    Tag.FRACTION_DONE,
    Tag.SWAP_SIZE,
    Tag.WORKING_SET_SIZE,
    Tag.WORKING_SET_SIZE_SMOOTHED,
    Tag.PAGE_FAULT_RATE,
    Tag.BYTES_SENT,
    Tag.BYTES_RECEIVED,
    Tag.PROGRESS_RATE,
    Tag.P_FPOPS,
    Tag.P_IOPS,
    Tag.P_MEMBW,
    Tag.M_NBYTES,
    Tag.M_CACHE,
    Tag.M_SWAP,
    Tag.PEAK_FLOPS,
    Tag.XFER_SPEED,
    Tag.SCHED_PRIORITY,
    Tag.AVAILABLE_RAM,
    Tag.TOTALGLOBALMEM,
    Tag.SHAREDMEMPERBLOCK,
    Tag.MEMPITCH,
    Tag.TOTALCONSTMEM,
    Tag.TEXTUREALIGNMENT,
    Tag.DISK_SHARE,
    Tag.AMS_RESOURCE_SHARE_NEW,
    Tag.VIRTUAL_SIZE,
    # Bytes of a file transfer
    Tag.NBYTES,
    Tag.MAX_NBYTES,
    Tag.BYTES_XFERRED,
    Tag.LAST_BYTES_XFERRED,
    Tag.FILE_OFFSET,
    # Bytes sent and received on a day of the transfer history
    Tag.UP,
    Tag.DOWN,
    # The CPUs and the FLOPS an app version or a workunit uses, and the bytes of GPU memory
    Tag.AVG_NCPUS,
    Tag.FLOPS,
    Tag.GPU_RAM,
    # The estimated and the most operations, memory and disk of a workunit
    Tag.RSC_FPOPS_EST,
    Tag.RSC_FPOPS_BOUND,
    Tag.RSC_MEMORY_BOUND,
    Tag.RSC_DISK_BOUND,
    # The most and the average bytes per second of the network, in net_stats of get_state()
    Tag.BWUP,
    Tag.AVG_UP,
    Tag.BWDOWN,
    Tag.AVG_DOWN,
    # In time_stats of get_state(): fractions of the time, and durations in seconds
    Tag.ON_FRAC,
    Tag.CONNECTED_FRAC,
    Tag.CPU_AND_NETWORK_AVAILABLE_FRAC,
    Tag.ACTIVE_FRAC,
    Tag.GPU_ACTIVE_FRAC,
    Tag.TOTAL_DURATION,
    Tag.TOTAL_ACTIVE_DURATION,
    Tag.TOTAL_GPU_ACTIVE_DURATION,
    Tag.PREVIOUS_UPTIME,
    Tag.SESSION_ACTIVE_DURATION,
    Tag.SESSION_GPU_ACTIVE_DURATION,
    # Of the global preferences
    Tag.BATTERY_CHARGE_MIN_PCT,
    Tag.BATTERY_MAX_TEMPERATURE,
    Tag.SUSPEND_IF_NO_RECENT_INPUT,
    Tag.SUSPEND_CPU_USAGE,
    Tag.START_HOUR,
    Tag.END_HOUR,
    Tag.NET_START_HOUR,
    Tag.NET_END_HOUR,
    Tag.WORK_BUF_MIN_DAYS,
    Tag.WORK_BUF_ADDITIONAL_DAYS,
    Tag.MAX_NCPUS_PCT,
    Tag.NIU_MAX_NCPUS_PCT,
    Tag.NIU_CPU_USAGE_LIMIT,
    Tag.NIU_SUSPEND_CPU_USAGE,
    Tag.CPU_SCHEDULING_PERIOD_MINUTES,
    Tag.DISK_INTERVAL,
    Tag.DISK_MAX_USED_GB,
    Tag.DISK_MAX_USED_PCT,
    Tag.DISK_MIN_FREE_GB,
    Tag.VM_MAX_USED_PCT,
    Tag.RAM_MAX_USED_BUSY_PCT,
    Tag.RAM_MAX_USED_IDLE_PCT,
    Tag.IDLE_TIME_TO_RUN,
    Tag.MAX_BYTES_SEC_UP,
    Tag.MAX_BYTES_SEC_DOWN,
    Tag.CPU_USAGE_LIMIT,
    Tag.DAILY_XFER_LIMIT_MB,
    # Seconds left of a backoff, sent only while there is one
    Tag.PROJECT_BACKOFF,
    Tag.DOWNLOAD_BACKOFF,
    Tag.UPLOAD_BACKOFF,
}

BOOL_TAG = {
    Tag.DISALLOW_ATTACH,
    Tag.SIMPLE_GUI_ONLY,
    Tag.P_VM_EXTENSIONS_DISABLED,
    Tag.HAVE_OPENCL,
    Tag.AVAILABLE,
    Tag.ENDIAN_LITTLE,
    Tag.IS_UPLOAD,
    Tag.HAVE_CUDA,
    Tag.WSL_AVAILABLE,
    Tag.AMS_PASSWORD_ERROR,
    Tag.MANAGER_MUST_QUIT,
    # Of an AMD and an Apple GPU, in coprocs. doublePrecision is 0 or 1 too, a CALboolean.
    Tag.HAVE_CAL,
    Tag.HAVE_METAL,
    Tag.DOUBLEPRECISION,
    # In replies this client does not ask for yet: get_state, get_notices and the proxy settings
    Tag.EXECUTING_AS_DAEMON,
    Tag.HAVE_ATI,
    # Of the global preferences, in get_state()
    Tag.RUN_ON_BATTERIES,
    Tag.RUN_IF_USER_ACTIVE,
    Tag.RUN_GPU_IF_USER_ACTIVE,
    Tag.LEAVE_APPS_IN_MEMORY,
    Tag.CONFIRM_BEFORE_CONNECTING,
    Tag.HANGUP_IF_DIALED,
    Tag.DONT_VERIFY_IMAGES,
    Tag.OVERRIDE_FILE_PRESENT,
    Tag.NETWORK_WIFI_ONLY,
    Tag.IS_PRIVATE,
    Tag.NO_AUTODETECT,
    Tag.SOCKS5_REMOTE_DNS,
    # The BOINC client sends these as an empty element when they are set, and leaves them out when
    # they are not.
    Tag.AMDRT_DETECTED,
    Tag.ANONYMOUS_PLATFORM,
    Tag.ATIRT_DETECTED,
    Tag.ATTACHED_VIA_ACCT_MGR,
    Tag.COOKIE_REQUIRED,
    Tag.COPROC_MISSING,
    Tag.COPY_FILE,
    Tag.DETACH_WHEN_DONE,
    Tag.DISALLOWED,
    Tag.DONT_REQUEST_MORE_WORK,
    Tag.DONT_THROTTLE,
    Tag.DONT_USE_DCF,
    Tag.DOWNLOAD_GZIPPED,
    Tag.EDF_SCHEDULED,
    Tag.ENDED,
    Tag.EXECUTABLE,
    Tag.GOT_SERVER_ACK,
    Tag.GZIP_WHEN_DONE,
    Tag.HAS_CUDA,
    Tag.HAS_OPENCL,
    Tag.HAVE_CREDENTIALS,
    Tag.IS_DEFAULT,
    Tag.IS_USER_FILE,
    Tag.IS_WRAPPER,
    Tag.MAIN_PROGRAM,
    Tag.MASTER_URL_FETCH_PENDING,
    Tag.NEEDS_NETWORK,
    Tag.NEEDS_SHMEM,
    Tag.NETWORK_WAIT,
    Tag.NON_CPU_INTENSIVE,
    Tag.OPTIONAL,
    Tag.PROJECT_SUSPENDED_VIA_GUI,
    Tag.READY_TO_REPORT,
    Tag.REPORT_IMMEDIATELY,
    Tag.SCHEDULER_RPC_IN_PROGRESS,
    Tag.SCHEDULER_WAIT,
    Tag.SEND_FULL_WORKLOAD,
    Tag.SIGNATURE_REQUIRED,
    Tag.STICKY,
    Tag.STRICT_MEMORY_BOUND,
    Tag.SUSPENDED_VIA_GUI,
    Tag.SWAP_TOO_LARGE,
    Tag.TOO_LARGE,
    Tag.TRICKLE_UP_PENDING,
    Tag.UPLOADED,
    Tag.USE_HTTP_AUTH,
    Tag.USE_HTTP_PROXY,
    Tag.USE_SOCKS_PROXY,
    Tag.USE_SYMLINKS,
    Tag.USE_WSLC,
    Tag.WANT_NETWORK,
}

LIST_TAG = {
    Tag.MSGS,
    Tag.RESULTS,
    Tag.PROJECTS,
    Tag.GUI_URLS,
    Tag.FILE_TRANSFERS,
    # The WSL distributions of a Windows host, in get_host_info()
    Tag.WSL,
    # The keywords of a workunit, in get_state()
    Tag.JOB_KEYWORDS,
}

# An element that comes once for each of something, side by side with other elements, such as the
# OpenCL properties of the CPU for each OpenCL platform in get_host_info(). They are a list, there
# only when there is one at least.
REPEATED_TAG = {
    Tag.OPENCL_CPU_PROP,
    # The GPUs a WSL distribution sees, in the wsl of get_host_info()
    Tag.WSL_GPU,
    # The files of an app version or a workunit, and the days of the week with their own hours in
    # the global preferences, in get_state()
    Tag.FILE_REF,
    Tag.DAY_PREFS,
}

TIMEDELTA_TAG = {
    Tag.ELAPSED_TIME,
    Tag.FINAL_CPU_TIME,
    # Of a task in get_old_results()
    Tag.CPU_TIME,
    Tag.FINAL_ELAPSED_TIME,
    Tag.ESTIMATED_CPU_TIME_REMAINING,
    Tag.CHECKPOINT_CPU_TIME,
    Tag.CURRENT_CPU_TIME,
    Tag.TIME_SO_FAR,
    Tag.ESTIMATED_XFER_TIME_REMAINING,
}

TIME_TAG = {
    Tag.TIME,
    Tag.CPID_TIME,
    Tag.USER_CREATE_TIME,
    Tag.HOST_CREATE_TIME,
    Tag.MIN_RPC_TIME,
    Tag.NEXT_RPC_TIME,
    Tag.REC_TIME,
    Tag.LAST_RPC_TIME,
    Tag.REPORT_DEADLINE,
    Tag.RECEIVED_TIME,
    Tag.FIRST_REQUEST_TIME,
    Tag.NEXT_REQUEST_TIME,
    Tag.PROJECT_FILES_DOWNLOADED_TIME,
    # In get_state(): when the averages of the network were last updated, when the BOINC client
    # started, this time and ever, the time of the reply, and when the preferences changed
    Tag.AVG_TIME_UP,
    Tag.AVG_TIME_DOWN,
    Tag.CLIENT_START_TIME,
    Tag.TOTAL_START_TIME,
    Tag.NOW,
    Tag.MOD_TIME,
    Tag.COMPLETED_TIME,
    # When the CPU benchmarks last ran, in get_host_info()
    Tag.P_CALCULATED,
    # The midnight in UTC that begins a day of the statistics
    Tag.DAY,
    # Of a notice
    Tag.CREATE_TIME,
    Tag.ARRIVAL_TIME,
}

# The enum of each element that is a state or a reason
ENUM_TAG: dict[str, type[IntEnum]] = {
    Tag.NETWORK_STATUS: NetworkStatus,
    Tag.TASK_MODE: Mode,
    Tag.TASK_MODE_PERM: Mode,
    Tag.GPU_MODE: Mode,
    Tag.GPU_MODE_PERM: Mode,
    Tag.NETWORK_MODE: Mode,
    Tag.NETWORK_MODE_PERM: Mode,
    Tag.TASK_SUSPEND_REASON: SuspendReason,
    Tag.GPU_SUSPEND_REASON: SuspendReason,
    Tag.NETWORK_SUSPEND_REASON: SuspendReason,
    Tag.SCHED_RPC_PENDING: RpcReason,
    Tag.STATE: ResultState,
    Tag.ACTIVE_TASK_STATE: ActiveTaskState,
    Tag.SCHEDULER_STATE: SchedulerState,
    Tag.PRI: MessagePriority,
    Tag.DOCKER_TYPE: DockerType,
    Tag.DOCKER_COMPOSE_TYPE: DockerType,
}

TAG_PARSER: dict[str, Callable[[str], Any]] = {
    Tag.BODY: lambda x: x.replace("<![CDATA[", "").replace("]]>", "").strip(),
    # Of a notice, which BOINC writes between newlines
    Tag.DESCRIPTION: str.strip,
    # Of a workunit, which BOINC writes between newlines too
    Tag.COMMAND_LINE: str.strip,
    # A number of GPUs: whole in coprocs of get_host_info(), and a fraction in what an app version
    # or a workunit uses in get_state()
    Tag.COUNT: lambda x: int(x) if x.lstrip("-").isdigit() else float(x),
    # A day of the transfer history, as the number of days since 1970-01-01 in the time zone of the
    # host BOINC runs on
    Tag.WHEN: lambda x: date(1970, 1, 1) + timedelta(days=int(x)),
    Tag.PROJECT_URL: lambda x: Project(master_url=x)
}
INTEGER_TAG_PARSER = int
FLOAT_TAG_PARSER = float


def TIME_TAG_PARSER(x: str) -> datetime | None:
    # BOINC sends a time as seconds since the epoch, which name an instant whatever the time zone.
    # Without a tzinfo it would be read in the time zone of the host running this client, which
    # need not be the one of the host running BOINC, and could not be compared with an aware time.
    seconds = float(x)
    # BOINC sends 0 for a time that has not been set, such as the next_rpc_time of a project that
    # has not asked for one. It is not 1970.
    if seconds == 0:
        return None
    return datetime.fromtimestamp(seconds, UTC)


def TIMEDELTA_TAG_PARSER(x: str) -> timedelta:
    return timedelta(seconds=float(x))


def ENUM_TAG_PARSER(enum: type[IntEnum]) -> Callable[[str], int]:
    def parse(x: str) -> int:
        value = int(x)
        try:
            return enum(value)
        except ValueError:
            # A value the enum does not have, such as a new reason in a newer BOINC client, is still
            # a number, not an error
            return value

    return parse


def BOOL_TAG_PARSER(x: str) -> bool:
    # BOINC writes a flag as 0 or 1, and reads any other number as true too. bool() would make
    # every non-empty string true, "0" included.
    return int(x) != 0


# A project has one of each per resource, such as CPU or NVIDIA, with its name and value. They are
# a dict of the value by the name of the resource: the time until which the project is backed off,
# or None, and the seconds it backs off for.
BY_RESOURCE_TAG: dict[str, Callable[[str], Any]] = {
    Tag.RSC_BACKOFF_TIME: TIME_TAG_PARSER,
    Tag.RSC_BACKOFF_INTERVAL: FLOAT_TAG_PARSER,
}

# A project has one of each per resource it applies to, with the name of the resource, and none
# when it applies to none. They are a list of the names.
RESOURCE_NAMES_TAG = {
    Tag.NO_RSC_AMS,
    Tag.NO_RSC_APPS,
    Tag.NO_RSC_CONFIG,
    Tag.NO_RSC_PREF,
}

# The name of the resource of each kind of GPU, as BOINC names the resources elsewhere, such as in
# rsc_backoff_time (proc_type_name_xml() in lib/coproc.cpp)
GPU_RESOURCE = {
    Tag.COPROC_CUDA: "NVIDIA",
    Tag.COPROC_ATI: "ATI",
    Tag.COPROC_INTEL_GPU: "intel_gpu",
    Tag.COPROC_APPLE_GPU: "apple_gpu",
}

_PARSERS: list[tuple[Callable[[str], Any], set[str]]] = [
    (INTEGER_TAG_PARSER, INTEGER_TAG),
    (FLOAT_TAG_PARSER, FLOAT_TAG),
    (TIME_TAG_PARSER, TIME_TAG),
    (TIMEDELTA_TAG_PARSER, TIMEDELTA_TAG),
    (BOOL_TAG_PARSER, BOOL_TAG),
]
for parser_func, tags in _PARSERS:
    TAG_PARSER.update((tag, parser_func) for tag in tags)
TAG_PARSER.update((tag, ENUM_TAG_PARSER(enum)) for tag, enum in ENUM_TAG.items())


def parse_coprocs(e: ET.Element) -> dict[str, Any]:
    # BOINC writes one element for each kind of GPU, with how many there are in count, so a dict by
    # the name of the resource keeps them all, and says which kind each is. Any other coprocessor is
    # a <coproc> with the name of its resource in <type>.
    return {GPU_RESOURCE.get(c.tag) or c.findtext(Tag.TYPE) or c.tag: parse_generic(c) for c in e}


def parse_generic(e: ET.Element):
    if e.tag == Tag.COPROCS:
        return parse_coprocs(e)
    if e.tag in LIST_TAG:
        # Checked first, so that an empty list is [], whether it comes as <results/> or with the
        # newline between its tags.
        return [parse_generic(cc) for cc in e]
    elif len(e) > 0:
        # recurse on elements with children
        res: dict[str, Any] = {}
        for c in e:
            if c.tag in BY_RESOURCE_TAG:
                value = BY_RESOURCE_TAG[c.tag](c.findtext(Tag.VALUE, "0"))
                res.setdefault(c.tag, {})[c.findtext(Tag.NAME, "")] = value
            elif c.tag in RESOURCE_NAMES_TAG:
                res.setdefault(c.tag, []).append(c.text or "")
            elif c.tag in REPEATED_TAG:
                res.setdefault(c.tag, []).append(parse_generic(c))
            else:
                res[c.tag] = parse_generic(c)
        return res
    elif e.text is not None:
        # set parsed value if available
        return TAG_PARSER.get(e.tag, str)(e.text)
    else:
        # ElementTree reads <tag/> and <tag></tag> the same, so whether an empty element is a flag
        # that is set or a text that is empty depends on the tag.
        return True if e.tag in BOOL_TAG else ""


# The flags BOINC writes in a task, and in its active task, only when they are set
RESULT_FLAG_TAG = (
    Tag.GOT_SERVER_ACK,
    Tag.READY_TO_REPORT,
    Tag.SUSPENDED_VIA_GUI,
    Tag.PROJECT_SUSPENDED_VIA_GUI,
    Tag.REPORT_IMMEDIATELY,
    Tag.EDF_SCHEDULED,
    Tag.COPROC_MISSING,
    Tag.SCHEDULER_WAIT,
    Tag.NETWORK_WAIT,
)
ACTIVE_TASK_FLAG_TAG = (
    Tag.TOO_LARGE,
    Tag.SWAP_TOO_LARGE,
    Tag.NEEDS_SHMEM,
    Tag.WANT_NETWORK,
)


def with_flags(reply: dict[str, Any], flags: tuple[str, ...]) -> Any:
    # The flags BOINC sends only when they are set are there, False, when it does not
    return dict.fromkeys(flags, False) | reply


def parse_result(e: ET.Element) -> dict[str, Any]:
    # The flags are there, False, when BOINC does not send them
    result: dict[str, Any] = dict.fromkeys(RESULT_FLAG_TAG, False)
    result.update(parse_generic(e))
    if Tag.ACTIVE_TASK in result:
        active_task: dict[str, Any] = dict.fromkeys(ACTIVE_TASK_FLAG_TAG, False)
        active_task.update(result[Tag.ACTIVE_TASK])
        result[Tag.ACTIVE_TASK] = active_task
    return result


# The flags of what get_state() has that BOINC writes only when they are set
APP_VERSION_FLAG_TAG = (Tag.DONT_THROTTLE, Tag.IS_WRAPPER, Tag.NEEDS_NETWORK)
FILE_REF_FLAG_TAG = (Tag.MAIN_PROGRAM, Tag.COPY_FILE, Tag.OPTIONAL)
STATE_FLAG_TAG = (Tag.HAVE_CUDA, Tag.HAVE_ATI)

# The elements of get_state() that come once for each project, app, app version, workunit, task
# and platform, and the list each goes in
STATE_LIST_TAG = {
    Tag.PROJECT: "projects",
    Tag.APP: "apps",
    Tag.APP_VERSION: "app_versions",
    Tag.WORKUNIT: "workunits",
    Tag.RESULT: "results",
    Tag.PLATFORM: "platforms",
}


def parse_state(e: ET.Element) -> dict[str, Any]:
    state: dict[str, Any] = dict.fromkeys(STATE_FLAG_TAG, False)
    state.update((key, []) for key in STATE_LIST_TAG.values())
    project_url = None
    for c in e:
        if c.tag == Tag.PROJECT:
            project = parse_project(c)
            # The apps, app versions and workunits after a project are its own, and do not say so
            project_url = Project(master_url=project.master_url)
            item: Any = project
        elif c.tag == Tag.RESULT:
            item = parse_result(c)
        elif c.tag in (Tag.APP, Tag.APP_VERSION, Tag.WORKUNIT):
            item = {Tag.PROJECT_URL: project_url} | parse_generic(c)
            if c.tag == Tag.APP_VERSION:
                item = with_flags(item, APP_VERSION_FLAG_TAG)
            for i, file_ref in enumerate(item.get(Tag.FILE_REF, [])):
                item[Tag.FILE_REF][i] = with_flags(file_ref, FILE_REF_FLAG_TAG)
        elif c.tag in STATE_LIST_TAG:
            item = parse_generic(c)
        else:
            state[c.tag] = parse_generic(c)
            continue
        state[STATE_LIST_TAG[c.tag]].append(item)
    return state


def parse_project(e: ET.Element) -> "Project":
    # The lists of resources, and of links, are there, empty, when BOINC sends none
    fields: dict[str, Any] = {tag: [] for tag in RESOURCE_NAMES_TAG}
    fields[Tag.GUI_URLS] = []
    fields.update(parse_generic(e))
    return Project(**fields)


class Project:
    """
    A project the BOINC client is attached to, from get_project_status(), or the project of a task

    Its fields are attributes, such as project_name or user_total_credit; a project of a task has
    only master_url. It compares equal, and hashes the same, as its master URL, so either can look
    the other up in a set or a dict.

    A flag BOINC sends only when it is set is False when it does not, and a value it sends only
    sometimes is None when it does not. On a project of a task they are those defaults too.
    """

    master_url: str
    project_name: str
    symstore: str
    user_name: str
    team_name: str
    host_venue: str
    email_hash: str
    cross_project_id: str
    external_cpid: str
    cpid_time: datetime | None
    user_total_credit: float
    user_expavg_credit: float
    user_create_time: datetime | None
    rpc_seqno: int
    userid: int
    teamid: int
    hostid: int
    host_total_credit: float
    host_expavg_credit: float
    host_create_time: datetime | None
    nrpc_failures: int
    master_fetch_failures: int
    # Until when the project is backed off, and when it asked to be contacted next
    min_rpc_time: datetime | None
    next_rpc_time: datetime | None
    rec: float
    rec_time: datetime | None
    resource_share: float
    desired_disk_usage: float
    duration_correction_factor: float
    sched_rpc_pending: RpcReason | int
    send_time_stats_log: int
    send_job_log: int
    njobs_success: int
    njobs_error: int
    elapsed_time: timedelta
    last_rpc_time: datetime | None
    # By the name of the resource, such as CPU or NVIDIA
    rsc_backoff_time: dict[str, datetime | None]
    rsc_backoff_interval: dict[str, float]
    # The resources each applies to, [] when none
    no_rsc_ams: list[str]
    no_rsc_apps: list[str]
    no_rsc_config: list[str]
    no_rsc_pref: list[str]
    # The links of the project to show, with name, description and url, [] when none
    gui_urls: list[dict[str, Any]]
    sched_priority: float
    project_files_downloaded_time: datetime | None
    project_dir: str

    # Bytes of the disk it uses, and may use; since BOINC 7.16.8
    disk_usage: float | None = None
    disk_share: float | None = None
    # Seconds left of the backoff of its downloads and uploads, while there is one
    download_backoff: float | None = None
    upload_backoff: float | None = None
    # The resource share an account manager has set
    ams_resource_share_new: float | None = None
    # The venue of the host, when it has one
    venue: str | None = None

    anonymous_platform: bool = False
    master_url_fetch_pending: bool = False
    trickle_up_pending: bool = False
    send_full_workload: bool = False
    dont_use_dcf: bool = False
    non_cpu_intensive: bool = False
    strict_memory_bound: bool = False
    suspended_via_gui: bool = False
    dont_request_more_work: bool = False
    detach_when_done: bool = False
    ended: bool = False
    attached_via_acct_mgr: bool = False
    scheduler_rpc_in_progress: bool = False
    use_symlinks: bool = False

    def __init__(self, *args, **kwargs):
        self.__dict__ = kwargs

    def __eq__(self, other):
        return str(other) == str(self)

    def __hash__(self):
        # Defining __eq__ alone makes a class unhashable. A project equals its URL, so it hashes
        # like its URL, and either can look the other up in a set or a dict.
        return hash(str(self))

    def __repr__(self):
        return f"<Project {self.master_url}, {self.__dict__}>"

    def __str__(self):
        return self.master_url
