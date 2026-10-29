"""Freeze a driver-only b15 startup regression with the unchanged qualitative article."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from closed_review.io import atomic_write_json, atomic_write_text
from closed_review.receipts import installed_identity

PREVIOUS = Path("/tmp/creview-support-b15-candidate.pf8uua67")
PREVIOUS_SHA = "939cd9f1f7942fa4a37b88d8a5a58108b7472558c2e82e8534227cb8995d8b85"
RUNNER = "aad45258aa8dd462a448e19f184e2dafa0edf3c582e70ec51f734a64fa8d3708"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(root):
    assert installed_identity()["sums_sha256"] == RUNNER
    assert digest(PREVIOUS / "SHA256SUMS") == PREVIOUS_SHA
    bundle = root / "bundle"
    bundle.mkdir(mode=0o700)
    lines = (PREVIOUS / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 23
    for line in lines:
        expected, name = line.split("  ", 1)
        source = PREVIOUS / name
        assert source.is_file() and not source.is_symlink()
        assert source.resolve().is_relative_to(PREVIOUS) and digest(source) == expected
        target = bundle / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o600)
    repo = Path(__file__).resolve().parents[2]
    shutil.copyfile(repo / "scripts/test-support-hermes.py", bundle / "test-support-hermes.py")
    shutil.copyfile(PREVIOUS / "SHA256SUMS", bundle / "predecessor-SHA256SUMS")
    changed = [line.split("  ", 1)[1] for line in lines
               if digest(bundle / line.split("  ", 1)[1]) != line.split("  ", 1)[0]]
    assert changed == ["test-support-hermes.py"], changed
    manifest = json.loads((bundle / "corpus-manifest.json").read_text())
    manifest["cases"] = [r for r in manifest["cases"] if r["case_id"] == "public-qualitative"]
    assert len(manifest["cases"]) == 1
    manifest["corpus_id"] += "-qualitative-startup-h3"
    assert digest(bundle / "manuscripts" / manifest["cases"][0]["file"]) == (
        manifest["cases"][0]["sha256"])
    atomic_write_json(bundle / "qualitative-manifest.json", manifest)
    files = sorted(p for p in bundle.rglob("*") if p.is_file())
    assert len(files) == 25
    listing = "".join(digest(p) + "  " + p.relative_to(bundle).as_posix() + "\n" for p in files)
    atomic_write_text(bundle / "SHA256SUMS", listing)
    record = dict(version="0.9.0b15", harness="startup-h3", runner=RUNNER,
        predecessor_bundle_manifest_sha256=PREVIOUS_SHA,
        bundle_manifest_sha256=digest(bundle / "SHA256SUMS"), bundle_files=len(files),
        changed_evaluator_files=changed, packaged_code_or_skill_changed=False,
        startup_driver_sha256=digest(bundle / "test-support-hermes.py"),
        source_sha256=manifest["cases"][0]["sha256"],
        targeted_manifest_sha256=digest(bundle / "qualitative-manifest.json"),
        scope="one_real_qualitative_pair_not_a_replacement_for_the_failed_full_batch",
        qualification="not_qualified")
    atomic_write_json(root / "attempt.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    main(parser.parse_args().root.resolve())
