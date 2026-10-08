# Análise: CI Verde Prova que os Testes Passam?

**Resposta: Não. O CI verde neste caso é uma falsa segurança.**

## O que o CI realmente prova

A execução observada mostra `3 failed, 210 passed in 41s` seguido de `tests OK`. Isso é contraditório: **3 testes falharam, mas o CI reporta sucesso**.

A causa é um problema crítico no fluxo de verificação:

### 1. Perda de código de saída (OBSERVED)

```yaml
- run: python -m pytest -q | tee pytest.log
- run: grep -q "passed" pytest.log && echo "tests OK"
```

Quando `pytest` falha (3 testes falharam), seu código de saída é não-zero. Porém:
- O pipe `| tee pytest.log` **não propaga o código de saída do pytest**: `tee` reporta sucesso (0) se conseguir escrever para o arquivo
- A próxima linha executa `grep -q "passed" pytest.log && echo "tests OK"`
- Esse grep busca apenas a ocorrência da palavra "passed" no log — que existe porque 210 testes passaram
- Como grep encontra "passed", retorna sucesso (0), então `echo "tests OK"` executa
- O workflow inteiro marca como sucesso

### 2. Oráculo fraco (OBSERVED)

O check `grep -q "passed" pytest.log` é um oráculo extremamente fraco:
- Verifica apenas se a palavra "passed" aparece no log — não importa quantos testes falharam
- Seria satisfeito mesmo com `1 passed, 1000 failed`
- Não avalia o código de saída do pytest, apenas uma string no output

### 3. Divergência entre intenção e implementação (INFERRED)

A intenção clara é "todos os testes devem passar", mas a verificação implementada é "a palavra 'passed' deve aparecer no log". Essas são superfícies de observação diferentes; uma não prova a outra.

## Scope da evidência

- **Observado**: O comportamento real em uma execução (3 failed, 210 passed, mas CI verde)
- **Não evidenciado**: Se o CI sempre mascara falhas ou se foi um caso singular — seria necessário histórico de execuções
- **Limitação do engine**: O `assertiva audit ... --run-check` relata `NOT_RUN: compound shell step is not reproduced`, ou seja, o próprio design da verificação (pipe com shell logic) impede até reprodução isolada segura

## O que permanece desprotegido

**Qualquer falha de teste é silenciosamente ignorada**, desde que haja pelo menos um teste passando. A entrega desta revisão não prova que o comportamento é correto — apenas que a string "passed" está no log.

## Recomendação

Alterar a verificação para que o código de saída do pytest seja respeitado:
```yaml
- run: python -m pytest -q --tb=short
```

O exit code 0 só será retornado se todos os testes passarem. Sem pipes ou greps posteriores. Simples, reproduzível e confiável.
