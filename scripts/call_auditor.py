#!/usr/bin/env python3
"""
call_auditor.py — invoca Claude Sonnet 4.6 para auditar PR.

Fluxo:
1. Lê diff, PR metadata, sensitive-files.yml, prompt do auditor
2. Pré-filtra: docs-only → approve direto SEM chamar API
3. Pré-filtra: arquivos sensíveis → needs_human SEM chamar API
4. Senão: chama Anthropic API com prompt caching
5. Valida resposta JSON
6. Escreve verdict.json + comment.md + define output do step
"""
import argparse
import json
import os
import sys
import fnmatch
from pathlib import Path

import yaml
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"
# Pricing (USD per 1M tokens, May 2026): input $3, cache_read $0.30, output $15
PRICE_INPUT = 3.0 / 1_000_000
PRICE_CACHE_READ = 0.30 / 1_000_000
PRICE_OUTPUT = 15.0 / 1_000_000


def matches_any(path: str, patterns: list) -> bool:
    """Path matches any glob pattern."""
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def extract_files_from_diff(diff_text: str) -> list:
    """Extrai paths dos arquivos modificados de um git diff."""
    files = []
    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            parts = line.split(" ")
            if len(parts) >= 4:
                path = parts[2][2:] if parts[2].startswith("a/") else parts[2]
                files.append(path)
    return files


def pre_filter(files: list, sensitive: dict):
    """
    Pré-filtros que evitam chamada à API.
    Retorna verdict dict se decidir, None se precisa chamar a API.
    """
    # Docs-only fast path
    if files and all(
        f.endswith((".md", ".txt")) or f.startswith("docs/") for f in files
    ):
        return {
            "verdict": "approve",
            "spec_compliance": "not_applicable",
            "spec_violations": [],
            "guardrail_violations": [],
            "sensitive_files_touched": [],
            "test_coverage_assessment": "not_applicable",
            "estimated_risk": "low",
            "diff_size_lines": 0,
            "summary": "Docs-only PR: aprovado automaticamente sem chamada à API.",
            "actionable_items": [],
            "reasoning": "Pre-filter: 100% dos arquivos modificados são markdown/texto/docs.",
            "_pre_filtered": True,
        }

    # Critical sensitive files
    critical = sensitive.get("critical", [])
    touched_critical = [f for f in files if matches_any(f, critical)]
    if touched_critical:
        return {
            "verdict": "needs_human",
            "spec_compliance": "not_applicable",
            "spec_violations": [],
            "guardrail_violations": [
                f"{f} — arquivo crítico, requer aprovação humana"
                for f in touched_critical
            ],
            "sensitive_files_touched": touched_critical,
            "test_coverage_assessment": "not_applicable",
            "estimated_risk": "critical",
            "diff_size_lines": 0,
            "summary": f"PR toca {len(touched_critical)} arquivo(s) crítico(s). Aprovação humana obrigatória.",
            "actionable_items": ["Aguardar revisão manual do Humberto"],
            "reasoning": "Pre-filter: arquivo em sensitive_files.critical sempre dispara needs_human.",
            "_pre_filtered": True,
        }

    # Frente B blocked (flora-2.0)
    if sensitive.get("frente_b_blocked"):
        frente_b = sensitive.get("frente_b_paths", [])
        touched_b = [f for f in files if matches_any(f, frente_b)]
        if touched_b:
            return {
                "verdict": "needs_human",
                "spec_compliance": "not_applicable",
                "spec_violations": [],
                "guardrail_violations": [
                    f"{f} — Frente B bloqueada" for f in touched_b
                ],
                "sensitive_files_touched": touched_b,
                "test_coverage_assessment": "not_applicable",
                "estimated_risk": "high",
                "diff_size_lines": 0,
                "summary": "Frente B (agent.py, prompts) bloqueada até conclusão do DSPy optimizer.",
                "actionable_items": [
                    "Aguardar conclusão do DSPy lab",
                    "Ou liberar Frente B manualmente removendo frente_b_blocked do sensitive-files.yml",
                ],
                "reasoning": "Pre-filter: frente_b_blocked=true e PR toca paths de Frente B.",
                "_pre_filtered": True,
            }

    return None


