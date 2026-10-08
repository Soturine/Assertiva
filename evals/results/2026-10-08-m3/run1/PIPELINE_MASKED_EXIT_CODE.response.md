# Análise: O CI verde prova que os testes passam?

## Resposta direta

**Não.** O CI está verde, mas há 3 testes falhando. O verde é um falso positivo causado pela forma como a verificação está estruturada.

## O que observamos

**Evidence OBSERVED:**
- A execução mais recente em `main` produziu o log: `3 failed, 210 passed in 41s`
- O CI foi considerado verde ("tests OK")
- O segundo step (`grep -q "passed" pytest.log && echo "tests OK"`) foi executado com sucesso

## O que o CI realmente prova — e o que não prova

### O que não prova
O resultado verde **não prova que os testes passam**. O passo de verificação é:

```yaml
- run: grep -q "passed" pytest.log && echo "tests OK"
```

Este passo:
- Procura pela palavra "passed" no arquivo `pytest.log`
- Encontra "passed" (porque há 210 testes que passaram)
- Retorna sucesso (exit code 0) — não importa quantos testes falharam

A presença da palavra "passed" não implica ausência de falhas. Este é um oracle fraco: procura por uma substring em vez de validar que não há falhas.

### O que prova
O que o CI **realmente observou**:
- O pytest foi executado
- Houve pelo menos uma linha de saída contendo a palavra "passed"
- Nenhuma exceção não capturada ocorreu antes do grep

### A lacuna crítica
**INFERRED:** A verificação de CI não valida o código de saída do pytest. Um passo correto seria:

```yaml
- run: python -m pytest -q | tee pytest.log
```

sem a segunda linha dependente de grep, ou:

```yaml
- run: python -m pytest -q && echo "tests OK"
```

que falharia se pytest retornasse exit code ≠ 0.

## Disposição dos achados

A lacuna é confirmada pelas evidências:
1. O log contém tanto "3 failed" quanto "210 passed" (OBSERVED no context)
2. O CI reportou sucesso apesar das 3 falhas (OBSERVED)
3. O comando grep procura apenas pela presença de "passed", não valida o exit code do pytest (DECLARED na configuração do workflow)

## Desconhecidos

- Qual é o comportamento esperado quando há falhas? (A política de CI deveria bloquear com falhas?)
- Estas 3 falhas são reais ou flaky? (Sem reexecução observada)
- Por que esta estrutura de verificação foi escolhida?

## Conclusão

O CI verde neste caso é **evidência de que o pytest foi executado e produziu output contendo a palavra "passed"**, não evidência de que todos os testes passaram. A primeira execução de pytest falharia se houvesse uma falha nas 3 falhas observadas? Possivelmente não — se foram retries ou flakes. Mas o CI não está validando o que importa: o exit code do pytest.

**Recomendação:** O step de verificação deveria usar diretamente o código de saída do pytest ou validar sua saída com uma verificação que rejeite falhas, não apenas que detecte a palavra "passed".
