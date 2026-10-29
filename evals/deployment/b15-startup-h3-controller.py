"""Monitor the separately frozen qualitative startup fix without changing old results."""

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

from closed_review.io import atomic_write_json, now_iso

BASE = Path("/home/jk/.local/state/creview-evaluations/b15-restored.w0fNUWyl")
BASE_CONTROLLER_SHA = "dc67ef135f09e513318c3fb28c8d9eef6f1adac26c069b6a6c5b0212ab1e2789"


def main(root, expected_manifest):
    import hashlib

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest(BASE / "controller.py") == BASE_CONTROLLER_SHA
    spec = importlib.util.spec_from_file_location("base_controller", BASE / "controller.py")
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    original = base.read(BASE / "suite-state.json")
    assert original["status"] == "finished" and original["engineering_passed"] is False
    assert base.ticks(original["controller_pid"]) != original["controller_start_ticks"]
    assert base.ticks(original["sampler_pid"]) != original["sampler_start_ticks"]
    identity = base.read(BASE / "runtime-identity.json")
    metadata = base.read(root / "attempt.json")
    bundle = root / "bundle"

    def verify():
        base.verify(BASE, identity)
        assert metadata["bundle_manifest_sha256"] == expected_manifest
        assert digest(bundle / "SHA256SUMS") == expected_manifest
        lines = (bundle / "SHA256SUMS").read_text().splitlines()
        assert len(lines) == 25
        for line in lines:
            expected, relative = line.split("  ", 1)
            path = bundle / relative
            assert path.is_file() and not path.is_symlink()
            assert path.resolve().is_relative_to(bundle) and digest(path) == expected

    state_file = root / "suite-state.json"
    assert not state_file.exists(), "preserve prior attempts"
    state = dict(status="preflight", started_at=now_iso(), controller_pid=os.getpid(),
        controller_start_ticks=base.ticks(os.getpid()), controller_sha256=digest(Path(__file__)),
        bundle_manifest_sha256=expected_manifest, runner=base.RUNNER, jobs=[],
        engineering_passed=False, qualification="not_qualified", attempt="b15_startup_h3",
        scope=metadata["scope"], predecessor_retained=True)
    atomic_write_json(state_file, state)
    sampler = None
    try:
        verify()
        base.idle()
        with (root / "memory-samples.log").open("xb") as log:
            sampler = subprocess.Popen(["bash", str(bundle / "monitor-qualification.sh"),
                str(identity["processes"]["native"]["pid"]), "10"], stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT)
        state.update(sampler_pid=sampler.pid, sampler_start_ticks=base.ticks(sampler.pid))
        command = [sys.executable, str(bundle / "evaluate-support-hermes.py")] + base.COMMON + [
            "--corpus", str(bundle / "manuscripts"), "--output", str(root / "qualitative-pair"),
            "--manifest", str(bundle / "qualitative-manifest.json"), "--repetitions", "1",
            "--language", "ko", "--timeout", "1800", "--total-timeout", "3600"]
        job = dict(name="qualitative-pair", started_at=now_iso(), status="running")
        with (root / "qualitative-pair-driver.log").open("xb") as log:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT)
            job.update(pid=child.pid, start_ticks=base.ticks(child.pid))
            state.update(status="running", jobs=[job])
            atomic_write_json(state_file, state)
            while child.poll() is None:
                try:
                    base.progress(root, job)
                except (OSError, ValueError, KeyError) as exc:
                    print("Observation error (job not restarted): " + type(exc).__name__,
                          flush=True)
                time.sleep(15)
            code = child.wait()
        job.update(status="finished", exit_code=code, finished_at=now_iso())
        verify()
        state.update(status="finished", engineering_passed=code == 0,
                     runtime_continuity_verified_after=True)
    except Exception as exc:
        state.update(status="failed", error=str(exc))
        print("Controller failed: " + repr(exc), flush=True)
    finally:
        if sampler is not None:
            sampler.terminate()
            sampler.wait(timeout=30)
            state["sampler_exit_code"] = sampler.returncode
        state["finished_at"] = now_iso()
        atomic_write_json(state_file, state)
    return 0 if state["engineering_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    raise SystemExit(main(args.root.resolve(), args.manifest_sha256))
