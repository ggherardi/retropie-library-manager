"""Only application code runs here. Archive members are data, never commands."""

import ctypes
import json
import os
import sys
import time
from pathlib import Path

MEMORY_LIMIT = 1024**3
CPU_SECONDS = 900


def windows_job(pid):
    """The parent owns this handle: its death also terminates the decoder."""
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_int64),
            ("job_time", ctypes.c_int64),
            ("flags", wintypes.DWORD),
            ("minimum", ctypes.c_size_t),
            ("maximum", ctypes.c_size_t),
            ("processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", ctypes.c_uint64 * 6),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = Extended()
    info.basic.flags = 0x2000 | 0x100 | 0x200 | 0x8 | 0x2
    info.basic.processes = 3  # venv launcher, Python interpreter and installed 7-Zip decoder
    info.basic.process_time = CPU_SECONDS * 10_000_000
    info.process_memory = info.job_memory = MEMORY_LIMIT
    process = None
    try:
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        process = kernel.OpenProcess(0x100 | 0x1, False, pid)  # SET_QUOTA | TERMINATE
        if not process or not kernel.AssignProcessToJobObject(handle, process):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    finally:
        if process:
            kernel.CloseHandle(process)
    return lambda: kernel.CloseHandle(handle)


def main(job):
    result = job / "result.json"
    try:
        # Windows parent attaches the resource-limited Job Object before this handshake.
        deadline = time.monotonic() + 30
        while not (job / "go").is_file():
            if time.monotonic() > deadline:
                raise ValueError("Worker non autorizzato dal processo principale")
            time.sleep(0.05)
        if sys.platform != "win32":
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
            resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
        request = json.loads((job / "request.json").read_text(encoding="utf8"))
        if sys.platform.startswith("linux"):
            import signal

            ctypes.CDLL(None).prctl(1, signal.SIGKILL)
            if os.getppid() != request["parent_pid"]:
                raise ValueError("Processo principale terminato")
        # Import decompression libraries only after limits have been applied.
        from backend import archive_import as module

        for name, value in request["limits"].items():
            setattr(module, name, value)
        if request["operation"] == "inventory":
            output = module._inventory(Path(request["path"]))
        elif request["operation"] == "hashes":
            output = module.hash_members(Path(request["path"]))
        elif request["operation"] == "arcade":
            from backend.archive_repack import repack

            output = repack(Path(request["data"]), request["archives"])
        else:
            budget = module.Budget(lambda: None)
            budget.bytes, budget.members = request["bytes"], request["members"]
            prepared, report = module.ArchiveStore(Path(request["data"]))._prepare(
                Path(request["path"]), request["entries"], budget, request["depth"], job / "work-data"
            )
            output = {
                "prepared": str(prepared),
                "report": report,
                "bytes": budget.bytes,
                "members": budget.members,
            }
        result.write_text(json.dumps({"output": output}), encoding="utf8")
    except BaseException as exc:
        result.write_text(json.dumps({"error": type(exc).__name__ + ": " + str(exc)[:1800]}), encoding="utf8")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