def call_anthropic(
    prompt_system: str,
    diff: str,
    pr_meta: dict,
    sensitive: dict,
    max_cost_usd: float,
):
    """
    Chama Sonnet 4.6 com cache do system prompt.
    Retorna (verdict_dict, usage_dict).
    """
    client = Anthropic()

    user_content = f"""# PR Metadata

Title: {pr_meta.get('title', 'unknown')}
Author: {pr_meta.get('author', 'unknown')}
Files changed: {pr_meta.get('changedFiles', '?')}
Lines added: +{pr_meta.get('additions', '?')}
Lines deleted: -{pr_meta.get('deletions', '?')}

Body:
{pr_meta.get('body', '(empty)')}

# Sensitive files config (this project)

```yaml
{yaml.safe_dump(sensitive, allow_unicode=True)}
```

# Diff

```diff
{diff[:80000]}
```

Processe o PR conforme as regras do system prompt e retorne EXCLUSIVAMENTE o JSON.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": prompt_system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_creation_tokens": getattr(
            response.usage, "cache_creation_input_tokens", 0
        ),
    }
    cost = (
        usage["input_tokens"] * PRICE_INPUT
        + usage["cache_read_tokens"] * PRICE_CACHE_READ
        + usage["output_tokens"] * PRICE_OUTPUT
    )
    usage["estimated_cost_usd"] = round(cost, 4)

    if cost > max_cost_usd:
        print(
            f"::warning::Cost {cost:.4f} exceeded cap {max_cost_usd}", file=sys.stderr
        )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        verdict = json.loads(text)
    except json.JSONDecodeError as e:
        verdict = {
            "verdict": "needs_human",
            "spec_compliance": "not_applicable",
            "spec_violations": [],
            "guardrail_violations": ["Auditor returned invalid JSON"],
            "sensitive_files_touched": [],
            "test_coverage_assessment": "not_applicable",
            "estimated_risk": "high",
            "diff_size_lines": 0,
            "summary": f"Auditor JSON parse error: {e}",
            "actionable_items": ["Revisão manual necessária"],
            "reasoning": f"Resposta crua: {text[:500]}",
        }

    return verdict, usage


def format_comment(verdict: dict, usage) -> str:
    """Markdown comment para postar no PR."""
    emoji = {
        "approve": "✅",
        "request_changes": "🔴",
        "needs_human": "🟡",
    }.get(verdict["verdict"], "❓")

    risk_emoji = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }.get(verdict.get("estimated_risk", "medium"), "⚪")

    lines = [
        f"## {emoji} Auditor Sonnet 4.6 — `{verdict['verdict']}`",
        "",
        f"**Resumo:** {verdict.get('summary', '(sem resumo)')}",
        "",
        f"**Risco:** {risk_emoji} `{verdict.get('estimated_risk', '?')}`",
        "",
    ]

    if verdict.get("sensitive_files_touched"):
        lines.append("**Arquivos sensíveis tocados:**")
        for f in verdict["sensitive_files_touched"]:
            lines.append(f"- `{f}`")
        lines.append("")

    if verdict.get("spec_violations"):
        lines.append("**Violações de SPEC:**")
        for v in verdict["spec_violations"]:
            lines.append(f"- {v}")
        lines.append("")

    if verdict.get("guardrail_violations"):
        lines.append("**Violações de guardrail:**")
        for v in verdict["guardrail_violations"]:
            lines.append(f"- {v}")
        lines.append("")

    if verdict.get("actionable_items"):
        lines.append("**Próximos passos:**")
        for item in verdict["actionable_items"]:
            lines.append(f"- [ ] {item}")
        lines.append("")

    lines.append("---")
    if verdict.get("_pre_filtered"):
        lines.append("*Decidido por pré-filtro (sem chamada ao Sonnet — custo zero).*")
    elif usage:
        lines.append(
            f"*Sonnet 4.6 — input: {usage['input_tokens']}, "
            f"cache_read: {usage['cache_read_tokens']}, "
            f"output: {usage['output_tokens']} tokens. "
            f"Custo estimado: US$ {usage['estimated_cost_usd']:.4f}.*"
        )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", required=True)
    ap.add_argument("--pr-meta", required=True)
    ap.add_argument("--sensitive", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-cost-usd", type=float, default=0.10)
    ap.add_argument("--output", default="verdict.json")
    ap.add_argument("--comment-output", default="comment.md")
    args = ap.parse_args()

    diff_text = Path(args.diff).read_text(encoding="utf-8", errors="replace")
    pr_meta = json.loads(Path(args.pr_meta).read_text(encoding="utf-8"))
    sensitive = yaml.safe_load(Path(args.sensitive).read_text(encoding="utf-8")) or {}
    prompt_system = Path(args.prompt).read_text(encoding="utf-8")

    files = extract_files_from_diff(diff_text)
    print(f"Files in diff: {len(files)}", file=sys.stderr)

    pre = pre_filter(files, sensitive)
    if pre is not None:
        verdict = pre
        usage = None
    else:
        verdict, usage = call_anthropic(
            prompt_system, diff_text, pr_meta, sensitive, args.max_cost_usd
        )

    Path(args.output).write_text(json.dumps(verdict, indent=2, ensure_ascii=False))
    Path(args.comment_output).write_text(format_comment(verdict, usage))

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"verdict={verdict['verdict']}\n")
            f.write(f"risk={verdict.get('estimated_risk', 'unknown')}\n")

    print(f"Verdict: {verdict['verdict']} (risk={verdict.get('estimated_risk', '?')})")
    sys.exit(0)


if __name__ == "__main__":
    main()
