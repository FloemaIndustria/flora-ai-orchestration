# SPEC: relax workflow auto-approve for trivial changes

**Status**: implemented (prompt change)
**Owner**: Humberto Pinto Jr
**Refs**: flora-dspy-lab PR #64 (caso motivador)

## Contexto

Auditor Sonnet 4.6 atual marca `needs_human + critical` em QUALQUER mudança em `.github/workflows/*.yml`, mesmo quando:
- a mudança altera somente valores numéricos (ex: budget cap 0.50 → 2.00)
- não toca permissões, secrets, lógica condicional, ou estrutura
- tem SPEC documentando a mudança

Custo dessa rigidez: cada ajuste trivial em workflow exige 1 clique manual do Humberto. Acumula em horas perdidas ao longo do tempo, sem ganho de segurança real (mudança trivial não pode causar comprometimento).

## Decisão

Adicionar exceção explícita no prompt do auditor que permite `verdict: approve` + `risk: low` quando TODAS as 3 condições simultaneamente verdadeiras:

1. **Mudança restrita a valores/metadados**: ints, floats, strings literais (descrição, default, mensagens), comentários. SEM novas chaves YAML, sem mudança em `runs-on`, `permissions`, `env`, `secrets`, `uses`, `if`, `concurrency`, jobs/steps adicionados/removidos.
2. **SPEC presente** em `specs/<feature>.md` no mesmo diff.
3. **Arquivo NÃO está em `sensitive_files.critical`** do projeto.

## Segurança preservada

- Workflows críticos (`governance-check.yml`, `audit-sonnet.yml`, qualquer outro em `sensitive_files.critical`) continuam SEMPRE exigindo aprovação humana.
- Mudança de permissões/secrets/triggers/estrutura → continua `needs_human + critical`.
- Princípio "seguro por padrão" mantido: na dúvida sobre se é "trivial", auditor escala pra `needs_human`.

## Mudanças

`prompts/auditor-system.md` (linhas 53 + nova seção entre "needs_human + high" e "Frente A vs Frente B"):
- Linha 53: referência à exceção
- Nova seção "Exceção: Workflow trivial com SPEC" com critérios explícitos

## Validação pós-merge

Re-rodar auditor em PR existente que motivou a mudança (flora-dspy-lab #64) com nova regra. Expectativa: verdict approve + risk low, summary mencionando "exceção workflow trivial aplicada".

## Reversão

Trivial: remover bloco da exceção + restaurar linha 53 original.
