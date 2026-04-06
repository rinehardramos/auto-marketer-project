"""Command-line interface for auto-marketer."""
from __future__ import annotations

import argparse
import sys

from auto_marketer import db, exporter, sender as sender_mod
from auto_marketer.email_generator import generate_batch
from auto_marketer.info_broker_client import InfoBrokerClient


def _cmd_campaign_create(args: argparse.Namespace) -> int:
    db.setup()
    cid = db.create_campaign(args.name, args.tone, args.goal)
    print(f"created campaign id={cid}")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    db.setup()
    campaign = db.get_campaign(args.campaign_id)
    if not campaign:
        print(f"campaign {args.campaign_id} not found", file=sys.stderr)
        return 2
    broker = InfoBrokerClient()
    profiles = broker.list_profiles(status=args.status, limit=args.limit)
    print(f"fetched {len(profiles)} profiles from info-broker")
    results = generate_batch(profiles, workers=args.workers, tone=campaign["tone"], goal=campaign["goal"])
    ok = fail = 0
    for r in results:
        prof = r["profile"] or {}
        prof_id = str(prof.get("id") or prof.get("profile_id") or "")
        did = db.save_draft(
            args.campaign_id,
            prof_id,
            r["recipient_email"],
            r["recipient_name"],
            r["subject"],
            r["body"],
        )
        if r["ok"]:
            ok += 1
        else:
            fail += 1
            db.mark_failed(did, r["error"] or "unknown")
    db.update_campaign_status(args.campaign_id, "ready")
    print(f"generated={ok} failed={fail}")
    return 0


def _cmd_send(args: argparse.Namespace) -> int:
    db.setup()
    if not db.get_campaign(args.campaign_id):
        print(f"campaign {args.campaign_id} not found", file=sys.stderr)
        return 2
    impl = sender_mod.build_sender(args.provider)
    counts = sender_mod.send_campaign(
        args.campaign_id,
        impl,
        rate_limit_per_min=args.rate_limit,
        dry_run=args.provider == "dry-run",
    )
    print(f"sent={counts['sent']} failed={counts['failed']} skipped={counts['skipped']}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    db.setup()
    if not db.get_campaign(args.campaign_id):
        print(f"campaign {args.campaign_id} not found", file=sys.stderr)
        return 2
    payload, _ctype, default_name = exporter.export_campaign(args.campaign_id, args.format)
    out = args.output or default_name
    with open(out, "wb") as f:
        f.write(payload)
    print(f"wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="auto-marketer", description="Auto Marketer CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    cc = sub.add_parser("campaign", help="Campaign management")
    cc_sub = cc.add_subparsers(dest="subcmd", required=True)
    cc_create = cc_sub.add_parser("create", help="Create a new campaign")
    cc_create.add_argument("--name", required=True)
    cc_create.add_argument("--tone", default="professional")
    cc_create.add_argument("--goal", required=True)
    cc_create.set_defaults(func=_cmd_campaign_create)

    gen = sub.add_parser("generate", help="Generate drafts for a campaign")
    gen.add_argument("--campaign-id", type=int, required=True)
    gen.add_argument("--limit", type=int, default=50)
    gen.add_argument("--status", default="completed")
    gen.add_argument("--workers", type=int, default=3)
    gen.set_defaults(func=_cmd_generate)

    snd = sub.add_parser("send", help="Send drafts in a campaign")
    snd.add_argument("--campaign-id", type=int, required=True)
    snd.add_argument("--provider", choices=["dry-run", "smtp", "noop"], default="dry-run")
    snd.add_argument("--rate-limit", type=int, default=30)
    snd.set_defaults(func=_cmd_send)

    exp = sub.add_parser("export", help="Export campaign drafts to a file")
    exp.add_argument("--campaign-id", type=int, required=True)
    exp.add_argument("--format", choices=["csv", "xlsx", "json"], default="csv")
    exp.add_argument("--output")
    exp.set_defaults(func=_cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
