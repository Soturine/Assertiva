# Auditoria dos Testes Django

## Resposta à pergunta

**Eles passam? Desconhecido.** A auditoria não conseguiu executar os testes. O executor do Django parou antes de qualquer invocação com erro de conexão ao banco de dados, bloqueando o resultado. Não há evidência de testes passando, falhando ou sendo coletados — a execução não começou.

## O que a auditoria observou

**Status da execução (OBSERVADO):** `django` runner bloqueado com zero invocações (`status: BLOCKED`).

**Erro fatal (OBSERVADO):** `django.db.utils.OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused`. O Django tentou conectar em `localhost:5432` e a conexão foi recusada.

**Origem da configuração (DECLARADO):** `settings.py` lê `DATABASES` da variável de ambiente `DATABASE_URL`, com padrão `localhost:5432`.

**Limitação da auditoria (OBSERVADO):** `DATABASE_URL` foi retida como variável semelhante a credencial. O motor do assertiva não a passou para o código executado, protegendo a confidencialidade. Seu shell tem `DATABASE_URL` apontando para um banco de dados de staging compartilhado, mas essa variável não alcançou a execução.

## Achado crítico

**Incompatibilidade entre ambiente de auditoria e ambiente local:**

1. **O motor retém variáveis credenciais** (`DATABASE_URL` é detectado como tal). Isto é correto por padrão — evita vazamento de credenciais.
2. **O projeto requer `DATABASE_URL`** para se conectar (não está usando o padrão `localhost:5432`, ou está mas nenhum servidor roda lá).
3. **Resultado:** os testes não rodaram. Zero invocações = zero evidência sobre testes passando ou falhando.

## O que não se sabe e por quê

- **Se os testes passam em seu ambiente local:** não foi rodado. A auditoria sem acesso a `DATABASE_URL` não pode executar a suite.
- **Se a configuração está correta:** não foi testada. Um banco PostgreSQL em `localhost:5432` funcionaria com o padrão, ou é necessário `DATABASE_URL`? Desconhecido.
- **Cobertura, oráculos, qualidade dos testes:** nada foi executado. Não há dados sobre o que os testes cobrem, como fazem asserções ou se realmente verificam comportamento.
- **Se CI roda os testes:** não foi verificado. O workflow pode ter variáveis de ambiente diferentes que permitam conexão, ou pode estar em estado desconhecido.

## Recomendações para dar prosseguimento

Para responder "Eles passam?" com evidência real, você precisa:

1. **Configurar `.assertiva.toml`** com autorização para passar `DATABASE_URL`:
   ```toml
   [execution]
   authorize = ["manage.py test", "pytest", "unittest"]  # conforme seu runner
   env = ["DATABASE_URL"]
   ```
   Isto sinaliza explicitamente que você autoriza o acesso seguro a essa credencial para auditoria.

2. **Reexecutar a auditoria:**
   ```bash
   assertiva audit . --execute
   ```
   Desta vez, o Django conseguirá conectar e os testes rodarão (ou falharão com um resultado claro).

3. **Examinar a cobertura, oráculos e qualidade** uma vez que houver evidência de execução — ler os testes em paralelo com o código, verificar se as asserções realmente provam comportamento crítico, e investigar quaisquer sinais de teste fraco que o motor reportar.

## Resumo da evidência

- **Auditoria parcial:** sem execução = sem dados sobre testes passarem ou falharem.
- **Causa raiz:** variável de ambiente `DATABASE_URL` retida por proteção de confidencialidade.
- **Próximo passo:** autorizar a variável em `.assertiva.toml` e reexecutar.

A resposta "não se sabe ainda" é tão válida quanto "sim" ou "não" — o que importa é saber *por quê* e como obter a evidência que falta.
