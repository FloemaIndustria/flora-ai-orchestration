---
name: flora-verdict-reviewer
description: Revisa meta-criticamente um verdict JSON já produzido pelo auditor Sonnet 4.6 em PR específico de um dos repos da Floema. ATIVAR APENAS quando TODAS as condições forem verdadeiras simultaneamente — (1) Humberto identifica um PR específico por número e repo, (2) o auditor automático já rodou e produziu verdict (não está pedindo auditoria nova), (3) Humberto pede validação/revisão/checagem do verdict ou cola o JSON do verdict para análise. NÃO ATIVAR para — perguntas conceituais sobre auditoria, discussões sobre prompt do auditor sem PR concreto, pedidos de auditoria manual de código, status geral de repos, dúvidas sobre custos do Sonnet, ou qualquer pedido sem PR específico identificado. Em caso de dúvida sobre trigger, NÃO ativar — perguntar a Humberto se ele quer revisão estruturada de verdict.
---

# Flora Verdict Reviewer

Skill para revisar de forma estruturada o verdict do auditor Sonnet 4.6 em qualquer PR dos 4 repos da Floema. Output determinístico em 3 categorias: ✅ acertou / ⚠️ erro parcial / ❌ erro sério, cada uma com plano de ação correspondente.

Esta skill NÃO faz auditoria de código (isso é função do auditor automático no GitHub Actions). Ela faz **meta-auditoria**: avalia se o auditor decidiu bem.

---

## Quando usar

Triggers explícitos:
- "Revisa o verdict do PR #X"
- "Auditor rodou no PR Y, o que achou?"
- "Sonnet aprovou/rejeitou — confere"
- "Valida essa auditoria"
- Humberto cola JSON de verdict sem comando

Triggers implícitos:
- Humberto menciona "primeira auditoria" ou "validar auditor" sem PR específico → perguntar qual PR
- Humberto fala em "recalibrar o auditor" → primeiro revisar verdict, depois propor recalibração

NÃO usar quando:
- PR ainda não rodou pelo auditor (não há verdict para revisar)
- Humberto pede auditoria de código diretamente (consultor pode auditar manualmente, mas é função diferente — usar `flora-repo-pulse` ou auditoria livre)
- Pedido sobre custo/billing do auditor (não é meta-auditoria)

---

## Inputs necessários

Antes de produzir o output, garanta que tem:

1. **Link do PR** ou número + repo (ex: "flora-dspy-lab #52")
2. **Verdict do auditor** — JSON estruturado com no mínimo:
   - `verdict`: `"approve"` | `"request_changes"` | `"needs_human"`
   - `risk_level`: `"low"` | `"medium"` | `"high"` | `"critical"`
   - `summary`: texto livre
   - `sensitive_files_touched`: lista
   - `frente_b_blocked`: bool (apenas flora-2.0)
   - `cost_usd`: float
3. **Diff do PR** (via GitHub MCP, ou Humberto cola)
4. **Sensitive files do repo** (`.github/sensitive-files.yml`)

Se faltar algum dos 4, pedir antes de revisar. Não inventar contexto.

Use GitHub MCP para puxar diff e arquivos quando disponível. Se MCP não estiver conectado, pedir a Humberto para colar.

---

## Critérios de avaliação

### ✅ ACERTOU (todos os 5 verdadeiros)

1. **Risco bem calibrado** — não chamou `critical` em algo trivial, nem aprovou algo sensível
2. **Detectou TODOS os arquivos sensíveis tocados** — cruzar `sensitive_files_touched` do verdict contra o diff real e contra o `sensitive-files.yml`
3. **Summary acionável e específico** — não genérico tipo "código parece bom" ou "mudanças razoáveis"
4. **Respeitou regra Frente A/B** — apenas para flora-2.0: se PR tocou path da Frente B, `frente_b_blocked: true` deve estar setado
5. **JSON estruturado válido** — todos os campos esperados presentes, tipos corretos

### ⚠️ ERRO PARCIAL (qualquer um verdadeiro, mas nenhum da lista ❌)

- Risco levemente errado mas direção correta (ex: marcou `medium` o que seria `low`)
- Summary vago mas verdict final OK
- Detectou maioria dos arquivos sensíveis mas perdeu 1 não-crítico
- JSON válido mas faltou um campo opcional

### ❌ ERRO SÉRIO (qualquer um verdadeiro)

- **Aprovou algo sensível** (false negative crítico) — `verdict: "approve"` em PR que toca arquivo `critical` do `sensitive-files.yml`
- **Bloqueou tudo trivial** (false positive massivo) — `verdict: "request_changes"` em PR docs-only ou typo fix
- **JSON inválido** — campo obrigatório ausente ou tipo errado, parse falha
- **Violou regra Frente B** — aprovou PR que toca `agent.py` ou `prompts.py` no flora-2.0 com `frente_b_blocked` ausente ou `false`
- **Perdeu arquivo crítico** — PR tocou arquivo listado em `critical:` do `sensitive-files.yml` e o auditor não detectou
- **Custo acima do hard cap** — `cost_usd > 0.10` (default) sem justificativa

---

## Formato de output

