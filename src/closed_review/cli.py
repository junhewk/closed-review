from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .detect import detect_gateway
from .direct import finalize_direct_export, prepare_direct_export
from .errors import ReviewError
from .hermes import inspect_profile, install_skill, restore_privacy_block, skill_diff
from .io import read_statement
from .lookups import create_lookup, run_lookup, show_lookup
from .receipts import installed_identity, verify_receipt
from .references import (
    check_references,
    request_reference_metadata,
    run_reference_metadata,
    show_reference_check,
)
from .scan import (
    next_candidate,
    next_task,
    purge_scan,
    record_response,
    scan_status,
    start_scan,
    submit_task,
)
from .session import start_session
from .settings import set_gateway, trusted_gateway


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _paths(values: list[str] | None) -> list[Path]:
    return [Path(value) for value in values or []]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="creview", description="Local-first Hermes journal review utilities"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    support = commands.add_parser("support", help="Manuscript-only medical methodological support")
    support_commands = support.add_subparsers(dest="support_command", required=True)
    support_commands.add_parser("modules", help="List independent module families and criteria")
    support_route = support_commands.add_parser(
        "route", help="Suggest modules by article type; never run them"
    )
    support_route.add_argument("article_type")
    support_score = support_commands.add_parser(
        "score", help="Score human audits offline, never inside Hermes"
    )
    support_score.add_argument("audit", type=Path)
    support_start = support_commands.add_parser("start")
    support_start.add_argument("manuscript", type=Path)
    support_start.add_argument("--module", action="append", required=True)
    support_start.add_argument("--session")
    support_start.add_argument(
        "--language",
        default="inherit",
        help="follow the user's Hermes setting; never infer from server locale",
    )
    support_start.add_argument("--max-tasks", type=int, default=96)
    for name in ("next", "status", "report"):
        support_commands.add_parser(name).add_argument("run_id")
    support_submit = support_commands.add_parser("submit")
    support_submit.add_argument("run_id")
    support_submit.add_argument("answer", type=Path)
    support_read = support_commands.add_parser("read")
    support_read.add_argument("run_id")
    support_read.add_argument("--module", required=True)
    support_read.add_argument("--query")
    support_read.add_argument(
        "--query-file", type=Path, help="private file containing a confidential search string"
    )
    support_read.add_argument("--block-id", action="append")
    support_read.add_argument("--fact-id", action="append")
    support_read.add_argument(
        "--facts", action="store_true", help="page through this module's extracted facts"
    )
    support_read.add_argument("--assessments", action="store_true")
    support_read.add_argument("--calculations", action="store_true")
    support_read.add_argument("--offset", type=int, default=0)
    support_read.add_argument("--fragment-offset", type=int, default=0)
    support_record = support_commands.add_parser("record")
    support_record.add_argument("run_id")
    support_record.add_argument("observation_id", help="or run for a general note")
    support_record.add_argument("disposition")
    support_record.add_argument("--words")
    support_record.add_argument("--words-file", type=Path)
    support_export = support_commands.add_parser("export")
    support_export.add_argument("run_id")
    support_export.add_argument(
        "--output", type=Path, help="new private directory; never overwrite an existing one"
    )

    direct = commands.add_parser("direct", help="Manage private direct-review outputs")
    direct_commands = direct.add_subparsers(dest="direct_command", required=True)
    direct_prepare = direct_commands.add_parser("prepare-export")
    direct_prepare.add_argument("--session", help="session id from `creview session start`")
    direct_prepare.add_argument("--scan", help="link accepted findings from this scan")
    direct_finalize = direct_commands.add_parser("finalize")
    direct_finalize.add_argument("export_id")
    direct_finalize.add_argument("--profile")

    session = commands.add_parser(
        "session", help="Run the privacy preflight before reading a manuscript"
    )
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_start = session_commands.add_parser("start")
    session_start.add_argument("--profile")
    session_start.add_argument(
        "--support",
        action="store_true",
        help="require strict medical-support profile/runtime route checks",
    )
    session_start.add_argument("--skip-live", action="store_true", help=argparse.SUPPRESS)

    receipts = commands.add_parser("receipts", help="Verify export receipts")
    receipt_commands = receipts.add_subparsers(dest="receipt_command", required=True)
    receipt_verify = receipt_commands.add_parser("verify")
    receipt_verify.add_argument("receipt", type=Path)
    receipt_verify.add_argument(
        "--sums", type=Path, help="reference `creview receipts sums` output from the release"
    )
    receipt_commands.add_parser("sums")

    lookup = commands.add_parser("lookup", help="Manage individually approved scholarly queries")
    lookup_commands = lookup.add_subparsers(dest="lookup_command", required=True)
    lookup_request = lookup_commands.add_parser("request")
    lookup_request.add_argument("--provider", choices=["crossref", "openalex"], required=True)
    lookup_request.add_argument("--query", required=True)
    lookup_request.add_argument("--session")
    lookup_run = lookup_commands.add_parser("run")
    lookup_run.add_argument("request_id")
    lookup_run.add_argument("--approval-statement")
    lookup_run.add_argument("--approval-file", type=Path)
    lookup_run.add_argument("--session")
    lookup_show = lookup_commands.add_parser("show")
    lookup_show.add_argument("request_id")
    lookup_show.add_argument("--session")

    references = commands.add_parser(
        "references", help="Run an explicitly requested mechanical reference check"
    )
    reference_commands = references.add_subparsers(dest="reference_command", required=True)
    reference_check = reference_commands.add_parser("check")
    reference_check.add_argument("manuscript", type=Path)
    reference_show = reference_commands.add_parser("show")
    reference_show.add_argument("check_id")
    metadata_request = reference_commands.add_parser("request-metadata")
    metadata_request.add_argument("check_id")
    metadata_request.add_argument("--provider", choices=["crossref", "openalex"], required=True)
    metadata_run = reference_commands.add_parser("run-metadata")
    metadata_run.add_argument("check_id")
    metadata_run.add_argument("request_id")
    metadata_run.add_argument("--approval-statement")
    metadata_run.add_argument("--approval-file", type=Path)

    scan = commands.add_parser("scan", help="Legacy deep scan (not the default support workflow)")
    scan_commands = scan.add_subparsers(dest="scan_command", required=True)
    scan_start = scan_commands.add_parser("start")
    scan_start.add_argument("manuscript", type=Path)
    scan_start.add_argument("--supplement", action="append", default=[])
    scan_start.add_argument("--session")
    scan_start.add_argument(
        "--profile", action="append", default=[], help="a design profile chosen for the review"
    )
    scan_start.add_argument("--no-profile", action="store_true", help="no profile fits")
    scan_start.add_argument(
        "--confirmation", help="what the reviewer said about the profiles (optional, recorded)"
    )
    scan_start.add_argument("--confirmation-file", type=Path)
    for name in ("next", "status"):
        scan_commands.add_parser(name).add_argument("scan_id")
    scan_candidate = scan_commands.add_parser("candidate")
    scan_candidate.add_argument("scan_id")
    scan_candidate.add_argument(
        "--reserve", action="store_true", help="only when the reviewer asks for further minors"
    )
    scan_submit = scan_commands.add_parser("submit")
    scan_submit.add_argument("scan_id")
    scan_submit.add_argument("answer", type=Path)
    scan_record = scan_commands.add_parser("record")
    scan_record.add_argument("scan_id")
    scan_record.add_argument("finding_id")
    scan_record.add_argument("disposition")
    scan_record.add_argument("--words", help="the reviewer's reply, quoted from their message")
    scan_record.add_argument("--words-file", type=Path)
    scan_purge = scan_commands.add_parser("purge")
    scan_purge.add_argument("scan_id")
    scan_purge.add_argument("--confirm", required=True)

    config = commands.add_parser("config", help="Set the trusted model gateway")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    gateway = config_commands.add_parser(
        "gateway", help="store the only model endpoint confidential material may reach"
    )
    gateway.add_argument("--url", required=True, help="OpenAI-compatible base URL")
    gateway.add_argument("--model", required=True, help="the review model's name on that gateway")
    gateway.add_argument(
        "--trusted-model",
        action="append",
        default=[],
        help="another model on the same gateway that Hermes routes may use (repeatable)",
    )
    config_commands.add_parser("show", help="show the trusted gateway in effect")
    detect = config_commands.add_parser(
        "detect", help="find the local or private model server and, with --apply, store it"
    )
    detect.add_argument("--profile")
    detect.add_argument("--model", help="the model to use when the server lists several")
    detect.add_argument("--apply", action="store_true")

    hermes = commands.add_parser("hermes", help="Install and verify the Hermes skill")
    hermes_commands = hermes.add_subparsers(dest="hermes_command", required=True)
    setup = hermes_commands.add_parser("setup-profile", help="Create a dedicated review profile")
    setup.add_argument("--profile", default="closed-review")
    setup.add_argument("--gateway-url", required=True)
    setup.add_argument("--model", required=True)
    setup.add_argument("--context-length", type=int)
    setup.add_argument("--apply", action="store_true")
    smoke = hermes_commands.add_parser(
        "smoke", help="Legacy scan smoke; does not qualify medical support"
    )
    smoke.add_argument("--profile", default="closed-review")
    smoke.add_argument("--hermes", help="Hermes executable (otherwise resolved from PATH)")
    smoke.add_argument("--timeout", type=int, default=900, help="total wall-clock limit in seconds")
    smoke.add_argument("--keep", action="store_true", help="retain synthetic session artifacts")
    install = hermes_commands.add_parser("install")
    install.add_argument("--profile")
    install.add_argument("--apply", action="store_true")
    install.add_argument(
        "--replace-unmanaged",
        action="store_true",
        help="move a manually copied skill to a backup and install the managed copy",
    )
    doctor = hermes_commands.add_parser("doctor")
    doctor.add_argument("--profile")
    doctor.add_argument("--skip-live", action="store_true", help=argparse.SUPPRESS)
    doctor.add_argument(
        "--support", action="store_true", help="require strict medical-support readiness"
    )
    diff = hermes_commands.add_parser(
        "skill-diff", help="show how the skill's privacy block differs from this release"
    )
    diff.add_argument("--profile")
    restore = hermes_commands.add_parser(
        "skill-restore", help="restore only the skill's privacy block, keeping other edits"
    )
    restore.add_argument("--profile")
    restore.add_argument("--apply", action="store_true")
    return parser


