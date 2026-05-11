# SPEC — WhatsApp Notifier para `needs_human`

**Status**: proposta
**Owner**: Humberto Pinto Jr.
**Autor**: Consultor Claude Desktop (Flora AI Lab)
**Data**: 11/05/2026
**Versão**: 1.0

---

## Problema

Quando o auditor Sonnet 4.6 retorna `verdict: "needs_human"` em um PR, o único canal de aviso hoje é o email do GitHub (via @mention do bot). Humberto desligou notificação de email por excesso de spam — consequência: **PRs em `needs_human` ficam parados sem aviso**.

O workflow `whatsapp_failure_notify.yml` no `flora-dspy-lab` já notifica via WhatsApp, **mas apenas para falhas de workflows DSPy específicos**. Não escuta o auditor Sonnet, e não cobre os outros 3 repos.

## Objetivo

Notificar Humberto via WhatsApp (Z-API) quando o auditor retornar `needs_human` em qualquer PR de qualquer repo consumidor do template `flora-ai-orchestration`.

Out of scope (fica pra depois):
- Notificar `failure`/`timed_out` de workflows não-auditor nos repos `flora-2.0` e `mrp-floema`
- Filtrar `cancelled` no notifier existente do `flora-dspy-lab`
- Renomear/consolidar o notifier antigo do `flora-dspy-lab`

## Solução

### Arquitetura

Adicionar step final no reusable workflow `auditor.yml` que dispara apenas se `verdict == 'needs_human'`. Reusa o script `whatsapp_failure_notify.py` existente no `flora-dspy-lab` (que já tem `build_needs_human_message` pronto) — copiado pro `flora-ai-orchestration` e renomeado pra `whatsapp_notify.py`.

```
PR aberto → pre-filter → auditor Sonnet → verdict.json
                              ↓
                  steps.audit.outputs.verdict
                              ↓
              if verdict == 'needs_human':
                  step: chama whatsapp_notify.py → Z-API → WhatsApp Humberto
```

### Mudanças

1. **Novo arquivo**: `scripts/whatsapp_notify.py` (cópia adaptada de `flora-dspy-lab/scripts/whatsapp_failure_notify.py`)
2. **Modificar**: `.github/workflows/auditor.yml`
   - Declarar 4 secrets opcionais (`ZAPI_INSTANCE_ID`, `ZAPI_INSTANCE_TOKEN`, `ZAPI_CLIENT_TOKEN`, `WHATSAPP_NOTIFY_TO`)
   - Adicionar step final condicional `if: steps.audit.outputs.verdict == 'needs_human'`
   - Mapear `ZAPI_INSTANCE_TOKEN` (nome do org secret) → `ZAPI_TOKEN` (nome esperado pelo script)
3. **Modificar**: `docs/HOW_TO_CONSUME.md`
   - Documentar secrets opcionais para WhatsApp
   - Atualizar comportamento "fase 2 do template" → "ativo"

### Secrets necessários (org-level)

| Secret | Status |
|---|---|
| `ZAPI_INSTANCE_ID` | ✅ já existe org-level |
| `ZAPI_INSTANCE_TOKEN` | ✅ já existe org-level |
| `ZAPI_CLIENT_TOKEN` | ✅ já existe org-level |
| `WHATSAPP_NOTIFY_TO` | criado em 11/05/2026 pelo Humberto |
| `WHATSAPP_NOTIFY_ENABLED` | criado em 11/05/2026 pelo Humberto |

### Mensagem WhatsApp esperada

```
🟡 [Flora AI Lab] PR precisa aprovacao humana
Repo: FloemaIndustria/flora-2.0
PR: #4 - feat: instrumentar tools_count
Risco: high
Resumo: Patch toca agent.py (critical). Auditor pede revisão humana.
Link: https://github.com/FloemaIndustria/flora-2.0/pull/4
Proximo passo: revisar PR e aprovar/ajustar conforme auditor.
```

### Comportamento de erro

- Se `WHATSAPP_NOTIFY_ENABLED != true`: step pula silenciosamente (não bloqueia auditor)
- Se algum secret falta: step printa "WHATSAPP_NOTIFY_STATUS=FAIL" + lista secrets faltando, mas NÃO falha o workflow (`continue-on-error: true`)
- Z-API HTTP 5xx: script imprime erro, step não bloqueia

Princípio: notificação é **best-effort**. Falha em notificar nunca bloqueia o auditor.

## Critérios de aceitação

1. PR em qualquer repo consumidor que dispare `needs_human` gera mensagem WhatsApp pro `WHATSAPP_NOTIFY_TO`
2. PR com verdict `approve` ou `request_changes` NÃO gera WhatsApp
3. Repo sem secrets Z-API configurados ainda funciona (auditor não quebra)
4. Mensagem inclui: repo, PR#, título, risk, summary curto, link

## Custos

- Implementação: ~$0,02 (auditor revisa este PR)
- Operação: $0 (Z-API é assinatura mensal, sem custo por mensagem)

## Rollback

Reverter PR. Sem migração de dados, sem efeito persistente.

## Próximos passos pós-merge

1. Testar com PR de teste no `flora-2.0` que force `needs_human` (alterar `.github/workflows/audit-sonnet.yml` ou tocar arquivo critical)
2. Após validação, Humberto pode desligar definitivamente email do "Participating, @mentions and custom"
3. Considerar (fora desta SPEC): expandir notifier pra cobrir `failure`/`timed_out` de qualquer workflow do auditor
