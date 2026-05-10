import json
import os
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "settings.json"

_SUBFOLDER_STATUS: dict[str, str] = {
    "organização": "Organização",
    "separação":   "Separação",
    "acabamento":  "Acabamento",
    "concluídos":  "Concluído",
}

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def find_exported_files(os_number: str) -> list[dict]:
    """
    Busca todos os JPG/PNG cujo nome começa com os_number nas pastas
    de impressão configuradas e suas subpastas de status.

    Retorna lista de dicts ordenada por modified_at DESC:
      filepath    : str
      filename    : str
      material    : str  — "Adesivo" | "Lona" | "Papel"
      status      : str  — "Aguardando impressão" | "Organização" |
                           "Separação" | "Acabamento" | "Concluído"
      modified_at : float
    """
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    print_folders: dict[str, str] = settings.get("print_folders", {})
    results: list[dict] = []

    for material, root_path in print_folders.items():
        if not root_path or not os.path.isdir(root_path):
            continue

        _scan_dir(root_path, material, "Aguardando impressão", os_number, results)

        for sub_name, status in _SUBFOLDER_STATUS.items():
            sub_path = os.path.join(root_path, sub_name)
            if os.path.isdir(sub_path):
                _scan_dir(sub_path, material, status, os_number, results)

    results.sort(key=lambda x: x["modified_at"], reverse=True)
    return results


def _scan_dir(
    folder: str,
    material: str,
    status: str,
    os_number: str,
    results: list[dict],
) -> None:
    prefix = os_number.lower()
    try:
        for fname in os.listdir(folder):
            if not fname.lower().startswith(prefix):
                continue
            if Path(fname).suffix.lower() not in _IMAGE_EXTS:
                continue
            fpath = os.path.join(folder, fname)
            try:
                modified_at = os.path.getmtime(fpath)
            except OSError:
                continue
            results.append({
                "filepath":    fpath,
                "filename":    fname,
                "material":    material,
                "status":      status,
                "modified_at": modified_at,
            })
    except OSError:
        pass
