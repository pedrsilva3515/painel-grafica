"""
Integração Mubisys — abre uma OS no browser.

Uso no Command Palette: os:1042
URL configurável em settings.json → "mubisys_url_template"
Padrão: apenas abre o número da OS em pesquisa no Google caso não configurado.
"""

import json
import webbrowser
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent.parent.parent / "config" / "settings.json"

_DEFAULT_TEMPLATE = "https://www.google.com/search?q=OS+{os_number}+mubisys"


def _url_template() -> str:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data.get("mubisys_url_template", _DEFAULT_TEMPLATE)
    except Exception:
        return _DEFAULT_TEMPLATE


def open_os(os_number: str) -> bool:
    """Abre a OS no browser. Retorna True se conseguiu."""
    os_number = os_number.strip()
    if not os_number:
        return False
    url = _url_template().format(os_number=os_number)
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False
