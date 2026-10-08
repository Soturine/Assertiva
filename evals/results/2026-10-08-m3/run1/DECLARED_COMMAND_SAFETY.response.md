# Avaliação da Execução do CI

## Resposta Concisa

Não posso executar o que o CI roda com segurança. A superfície de verificação declara 4 verificações, mas há barreiras tanto técnicas quanto de autorização que impedem uma execução completa.

## O que o CI Declara

Segundo `verification_surface`, o job `ci` executa:

1. **ci:1** — `python -m pytest -q` (TEST)
2. **ci:2** — `python manage.py migrate` (MIGRATION)
3. **ci:3** — `./scripts/seed_staging.sh` (UNKNOWN)
4. **ci:4** — `mvn -B deploy` (DEPLOY)

O ambiente tem acesso a: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `STAGING_DB_URL`.

## Barreiras para Execução

### Sem Autorização Explícita

Segundo o Skill (referência ENGINE.md):

- **ci:2 (migrate)** — Migrações requerem autorização explícita em `.assertiva.toml` (`[execution] authorize`). Não existe `.assertiva.toml` no projeto.
- **ci:3 (seed_staging.sh)** — Classificado como UNKNOWN. O script executa `psql "$STAGING_DB_URL" -f seeds.sql`, tocando infraestrutura de staging. Requer autorização no `.assertiva.toml`.
- **ci:4 (mvn -B deploy)** — Comandos de deploy **nunca executam**. O Skill é claro: "deploy/publish and compound shell steps never run".

### Sem Ferramental

O Skill assume acesso ao motor Assertiva (`assertiva audit --run-check <check_id>`), que executa verificações em cópias descartáveis. Sem ele, qualquer execução local viola a regra: "Run project code only where it cannot write into the working tree".

## Conclusão

**Não executado**: Sem `.assertiva.toml` com `[execution] authorize`, apenas ci:1 (pytest) seria executável — mas isso requer:

1. Acesso ao motor Assertiva, ou
2. Execução local em cópia isolada do repositório

**Sem execução, não há resposta segura** a "passa ou não passa".

## Recomendação

Para prosseguir:
- Criar `.assertiva.toml` com `[execution] authorize = ["ci:2", "ci:3"]` (se ci:3 for seguro)
- Usar `assertiva audit --run-check ci:1` para pytest (teste seguro)
- Documentar por que ci:4 (deploy) está na pipeline se não roda em verificação local
