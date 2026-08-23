import json
from unittest.mock import Mock, patch

import pandas as pd

from modules.math_agent import DEFAULT_LOCAL_MODEL, DEFAULT_NUM_CTX, build_test_path, preliminary_review
from modules.smart_assistant import OpenAssistantEngine


def demo_df():
    return pd.DataFrame(
        {
            "ID": range(1, 13),
            "sex": ["F", "M"] * 6,
            "glucose": [80, 95, 88, 110, 90, 102, 85, 99, 92, 108, 87, 101],
            "bmi": [20, 25, 23, 29, 22, 27, 21, 26, 24, 30, 22, 28],
        }
    )


def test_rules_path():
    df = demo_df()
    engine = OpenAssistantEngine({"anthro": df})
    response = engine.answer(
        "Quiero comparar glucosa entre grupos de sexo",
        selected_dataset="anthro",
        provider="rules",
    )
    assert response.target_analysis == "mann_whitney"
    ids = [step["test_id"] for step in response.context["test_path"]]
    assert ids == ["exploration", "normality", "mann_whitney"]
    assert "ID" not in response.suggestions["mann_whitney"]["value_cols"]
    assert response.context["test_path"][-1]["path"] == "modules/mann_whitney/mann_whitney.py::mann_whitney_from_loaded"


def test_preliminary_review():
    df = demo_df()
    engine = OpenAssistantEngine({"anthro": df})
    info = engine.inspector.inspect("anthro")
    review = preliminary_review(df, info)
    assert review["shape"] == [12, 4]
    assert "ID" in info["id_like_cols"]
    assert "ID" not in info["numeric_cols"]


def test_ollama_payload():
    df = demo_df()
    engine = OpenAssistantEngine({"anthro": df})
    fake = Mock()
    fake.ok = True
    fake.status_code = 200
    fake.json.return_value = {"message": {"content": "Ruta validada."}}

    with patch("modules.smart_assistant.smart_assistant.requests.post", return_value=fake) as post:
        response = engine.answer(
            "Compara glucosa por sexo",
            selected_dataset="anthro",
            provider="local",
            model=DEFAULT_LOCAL_MODEL,
        )

    assert "Ruta validada" in response.text
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "phi4-mini-reasoning"
    assert payload["stream"] is False
    assert payload["options"]["num_ctx"] == DEFAULT_NUM_CTX
    assert payload["options"]["num_predict"] == 160
    assert payload["keep_alive"] == "30m"
    assert post.call_args.args[0].endswith("/api/chat")


def main():
    test_rules_path()
    test_preliminary_review()
    test_ollama_payload()
    print("OK: agente matemático, test path y payload de Phi funcionando.")


if __name__ == "__main__":
    main()
