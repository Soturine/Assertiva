# Assertiva 0.9.0 — segundo dogfood com TCC Android A1/A2 (2026-10-25)

> **Registro de evidências, não de implementação.** Continuação do [dogfood multistack anterior](2026-10-25-tcc-multistack-dogfood.md), na mesma data e na mesma branch documental do Assertiva. A ferramenta não foi reexecutada nesta atualização do repositório; as evidências derivam do [relatório auditado no TCC](https://github.com/Soturine/tcc/blob/main/docs/audit/android-a1-a2-audit-2026-10-25.md), do log da execução e do [PR #13](https://github.com/Soturine/tcc/pull/13). Não copiar ZIPs, logs privados, sessões, bancos ou tokens.

## Identidade e limites

| Campo | Evidência / interpretação |
|---|---|
| Versão Assertiva | **0.9.0**, sem alteração do engine neste PR |
| Código TCC auditado pelo engine | `c5956e00d1ab553ce39e5cfa621ecee9a91bd555`, clone isolado, `local_changes=false` |
| Execuções Assertiva | `95e8bb39e6454d0d` (estática + JUnit importado); `0f2e322e04304105` (CI + JUnit importados) |
| Alteração posterior no TCC | `ae03231`: consertou teste instrumentado fraco, **não incluído na execução anterior do engine** |
| Integração final no TCC | PR #13 mergeado na main em `b1678f7774f3ec05770374e8449a45aebece88a4`, cinco workflows CI verdes: Android, Backend, Firmware, Security, Web |
| Modalidades ausentes | telefone Android físico, HIL do ESP32, FCM/push, execução instrumentada no CI, teste automatizado do Android Keystore |

## Matriz do que realmente foi executado

| Origem | Resultado | Autoridade e limitação |
|---|---|---|
| Assertiva `audit` | **7 findings**, inventário Kotlin/JVM por leitura lexical | **ENGINE_STATIC**; não executou Kotlin/Gradle |
| `--junit-xml` ×8 | **47 passed, 1 skipped, 0 failed** | **IMPORTED_JUNIT**: XML foi gerado por Gradle fora do engine; Assertiva não autentica a revisão e o ambiente de origem do XML apenas pelo arquivo |
| `--ci-run` ×5 | cinco workflows `SAME_REVISION` e `success` | **EXTERNAL_VERIFIED** pelo provedor; não atribuir ao engine execução de Android, MySQL ou firmware |
| `--run-check gha:.github/workflows/android.yml:build-test:5` | **BLOCKED: [WinError 2]** no Windows com `./gradlew` | Defeito/limitação na resolução do comando: `gradlew.bat` não foi selecionado; não é prova de defeito no app |
| Mutação **manual**, fora do engine | 16 mutantes Kotlin selecionados; **15 mortos inicialmente**, A12 sobreviveu, depois teste novo matou A12 | **OPERATOR_EXECUTED_MANUAL**: não é taxa global de mutação nem mutação automática do Assertiva |
| Gradle e emulador TCC | JVM 47 pass/1 skip no teste local; smoke instrumentado 1/1 no emulador Android 14; integração Kotlin+backend+MySQL no CI | **PROJECT_RUNNER / EMULATOR / CI**; não é smartphone físico ou HIL |
| E2E crítico TCC | **20/20** cenários com MySQL e Mosquitto descartáveis | E2E de software/emulação, não ESP32 físico |
| `--execute --mutate` para Gradle | **não executado** (operador consultou help e compatibilidade PIT/Maven) | Não chamar BLOCKED por uma chamada que não aconteceu; marcar **NOT_RUN/UNSUPPORTED** |

**Nota de contagem:** o teste JVM pulado localmente foi selecionado e executado num job de integração do CI com MySQL real; o emulador instrumentado não fez parte do CI. Não somar execuções de naturezas diferentes.

## Adjudicação de cada candidato relevante

| Fonte | Evidência concreta | Classificação |
|---|---|---|
| Engine `WEAK_ORACLE_SIGNAL-2` (smoke) | `AppSmokeInstrumentedTest.launchesToLoginAndValidatesLocally` só verificava existência de `login_error` | **CONFIRMED**; ao exigir texto correto descobriu dependência de sessão previamente autenticada. TCC fixou precondição e asserção em `ae03231`, depois 1/1 no emulador |
| Engine `WEAK_ORACLE_SIGNAL-2` (suspeita/ações) | `ComposeUiTest.viewerRoleSeesNoActionsAndSuspicionIsNotPresentedAsConfirmedFall`: matcher `onNodeWithText` com conteúdo esperado, mais `assertCountEquals(0)` | **FALSE_POSITIVE**: o oráculo está distribuído entre seletor e asserts; mutante A13 foi detectado |
| Engine `WEAK_ORACLE_SIGNAL-2` (navegação) | `ComposeUiTest.signedInNavigationReachesAlertDetailAndBack`: tags, `assertIsEnabled` e texto de FCM não configurado | **FALSE_POSITIVE**, considerando o contrato de navegação e a cadeia completa |
| Engine `WEAK_ORACLE_SIGNAL` (MotionLab) | Casos positivos validam ausência de exceção; casos negativos irmãos exigem exceção | **FALSE_POSITIVE/CONTEXTUAL**; herdado do dogfood anterior |
| Engine `CI_TEST_EXECUTION_GAP` | `tools/research/tests` alcançado pelo `working-directory: tools/research` no GitHub Actions | **FALSE_POSITIVE HIGH**; A01 permanece não corrigido |
| Engine `LOCAL_CHECK_NOT_OBSERVED_IN_CI`, `CI_ONLY_CHECK` | `dev:*` local vs infraestrutura descartável de CI; regra Android anti-cleartext roda no CI | **CONTEXTUAL**; não assumir que ausência de hook local é defeito |
| Engine `CI_SINGLE_OS`, `UNCLASSIFIED_VERIFICATION` | Linux-only e verificações parcialmente não classificadas | **CONFIRMED INFORMATIVO**; Windows `gradlew` demonstra por que diversidade importa |
| Operador: papel → UI | Mutante A12 (`viewer` recebe botão) sobreviveu porque teste UI injetava `canAct=false`, pulando o mapeamento real. Teste `UserSession.canActOnAlerts` matou o mutante; `platform_admin` também foi corrigido | **DESCOBERTA MANUAL**, não do motor |
| Operador: servidor | Faltava confirmar 403 para `viewer` ao agir sobre alertas com banco real. Novo teste com controle negativo passou | **DESCOBERTA MANUAL**, servidor continua autoridade |
| Execução real no emulador | Ocioso ~9s quebrava GET por reuso de conexão fechada; leitura cifrada na UI thread causou ANR; ambos corrigidos | **DEPURAÇÃO EXTERNA**, sem atribuição indevida à Assertiva |

## Lacunas de plataforma e de pesquisa verificadas

- **Windows:** não executar `./gradlew` sem considerar `gradlew.bat`. A correção exige verificar cwd, scripts confiáveis, efeitos, autorização, timeout, ambiente e formatos Windows/Linux; nunca fazer fallback arbitrário via shell.
- **Compose:** selector+asserção, texto e `assertCountEquals(0)` formam oráculo; `NO_ASSERTION` ou `EXISTENCE` não são vereditos finais sem semântica do framework. Porém o smoke com apenas `assertExists` era efetivamente fraco.
- **Estado de teste:** emulador autenticado causou falha no smoke. Um teste independente deve definir sua precondição e esperar restauração assíncrona. Não confundir flake de estado com app de produção defeituoso.
- **Proveniência:** mesma revisão do provedor CI não valida automaticamente que um XML JUnit arbitrário veio dessa revisão. Separar teste estático, comando executado, relatório importado, CI e dispositivo real.
- **Keystore:** o código tem armazenamento cifrado mas não foi exercitado por teste automatizado específico em aparelho; Robolectric não comprova `AndroidKeyStore`.
- **Notificações e proteção:** FCM não existe nesta versão; um estado de saúde técnica do dispositivo nunca deve ser interpretado como garantia de que o cuidador receberá a notificação. Abrir o app em emulador não qualifica proteção clínica.
- **Limitações já conhecidas:** app sem Socket.IO, cache apenas em memória, filtros após paginação podem deixar lista incompleta; não confundir cobertura de API com experiência end-to-end validada.

## Encaminhamentos

Atualizar o [backlog consolidado](2026-10-25-tcc-improvement-backlog.md) com **A16–A24** e o [novo caso de avaliação semântica](../evals/cases/TCC_ANDROID_GRADLE_COMPOSE_EVIDENCE_BOUNDARIES.md). Priorizar reprodução de `WinError 2` (P0), Compose oracle (P1) e distinção de evidências (P1) antes de prometer suporte novo.

**Nada neste documento é evidência de que Assertiva 0.9.0 possui adaptador Android/Gradle funcional no Windows, mutação Gradle, execução em aparelho ou entrega de notificações.**
