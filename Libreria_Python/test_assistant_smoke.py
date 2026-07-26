import pandas as pd

from Smart_Assistant import OpenAssistantEngine


def main():
    df = pd.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5, 6],
            "sex": ["F", "M", "F", "M", "F", "M"],
            "glucose": [80, 95, 88, 110, 90, 102],
            "bmi": [20, 25, 23, 29, 22, 27],
        }
    )
    engine = OpenAssistantEngine({"anthro": df})
    response = engine.answer(
        "Quiero comparar glucosa entre grupos de sexo. ¿Qué prueba y parámetros uso?",
        selected_dataset="anthro",
        provider="rules",
    )
    assert response.target_analysis == "mann_whitney"
    assert "mann_whitney" in response.suggestions
    print("OK: motor determinístico y sugerencias funcionando.")


if __name__ == "__main__":
    main()