Sempre nesta estrutura, em markdown, em português:

```markdown
# Revisão do Verdict — [repo] PR #N

**Verdict do auditor**: `[approve|request_changes|needs_human]` | Risco: `[level]` | Custo: US$ [valor]
**Veredito do consultor**: ✅ Acertou | ⚠️ Erro parcial | ❌ Erro sério

## Análise por critério

| Critério | Status | Observação |
|---|---|---|
| Risco calibrado | ✅/⚠️/❌ | [...] |
| Detecção de sensíveis | ✅/⚠️/❌ | [...] |
| Summary acionável | ✅/⚠️/❌ | [...] |
| Frente A/B (se flora-2.0) | ✅/⚠️/❌/N/A | [...] |
| JSON válido | ✅/⚠️/❌ | [...] |

## O que o auditor acertou
- [ponto 1]
- [ponto 2]

## O que o auditor errou (se houver)
- [erro 1 com evidência específica do diff/yml]
- [erro 2]

## Decisão recomendada
[Uma das 3:]
- ✅ Aceitar verdict, prosseguir com ação que o verdict implica (merge / pedir aprovação humana / corrigir e refazer PR)
- ⚠️ Aceitar verdict mas ajustar prompt do auditor para próximo ciclo (descrever ajuste exato em `auditor-system.md`)
- ❌ Rejeitar verdict, abrir investigação de recalibração (descrever plano)

## Próximas ações concretas
- [ ] [ação 1, com link/comando se aplicável]
- [ ] [ação 2]

## Plano de recalibração (apenas se ❌)
**Tentativa atual**: [1 | 2 | 3]
- **Tentativa 1** — Ajustar `auditor-system.md`: [diff específico, com bloco antes/depois]
- **Tentativa 2** — Adaptar `call_auditor.py` para suportar GPT-5: [escopo da mudança]
- **Tentativa 3** — Ensemble Sonnet + GPT-5 com decisão consensual: [arquitetura]
```

---

## Regras de execução

1. **Não inventar conteúdo do diff.** Se não tem acesso ao diff (via MCP ou colado), pedir antes de revisar. Especulação aqui causa false positives no consultor.

2. **Cruzar sempre com `sensitive-files.yml` real.** Cada repo tem o seu. Não usar memória — ler do arquivo no momento da revisão.

3. **Frente A/B só vale para `flora-2.0`.** Para os outros 3 repos, marcar como `N/A` na tabela.

4. **Custo é hard constraint.** Se `cost_usd > 0.10` (default do template), marcar ❌ mesmo que o resto esteja perfeito. Hard caps existem por razão.

5. **Plano de recalibração só aparece em ❌.** Em ✅ ou ⚠️, omitir a seção.

6. **Numeração de tentativas é cumulativa.** Se Humberto já está na "tentativa 2" para o mesmo tipo de erro, a próxima recalibração é "tentativa 3". Consultar HANDOFF.md para histórico antes de propor.

7. **Após 3 tentativas falhas no mesmo tipo de erro**, escalar: parar de recalibrar prompt, propor mudança estrutural (modelo, arquitetura de pré-filtros, ou scope do auditor).

---

## Exemplo de uso

**Input do Humberto:**
> "Auditor rodou no PR #52 do flora-dspy-lab. Revisa o verdict."

**Fluxo:**
1. Verificar se tem GitHub MCP conectado.
2. Puxar PR #52: diff, arquivos tocados, verdict do auditor (comentário do bot no PR).
3. Ler `flora-dspy-lab/.github/sensitive-files.yml`.
4. Aplicar os 5 critérios.
5. Produzir output no formato padrão.
6. Se ✅: registrar no HANDOFF.md "auditor validado em PR #52, prosseguir".
7. Se ⚠️ ou ❌: propor diff específico em `auditor-system.md` ou plano estrutural.

---

## Interação com outras skills

- **Após revisão ✅**: oferecer rodar `flora-handoff-updater` para registrar a validação.
- **Após revisão ❌ tentativa 3**: oferecer rodar `flora-repo-pulse` no `flora-ai-orchestration` para avaliar se o problema é estrutural (prompt do auditor) ou sistêmico (modelo).
- **Nunca chamar** `flora-spec-writer` daqui — escopo diferente.

---

## Versionamento

```
# Versão: 1.2 (2026-05-10)
# Changelog:
#   - v1.2: Correção de enum. `verdict` ∈ {approve, request_changes, needs_human}. Removido `reject` (legacy bug do HANDOFF v2.0). Identificado pelo próprio auditor Sonnet na primeira execução real (PR #53 do flora-dspy-lab, custo US$ 0.0247).
#   - v1.1: Description restritiva — trigger exige 3 condições simultâneas (PR específico + verdict produzido + pedido de revisão). Default em ambiguidade = não ativar. Skill projetada para uso raro mas crítico.
#   - v1.0: Bootstrap inicial. Critérios derivados do HANDOFF v2.0 do Flora AI Lab.
```

Mudanças nesta skill devem ser commitadas em `flora-ai-orchestration/skills/flora-verdict-reviewer/SKILL.md` e o changelog atualizado.
