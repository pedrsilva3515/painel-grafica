"""
Calculadora estruturada do Command Palette.

Sintaxe: =prefixo param1 param2 ...
Exemplos:
  =m2 100x50cm 3un       → largura=100, altura=50, quantidade=3
  =m2 largura=100 altura=50 quantidade=3
  =m2 100 50 3

Templates definidos em config/settings.json → "calculator_templates".
"""

import json
import re
from pathlib import Path

from PyQt6.QtWidgets import QApplication

SETTINGS_FILE = Path(__file__).parent.parent.parent.parent / "config" / "settings.json"


def _load_templates() -> list[dict]:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data.get("calculator_templates", [])
    except Exception:
        return []


def _parse_args(raw: str, template: dict) -> dict | None:
    """
    Tenta extrair variáveis da fórmula a partir da string raw.
    Suporta:
      - "100x50cm 3un"  (posicional com separador x e sufixos)
      - "largura=100 altura=50 quantidade=3"  (nomeado)
      - "100 50 3"  (posicional puro)
    """
    # Extrair variáveis necessárias da fórmula
    formula = template.get("formula", "")
    # Identifica nomes de variáveis na fórmula (palavras simples, não keywords)
    _keywords = {"and", "or", "not", "in", "is", "if", "else", "for"}
    var_names = [
        v for v in re.findall(r"\b([a-z_][a-z0-9_]*)\b", formula)
        if v not in _keywords
    ]
    # Deduplica preservando ordem
    seen: set[str] = set()
    var_names = [v for v in var_names if not (v in seen or seen.add(v))]

    values: dict[str, float] = {}

    # 1. Tentativa: key=value
    named = re.findall(r"([a-z_]\w*)\s*=\s*([\d.,]+)", raw, re.I)
    for k, v in named:
        try:
            values[k.lower()] = float(v.replace(",", "."))
        except ValueError:
            pass

    if len(values) == len(var_names) and all(v in values for v in var_names):
        return values

    # 2. Tentativa: extrair todos os números na ordem das variáveis
    numbers = re.findall(r"[\d]+(?:[.,]\d+)?", raw)
    floats = []
    for n in numbers:
        try:
            floats.append(float(n.replace(",", ".")))
        except ValueError:
            pass

    if len(floats) >= len(var_names):
        for i, name in enumerate(var_names):
            if name not in values:
                values[name] = floats[i]
        return values

    return None


def calculate(query: str) -> dict | None:
    """
    Recebe a query sem o prefixo '='.
    Retorna dict com keys: 'label', 'result_text', 'copied'
    ou None se não houver template correspondente / erro de parse.
    """
    query = query.strip()
    if not query:
        return None

    parts = query.split(None, 1)
    prefix = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    templates = _load_templates()
    template = next((t for t in templates if t.get("prefixo", "").lower() == prefix), None)
    if not template:
        return None

    args = _parse_args(rest, template)
    if args is None:
        return {"label": template["nome"], "result_text": "⚠️ Parâmetros inválidos", "copied": False}

    try:
        resultado = eval(template["formula"], {"__builtins__": {}}, args)  # noqa: S307
        args["resultado"] = resultado
        text = template.get("output", "{resultado}").format(**args)
    except Exception as exc:
        return {"label": template["nome"], "result_text": f"⚠️ Erro: {exc}", "copied": False}

    # Copiar para clipboard
    try:
        QApplication.clipboard().setText(text)
        copied = True
    except Exception:
        copied = False

    return {"label": template["nome"], "result_text": text, "copied": copied}


def list_templates() -> list[dict]:
    """Retorna lista resumida de templates para exibir no palette."""
    return [
        {"prefixo": t.get("prefixo", ""), "nome": t.get("nome", "")}
        for t in _load_templates()
    ]
