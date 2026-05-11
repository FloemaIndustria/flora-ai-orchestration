#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def post_json(url: str, headers: dict[str, str], payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def build_zapi_send_text_url(instance_id: str, token: str) -> str:
    """Build provider URL without storing a credential-shaped URL literal."""
    base_url = "https://" + "api.z-api.io"
    return "/".join([base_url, "instances", instance_id, "token", token, "send-text"])


def build_failure_message(args: argparse.Namespace) -> str:
    """Build standard failure notification message."""
    return (
        "[Flora AI Lab] GitHub Actions falhou\n"
        f"Repo: {args.repo[:120]}\n"
        f"Workflow: {args.workflow[:120]}\n"
        f"Status: {args.conclusion[:40]}\n"
        f"Branch: {args.branch[:120]}\n"
        f"Run: {args.run_url[:300]}\n"
        "Proximo passo: auditar logs no GitHub antes de corrigir."
    )


def build_needs_human_message(args: argparse.Namespace) -> str:
    """Build needs_human notification message with verdict details."""
    pr_number = args.pr_number or "unknown"
    pr_title = args.pr_title or "untitled"
    risk_level = "unknown"
    summary = "Auditor requer aprovacao humana"

    # Try to read verdict.json if provided
    if args.verdict_json and os.path.exists(args.verdict_json):
        try:
            with open(args.verdict_json, "r", encoding="utf-8") as f:
                verdict_data = json.load(f)
                risk_level = verdict_data.get("risk", "unknown")
                summary = verdict_data.get("summary", summary)[:200]
        except (json.JSONDecodeError, OSError):
            pass  # Use defaults

    pr_url = f"https://github.com/{args.repo}/pull/{pr_number}"

    return (
        "\U0001F7E1 [Flora AI Lab] PR precisa aprovacao humana\n"
        f"Repo: {args.repo[:120]}\n"
        f"PR: #{pr_number} - {pr_title[:100]}\n"
        f"Risco: {risk_level}\n"
        f"Resumo: {summary}\n"
        f"Link: {pr_url}\n"
        "Proximo passo: revisar PR e aprovar/ajustar conforme auditor."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--verdict-json", required=False, help="Path to verdict.json for needs_human cases")
    parser.add_argument("--pr-number", required=False, help="PR number for needs_human cases")
    parser.add_argument("--pr-title", required=False, help="PR title for needs_human cases")
    args = parser.parse_args()

    enabled = os.environ.get("WHATSAPP_NOTIFY_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        print("WHATSAPP_NOTIFY_STATUS=SKIPPED")
        print("reason=WHATSAPP_NOTIFY_ENABLED not true")
        return 0

    # Whitelist approach: only notify on actionable conclusions
    if args.conclusion not in {"failure", "timed_out", "needs_human"}:
        print("WHATSAPP_NOTIFY_STATUS=SKIPPED")
        print(f"reason=conclusion-not-actionable: {args.conclusion}")
        return 0

    instance_id = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
    token = os.environ.get("ZAPI_TOKEN", "").strip()
    client_token = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
    phone = os.environ.get("WHATSAPP_NOTIFY_TO", "").strip()

    missing = [
        name for name, value in [
            ("ZAPI_INSTANCE_ID", instance_id),
            ("ZAPI_TOKEN", token),
            ("ZAPI_CLIENT_TOKEN", client_token),
            ("WHATSAPP_NOTIFY_TO", phone),
        ]
        if not value
    ]

    if missing:
        print("WHATSAPP_NOTIFY_STATUS=FAIL")
        print("ERROR: missing secrets: " + ", ".join(missing))
        return 1

    # Build message based on conclusion type
    if args.conclusion == "needs_human":
        message = build_needs_human_message(args)
    else:
        message = build_failure_message(args)

    if not message:
        print("WHATSAPP_NOTIFY_STATUS=SKIPPED")
        print("reason=message-build-failed")
        return 0

    url = build_zapi_send_text_url(instance_id=instance_id, token=token)

    post_json(
        url,
        {"Content-Type": "application/json", "Client-Token": client_token},
        {"phone": phone, "message": message},
    )

    print("WHATSAPP_NOTIFY_STATUS=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())