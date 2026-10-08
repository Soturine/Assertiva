# Avaliação: CI verde prova que testes passam?

## Resposta

**Não. CI está verde, mas os testes tiveram 3 falhas. CI falha em capturar falhas.**

---

## O que CI realmente prova

**OBSERVADO:** Últimas execução em `main`:
- Pytest saída: `3 failed, 210 passed in 41s`
- Step 2 exit: sucesso ("tests OK" foi ecoado)
- CI final: verde

**DECLARADO:** Workflow define:
```yaml
- run: python -m pytest -q | tee pytest.log
- run: grep -q "passed" pytest.log && echo "tests OK"
```

**INFERRED:** Step 2 não valida testes com sucesso. Verifica apenas se string "passed" existe no log. Fluxo:
1. `grep -q "passed" pytest.log` → acha `210 passed` no log → exit 0
2. `echo "tests OK"` → executa → exit 0
3. Step inteiro → exit 0 (último comando)

Step 2 ignoraria completamente a falha. Se pytest produzisse `3 failed, 0 passed`, grep não acharia "passed", step falharia corretamente. Mas com `3 failed, 210 passed`, grep acha "passed", step passa — **não validou que nenhum falhou**.

---

## O que CI não prova

- **Que nenhum teste falhou.** Step 2 não verifica ausência de falhas; verifica presença da palavra "passed".
- **Que testes realmente rodaram.** Pytest saiu com código 0 ou 1? Piped step assume exit do pytest, mas `grep && echo` move exit para grep's resultado, não pytest's.
- **Fidelidade do step.** Engine recusa reproduzir `compound shell step` (gha:... test:1). `grep -q && echo` nunca foi testado localmente; apenas declarado no workflow.

---

## Achado crítico

Este é um **falso verde.** CI aceita "tests OK" de forma que testes com falhas pode passar:
- Pytest registra `3 failed` + `210 passed` → exit 1 (falha)
- Mas step 2 ignora pytest exit
- Step 2 só checa grep por "passed" → encontra → echo → exit 0 → **CI verde, testes com falha**

Risco: Qualquer CI observado assim pode estar mascarando falhas reais.

---

## Ignorados

- Comando exato de pytest (`-q` reduz verbosidade; omite lista de falhas)
- Se workflow gating realmente bloqueia merge ou deploy on "green"
- Acesso ao histórico do provider para confirmar SHA desta execução matched HEAD

---

## Recomendação

Altere step 2 para validar sucesso:
```yaml
- run: python -m pytest -q
```

Remova `grep && echo`. Deixe pytest exit code governa o step. Se precisar log: guarde-o, mas não o use para fingir sucesso. Assim CI verde realmente significa todos testes passaram.
