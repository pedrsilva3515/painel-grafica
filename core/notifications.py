import json
from pathlib import Path

_SETTINGS = Path(__file__).parent.parent / "config" / "settings.json"

# Keys and their default enabled state
DEFAULTS: dict[str, bool] = {
    "prazos_criticos":      True,
    "cdr_nova_os":          True,
    "cdr_os_renomeada":     True,
    "indice_atualizado":    True,
    "app_pronto":           True,
    "configuracoes_salvas": True,
    "lembretes":            True,
}


def is_enabled(key: str) -> bool:
    try:
        data = json.loads(_SETTINGS.read_text(encoding="utf-8"))
        return data.get("notifications", {}).get(key, DEFAULTS.get(key, True))
    except Exception:
        return True
