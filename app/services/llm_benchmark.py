from dataclasses import dataclass
import json
import re
import time
from typing import Any

from app.services.llm import LLMChatMessage, LLMProvider


BENCHMARK_SYSTEM_PROMPT = """/no_think
You are a source-faithful document analysis component.
You are analyzing Hungarian source text.
You may rely only on the provided SOURCE text.
Do not infer and do not fill in missing facts.
Return only a valid JSON object, with user-facing text in Hungarian.
Every claims item must include quote_text, and quote_text must appear literally in the SOURCE text.
Copy quote_text character-exactly from the SOURCE text: do not translate, fix, add accents, or normalize it.
If there is not enough source support for a claim, do not put it into claims; put it into unsupported_claims.
If the claim requested in the task is not present in the SOURCE text, the claims list must be empty.
Expected JSON shape:
{"claims":[{"claim_text":"...","quote_text":"...","source_label":"chunk_1"}],"unsupported_claims":["..."]}
"""


@dataclass(frozen=True)
class BenchmarkTask:
    name: str
    source_text: str
    instruction: str
    expected_quote: str | None
    expected_no_claims: bool = False


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    task_name: str
    score: int
    max_score: int
    elapsed_seconds: float
    valid_json: bool
    quote_valid: bool
    no_source_respected: bool
    raw_content: str
    errors: list[str]


BENCHMARK_TASKS = [
    BenchmarkTask(
        name="supported_claim_hu",
        source_text=(
            "chunk_1:\n"
            "A jegyzokonyv szerint 2024. marcius 12-en 18:42-kor telefonhivas tortent "
            "Kovacs Anna es Nagy Peter kozott. A hivas idotartama 3 perc 14 masodperc volt."
        ),
        instruction="Extract one source-supported claim about the phone call. Return the claim text in Hungarian.",
        expected_quote="2024. marcius 12-en 18:42-kor telefonhivas tortent Kovacs Anna es Nagy Peter kozott",
    ),
    BenchmarkTask(
        name="no_source_no_claim",
        source_text=(
            "chunk_1:\n"
            "A helyszini szemle 09:15-kor kezdodott. A jegyzokonyv csak a lezart ajto allapotat rogzitette."
        ),
        instruction="Determine who opened the door. If the SOURCE does not state this, return an empty claims list.",
        expected_quote=None,
        expected_no_claims=True,
    ),
    BenchmarkTask(
        name="exact_quote_boundary",
        source_text=(
            "chunk_1:\n"
            "A tanukent meghallgatott szemely azt mondta: \"a kek taskat a lepcso mellett lattam\". "
            "Mas targyrol nem tett emlitest."
        ),
        instruction="Extract what the witness saw. Return the claim text in Hungarian.",
        expected_quote="a kek taskat a lepcso mellett lattam",
    ),
]


def run_benchmark(
    provider: LLMProvider,
    models: list[str],
    tasks: list[BenchmarkTask] | None = None,
) -> list[BenchmarkResult]:
    benchmark_tasks = tasks or BENCHMARK_TASKS
    results: list[BenchmarkResult] = []
    for model in models:
        for task in benchmark_tasks:
            started_at = time.perf_counter()
            try:
                completion = provider.chat_completion(
                    model,
                    [
                        LLMChatMessage(role="system", content=BENCHMARK_SYSTEM_PROMPT),
                        LLMChatMessage(role="user", content=_task_prompt(task)),
                    ],
                    temperature=0.1,
                    max_tokens=1600,
                )
                elapsed = time.perf_counter() - started_at
                results.append(score_benchmark_output(model, task, completion.content, elapsed))
            except Exception as exc:  # noqa: BLE001 - benchmark should report provider failures per task
                elapsed = time.perf_counter() - started_at
                results.append(
                    BenchmarkResult(
                        model=model,
                        task_name=task.name,
                        score=0,
                        max_score=4,
                        elapsed_seconds=elapsed,
                        valid_json=False,
                        quote_valid=False,
                        no_source_respected=False,
                        raw_content="",
                        errors=[str(exc)],
                    )
                )
    return results


def score_benchmark_output(model: str, task: BenchmarkTask, raw_content: str, elapsed_seconds: float) -> BenchmarkResult:
    errors: list[str] = []
    payload = _parse_json_object(raw_content)
    valid_json = payload is not None
    score = 1 if valid_json else 0
    quote_valid = False
    no_source_respected = False

    claims: list[dict[str, Any]] = []
    unsupported_claims: list[Any] = []
    if payload is None:
        errors.append("invalid_json")
    else:
        claims_value = payload.get("claims")
        unsupported_value = payload.get("unsupported_claims")
        if isinstance(claims_value, list):
            claims = [item for item in claims_value if isinstance(item, dict)]
        else:
            errors.append("claims_not_list")
        if isinstance(unsupported_value, list):
            unsupported_claims = unsupported_value
        else:
            errors.append("unsupported_claims_not_list")

    if task.expected_no_claims:
        no_source_respected = len(claims) == 0 and len(unsupported_claims) > 0
        if no_source_respected:
            score += 3
        else:
            errors.append("no_source_rule_failed")
    else:
        quote_valid = _claims_quote_source_text(claims, task.source_text)
        if quote_valid:
            score += 1
        else:
            errors.append("quote_not_found_in_source")
        if task.expected_quote is not None and any(task.expected_quote in str(claim.get("quote_text", "")) for claim in claims):
            score += 1
        else:
            errors.append("expected_quote_missing")
        if claims and all(claim.get("source_label") == "chunk_1" for claim in claims):
            score += 1
        else:
            errors.append("source_label_missing")

    return BenchmarkResult(
        model=model,
        task_name=task.name,
        score=score,
        max_score=4,
        elapsed_seconds=elapsed_seconds,
        valid_json=valid_json,
        quote_valid=quote_valid,
        no_source_respected=no_source_respected,
        raw_content=raw_content,
        errors=errors,
    )


def summarize_results(results: list[BenchmarkResult]) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for result in results:
        item = summary.setdefault(result.model, {"score": 0, "max_score": 0, "tasks": 0, "seconds": 0.0})
        item["score"] += result.score
        item["max_score"] += result.max_score
        item["tasks"] += 1
        item["seconds"] += result.elapsed_seconds
    return summary


def _task_prompt(task: BenchmarkTask) -> str:
    return f"SOURCE:\n{task.source_text}\n\nTASK:\n{task.instruction}"


def _parse_json_object(raw_content: str) -> dict[str, Any] | None:
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match is None:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _claims_quote_source_text(claims: list[dict[str, Any]], source_text: str) -> bool:
    if not claims:
        return False
    for claim in claims:
        quote_text = claim.get("quote_text")
        if not isinstance(quote_text, str) or quote_text == "" or quote_text not in source_text:
            return False
    return True
