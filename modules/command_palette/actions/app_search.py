"""
Busca de aplicativos instalados no Windows.

Escaneia os atalhos (.lnk) das pastas do Menu Iniciar — tanto do usuário
atual quanto do sistema — e retorna apps que casam com a query.

Cache em memória é recarregado a cada 10 minutos ou sob demanda.
"""

import os
import time
from pathlib import Path

_STARTMENU_DIRS = [
    Path(os.environ.get("APPDATA", ""))    / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
]

_cache: list[dict] = []
_cache_at: float = 0.0
_CACHE_TTL = 600  # 10 minutos


def _scan() -> list[dict]:
    apps: list[dict] = []
    for base in _STARTMENU_DIRS:
        if not base.exists():
            continue
        for lnk in base.rglob("*.lnk"):
            name = lnk.stem  # nome sem extensão
            # Ignora atalhos de desinstaladores e entradas de suporte
            low = name.lower()
            if any(skip in low for skip in ("uninstall", "desinstalar", "help", "readme", "release note")):
                continue
            apps.append({
                "_app":     True,
                "name":     name,
                "lnk_path": str(lnk),
                "folder":   str(lnk.parent.relative_to(base)) if lnk.parent != base else "",
            })
    apps.sort(key=lambda a: a["name"].lower())
    return apps


def _get_cache() -> list[dict]:
    global _cache, _cache_at
    if not _cache or (time.time() - _cache_at) > _CACHE_TTL:
        _cache = _scan()
        _cache_at = time.time()
    return _cache


def search_apps(query: str, limit: int = 8) -> list[dict]:
    """
    Retorna apps cujo nome contém a query (case-insensitive).
    Prioriza matches que começam com a query.
    """
    q = query.lower().strip()
    if not q:
        return []

    results = []
    for app in _get_cache():
        name_low = app["name"].lower()
        if q in name_low:
            results.append((0 if name_low.startswith(q) else 1, app))

    results.sort(key=lambda x: x[0])
    return [r[1] for r in results[:limit]]


def refresh_cache() -> int:
    """Força recarregamento do cache. Retorna número de apps encontrados."""
    global _cache, _cache_at
    _cache = _scan()
    _cache_at = time.time()
    return len(_cache)
