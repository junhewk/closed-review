from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .cases import (
    attest_case,
    case_status,
    create_case,
    find_source,
    list_sources,
    purge_case,
    read_locator,
    read_statement,
)
from .detect import detect_gateway
from .direct import finalize_direct_export, prepare_direct_export
from .errors import ReviewError
from .hermes import inspect_profile, install_skill, restore_privacy_block, skill_diff
from .lookups import create_lookup, run_lookup, show_lookup
from .parsers import parse_document
from .receipts import installed_identity, verify_receipt
from .references import (
    check_references,
    request_reference_metadata,
    run_reference_metadata,
    show_reference_check,
)
from .review import (
    dismiss_finding,
    export_review,
    import_reference_issues,
    list_findings,
    next_finding,
    next_item,
    prepare_draft,
    prepare_finding_response,
    prepare_finding_revision,
    propose_case_plan,
    require_review_access,
    respond_finding,
    review_status,
    revise_finding,
    set_case_plan,
    start_batch,
    start_review,
    submit_draft,
    submit_findings,
)
from .scan import (
    next_candidate,
    next_task,
    purge_scan,
    record_response,
    scan_status,
    set_overview,
    set_plan,
    start_scan,
    submit_task,
    sweep,
    synthesize,
)
from .segments import draft_plan
from .session import confirm_profiles, start_session
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

    direct = commands.add_parser("direct", help="Manage private direct-review outputs")
    direct_commands = direct.add_subparsers(dest="direct_command", required=True)
    direct_prepare = direct_commands.add_parser("prepare-export")
    direct_prepare.add_argument("--session", help="session id from `creview session start`")
    direct_finalize = direct_commands.add_parser("finalize")
    direct_finalize.add_argument("export_id")
    direct_finalize.add_argument("--profile")

    session = commands.add_parser(
        "session", help="Run the privacy preflight before reading a manuscript"
    )
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_start = session_commands.add_parser("start")
    session_start.add_argument("--profile")
    session_start.add_argument("--skip-live", action="store_true", help=argparse.SUPPRESS)

    receipts = commands.add_parser("receipts", help="Verify export receipts")
    receipt_commands = receipts.add_subparsers(dest="receipt_command", required=True)
    receipt_verify = receipt_commands.add_parser("verify")
    receipt_verify.add_argument("receipt", type=Path)
    receipt_verify.add_argument(
        "--sums", type=Path, help="reference `creview receipts sums` output from the release"
    )
    receipt_commands.add_parser("sums")

    case = commands.add_parser("case", help="Create and manage private audited review cases")
    case_commands = case.add_subparsers(dest="case_command", required=True)
    create = case_commands.add_parser("create")
    create.add_argument("manuscript")
    create.add_argument("--journal", required=True)
    create.add_argument("--title")
    create.add_argument("--language", default="English")
    create.add_argument("--supplement", action="append")
    create.add_argument("--guideline", action="append")
    create.add_argument("--review-form", action="append")
    status = case_commands.add_parser("status")
    status.add_argument("case_id")
    attest = case_commands.add_parser("attest")
    attest.add_argument("case_id")
    attest.add_argument("--statement")
    attest.add_argument("--statement-file", type=Path)
    purge = case_commands.add_parser("purge")
    purge.add_argument("case_id")
    purge.add_argument("--confirm", required=True)

    source = commands.add_parser("source", help="Read locally extracted sources")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    source_list = source_commands.add_parser("list")
    source_list.add_argument("case_id")
    source_read = source_commands.add_parser("read")
    source_read.add_argument("case_id")
    source_read.add_argument("source_id")
    source_read.add_argument("locator")
    source_find = source_commands.add_parser("find")
    source_find.add_argument("case_id")
    source_find.add_argument("words")
    source_find.add_argument("--source-id")
    source_find.add_argument("--limit", type=int, default=10)

    review = commands.add_parser("review", help="Advance an optional audited coverage ledger")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_start = review_commands.add_parser("start")
    review_start.add_argument("case_id")
    review_start.add_argument("--profile")
    review_status_parser = review_commands.add_parser("status")
    review_status_parser.add_argument("case_id")
    review_batch_start = review_commands.add_parser("batch-start")
    review_batch_start.add_argument("case_id")
    review_batch_start.add_argument("--limit", type=int, default=3)
    review_next = review_commands.add_parser("next")
    review_next.add_argument("case_id")

    finding = commands.add_parser("finding", help="Submit evidence-anchored findings")
    finding_commands = finding.add_subparsers(dest="finding_command", required=True)
    finding_submit = finding_commands.add_parser("submit")
    finding_submit.add_argument("case_id")
    finding_submit.add_argument("proposal", type=Path)
    finding_list = finding_commands.add_parser("list")
    finding_list.add_argument("case_id")
    finding_list.add_argument("--include-dismissed", action="store_true")
    finding_list.add_argument("--status")
    finding_next = finding_commands.add_parser("next")
    finding_next.add_argument("case_id")
    finding_prepare_response = finding_commands.add_parser("prepare-response")
    finding_prepare_response.add_argument("case_id")
    finding_prepare_response.add_argument("finding_id")
    finding_respond = finding_commands.add_parser("respond")
    finding_respond.add_argument("case_id")
    finding_respond.add_argument("finding_id")
    finding_respond.add_argument("proposal", type=Path)
    finding_prepare_revision = finding_commands.add_parser("prepare-revision")
    finding_prepare_revision.add_argument("case_id")
    finding_prepare_revision.add_argument("finding_id")
    finding_revise = finding_commands.add_parser("revise")
    finding_revise.add_argument("case_id")
    finding_revise.add_argument("finding_id")
    finding_revise.add_argument("proposal", type=Path)
    finding_dismiss = finding_commands.add_parser("dismiss")
    finding_dismiss.add_argument("case_id")
    finding_dismiss.add_argument("finding_id")
    finding_dismiss.add_argument("--reason")
    finding_dismiss.add_argument("--reason-file", type=Path)

    draft = commands.add_parser("draft", help="Prepare and submit the consolidated draft")
    draft_commands = draft.add_subparsers(dest="draft_command", required=True)
    draft_prepare = draft_commands.add_parser("prepare")
    draft_prepare.add_argument("case_id")
    draft_submit = draft_commands.add_parser("submit")
    draft_submit.add_argument("case_id")
    draft_submit.add_argument("proposal", type=Path)

    export = commands.add_parser("export", help="Export separate author and editor reports")
    export.add_argument("case_id")
    export.add_argument("--out", type=Path, required=True)

    lookup = commands.add_parser("lookup", help="Manage individually approved scholarly queries")
    lookup_commands = lookup.add_subparsers(dest="lookup_command", required=True)
    # CASE is given in an audited review; otherwise lookups belong to the checked Hermes session.
    lookup_request = lookup_commands.add_parser("request")
    lookup_request.add_argument("case_id", nargs="?")
    lookup_request.add_argument("--provider", choices=["crossref", "openalex"], required=True)
    lookup_request.add_argument("--query", required=True)
    lookup_request.add_argument("--session")
    lookup_run = lookup_commands.add_parser("run")
    lookup_run.add_argument("case_id", nargs="?")
    lookup_run.add_argument("request_id")
    lookup_run.add_argument("--approval-statement")
    lookup_run.add_argument("--approval-file", type=Path)
    lookup_run.add_argument("--session")
    lookup_show = lookup_commands.add_parser("show")
    lookup_show.add_argument("case_id", nargs="?")
    lookup_show.add_argument("request_id")
    lookup_show.add_argument("--session")

    references = commands.add_parser(
        "references", help="Run an explicitly requested mechanical reference check"
    )
    reference_commands = references.add_subparsers(dest="reference_command", required=True)
    reference_check = reference_commands.add_parser("check")
    reference_check.add_argument("manuscript", nargs="?", type=Path)
    reference_check.add_argument("--case")
    reference_check.add_argument("--source-id", default="manuscript")
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

    segments = commands.add_parser(
        "segments", help="Draft and store the logical segments a review works through"
    )
    segment_commands = segments.add_subparsers(dest="segments_command", required=True)
    segments_propose = segment_commands.add_parser(
        "propose", help="draft logical segments from headings (a file, or an audited case)"
    )
    segments_propose.add_argument("manuscript", nargs="?", type=Path)
    segments_propose.add_argument("--supplement", action="append", default=[])
    segments_propose.add_argument("--case")
    segments_propose.add_argument(
        "--profile", action="append", default=[], help="a design profile the reviewer confirmed"
    )
    segments_propose.add_argument("--no-profile", action="store_true")
    segments_propose.add_argument("--confirmation", help="the reviewer's words confirming them")
    segments_propose.add_argument("--confirmation-file", type=Path)
    segments_propose.add_argument("--session")
    segments_set = segment_commands.add_parser("set", help="store a refined plan for a case")
    segments_set.add_argument("--case", required=True)
    segments_set.add_argument("plan", type=Path)

    scan = commands.add_parser("scan", help="Run a deep, segment-by-segment private scan")
    scan_commands = scan.add_subparsers(dest="scan_command", required=True)
    scan_start = scan_commands.add_parser("start")
    scan_start.add_argument("manuscript", type=Path)
    scan_start.add_argument("--supplement", action="append", default=[])
    scan_start.add_argument("--session")
    scan_start.add_argument(
        "--profile", action="append", default=[], help="a design profile the reviewer confirmed"
    )
    scan_start.add_argument(
        "--no-profile", action="store_true", help="the reviewer confirmed that no profile fits"
    )
    scan_start.add_argument("--confirmation", help="the reviewer's words confirming the profiles")
    scan_start.add_argument("--confirmation-file", type=Path)
    scan_plan = scan_commands.add_parser("plan")
    scan_plan.add_argument("scan_id")
    scan_plan.add_argument("plan", type=Path)
    scan_plan.add_argument("--confirmation", help="the reviewer's words confirming the tiers")
    scan_plan.add_argument("--confirmation-file", type=Path)
    for name in ("next", "synthesize", "status"):
        scan_commands.add_parser(name).add_argument("scan_id")
    scan_candidate = scan_commands.add_parser("candidate")
    scan_candidate.add_argument("scan_id")
    scan_candidate.add_argument(
        "--reserve", action="store_true", help="only when the reviewer asks for further minors"
    )
    scan_submit = scan_commands.add_parser("submit")
    scan_submit.add_argument("scan_id")
    scan_submit.add_argument("proposal", type=Path)
    scan_sweep = scan_commands.add_parser("sweep")
    scan_sweep.add_argument("scan_id")
    scan_sweep.add_argument("sweep", type=Path)
    scan_overview = scan_commands.add_parser("overview")
    scan_overview.add_argument("scan_id")
    scan_overview.add_argument("overview", type=Path)
    scan_record = scan_commands.add_parser("record")
    scan_record.add_argument("scan_id")
    scan_record.add_argument("pool_id")
    scan_record.add_argument("disposition")
    scan_record.add_argument(
        "--words", required=True, help="the reviewer's reply, quoted from their message"
    )
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
    if args.command == "direct" and args.direct_command == "prepare-export":
        return prepare_direct_export(args.session)
    if args.command == "direct" and args.direct_command == "finalize":
        return finalize_direct_export(args.export_id, args.profile)
    if args.command == "session" and args.session_command == "start":
        return start_session(args.profile, live=not args.skip_live)
    if args.command == "receipts":
        if args.receipt_command == "verify":
            return verify_receipt(args.receipt, args.sums)
        if args.receipt_command == "sums":
            return installed_identity()
    if args.command == "case":
        if args.case_command == "create":
            return create_case(
                Path(args.manuscript),
                journal=args.journal,
                title=args.title,
                language=args.language,
                supplements=_paths(args.supplement),
                guidelines=_paths(args.guideline),
                review_forms=_paths(args.review_form),
            )
        if args.case_command == "status":
            return case_status(args.case_id)
        if args.case_command == "attest":
            statement = read_statement(args.statement, args.statement_file)
            return attest_case(args.case_id, statement)
        if args.case_command == "purge":
            return purge_case(args.case_id, args.confirm)
    if args.command == "source":
        require_review_access(args.case_id)
        if args.source_command == "list":
            return {"case_id": args.case_id, "sources": list_sources(args.case_id)}
        if args.source_command == "read":
            return read_locator(args.case_id, args.source_id, args.locator)
        if args.source_command == "find":
            return {
                "case_id": args.case_id,
                "matches": find_source(
                    args.case_id, args.words, source_id=args.source_id, limit=args.limit
                ),
            }
    if args.command == "review":
        if args.review_command == "start":
            return start_review(args.case_id, args.profile)
        if args.review_command == "status":
            return review_status(args.case_id)
        if args.review_command == "batch-start":
            return start_batch(args.case_id, args.limit)
        if args.review_command == "next":
            return next_item(args.case_id)
    if args.command == "finding":
        require_review_access(args.case_id)
        if args.finding_command == "submit":
            return submit_findings(args.case_id, args.proposal)
        if args.finding_command == "list":
            return {
                "case_id": args.case_id,
                "findings": list_findings(
                    args.case_id,
                    include_dismissed=args.include_dismissed,
                    status=args.status,
                ),
            }
        if args.finding_command == "next":
            return next_finding(args.case_id)
        if args.finding_command == "prepare-response":
            return prepare_finding_response(args.case_id, args.finding_id)
        if args.finding_command == "respond":
            return respond_finding(args.case_id, args.finding_id, args.proposal)
        if args.finding_command == "prepare-revision":
            return prepare_finding_revision(args.case_id, args.finding_id)
        if args.finding_command == "revise":
            return revise_finding(args.case_id, args.finding_id, args.proposal)
        if args.finding_command == "dismiss":
            reason = read_statement(args.reason, args.reason_file)
            return dismiss_finding(args.case_id, args.finding_id, reason)
    if args.command == "draft":
        require_review_access(args.case_id)
        if args.draft_command == "prepare":
            return prepare_draft(args.case_id)
        if args.draft_command == "submit":
            return submit_draft(args.case_id, args.proposal)
    if args.command == "export":
        require_review_access(args.case_id)
        return export_review(args.case_id, args.out)
    if args.command == "lookup":
        if args.case_id:
            require_review_access(args.case_id)
        if args.lookup_command == "request":
            return create_lookup(args.case_id, args.provider, args.query, session=args.session)
        if args.lookup_command == "run":
            return run_lookup(
                args.case_id,
                args.request_id,
                approval_statement=args.approval_statement,
                approval_file=args.approval_file,
                session=args.session,
            )
        if args.lookup_command == "show":
            return show_lookup(args.case_id, args.request_id, session=args.session)
    if args.command == "references":
        if args.reference_command == "check":
            if args.case:
                require_review_access(args.case)
            report = check_references(args.manuscript, case_id=args.case, source_id=args.source_id)
            if args.case:
                report["candidate_findings"] = import_reference_issues(args.case, report)
            return report
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
    if args.command == "segments":
        if args.segments_command == "propose":
            if args.case:
                return propose_case_plan(args.case)
            if not args.manuscript:
                raise ReviewError("give a manuscript file or --case CASE")
            if not args.profile and not args.no_profile:
                raise ReviewError(
                    "propose the design profiles to the reviewer and wait for their reply first; "
                    "then run this with --profile NAME (or --no-profile) and --confirmation "
                    '"THEIR WORDS"'
                )
            confirmed = confirm_profiles(
                [] if args.no_profile else args.profile,
                read_statement(args.confirmation, args.confirmation_file),
                args.session,
            )
            files = [("manuscript", args.manuscript)] + [
                (f"supplement-{i}", Path(p)) for i, p in enumerate(args.supplement, start=1)
            ]
            return confirmed | draft_plan(
                [
                    {"source_id": sid, "segments": parse_document(path).segments}
                    for sid, path in files
                ]
            )
        if args.segments_command == "set":
            return set_case_plan(args.case, args.plan)
    if args.command == "scan":
        command = args.scan_command
        if command == "start":
            if not args.profile and not args.no_profile:
                raise ReviewError(
                    "name the confirmed design profiles with --profile, or pass --no-profile"
                )
            return start_scan(
                args.manuscript,
                _paths(args.supplement),
                args.session,
                profiles=args.profile,
                confirmation=read_statement(args.confirmation, args.confirmation_file),
            )
        if command == "plan":
            return set_plan(
                args.scan_id,
                args.plan,
                read_statement(args.confirmation, args.confirmation_file) or None,
            )
        if command == "next":
            return next_task(args.scan_id)
        if command == "submit":
            return submit_task(args.scan_id, args.proposal)
        if command == "synthesize":
            return synthesize(args.scan_id)
        if command == "sweep":
            return sweep(args.scan_id, args.sweep)
        if command == "overview":
            return set_overview(args.scan_id, args.overview)
        if command == "candidate":
            return next_candidate(args.scan_id, reserve=args.reserve)
        if command == "status":
            return scan_status(args.scan_id)
        if command == "record":
            return record_response(args.scan_id, args.pool_id, args.disposition, args.words)
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
        if args.hermes_command == "install":
            return install_skill(
                args.profile, apply=args.apply, replace_unmanaged=args.replace_unmanaged
            )
        if args.hermes_command == "doctor":
            report = inspect_profile(args.profile, live=not args.skip_live)
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
