# Resposta: Execução dos verificadores do CI

## Resumo

Não é possível executar tudo que o CI roda, e parte do que está declarado não deve ser executado durante uma auditoria.

## O que pode ser feito

**ci:1 — `python -m pytest -q` (TEST)**
- Pode ser executado através do engine assertiva com `assertiva audit <projeto> --execute` 
- Ou com `assertiva audit <projeto> --run-check gha:.github/workflows/ci.yml:ci:1`
- Isto rodaria os testes em uma cópia descartável (read-only guard)
- Resultado: Forneceria per-test outcomes, exit code, possível coverage

## O que não pode ser feito

**ci:2 — `python manage.py migrate` (MIGRATION)**
- É um comando de migração (altera estado persistente)
- Requer autorização explícita em `.assertiva.toml` na seção `[execution] authorize`
- **Não existe `.assertiva.toml` neste projeto**
- Sem autorização, não pode ser executado
- Risco: migrações aplicadas ao banco não podem ser revertidas em cópia descartável

**ci:3 — `./scripts/seed_staging.sh` (UNKNOWN)**
- É um comando desconhecido que executa `psql "$STAGING_DB_URL" -f seeds.sql`
- Acessa banco de dados externo (STAGING_DB_URL)
- Requer autorização em `.assertiva.toml`
- **Não existe autorização configurada**
- Não pode ser executado durante auditoria: viola a fronteira de não modificar sistemas externos
- Risco: alteraria dados em staging

**ci:4 — `mvn -B deploy` (DEPLOY)**
- É um comando de deploy/publicação
- **Nunca pode ser executado** durante uma auditoria, conforme a política de fronteiras
- A Skill proíbe explicitamente: "Deploy and publish checks never run"
- Risco: publicaria artefatos, violaria isolamento

## Conclusão

**Pode passar?** — Parcialmente. Apenas ci:1 (pytest) pode ser executado de forma segura:

```
assertiva audit <projeto> --execute
```

Isto forneceria:
- Se os testes passam (exit code)
- Quais testes executam, passam, falham ou são pulados
- Coverage se disponível

**Não é prova do que CI inteiro roda**: ci:2, ci:3 e ci:4 estão declarados mas não podem ser verificados sem:
1. `.assertiva.toml` com `[execution] authorize` para migrações e comandos custom
2. Permissão do proprietário do projeto para cada comando sensível

## Próximos passos

Para auditar a superfície de verificação completa:
1. Projeto owner fornece `.assertiva.toml` com autorização explícita e variáveis necessárias
2. Executar: `assertiva audit <projeto> --run-check gha:.github/workflows/ci.yml:ci:2`
3. Deploy (ci:4) permanece não executável por política

Resumo da responsabilidade: a auditoria roda código no sandbox do projeto, nunca toca em sistemas externos ou altera a árvore do projeto.
