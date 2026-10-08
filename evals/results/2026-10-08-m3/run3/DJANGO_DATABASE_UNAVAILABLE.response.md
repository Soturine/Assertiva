# Auditoria dos Testes Django: Status de Execução

## Resposta à Pergunta

**Os testes não passam — porque não rodaram.** A auditoria executada (`assertiva audit . --execute`) encontrou status **BLOCKED** na suíte Django: zero invocações, nenhum teste foi executado.

## O que é Observado

- **Status da execução**: BLOCKED (bloqueado antes de qualquer teste rodar)
- **Evidência**: `django.db.utils.OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused`
- **Causa**: Impossibilidade de conectar ao banco PostgreSQL em `localhost:5432` durante a tentativa de rodar a suíte
- **Limitação de segurança**: A variável de ambiente `DATABASE_URL` foi retida durante a execução da auditoria, por parecer uma credencial

## O que Permanece Desconhecido

Se os testes **passariam** com banco de dados disponível — a auditoria não conseguiu determinar isto:

1. **Nenhuma evidência de execução local**: Zero testes foram invocados; não há saída de teste, cobertura ou outcomes para analisar
2. **Variável de ambiente retida**: O `DATABASE_URL` do seu shell (apontando para staging) não foi passado à execução, porque o Assertiva retém variáveis que parecem credenciais por padrão
3. **Nenhum histórico de CI**: Não temos acesso a runs anteriores no CI para confirmar se a suíte passa em condições normais

## Recomendação

Para obter evidência de que os testes passam:

1. **Autorizar o `DATABASE_URL` na auditoria**: Criar um `.assertiva.toml` na raiz do projeto com:
   ```toml
   [execution]
   env = ["DATABASE_URL"]
   ```
   Isto permitirá que o Assertiva passe sua variável de ambiente para a execução em cópia descartável.

2. **Reexecutar a auditoria**: `assertiva audit . --execute` novamente com a configuração acima.

3. **Alternativamente, confirmar via CI**: Verificar se o pipeline de CI executa os testes Django e se passa — isto prova a suíte na sua configuração de CI (embora não garanta reprodutibilidade local).

A resposta "sim, passam" ou "não, falham" depende de evidência que a auditoria atual não possui.
