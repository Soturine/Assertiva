"""Localized presentation of the engine's own narrative sentences.

Each entry is the engine's exact English template with named placeholders and its pt-BR rendering. A sentence is
localized only on a whole-sentence match of a template; the values in the placeholders are technical (paths, ids,
commands, counts, tool output) and are inserted unchanged. A placeholder written ``{name:kind}`` is presented through
a catalog: ``st`` (status label), ``check`` (qualification check label), ``metrics`` (comma-separated metric ids).
Sentences that match no template are raw text and stay in their original language, in technical detail.
"""

from __future__ import annotations

import re
from functools import lru_cache

# (English template exactly as the engine writes it, pt-BR)
NARRATIVE: list[tuple[str, str]] = [
    # claim boundary: audit
    ("native {adapter} run in an isolated copy: {status:st} ({n} invocations)",
     "execução nativa {adapter} em cópia isolada: {status:st} ({n} invocações)"),
    ("results ingested from {source} via {adapter} (not executed by Assertiva): {status:st} ({n} cases)",
     "resultados ingeridos de {source} via {adapter} (não executados pelo Assertiva): {status:st} ({n} casos)"),
    ("static oracle signals (E3 heuristics, not execution)", "sinais estáticos de oráculo (heurísticas E3, não execução)"),
    ("{n} declared verification checks (configuration, not run evidence)",
     "{n} verificações declaradas (configuração, não evidência de execução)"),
    ("ingested mutation report(s): {reports}", "relatório(s) de mutação ingerido(s): {reports}"),
    ("no tests were executed; test outcomes are UNKNOWN", "nenhum teste foi executado; os resultados dos testes são DESCONHECIDOS"),
    ("whether declared CI checks actually ran, on which revision, and whether they gate merges",
     "se as verificações de CI declaradas realmente executaram, em qual revisão e se bloqueiam merges"),
    ("coverage", "cobertura"),
    ("mutation / negative-control strength", "força contra mutação / controles negativos"),
    ("build, package and installed-artifact behavior", "comportamento do build, do pacote e do artefato instalado"),
    ("startup, health and deployment behavior", "comportamento de inicialização, saúde e implantação"),
    ("{adapter} {dimension}: {value}, not executed", "{adapter} {dimension}: {value}, não executado"),
    ("declared check {check} reproduced in an isolated copy: {status:st} ({detail})",
     "verificação declarada {check} reproduzida em cópia isolada: {status:st} ({detail})"),
    ("per-test outcomes are UNKNOWN: declared test checks ran as whole commands",
     "os resultados por teste são DESCONHECIDOS: as verificações de teste declaradas rodaram como comandos inteiros"),
    ("full-suite outcome: {n} mapped test files were not run",
     "resultado da suíte completa: {n} arquivos de teste mapeados não foram executados"),
    # claim boundary: improve
    ("Candidate evidence was observed in an isolated copy; the candidate is not applied to the project.",
     "A evidência do candidato foi observada em uma cópia isolada; o candidato não foi aplicado ao projeto."),
    ("preview/deployment behavior: no authorized non-production preview adapter; production is never used to qualify tests",
     "comportamento de preview/implantação: nenhum adaptador de preview fora de produção autorizado; produção nunca é usada para qualificar testes"),
    ("preview/deployment behavior: no authorized non-production preview adapter",
     "comportamento de preview/implantação: nenhum adaptador de preview fora de produção autorizado"),
    ("APPLIED: {n} approved changes applied; files match candidate: {match}",
     "APLICADO: {n} mudanças aprovadas aplicadas; arquivos iguais ao candidato: {match}"),
    ("metric {name}: not measured in both states", "métrica {name}: não medida nos dois estados"),
    # audit limitations
    ("test evidence is UNKNOWN for this toolchain until an adapter or portable report is available",
     "a evidência de testes é DESCONHECIDA para este ferramental até haver um adaptador ou relatório portátil"),
    ("static inventory is bounded source analysis, not native collection",
     "o inventário estático é uma análise limitada do código-fonte, não a coleta nativa"),
    ("tests were not executed; --execute collects native evidence by running project code in an isolated copy",
     "os testes não foram executados; --execute coleta evidência nativa executando o código do projeto em uma cópia isolada"),
    ("{n} tests were deselected by the run's own filters; they are not evidenced",
     "{n} testes foram desselecionados pelos filtros da própria execução; não são evidenciados"),
    # state evidence
    ("report source does not match the {state} state: {files}", "a origem do relatório não corresponde ao estado {state}: {files}"),
    ("project links point outside its root ({links}); executions may reach their targets",
     "links do projeto apontam para fora da raiz ({links}); execuções podem alcançar seus destinos"),
    ("no executable runner adapter recognized this project; test evidence is UNKNOWN",
     "nenhum adaptador executável reconheceu este projeto; a evidência de testes é DESCONHECIDA"),
    ("installed dependencies are linked from the project, not isolated ({deps}); runs can read and write them, and dependency changes made by a candidate are not installed",
     "dependências instaladas são vinculadas a partir do projeto, não isoladas ({deps}); execuções podem lê-las e alterá-las, e mudanças de dependência feitas por um candidato não são instaladas"),
    ("coverage was requested but Vitest produced no json-summary",
     "a cobertura foi solicitada, mas o Vitest não produziu json-summary"),
    ("no Vitest coverage provider is installed (@vitest/coverage-v8 or -istanbul); coverage was not measured",
     "nenhum provedor de cobertura do Vitest está instalado (@vitest/coverage-v8 ou -istanbul); a cobertura não foi medida"),
    ("Vitest's JSON report does not name the project a test ran in; a file included by several projects appears once per project",
     "o relatório JSON do Vitest não nomeia o projeto em que um teste executou; um arquivo incluído por vários projetos aparece uma vez por projeto"),
    ("after retries Vitest reports the final status; a pass after failed attempts is recognized by the failure messages it keeps, the attempt count is unknown",
     "após novas tentativas o Vitest relata o status final; uma aprovação após tentativas falhas é reconhecida pelas mensagens de falha que ele mantém, o número de tentativas é desconhecido"),
    ("the runner exited with code {code} although no recorded test failed",
     "o executor terminou com código {code} embora nenhum teste registrado tenha falhado"),
    ("unittest counts an unexpected success (expectedFailure that passed) as a failure of the run",
     "o unittest conta um sucesso inesperado (expectedFailure que passou) como falha da execução"),
    ("{adapter} could not be executed: {detail}", "{adapter} não pôde ser executado: {detail}"),
    ("{adapter} produced no native evidence: {detail}", "{adapter} não produziu evidência nativa: {detail}"),
    ("{adapter} stopped before running any test: {detail}", "{adapter} parou antes de executar qualquer teste: {detail}"),
    ("unittest collects TestCase methods only; plain test functions are not run by this runner",
     "o unittest coleta apenas métodos de TestCase; funções de teste simples não são executadas por este executor"),
    ("credential-like environment variables were withheld from executed project code: {names}",
     "variáveis de ambiente com aparência de credencial foram retidas do código do projeto executado: {names}"),
    ("{adapter} cannot run a selected subset; it ran its full suite",
     "{adapter} não consegue executar um subconjunto selecionado; executou a suíte completa"),
    ("{adapter}: none of the selected tests belong to it; it was not run",
     "{adapter}: nenhum dos testes selecionados pertence a ele; não foi executado"),
    # runner adapters
    ("coverage.py is not available in the target interpreter; coverage was not measured",
     "o coverage.py não está disponível no interpretador alvo; a cobertura não foi medida"),
    ("pytest could not be executed: {detail}", "o pytest não pôde ser executado: {detail}"),
    ("coverage.py ran but produced no reportable data", "o coverage.py executou, mas não produziu dados reportáveis"),
    ("pytest produced no native evidence: {detail}", "o pytest não produziu evidência nativa: {detail}"),
    ("custom collected items: declaration provenance and oracle analysis are unavailable for them",
     "itens coletados personalizados: proveniência da declaração e análise de oráculo indisponíveis para eles"),
    ("dynamically generated tests: declaration is a runtime factory, not a source definition",
     "testes gerados dinamicamente: a declaração é uma fábrica em tempo de execução, não uma definição no código"),
    ("no tests were collected; this is not evidence of a passing suite",
     "nenhum teste foi coletado; isso não é evidência de uma suíte aprovada"),
    ("pytest exited with code {code}", "o pytest terminou com código {code}"),
    ("{adapter} results could not be read: {detail}", "os resultados de {adapter} não puderam ser lidos: {detail}"),
    ("retried tests passed only after earlier failed attempts: {tests}",
     "testes repetidos só passaram após tentativas anteriores com falha: {tests}"),
    ("no test was executed; this is not evidence of a passing suite",
     "nenhum teste foi executado; isso não é evidência de uma suíte aprovada"),
    ("coverage was requested but Jest produced no json-summary", "a cobertura foi solicitada, mas o Jest não produziu json-summary"),
    ("the report does not record which revision/source it was produced from",
     "o relatório não registra a revisão/código a partir do qual foi produzido"),
    ("PIT reported a partial run", "o PIT relatou uma execução parcial"),
    ("JUnit XML could not be read: {detail}", "o JUnit XML não pôde ser lido: {detail}"),
    ("the report contains no executed test cases", "o relatório não contém casos de teste executados"),
    ("no Surefire or Failsafe report was produced by this run; test outcomes are unknown",
     "esta execução não produziu relatório Surefire ou Failsafe; os resultados dos testes são desconhecidos"),
    ("reports that could not be read provide no evidence: {files}", "relatórios que não puderam ser lidos não fornecem evidência: {files}"),
    ("a separate JaCoCo integration-test report exists and is not merged into this coverage",
     "existe um relatório JaCoCo separado de testes de integração que não foi mesclado a esta cobertura"),
    ("Maven selects tests per method: every parameterized case of a selected method ran",
     "o Maven seleciona testes por método: todos os casos parametrizados de um método selecionado executaram"),
    ("coverage requires the project's own JaCoCo report goal; none was produced",
     "a cobertura exige o goal de relatório JaCoCo do próprio projeto; nenhum foi produzido"),
    ("Playwright results could not be read: {detail}", "os resultados do Playwright não puderam ser lidos: {detail}"),
    ("Playwright reported an error outside any test: {detail}", "o Playwright relatou um erro fora de qualquer teste: {detail}"),
    ("project {name} was selected but not executed: its browser is not installed (Assertiva does not install browsers)",
     "o projeto {name} foi selecionado, mas não executado: o navegador dele não está instalado (o Assertiva não instala navegadores)"),
    ("project {name} is declared but was not selected in this run", "o projeto {name} é declarado, mas não foi selecionado nesta execução"),
    ("no browser test was executed; this is not evidence of a passing suite",
     "nenhum teste de navegador foi executado; isso não é evidência de uma suíte aprovada"),
    ("browser tests are not coverage-instrumented by Assertiva", "testes de navegador não são instrumentados para cobertura pelo Assertiva"),
    ("the Cobertura report has rates but no counts: its denominators are unknown",
     "o relatório Cobertura tem taxas, mas não contagens: seus denominadores são desconhecidos"),
    # artifact adapter
    ("only the wheel was built and verified; the sdist was not", "apenas o wheel foi construído e verificado; o sdist não"),
    ("no clean install from a package index was performed (offline)", "nenhuma instalação limpa a partir de um índice de pacotes foi feita (offline)"),
    ("build backend not importable locally: isolated build may need network access",
     "o backend de build não é importável localmente: o build isolado pode precisar de acesso à rede"),
    ("imports did not resolve to the installed artifact: {modules}", "os imports não resolveram para o artefato instalado: {modules}"),
    ("only build, install and import were verified; no tests ran against the artifact",
     "apenas build, instalação e import foram verificados; nenhum teste executou contra o artefato"),
    ("no tests were collected against the installed artifact", "nenhum teste foi coletado contra o artefato instalado"),
    # verification surface
    ("no adapter classifies this command; its semantics are unknown", "nenhum adaptador classifica este comando; sua semântica é desconhecida"),
    ("step also runs unclassified commands: {commands}", "a etapa também executa comandos não classificados: {commands}"),
    # selection, impact and components
    ("unknown relations exist but no test reaches them statically", "existem relações desconhecidas, mas nenhum teste as alcança estaticamente"),
    ("no adapter can relate this project's files to its tests; every change is an unknown impact",
     "nenhum adaptador consegue relacionar os arquivos deste projeto aos seus testes; toda mudança tem impacto desconhecido"),
    ("component name {name} is declared twice; the second declaration was ignored",
     "o nome de componente {name} foi declarado duas vezes; a segunda declaração foi ignorada"),
    ("pnpm-workspace.yaml layouts are not read yet; their packages are not components",
     "layouts de pnpm-workspace.yaml ainda não são lidos; seus pacotes não são componentes"),
    ("{member} has no package name; it is not a component", "{member} não tem nome de pacote; não é um componente"),
    ("{manifest} could not be read ({error}); it is not a component", "{manifest} não pôde ser lido ({error}); não é um componente"),
    # qualification summaries
    ("no runner adapter could discover candidate tests", "nenhum adaptador de execução conseguiu descobrir os testes do candidato"),
    ("collection errors: {errors}", "erros de coleta: {errors}"),
    ("runner could not execute", "o executor não conseguiu executar"),
    ("no candidate invocations were collected", "nenhuma invocação do candidato foi coletada"),
    ("{n} invocations collected natively without errors", "{n} invocações coletadas nativamente sem erros"),
    ("no runner adapter could execute candidate tests", "nenhum adaptador de execução conseguiu executar os testes do candidato"),
    ("candidate test files failed to collect: {files}", "arquivos de teste do candidato falharam na coleta: {files}"),
    ("the candidate does not add or modify executable tests", "o candidato não adiciona nem modifica testes executáveis"),
    ("failing candidate invocations: {tests}", "invocações do candidato com falha: {tests}"),
    ("every candidate invocation was skipped or not run", "toda invocação do candidato foi ignorada ou não executada"),
    ("{n} added/modified invocations executed without failure", "{n} invocações adicionadas/modificadas executaram sem falha"),
    ("no runner adapter produced baseline/candidate execution evidence",
     "nenhum adaptador de execução produziu evidência de execução da baseline/candidato"),
    ("the baseline had no passing invocations to protect", "a baseline não tinha invocações aprovadas a proteger"),
    ("original regression run could not execute", "a execução de regressão original não pôde ser feita"),
    ("original tests no longer pass against the candidate: {tests}", "testes originais deixaram de passar contra o candidato: {tests}"),
    ("all {n} originally passing invocations still pass", "todas as {n} invocações originalmente aprovadas continuam passando"),
    ("all {n} originally passing invocations still pass (original versions of {m} changed test files restored)",
     "todas as {n} invocações originalmente aprovadas continuam passando (versões originais de {m} arquivos de teste alterados restauradas)"),
    ("regressed: {names:metrics}", "regrediu: {names:metrics}"),
    ("coverage population changed; percentages are not comparable", "a população da cobertura mudou; os percentuais não são comparáveis"),
    ("partial evidence: {names:metrics}", "evidência parcial: {names:metrics}"),
    ("coverage or oracle signals were not measured for both states", "sinais de cobertura ou de oráculo não foram medidos nos dois estados"),
    ("no regression in {names:metrics}", "nenhuma regressão em {names:metrics}"),
    ("dimensions are static AST signals (E3); outcomes come from the native run (E1); rollback and external side effects are not evidenced",
     "as dimensões são sinais estáticos de AST (E3); os resultados vêm da execução nativa (E1); rollback e efeitos externos não são evidenciados"),
    ("negative-path evidence weakened: {names:metrics}", "a evidência de caminhos negativos enfraqueceu: {names:metrics}"),
    ("the candidate does not add or modify negative-path tests", "o candidato não adiciona nem modifica testes de caminho negativo"),
    ("no negative controls or mutation evidence were provided", "nenhum controle negativo ou evidência de mutação foi fornecido"),
    ("a green suite was not challenged with deliberately broken behavior",
     "uma suíte verde não foi desafiada com comportamento deliberadamente quebrado"),
    ("{n} negative controls killed", "controles negativos detectados: {n}"),
    ("mutation evidence could not be read", "a evidência de mutação não pôde ser lida"),
    ("{source}: unreadable mutation report ({error})", "{source}: relatório de mutação ilegível ({error})"),
    ("no build/package adapter supports this project", "nenhum adaptador de build/pacote suporta este projeto"),
    ("source-tree tests do not prove a built artifact", "testes na árvore de código não comprovam um artefato construído"),
    ("files in packaged directories missing from the artifact: {files}",
     "arquivos em diretórios empacotados ausentes do artefato: {files}"),
    ("no delivery pipeline was discovered", "nenhum pipeline de entrega foi descoberto"),
    ("delivery-path verification is UNKNOWN", "a verificação do caminho de entrega é DESCONHECIDA"),
    ("reproduced {a}/{b} delivery checks locally", "{a} de {b} verificações de entrega reproduzidas localmente"),
    ("reproduced {a}/{b} delivery checks locally; a reproduced gating check failed",
     "{a} de {b} verificações de entrega reproduzidas localmente; uma verificação bloqueante reproduzida falhou"),
    ("reproduced {a}/{b} delivery checks locally; a reproduced check could not run",
     "{a} de {b} verificações de entrega reproduzidas localmente; uma verificação reproduzida não pôde executar"),
    ("reproduced {a}/{b} delivery checks locally; all gating checks passed",
     "{a} de {b} verificações de entrega reproduzidas localmente; todas as verificações bloqueantes passaram"),
    ("not reproduced: {label}: discovered, not authorized (assertiva improve --run-check {check})",
     "não reproduzida: {label}: descoberta, não autorizada (assertiva improve --run-check {check})"),
    ("not reproduced: {label}: {reason}", "não reproduzida: {label}: {reason}"),
    ("{label}: only the local environment was reproduced, not matrix {matrix}",
     "{label}: apenas o ambiente local foi reproduzido, não a matriz {matrix}"),
    ("{label}: condition `{condition}` was not evaluated", "{label}: a condição `{condition}` não foi avaliada"),
    ("{label}: {status:st} but allowed to fail ({gate}): {detail}", "{label}: {status:st}, mas com falha permitida ({gate}): {detail}"),
    ("{label}: {status:st}: {detail}", "{label}: {status:st}: {detail}"),
    ("absence of observed instability is not proof of stability", "a ausência de instabilidade observada não prova estabilidade"),
    ("order dependence was not measured", "a dependência de ordem não foi medida"),
    ("only the first {a} of {b} relevant invocations were rerun", "apenas as primeiras {a} de {b} invocações relevantes foram reexecutadas"),
    ("no instability observed in {a} executions of {b} invocations; wall clock {x:num}s -> {y:num}s ({delta:st})",
     "nenhuma instabilidade observada em {a} execuções de {b} invocações; tempo de relógio {x:num} s → {y:num} s ({delta:st})"),
    ("no relevant invocation was rerun; wall clock {x:num}s -> {y:num}s ({delta:st})",
     "nenhuma invocação relevante foi reexecutada; tempo de relógio {x:num} s → {y:num} s ({delta:st})"),
    ("no relevant invocation was rerun; wall clock unknown", "nenhuma invocação relevante foi reexecutada; tempo de relógio desconhecido"),
    # change set
    ("added in candidate", "adicionado no candidato"),
    ("modified in candidate", "modificado no candidato"),
    # evidence delta
    ("denominator changed: {before} -> {after}; the percentages measure different populations",
     "o denominador mudou: {before} → {after}; os percentuais medem populações diferentes"),
    # dynamic finding summaries
    ("The project declares {dimension} {values} but no CI job states which {dimension2} it runs.",
     "O projeto declara {dimension} {values}, mas nenhum job de CI informa qual {dimension2} executa."),
    ("Declared {dimension} {values} is not selected by any CI job.", "{dimension} declarado {values} não é selecionado por nenhum job de CI."),
    ("Every CI job that states an operating system runs on {os}; others are not evidenced.",
     "Todo job de CI que informa um sistema operacional executa em {os}; os demais não são evidenciados."),
]

