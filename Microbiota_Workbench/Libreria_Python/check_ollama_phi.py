"""Verifica conexión con Ollama y presencia de Phi-4 Mini Reasoning."""
import os
import sys
import requests

MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini-reasoning")
BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def main():
    print(f"Ollama: {BASE}")
    print(f"Modelo esperado: {MODEL}")
    try:
        response = requests.get(BASE + "/api/tags", timeout=5)
        response.raise_for_status()
    except Exception as exc:
        print(f"ERROR: no pude conectar con Ollama: {exc}")
        print("Inicia Ollama y vuelve a ejecutar este archivo.")
        return 1

    models = []
    for item in response.json().get("models", []):
        name = str(item.get("name") or item.get("model") or "")
        if name:
            models.append(name)

    matches = [name for name in models if name == MODEL or name.startswith(MODEL + ":")]
    if not matches:
        print("ERROR: Phi-4 Mini Reasoning no aparece instalado.")
        print(f"Ejecuta: ollama pull {MODEL}")
        return 2

    print("OK: modelo encontrado:")
    for name in matches:
        print(" -", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
