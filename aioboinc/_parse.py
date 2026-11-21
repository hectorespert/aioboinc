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
    Tag.COUNT,
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
}

# An element that comes once for each of something, side by side with other elements, such as the
# OpenCL properties of the CPU for each OpenCL platform in get_host_info(). They are a list, there
# only when there is one at least.
REPEATED_TAG = {
    Tag.OPENCL_CPU_PROP,
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


def parse_project(e: ET.Element) -> "Project":
    # The lists of resources are there, empty, when BOINC sends none
    fields: dict[str, Any] = {tag: [] for tag in RESOURCE_NAMES_TAG}
    fields.update(parse_generic(e))
    return Project(**fields)


class Project:
    """
    A project the BOINC client is attached to, from get_project_status(), or the project of a task

    Its fields are attributes, such as project_name or user_total_credit; a project of a task has
    only master_url. It compares equal, and hashes the same, as its master URL, so either can look
    the other up in a set or a dict.
    """

    master_url: str

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
