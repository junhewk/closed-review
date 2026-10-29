"""Prepare a new persistent b15 attempt; never restore lost state or change services."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def stat(path):
    value = path.stat()
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns)


def main(root):
    bundle = root / "bundle"
    assert not (root / "venv").exists(), "preserve previous preparation attempts"
    assert digest(bundle / "SHA256SUMS") == (
        "939cd9f1f7942fa4a37b88d8a5a58108b7472558c2e82e8534227cb8995d8b85")
    lines = (bundle / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 23
    for line in lines:
        expected, relative = line.split("  ", 1)
        path = bundle / relative
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(bundle)
        assert digest(path) == expected
    previous = root / "previous-runtime-identity.json"
    assert digest(previous) == (
        "496f43a38f6d6c76cbb469fe7c0d1a6bb7e97ef8763af129429da1953fc4d8af")
    old = json.loads(previous.read_text())
    assert old["status"] == "finished" and len(old["files"]) == 21
    files = []
    for item in old["files"]:
        path = Path(item["path"])
        before = stat(path)
        same = before == item["stat"] and str(path.resolve()) == item["resolved_path"]
        actual = item["sha256"] if same else digest(path)
        assert actual == item["sha256"], f"runtime file changed: {path}"
        assert stat(path) == before
        files.append(dict(path=str(path), stat=before, sha256=actual,
                          verification="prior_hash_with_unchanged_stat" if same else "rehashed"))
    # Discover the real native server, not another workload or a reused old PID.
    native = []
    for directory in Path("/proc").iterdir():
        if directory.name.isdigit():
            try:
                if (directory / "exe").resolve() == Path("/home/jk/Strata/engine/strata"):
                    native.append(int(directory.name))
            except OSError:
                pass
    assert len(native) == 1, "one known Strata process is required"
    processes = {"native": native[0]}
    for name, unit in (("server", "strata-qwen.service"), ("gateway", "llm-gateway.service")):
        value = subprocess.check_output(
            ["systemctl", "--user", "show", unit, "--property=MainPID", "--value"], text=True)
        processes[name] = int(value.strip())
        assert processes[name] > 0
    watched = {}
    for role, pid in processes.items():
        fields = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
        assert fields[0] != "Z"
        watched[role] = dict(pid=pid, start_ticks=fields[19])
    native_pid = processes["native"]
    assert digest(Path(f"/proc/{native_pid}/exe")) == next(
        item["sha256"] for item in files if item["path"] == "/home/jk/Strata/engine/strata")
    argv = Path(f"/proc/{native_pid}/cmdline").read_bytes().decode().split("\0")
    expected_flags = {
        "--pack": "/home/jk/Strata-data/packs/iq3_s",
        "--native": ("/home/jk/Strata-data/models/IQ3_S/"
                     "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"),
        "--expert-profile": "/home/jk/Strata/data/expert-profile.bin",
        "--prefill": "auto", "--mtp": "/home/jk/Strata-data/mtp/rt", "--max-context": "262144",
    }
    flags = {key: argv[argv.index(key) + 1] for key in expected_flags}
    assert flags == expected_flags, "native runtime flags changed"
    identity = dict(
        boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        files=files, processes=watched, native_flags=flags,
        prior_identity_sha256=digest(previous),
        caveat="File/stat/argv checks, not loaded-memory or OS network-isolation attestation.",
        hermes_head=subprocess.check_output(
            ["git", "-C", "/home/jk/.hermes/hermes-agent", "rev-parse", "HEAD"], text=True).strip(),
        hermes_wrapper_sha256=digest(Path("/home/jk/.local/bin/hermes")),
    )
    assert identity["hermes_head"] == "ebadb5462e46c168a7eb097895faa647493e0a26"
    identity["hermes_files"] = []
    for name in ("/home/jk/.local/bin/hermes",
                 "/home/jk/.hermes/hermes-agent/.hermes/bin/hermes",
                 "/home/jk/.hermes/hermes-agent/agent/conversation_loop.py",
                 "/home/jk/.hermes/hermes-agent/agent/conversation_compression.py",
                 "/home/jk/.hermes/hermes-agent/tools/file_tools_write_guards.py"):
        path = Path(name)
        before = stat(path)
        value = digest(path)
        assert stat(path) == before
        identity["hermes_files"].append(dict(path=name, stat=before, sha256=value))
    with (root / "runtime-identity.json").open("x") as stream:
        json.dump(identity, stream, indent=2)
    print(json.dumps({"runtime_files_verified": len(files), "processes": watched,
                      "rehashed_files": sum(f["verification"] == "rehashed" for f in files)}),
          flush=True)
    uv = "/home/jk/.local/bin/uv"
    python = root / "venv/bin/python"
    subprocess.run([uv, "venv", "--python",
                    "/home/jk/.local/share/uv/python/cpython-3.14.2-linux-x86_64-gnu/bin/python3.14",
                    str(root / "venv")], check=True)
    subprocess.run([uv, "pip", "sync", "--offline", "--python", str(python), "--require-hashes",
                    str(bundle / "runtime-requirements.txt")], check=True)
    subprocess.run([uv, "pip", "install", "--offline", "--python", str(python), "--no-deps",
                    str(bundle / "closed_review-0.9.0b15-py3-none-any.whl")], check=True)
    check = r'''
import json, sys
from pathlib import Path
from closed_review.deployment import setup_profile
from closed_review.hermes import inspect_profile
from closed_review.io import atomic_write_json
from closed_review.receipts import installed_identity
from closed_review.smoke import _child_environment, environment
root = Path(sys.argv[1])
identity = installed_identity()
assert identity['version'] == '0.9.0b15'
assert identity['sums_sha256'] == 'aad45258aa8dd462a448e19f184e2dafa0edf3c582e70ec51f734a64fa8d3708'
env = _child_environment(root / 'preflight-hermes', gateway_url='http://100.122.169.13:8091/v1')
with environment(env):
    setup = setup_profile('pilot', gateway_url='http://100.122.169.13:8091/v1',
        model='qwen3.8-flash-next', context_length=262144, apply=True)
profile = Path(setup['profile_root'])
env.update(HERMES_HOME=str(profile), CREVIEW_HOME=str(profile / 'review-data'))
with environment(env):
    report = inspect_profile(None, live=True)
atomic_write_json(root / 'preflight.json', report)
assert report['ready'] and report['support_readiness']['ready'], report['problems']
atomic_write_json(root / 'runtime-install.json', dict(runtime=str(root), python=sys.version,
    identity=identity['sums_sha256'], strict_preflight=True, qualification='not_qualified',
    generation_started=False))
print(json.dumps(dict(runtime=str(root), preflight_ready=True,
    runtime_status=report['support_readiness']['runtime']['status'])))
'''
    subprocess.run([str(python), "-c", check, str(root)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    main(parser.parse_args().root.resolve())
