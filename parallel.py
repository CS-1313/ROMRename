import os
import sys
import pickle
import signal
import ctypes
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from engine import MatchEngine

RAM_BUDGET_FRACTION = 0.5
WORKER_BASE_BYTES = 40 * 1024 * 1024
WORKER_STATE_EXPANSION = 4
WINDOWS_MAX_WORKERS = 61

_worker_engine = None


def logical_cpus():
    if hasattr(os, "sched_getaffinity"):
        try:
            return max(1, len(os.sched_getaffinity(0)))
        except Exception:
            pass
    return max(1, os.cpu_count() or 1)


def ram_info():
    try:
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullTotalPhys, stat.ullAvailPhys
        if os.path.exists("/proc/meminfo"):
            vals = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        vals[parts[0].rstrip(":")] = int(parts[1]) * 1024
            total = vals.get("MemTotal")
            avail = vals.get("MemAvailable", vals.get("MemFree"))
            if total:
                return total, avail
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return total, total // 2
    except Exception:
        return None, None


def engine_state(engine):
    state = {"is_raw_math": engine.is_raw_math, "strip_n": engine.strip_n, "prefer_base": engine.prefer_base}
    if engine.is_raw_math:
        state["name_db"] = engine.name_db
    else:
        state["ghost_db"] = engine.ghost_db
        state["ghost_list"] = engine.ghost_list
    return state


def plan_workers(state_bytes, requested=0):
    cpus = logical_cpus()
    total_ram, avail_ram = ram_info()
    per_worker = WORKER_BASE_BYTES + state_bytes * WORKER_STATE_EXPANSION
    cpu_cap = max(1, cpus - 1)
    if avail_ram:
        ram_cap = max(1, int((avail_ram * RAM_BUDGET_FRACTION) // per_worker))
    else:
        ram_cap = cpu_cap
    limit = min(cpu_cap, ram_cap)
    if sys.platform == "win32":
        limit = min(limit, WINDOWS_MAX_WORKERS)
    workers = min(requested, limit) if requested and requested > 0 else limit
    info = {
        "cpus": cpus,
        "total_ram": total_ram,
        "avail_ram": avail_ram,
        "per_worker": per_worker,
        "cpu_cap": cpu_cap,
        "ram_cap": ram_cap,
        "workers": max(1, workers),
    }
    return info["workers"], info


def describe_system():
    cpus = logical_cpus()
    total_ram, avail_ram = ram_info()
    if total_ram:
        return f"Detected {cpus} logical CPU threads, {avail_ram / 1024**3:.1f} GB free of {total_ram / 1024**3:.1f} GB RAM"
    return f"Detected {cpus} logical CPU threads"


def _lower_priority():
    try:
        if sys.platform == "win32":
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)
        elif hasattr(os, "nice"):
            os.nice(5)
    except Exception:
        pass


def _init_worker(state_bytes):
    global _worker_engine
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass
    _lower_priority()
    state = pickle.loads(state_bytes)
    eng = MatchEngine()
    eng.is_raw_math = state["is_raw_math"]
    eng.strip_n = state["strip_n"]
    eng.prefer_base = state["prefer_base"]
    if eng.is_raw_math:
        eng.name_db = state["name_db"]
        eng.name_set = set(eng.name_db)
    else:
        eng.ghost_db = state["ghost_db"]
        eng.ghost_list = state["ghost_list"]
    _worker_engine = eng


def _match_task(clean_name, orig_raw, curr_n, region):
    return _worker_engine.find_match(clean_name, orig_raw, curr_n, region)


class ParallelMatcher:
    def __init__(self, engine, workers=0):
        state_bytes = pickle.dumps(engine_state(engine), protocol=pickle.HIGHEST_PROTOCOL)
        self.workers, self.info = plan_workers(len(state_bytes), workers)
        self.pool = ProcessPoolExecutor(max_workers=self.workers, initializer=_init_worker, initargs=(state_bytes,))
        self._futures = set()

    def submit(self, clean_name, orig_raw, curr_n, region):
        fut = self.pool.submit(_match_task, clean_name, orig_raw, curr_n, region)
        self._futures.add(fut)
        fut.add_done_callback(self._futures.discard)
        return fut

    def shutdown(self, cancel=False):
        if cancel:
            for fut in list(self._futures):
                fut.cancel()
        try:
            self.pool.shutdown(wait=not cancel)
        except Exception:
            pass


class OrderedMatchPipeline:
    """Fans fuzzy-match jobs out to worker processes and hands results back in submission order.

    If the worker pool cannot start or breaks, matching silently falls back to the local engine."""

    def __init__(self, engine, workers=0, logger=print, window_factor=4):
        self.engine = engine
        self.logger = logger
        self.matcher = None
        self.info = None
        self._pending = deque()
        try:
            self.matcher = ParallelMatcher(engine, workers)
            self.info = self.matcher.info
        except Exception as e:
            self.logger(f"[!] Could not start worker processes ({e}). Falling back to single-thread matching.")
        self.workers = self.matcher.workers if self.matcher else 1
        self.window = max(2, self.workers * window_factor)

    def _degrade(self, err):
        if self.matcher is not None:
            self.logger(f"[!] Worker pool failed ({err!r}). Continuing in single-thread mode.")
            matcher, self.matcher = self.matcher, None
            matcher.shutdown(cancel=True)

    def _resolve(self, match_args, fut):
        if match_args is None:
            return None
        if fut is not None:
            try:
                return fut.result()
            except Exception as e:
                self._degrade(e)
        return self.engine.find_match(*match_args)

    def _pop_one(self):
        payload, match_args, fut = self._pending.popleft()
        return payload, self._resolve(match_args, fut)

    def submit(self, payload, match_args=None):
        fut = None
        if match_args is not None and self.matcher is not None:
            try:
                fut = self.matcher.submit(*match_args)
            except Exception as e:
                self._degrade(e)
        self._pending.append((payload, match_args, fut))
        out = self.drain_ready()
        while len(self._pending) >= self.window:
            out.append(self._pop_one())
        return out

    def drain_ready(self):
        out = []
        while self._pending:
            _, match_args, fut = self._pending[0]
            if match_args is not None and fut is not None and not fut.done():
                break
            out.append(self._pop_one())
        return out

    def drain(self):
        while self._pending:
            yield self._pop_one()

    def __len__(self):
        return len(self._pending)

    def close(self, cancel=False):
        if cancel:
            self._pending.clear()
        if self.matcher is not None:
            self.matcher.shutdown(cancel=cancel)
            self.matcher = None
