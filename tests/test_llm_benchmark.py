from app.services.llm_benchmark import BENCHMARK_TASKS, score_benchmark_output, summarize_results


def test_benchmark_scores_valid_supported_claim() -> None:
    task = BENCHMARK_TASKS[0]
    raw_content = (
        '{"claims":[{"claim_text":"Telefonhivas tortent.",'
        '"quote_text":"2024. marcius 12-en 18:42-kor telefonhivas tortent Kovacs Anna es Nagy Peter kozott",'
        '"source_label":"chunk_1"}],"unsupported_claims":[]}'
    )

    result = score_benchmark_output("model-a", task, raw_content, 1.0)

    assert result.score == result.max_score
    assert result.valid_json is True
    assert result.quote_valid is True


def test_benchmark_scores_no_source_rule() -> None:
    task = BENCHMARK_TASKS[1]
    raw_content = '{"claims":[],"unsupported_claims":["A forras nem nevezi meg, ki nyitotta ki az ajtot."]}'

    result = score_benchmark_output("model-a", task, raw_content, 1.0)

    assert result.score == result.max_score
    assert result.no_source_respected is True


def test_benchmark_rejects_quote_not_in_source() -> None:
    task = BENCHMARK_TASKS[2]
    raw_content = (
        '{"claims":[{"claim_text":"A tanu piros taskat latott.",'
        '"quote_text":"a piros taskat lattam","source_label":"chunk_1"}],"unsupported_claims":[]}'
    )

    result = score_benchmark_output("model-a", task, raw_content, 1.0)

    assert result.quote_valid is False
    assert "quote_not_found_in_source" in result.errors


def test_benchmark_summary_groups_by_model() -> None:
    first = score_benchmark_output(
        "model-a",
        BENCHMARK_TASKS[1],
        '{"claims":[],"unsupported_claims":["nincs forras"]}',
        2.0,
    )
    second = score_benchmark_output(
        "model-a",
        BENCHMARK_TASKS[1],
        '{"claims":[],"unsupported_claims":["nincs forras"]}',
        3.0,
    )

    summary = summarize_results([first, second])

    assert summary["model-a"]["tasks"] == 2
    assert summary["model-a"]["seconds"] == 5.0
