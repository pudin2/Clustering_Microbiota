import os
import pandas as pd

from modules.smart_assistant import OpenAssistantEngine


def main():
    df = pd.DataFrame({
        "ID": range(1, 41),
        "sex": ["Male", "Female"] * 20,
        "glucose": [80 + (i % 12) for i in range(40)],
        "HDL": [40 + (i % 10) for i in range(40)],
        "LDL": [90 + (i % 15) for i in range(40)],
        "age": [20 + (i % 30) for i in range(40)],
    })
    engine = OpenAssistantEngine({"anthro_data": df})
    response = engine.answer(
        "Quiero comparar glucosa entre grupos de sexo. ¿Qué prueba y parámetros uso?",
        selected_dataset="anthro_data",
        provider="local",
        model=os.getenv("OLLAMA_MODEL", "phi4-mini-reasoning:3.8b-q4_K_M"),
    )
    print(response.text)
    if response.warnings:
        print("\nAVISOS:")
        for item in response.warnings:
            print("-", item)
    if response.context.get("llm_metrics"):
        print("\nMETRICAS:", response.context["llm_metrics"])


if __name__ == "__main__":
    main()
