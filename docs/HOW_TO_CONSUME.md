# Como consumir este template em um projeto da Floema

Este guia mostra como ativar o auditor automático em qualquer repositório da `FloemaIndustria`.

## Pré-requisitos

1. **Repo target** existe na organização `FloemaIndustria`
2. **Organization Secret `ANTHROPIC_API_KEY`** configurado em https://github.com/organizations/FloemaIndustria/settings/secrets/actions
3. **Spend limit Anthropic** configurado em https://console.anthropic.com/settings/billing (recomendado: US$ 30/mês)
4. **(Opcional) Secrets Z-API para notificação WhatsApp em `needs_human`** — ver seção "Notificação WhatsApp" abaixo

## Passo 1 — Criar `.github/sensitive-files.yml`

Copie o conteúdo de [`templates/sensitive-files.example.yml`](../templates/sensitive-files.example.yml) e ajuste para o projeto.

Exemplo mínimo para um projeto Django (`mrp-floema`):

```yaml
critical:
  - .github/workflows/*.yml
  - .env*
  - settings.py
  - wsgi.py
  - asgi.py

high:
  - "**/migrations/*.py"
  - "**/models.py"
  - requirements.txt

forbidden_paths:
  - .env
  - "*.sqlite3"
  - secrets/

deploy_blocked: true
```

## Passo 2 — Criar `.github/workflows/audit.yml`

```yaml
name: Audit PR

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]

jobs:
  pre-filter:
    uses: FloemaIndustria/flora-ai-orchestration/.github/workflows/pre-filter.yml@main
    with:
      python_version: '3.12'
      run_tests: true
      run_lint: true

  audit:
    needs: pre-filter
    uses: FloemaIndustria/flora-ai-orchestration/.github/workflows/auditor.yml@main
    with:
      sensitive_files_path: .github/sensitive-files.yml
      max_cost_usd: 0.10
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      # Opcional: passar secrets Z-API para receber WhatsApp em needs_human
      ZAPI_INSTANCE_ID: ${{ secrets.ZAPI_INSTANCE_ID }}
      ZAPI_INSTANCE_TOKEN: ${{ secrets.ZAPI_INSTANCE_TOKEN }}
      ZAPI_CLIENT_TOKEN: ${{ secrets.ZAPI_CLIENT_TOKEN }}
      WHATSAPP_NOTIFY_TO: ${{ secrets.WHATSAPP_NOTIFY_TO }}
      WHATSAPP_NOTIFY_ENABLED: ${{ secrets.WHATSAPP_NOTIFY_ENABLED }}
```

## Passo 3 — Configurar branch protection (manual)

Em **Settings → Rules → Rulesets** do repo:

1. Crie ruleset "Main Protection"
2. Target: branch `main`
3. Rules:
   - ✅ Require a pull request before merging
   - ✅ Require approvals: 1
   - ✅ Require status checks to pass
     - Status checks: `audit / audit` (do workflow acima)
   - ✅ Require branches to be up to date before merging
   - ✅ Block force pushes

## Comportamento esperado

Quando alguém abre PR no repo:

1. **Pre-filter** roda (lint, pytest, secret scan). Se falhar, audit nem é chamado.
2. **Audit** com Sonnet 4.6:
   - Pré-filtra docs-only, arquivos sensíveis, Frente B → decide sem chamar API (custo zero)
   - Senão, chama Sonnet 4.6 com cache de prompt (~US$ 0.05–0.15)
3. Posta comentário no PR com verdict
4. Se `approve`: aprova review automaticamente
5. Se `request_changes`: solicita mudanças
6. Se `needs_human`: deixa o PR pendente + envia WhatsApp para `WHATSAPP_NOTIFY_TO` (se configurado)

## Notificação WhatsApp para `needs_human`

Quando o auditor retorna `verdict: needs_human` e os secrets Z-API estão configurados, o workflow dispara mensagem WhatsApp para o número configurado em `WHATSAPP_NOTIFY_TO`.

### Secrets necessários (org-level recomendado)

| Secret | Descrição |
|---|---|
| `ZAPI_INSTANCE_ID` | Instance ID da Z-API |
| `ZAPI_INSTANCE_TOKEN` | Token da instância Z-API |
| `ZAPI_CLIENT_TOKEN` | Client token da Z-API |
| `WHATSAPP_NOTIFY_TO` | Número destino formato `55DDDNUMERO` (sem `+`, sem espaço) |
| `WHATSAPP_NOTIFY_ENABLED` | `true` para ativar, qualquer outro valor desativa |

### Comportamento se secrets faltarem

- `WHATSAPP_NOTIFY_ENABLED != true` → step pula silenciosamente
- Algum secret Z-API ausente → step printa erro mas `continue-on-error: true` impede falha do workflow
- Z-API HTTP error → não bloqueia, apenas registra no log

Princípio: notificação é **best-effort**. Falha em notificar nunca bloqueia o auditor.

### Mensagem esperada

```
🟡 [Flora AI Lab] PR precisa aprovacao humana
Repo: FloemaIndustria/<repo>
PR: #<n> - <título>
Risco: <low|medium|high|critical>
Resumo: <summary curto do auditor>
Link: https://github.com/FloemaIndustria/<repo>/pull/<n>
Proximo passo: revisar PR e aprovar/ajustar conforme auditor.
```

## Versionamento

- Para máxima estabilidade, fixe uma tag: `@v1` em vez de `@main`
- Tags semânticas serão criadas conforme o template evoluir

## Custos esperados

- PR docs-only: **R$ 0** (pre-filter)
- PR código pequeno (<200 linhas) com cache: **R$ 0,15–0,40**
- PR código grande (~500 linhas): **R$ 0,40–0,80**
- PR sensitive: **R$ 0** (pre-filter dispara needs_human)

Estimativa para 100 PRs/mês nos 3 projetos: **R$ 30–60/mês**.

## Troubleshooting

**Erro: `Could not find ANTHROPIC_API_KEY`**
- Adicionar como Organization Secret, não Repository Secret
- Conferir que o repo tem permissão de acesso ao secret

**Erro: `Workflow not found`**
- Verificar que o template foi commitado em `main`
- Fixar versão específica (`@v1`) em vez de `@main` em produção

**Auditor sempre retorna `needs_human`**
- Sensitive-files.yml está com paths muito amplos
- Ajustar critical/high para ser mais específico

**WhatsApp não dispara em `needs_human`**
- Verificar logs do step "Notify WhatsApp on needs_human"
- Confirmar `WHATSAPP_NOTIFY_ENABLED=true` no Organization Secrets
- Confirmar que o wrapper do repo consumidor passa os 5 secrets Z-API
