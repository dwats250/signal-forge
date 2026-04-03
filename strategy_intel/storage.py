import json
import os
from typing import List

from .models import EdgeComponent

LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "library.json")


def _load_raw() -> dict:
    if not os.path.exists(LIBRARY_PATH):
        data = {"components": []}
        _save_raw(data)
        return data
    with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "components" not in data:
        data["components"] = []
    return data


def _save_raw(data: dict) -> None:
    with open(LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_components() -> List[EdgeComponent]:
    data = _load_raw()
    return [EdgeComponent.from_dict(c) for c in data.get("components", [])]


def save_component(component: EdgeComponent) -> None:
    data = _load_raw()
    data["components"].append(component.to_dict())
    _save_raw(data)


def replace_all(components: List[EdgeComponent]) -> None:
    _save_raw({"components": [c.to_dict() for c in components]})
