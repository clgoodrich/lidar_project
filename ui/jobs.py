"""JobManager: run pipeline scripts as managed subprocesses.

Design (see docs/ui/UI_PLAN.md):
  * every job is `python -u <script> <args>`, cwd = repo root, stdout+stderr
    teed to ui/runs/<id>/output.log. The UI never imports heavy scripts.
  * one FIFO queue drained by a daemon worker thread. GPU jobs are strictly
    serialized (one 8 GB card); CPU jobs run up to `cpu_cap` in parallel.
  * state persisted to ui/jobs.jsonl (append-only) so a Streamlit rerun or app
    restart reconstructs the picture.
  * on startup, jobs marked running are reconciled against live PIDs:
    alive -> re-attach (keep polling); dead -> orphaned.
  * cancel kills the whole process tree via psutil.

The manager is created once via st.cache_resource so it is a singleton across
all Streamlit reruns and browser sessions.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import psutil

from paths import LEDGER, PYEXE, ROOT, RUNS

TERMINAL = {"done", "failed", "cancelled", "orphaned"}


@dataclass
class Job:
    id: str
    task_id: str
    label: str
    cmd: list[str]
    gpu: bool
    params: dict
    status: str = "queued"          # queued|running|done|failed|cancelled|orphaned
    pid: int | None = None
    returncode: int | None = None
    created: float = field(default_factory=time.time)
    started: float | None = None
    ended: float | None = None
    git_commit: str = ""
    log_path: str = ""

    @property
    def elapsed(self) -> float:
        if self.started is None:
            return 0.0
        return (self.ended or time.time()) - self.started


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=ROOT, capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except Exception:
        return ""


def _kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
        procs = parent.children(recursive=True) + [parent]
        for p in procs:
            try:
                p.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(procs, timeout=5)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass


class JobManager:
    def __init__(self, cpu_cap: int = 2):
        self.jobs: dict[str, Job] = {}
        self.cpu_cap = cpu_cap
        self._procs: dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()
        self._counter = 0
        self._load_and_reconcile()
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()

    # ---- persistence ----
    def _append_ledger(self, job: Job) -> None:
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(job)) + "\n")

    def _load_and_reconcile(self) -> None:
        if not LEDGER.exists():
            return
        latest: dict[str, dict] = {}
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                latest[d["id"]] = d          # last write wins
            except json.JSONDecodeError:
                continue
        for d in latest.values():
            job = Job(**{k: d.get(k) for k in Job.__dataclass_fields__})
            if job.status in ("running", "queued") and job.pid:
                # reconcile against live process
                if psutil.pid_exists(job.pid):
                    job.status = "running"   # re-attach; loop will re-poll
                else:
                    job.status = "orphaned"
                    job.ended = job.ended or time.time()
            elif job.status == "queued":
                job.status = "orphaned"      # never started before shutdown
            self.jobs[job.id] = job
        n_orphan = sum(1 for j in self.jobs.values() if j.status == "orphaned")
        if n_orphan:
            print(f"[jobs] reconciled {n_orphan} orphaned job(s)")

    # ---- submission ----
    def submit(self, task_id: str, label: str, script: str,
               args: list[str], gpu: bool, params: dict) -> str:
        with self._lock:
            self._counter += 1
            jid = f"j{int(time.time())%100000}_{self._counter:03d}"
        run_dir = RUNS / jid
        run_dir.mkdir(parents=True, exist_ok=True)
        cmd = [PYEXE, "-u", script, *args]
        job = Job(id=jid, task_id=task_id, label=label, cmd=cmd, gpu=gpu,
                  params=params, git_commit=_git_commit(),
                  log_path=str(run_dir / "output.log"))
        (run_dir / "cmd.json").write_text(
            json.dumps({"cmd": cmd, "task_id": task_id, "params": params,
                        "git_commit": job.git_commit}, indent=2),
            encoding="utf-8")
        with self._lock:
            self.jobs[jid] = job
        self._append_ledger(job)
        return jid

    def cancel(self, jid: str) -> None:
        with self._lock:
            job = self.jobs.get(jid)
            if not job or job.status in TERMINAL:
                return
            if job.pid:
                _kill_tree(job.pid)
            job.status = "cancelled"
            job.ended = time.time()
            self._procs.pop(jid, None)
        self._append_ledger(job)

    # ---- worker ----
    def _gpu_running(self) -> bool:
        return any(j.status == "running" and j.gpu
                   for j in self.jobs.values())

    def _cpu_running(self) -> int:
        return sum(1 for j in self.jobs.values()
                   if j.status == "running" and not j.gpu)

    def _launch(self, job: Job) -> None:
        env = None  # inherit; PYTHONIOENCODING set by parent below
        import os
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        log = open(job.log_path, "w", encoding="utf-8", buffering=1)
        proc = subprocess.Popen(job.cmd, cwd=str(ROOT), stdout=log,
                                stderr=subprocess.STDOUT, env=env)
        job.pid = proc.pid
        job.status = "running"
        job.started = time.time()
        self._procs[job.id] = proc
        self._append_ledger(job)

    def _finish(self, job: Job, rc: int | None) -> None:
        job.returncode = rc
        job.ended = time.time()
        # failure if rc != 0, or log shows a traceback
        failed = rc not in (0, None)
        if not failed and job.log_path and Path(job.log_path).exists():
            tail = Path(job.log_path).read_text(
                encoding="utf-8", errors="replace")[-4000:]
            if "Traceback (most recent call last)" in tail:
                failed = True
        job.status = "failed" if failed else "done"
        self._procs.pop(job.id, None)
        self._append_ledger(job)

    def _loop(self) -> None:
        while True:
            try:
                with self._lock:
                    # poll running procs we own
                    for jid, proc in list(self._procs.items()):
                        rc = proc.poll()
                        if rc is not None:
                            self._finish(self.jobs[jid], rc)
                    # poll re-attached (no Popen handle) running jobs
                    for job in self.jobs.values():
                        if (job.status == "running" and job.id not in
                                self._procs and job.pid):
                            if not psutil.pid_exists(job.pid):
                                self._finish(job, None)
                    # start queued jobs, FIFO by creation
                    for job in sorted((j for j in self.jobs.values()
                                       if j.status == "queued"),
                                      key=lambda j: j.created):
                        if job.gpu and self._gpu_running():
                            continue
                        if not job.gpu and self._cpu_running() >= self.cpu_cap:
                            continue
                        if job.gpu and self._cpu_running() and False:
                            pass  # (GPU may run alongside CPU; only GPU-GPU excl)
                        self._launch(job)
            except Exception as e:  # never let the worker die
                print(f"[jobs] worker error: {e}")
            time.sleep(1.0)

    # ---- queries ----
    def snapshot(self) -> list[Job]:
        with self._lock:
            return sorted(self.jobs.values(), key=lambda j: j.created,
                          reverse=True)

    def get(self, jid: str) -> Job | None:
        return self.jobs.get(jid)

    def tail(self, jid: str, n: int = 200) -> str:
        job = self.jobs.get(jid)
        if not job or not job.log_path or not Path(job.log_path).exists():
            return ""
        lines = Path(job.log_path).read_text(
            encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
