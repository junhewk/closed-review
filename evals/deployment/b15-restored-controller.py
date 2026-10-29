"""New post-reboot b15 attempt using the unchanged 23-file frozen bundle.

Public pairs run first to investigate the lost partial result. Nothing resumes, replaces,
or upgrades the lost pre-reboot run. Results and profiles live in persistent private storage.
"""

import argparse
import hashlib
import http.client
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from closed_review.io import atomic_write_json, now_iso
from closed_review.receipts import installed_identity

RUNNER = "aad45258aa8dd462a448e19f184e2dafa0edf3c582e70ec51f734a64fa8d3708"
BUNDLE_SHA = "939cd9f1f7942fa4a37b88d8a5a58108b7472558c2e82e8534227cb8995d8b85"
COMMON = ["--gateway-url", "http://100.122.169.13:8091/v1", "--model", "qwen3.8-flash-next",
          "--context-length", "262144", "--hermes", "/home/jk/.local/bin/hermes"]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ticks(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except FileNotFoundError:
        return None


def verify(root, identity):
    assert installed_identity()["sums_sha256"] == RUNNER
    bundle = root / "bundle"
    assert digest(bundle / "SHA256SUMS") == BUNDLE_SHA
    lines = (bundle / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 23
    for line in lines:
        expected, relative = line.split("  ", 1)
        path = bundle / relative
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(bundle)
        assert digest(path) == expected
    assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == identity["boot_id"]
    for item in identity["processes"].values():
        assert ticks(item["pid"]) == item["start_ticks"]
    for item in identity["files"] + identity["hermes_files"]:
        value = Path(item["path"]).stat()
        assert item["stat"] == dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                                    mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns)


def idle():
    deadline = time.monotonic() + 1200
    while True:
        connection = http.client.HTTPConnection("127.0.0.1", 1919, timeout=10)
        try:
            connection.request("GET", "/slots")
            response = connection.getresponse()
            assert response.status == 200
            slots = json.loads(response.read())
        finally:
            connection.close()
        if slots and all(s.get("is_processing") is False for s in slots):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("shared service busy: no new inference job started")
        time.sleep(15)


def progress(root, job):
    result = dict(at=now_iso(), job=job["name"], driver_pid=job["pid"], records=[])
    for path in (root / job["name"]).glob("**/review-data/support/*/run.json"):
        try:
            run = read(path)
            result["records"].append(dict(run_id=run["id"], task=run["cursor"],
                tasks=len(run["tasks"]), modified_ns=path.stat().st_mtime_ns,
                modules={k: dict(status=v["status"], facts=len(v["facts"]),
                    calculations=len(v["calculations"]), observations=len(v["observations"]),
                    failures=v["failures"], extraction_limits=v.get("extraction_limits", []),
                    coverage_gaps=v.get("coverage_gaps", [])) for k, v in run["modules"].items()}))
        except (OSError, ValueError, KeyError) as exc:
            result.setdefault("observation_errors", []).append(type(exc).__name__)
    atomic_write_json(root / "latest-observation.json", result)
    print(json.dumps(result, ensure_ascii=True), flush=True)


def main(root):
    state_file = root / "suite-state.json"
    assert not state_file.exists(), "preserve this attempt; never restart over it"
    identity_path = root / "runtime-identity.json"
    identity = read(identity_path)
    state = dict(status="preflight", started_at=now_iso(), controller_pid=os.getpid(),
        controller_start_ticks=ticks(os.getpid()), identity=RUNNER,
        bundle_manifest_sha256=BUNDLE_SHA, controller_sha256=digest(Path(__file__)),
        bootstrap_sha256=digest(root / "bootstrap.py"),
        runtime_identity_sha256=digest(identity_path), boot_id=identity["boot_id"],
        qualification="not_qualified", engineering_passed=False, jobs=[],
        attempt="b15_post_reboot_new_attempt_not_resume",
        interrupted_predecessor="/tmp/creview-support-runtime._z4usy4r",
        predecessor_outcome="interrupted_outputs_lost_not_passed",
        memory_caveat="Warm shared samples, not cold/exclusive/minimum hardware.",
        semantic_quality="not_assessed_requires_human_review")
    atomic_write_json(state_file, state)
    bundle = root / "bundle"
    sampler = None
    try:
        verify(root, identity)
        preflight = read(root / "preflight.json")
        assert preflight["ready"] and preflight["support_readiness"]["ready"]
        idle()
        with (root / "memory-samples.log").open("xb") as log:
            sampler = subprocess.Popen(["bash", str(bundle / "monitor-qualification.sh"),
                str(identity["processes"]["native"]["pid"]), "10"], stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT)
        state.update(sampler_pid=sampler.pid, sampler_start_ticks=ticks(sampler.pid))
        jobs = [
            ("public-pairs", "evaluate-support-hermes.py", [], "manuscripts",
             ["--manifest", str(bundle / "corpus-manifest.json"), "--repetitions", "1",
              "--language", "ko", "--timeout", "1800", "--total-timeout", "21600"]),
            ("native-pairs", "evaluate-support-hermes.py", [], "native-manuscripts",
             ["--manifest", str(bundle / "native-manifest.json"), "--repetitions", "1",
              "--language", "ko", "--timeout", "1200", "--total-timeout", "7200"]),
            ("iteration-handoff", "probe-support-handoff.py", ["iteration"],
             "synthetic-manuscripts", ["--timeout", "900"]),
            ("stale-draft", "probe-support-handoff.py", ["draft"],
             "synthetic-manuscripts", ["--timeout", "900"]),
            ("bootstrap-limit", "probe-support-bootstrap.py", [],
             "synthetic-manuscripts", ["--timeout", "900"]),
            ("compression", "probe-support-recovery.py", ["compression"],
             "synthetic-manuscripts", ["--timeout", "900"]),
        ]
        state["status"] = "running"
        for name, script, mode, corpus, extra in jobs:
            verify(root, identity)
            idle()
            assert sampler.poll() is None, "memory sampler stopped"
            assert not (root / name).exists()
            command = [sys.executable, str(bundle / script)] + mode + COMMON + [
                "--corpus", str(bundle / corpus), "--output", str(root / name)] + extra
            job = dict(name=name, started_at=now_iso(), status="running",
                       driver_log=name + "-driver.log")
            state["jobs"].append(job)
            with (root / job["driver_log"]).open("xb") as log:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=subprocess.STDOUT)
                job.update(pid=child.pid, start_ticks=ticks(child.pid))
                atomic_write_json(state_file, state)
                while child.poll() is None:
                    try:
                        progress(root, job)
                    except Exception as exc:
                        print("Observation error (job not restarted): " + type(exc).__name__,
                              flush=True)
                    time.sleep(15)
                code = child.wait()
            job.update(status="finished", finished_at=now_iso(), exit_code=code)
            atomic_write_json(state_file, state)
            print(f"Finished {name}: exit {code}", flush=True)
        verify(root, identity)
        state.update(status="finished", runtime_continuity_verified_after=True,
                     engineering_passed=all(job["exit_code"] == 0 for job in state["jobs"]))
    except Exception as exc:
        state.update(status="failed", error=str(exc))
        print("Controller failed: " + repr(exc), flush=True)
    finally:
        if sampler is not None:
            sampler.terminate()
            sampler.wait(timeout=30)
            state["sampler_finished_at"] = now_iso()
            state["sampler_exit_code"] = sampler.returncode
        state["finished_at"] = now_iso()
        atomic_write_json(state_file, state)
    return 0 if state["engineering_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    raise SystemExit(main(parser.parse_args().root.resolve()))