def dispatch(args: argparse.Namespace) -> Any:
    if args.command == "support":
        from .support import workflow
        from .support.methods import catalogue
        from .support.render import export

        command = args.support_command
        if command == "route":
            from .support.methods import route_modules

            return route_modules(args.article_type)
        if command == "modules":
            return catalogue()
        if command == "score":
            from .support.qualification import score

            return score(args.audit)
        if command == "start":
            return workflow.start(
                args.manuscript,
                args.module,
                session=args.session,
                language=args.language,
                max_tasks=args.max_tasks,
            )
        if command == "next":
            return workflow.next_task(args.run_id)
        if command == "submit":
            return workflow.submit(args.run_id, args.answer)
        if command == "read":
            if args.query is not None and args.query_file is not None:
                raise ReviewError("choose --query or --query-file, not both")
            query = (
                read_statement(args.query, args.query_file)
                if args.query is not None or args.query_file
                else None
            )
            return workflow.read(
                args.run_id,
                args.module,
                query=query,
                block_ids=args.block_id,
                fact_ids=args.fact_id,
                offset=args.offset,
                facts=args.facts,
                assessments=args.assessments,
                calculations=args.calculations,
                fragment_offset=args.fragment_offset,
            )
        if command == "status":
            return workflow.status(args.run_id)
        if command == "report":
            return workflow.report(args.run_id)
        if command == "record":
            return workflow.record(
                args.run_id,
                args.observation_id,
                args.disposition,
                read_statement(args.words, args.words_file),
            )
        if command == "export":
            return export(args.run_id, args.output)
    if args.command == "direct" and args.direct_command == "prepare-export":
        return prepare_direct_export(args.session, args.scan)
    if args.command == "direct" and args.direct_command == "finalize":
        return finalize_direct_export(args.export_id, args.profile)
    if args.command == "session" and args.session_command == "start":
        return start_session(args.profile, live=not args.skip_live, support=args.support)
    if args.command == "receipts":
        if args.receipt_command == "verify":
            return verify_receipt(args.receipt, args.sums)
        if args.receipt_command == "sums":
            return installed_identity()
    if args.command == "lookup":
        if args.lookup_command == "request":
            return create_lookup(args.provider, args.query, session=args.session)
        if args.lookup_command == "run":
            return run_lookup(
                args.request_id,
                approval_statement=args.approval_statement,
                approval_file=args.approval_file,
                session=args.session,
            )
        if args.lookup_command == "show":
            return show_lookup(args.request_id, session=args.session)
    if args.command == "references":
        if args.reference_command == "check":
            return check_references(args.manuscript)
        if args.reference_command == "show":
            return show_reference_check(args.check_id)
        if args.reference_command == "request-metadata":
            return request_reference_metadata(args.check_id, args.provider)
        if args.reference_command == "run-metadata":
            return run_reference_metadata(
                args.check_id,
                args.request_id,
                approval_statement=args.approval_statement,
                approval_file=args.approval_file,
            )
    if args.command == "scan":
        command = args.scan_command
        if command == "start":
            if not args.profile and not args.no_profile:
                raise ReviewError(
                    "name the design profiles chosen for the review with --profile, or pass "
                    "--no-profile"
                )
            return start_scan(
                args.manuscript,
                _paths(args.supplement),
                args.session,
                profiles=args.profile,
                confirmation=read_statement(args.confirmation, args.confirmation_file),
            )
        if command == "next":
            return next_task(args.scan_id)
        if command == "submit":
            return submit_task(args.scan_id, args.answer)
        if command == "candidate":
            return next_candidate(args.scan_id, reserve=args.reserve)
        if command == "status":
            return scan_status(args.scan_id)
        if command == "record":
            words = read_statement(args.words, args.words_file)
            return record_response(args.scan_id, args.finding_id, args.disposition, words)
        if command == "purge":
            return purge_scan(args.scan_id, args.confirm)
    if args.command == "config":
        if args.config_command == "gateway":
            return set_gateway(args.url, args.model, args.trusted_model)
        if args.config_command == "show":
            return trusted_gateway()
        if args.config_command == "detect":
            return detect_gateway(args.profile, model=args.model, apply=args.apply)
    if args.command == "hermes":
        if args.hermes_command == "setup-profile":
            from .deployment import setup_profile

            return setup_profile(
                args.profile,
                gateway_url=args.gateway_url,
                model=args.model,
                context_length=args.context_length,
                apply=args.apply,
            )
        if args.hermes_command == "smoke":
            from .smoke import run_smoke

            result = run_smoke(
                args.profile, hermes=args.hermes, timeout=args.timeout, keep=args.keep
            )
            if not result["passed"]:
                emit(result)
                raise ReviewError("synthetic workflow did not pass; see the checks above")
            return result
        if args.hermes_command == "install":
            return install_skill(
                args.profile, apply=args.apply, replace_unmanaged=args.replace_unmanaged
            )
        if args.hermes_command == "doctor":
            report = inspect_profile(args.profile, live=not args.skip_live)
            if args.support and not report["support_readiness"]["ready"]:
                raise ReviewError(
                    "medical support profile is not ready: "
                    + "; ".join(report["support_readiness"]["problems"])
                )
            if not report["ready"]:
                raise ReviewError("Hermes profile is not ready: " + "; ".join(report["problems"]))
            return report
        if args.hermes_command == "skill-diff":
            return skill_diff(args.profile)
        if args.hermes_command == "skill-restore":
            return restore_privacy_block(args.profile, apply=args.apply)
    raise ReviewError("unknown command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit(dispatch(args))
        return 0
    except ReviewError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
