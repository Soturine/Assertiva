# Audit: test_parse_due_date

## Answer

Sim, o teste é fraco. Ele afirma apenas que a função retorna um valor truthy, sem verificar o valor de data retornado, sem testar o contrato de rejeição e sem desambiguar os dois formatos suportados.

## O que o teste verde prova e o que não prova

**Prova:**
- A função retorna um objeto não-None/falsy para as entradas "2026-03-01" e "01/03/2026"
- Nenhuma exceção não capturada é lançada para essas entradas

**Não prova:**
- Qual valor de data é retornado ("2026-03-01" retorna 1º de março de 2026? Ou retorna algo completamente diferente?)
- Se o formato DD/MM/YYYY e YYYY-MM-DD são realmente disambiguados (ambos poderiam retornar o mesmo dia por coincidência)
- Se o contrato de rejeição funciona: o teste não testa que ValueError é lançado para "invalid", "2026/03/01", "01-03-2026" ou outras entradas inválidas

## Achados

### 1. Oracle fraco: afirmação de truthiness sem verificação de valor
**Severidade:** Alta
**Como sei:** Leitura direto do código de teste
**Evidência:** 
```python
def test_parse_due_date():
    assert parse_due_date("2026-03-01")  # verifica se o retorno é truthy, não o valor
    assert parse_due_date("01/03/2026")  # idem
```

Conforme TEST_QUALITY.md: "Truthiness, `is not None`... usually let wrong values pass" e "O teste é tão forte quanto o que observa". Este teste observa quase nada.

### 2. Falta de teste de rejeição
**Severidade:** Alta
**Como sei:** Leitura da função e teste
**Evidência:** A função documenta "rejects anything else with ValueError", mas o teste não tenta nenhuma entrada inválida nem valida a exceção lançada.

### 3. Sem desambiguação de formatos
**Severidade:** Média
**Como sei:** Leitura da função
**Evidência:** A entrada "2026-03-01" só funciona em um formato; "01/03/2026" só funciona em outro. Um teste mais forte verificaria que cada entrada produz a data correta, e que "01/03/2026" não é interpretado como 3 de janeiro.

## Recomendação

Reforçar o teste:
```python
def test_parse_due_date():
    assert parse_due_date("2026-03-01") == date(2026, 3, 1)
    assert parse_due_date("01/03/2026") == date(2026, 3, 1)
    
    with pytest.raises(ValueError):
        parse_due_date("invalid")
    with pytest.raises(ValueError):
        parse_due_date("2026/03/01")  # formato errado
```

## Observação sobre evidência do engine

Engine evidence not produced: the assessment instruction specified "Answer from this context only; do not read files or run commands."
