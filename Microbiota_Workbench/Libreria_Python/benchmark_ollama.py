import json
import os
import time
from pathlib import Path

import requests


def load_env():
    for path in [Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"]:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        break


def seconds(ns):
    return round(float(ns or 0) / 1_000_000_000, 3)


def main():
    load_env()
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "phi4-mini-reasoning:3.8b-q4_K_M")
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
    num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "160"))
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Responde de forma muy breve. No hagas cálculos innecesarios."},
            {"role": "user", "content": "Indica en tres puntos qué revisar antes de comparar dos grupos numéricos."},
        ],
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0.05,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        },
    }

    start = time.perf_counter()
    response = requests.post(base + "/api/chat", json=payload, timeout=300)
    elapsed = time.perf_counter() - start
    response.raise_for_status()
    data = response.json()
    eval_count = int(data.get("eval_count") or 0)
    eval_seconds = float(data.get("eval_duration") or 0) / 1_000_000_000

    report = {
        "model": model,
        "wall_seconds": round(elapsed, 3),
        "ollama_total_seconds": seconds(data.get("total_duration")),
        "load_seconds": seconds(data.get("load_duration")),
        "prompt_seconds": seconds(data.get("prompt_eval_duration")),
        "generation_seconds": seconds(data.get("eval_duration")),
        "prompt_tokens": int(data.get("prompt_eval_count") or 0),
        "generated_tokens": eval_count,
        "tokens_per_second": round(eval_count / eval_seconds, 2) if eval_count and eval_seconds else None,
        "num_ctx": num_ctx,
        "num_predict": num_predict,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nRespuesta del modelo:\n" + ((data.get("message") or {}).get("content") or ""))


if __name__ == "__main__":
    main()
