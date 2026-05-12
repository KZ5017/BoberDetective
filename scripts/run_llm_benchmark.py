from __future__ import annotations

import argparse
from dataclasses import replace

from app.core.config import get_settings
from app.services.llm import LMStudioNativeProvider, OpenAICompatibleLocalProvider
from app.services.llm_benchmark import run_benchmark, summarize_results


DEFAULT_MODELS = [
    "qwen/qwen3.5-9b",
    "meta-llama-3.1-8b-instruct",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small synthetic source-faithfulness benchmark against local LM Studio models.")
    parser.add_argument("--model", action="append", dest="models", help="Model id to benchmark. Can be repeated.")
    parser.add_argument("--provider", choices=["openai", "native"], default="openai", help="LM Studio API style to use.")
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout in seconds for each model call.")
    parser.add_argument("--show-raw", action="store_true", help="Print raw model outputs after each task result.")
    args = parser.parse_args()

    settings = replace(get_settings(), llm_timeout_seconds=args.timeout)
    provider = LMStudioNativeProvider(settings) if args.provider == "native" else OpenAICompatibleLocalProvider(settings)
    models = args.models or DEFAULT_MODELS
    results = run_benchmark(provider, models)
    summary = summarize_results(results)

    print(f"Provider: {args.provider}")
    print("Model summary")
    for model, item in summary.items():
        print(f"- {model}: {item['score']}/{item['max_score']} points, {item['tasks']} tasks, {item['seconds']:.1f}s")

    print("\nTask details")
    for result in results:
        errors = ", ".join(result.errors) if result.errors else "none"
        print(
            f"- {result.model} / {result.task_name}: "
            f"{result.score}/{result.max_score}, {result.elapsed_seconds:.1f}s, errors={errors}"
        )
        if args.show_raw:
            print("  raw:")
            for line in result.raw_content.splitlines() or [""]:
                print(f"    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