_PLACEHOLDER = re.compile(r"\{(\w+)(?::(\w+))?\}")
# What a placeholder may contain, so a generic template cannot swallow an unrelated sentence.
_SHAPE = {"n": r"\d+", "m": r"\d+", "a": r"\d+", "b": r"\d+", "code": r"-?\d+", "x": r"[\d.]+", "y": r"[\d.]+"}
_KIND_SHAPE = {"st": r"[A-Z][A-Z_]*", "metrics": r"[a-z_]+(?:, [a-z_]+)*", "num": r"\d+(?:\.\d+)?"}


@lru_cache(maxsize=None)
def _compiled() -> list[tuple[re.Pattern, str, str, dict[str, str]]]:
    out = []
    for en, pt in NARRATIVE:
        kinds: dict[str, str] = {}
        parts, last = [], 0
        for m in _PLACEHOLDER.finditer(en):
            parts.append(re.escape(en[last:m.start()]))
            shape = _KIND_SHAPE.get(m.group(2) or "") or _SHAPE.get(m.group(1)) or ".+?"
            parts.append(f"(?P<{m.group(1)}>{shape})")
            if m.group(2):
                kinds[m.group(1)] = m.group(2)
            last = m.end()
        parts.append(re.escape(en[last:]))
        out.append((re.compile("".join(parts), re.S), en, pt, kinds))
    return out


def match(sentence: str) -> tuple[int, dict[str, str], dict[str, str]] | None:
    """(template index, values, presentation kinds) for a whole-sentence match; the most literal template wins."""
    best = None
    for index, (pattern, en, _pt, kinds) in enumerate(_compiled()):
        m = pattern.fullmatch(sentence)
        if m:
            literal = len(_PLACEHOLDER.sub("", en))
            if best is None or literal > best[0]:
                best = (literal, index, m.groupdict(), kinds)
    return None if best is None else (best[1], best[2], best[3])


def template(index: int) -> tuple[str, str]:
    return NARRATIVE[index]


def strip_kinds(text: str) -> str:
    """Template text with ``{name:kind}`` reduced to ``{name}`` (the form str.format and the page script fill)."""
    return _PLACEHOLDER.sub(lambda m: "{" + m.group(1) + "}", text)
