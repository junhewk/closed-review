"""Record a detached exact-wheel test run independently of terminal-session lifetime."""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main(output):
    output.mkdir(mode=0o700)
    python = "/tmp/creview-support-b15-development.lnZyr4W9/venv/bin/python"
    command = [python, "-m", "pytest", "-o", "pythonpath=", "--junitxml", str(output / "tests.xml")]
    started = dict(started_at=datetime.now(UTC).isoformat(), supervisor_pid=os.getpid(),
                   command=command, qualification="not_qualified")
    with (output / "started.json").open("x") as stream:
        json.dump(started, stream, indent=2)
    with (output / "pytest.log").open("xb") as log:
        child = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[2],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        with (output / "child.json").open("x") as stream:
            json.dump(dict(pid=child.pid), stream)
        code = child.wait()
    with (output / "finished.json").open("x") as stream:
        json.dump(dict(**started, finished_at=datetime.now(UTC).isoformat(),
                       exit_code=code), stream, indent=2)
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(main(parser.parse_args().output.resolve()))
