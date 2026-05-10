"""
Parse CDR filenames into structured order fields.

Format:  [@|#]P{OS} - {cliente} {material}{índice} x{quantidade} {acabamento}

Test cases
----------
1. Basic:
   "P02107 - Teste A1 x10"
   → os="P02107", client="Teste", material="A", index=1, qty=10, finishing="", urgent=False

2. Urgency prefix @:
   "@P02107 - Pedro Funcionario L@1 x5 com verniz"
   → os="P02107", client="Pedro Funcionario", material="L@", index=1, qty=5,
     finishing="com verniz", urgent=True, urgent_type="@"

3. Urgency prefix # and client with &:
   "#P00831 - Coco & Cia A2 x1"
   → os="P00831", client="Coco & Cia", material="A", index=2, qty=1,
     finishing="", urgent=True, urgent_type="#"

4. Material blackout:
   "P01500 - Cliente X blackout1 x3 sem acabamento"
   → os="P01500", client="Cliente X", material="blackout", index=1, qty=3,
     finishing="sem acabamento"

5. No match (plain name):
   "rascunho_final"
   → os="", client_name="rascunho_final", title="rascunho_final", notes=""
"""

import re

# Token that marks the start of the material+index block:
# letters and/or @ followed by one or more digits, end of token.
_MATERIAL_RE = re.compile(r'^([A-Za-z@]+)\d+$')

# Top-level pattern: optional urgency prefix, then P<os>, then " - ", then rest.
_HEADER_RE = re.compile(
    r'^(?P<pfx>[@#])?P(?P<os>\w+)\s+-\s+(?P<rest>.+)$'
)

# Quantity token: x<digits>
_QTY_RE = re.compile(r'^x(\d+)$', re.IGNORECASE)


def parse_cdr_filename(filename: str) -> dict:
    """
    Parses a CDR filename stem and returns a dict with keys:
      os_number, client_name, material, index, quantity,
      finishing, urgent, urgent_type, title, notes
    Returns a fallback dict if the name does not match the expected pattern.
    """
    m = _HEADER_RE.match(filename.strip())
    if not m:
        return _fallback(filename)

    pfx      = m.group("pfx") or ""
    os_number = m.group("os")
    rest      = m.group("rest").strip()

    # Split rest into tokens to locate the material+index boundary
    tokens = rest.split()
    if not tokens:
        return _fallback(filename)

    material_idx = None   # index in tokens[] where material token sits
    for i, tok in enumerate(tokens):
        if _MATERIAL_RE.match(tok):
            material_idx = i
            break

    if material_idx is None:
        return _fallback(filename)

    client_name = " ".join(tokens[:material_idx]).strip()
    mat_token   = tokens[material_idx]          # e.g. "A1", "L@1", "blackout2"

    # Split material token into letters and trailing digits
    mat_m = re.match(r'^([A-Za-z@]+)(\d+)$', mat_token)
    material = mat_m.group(1)
    index    = int(mat_m.group(2))

    # Everything after the material token
    after = tokens[material_idx + 1:]

    # Find quantity token (x<n>)
    quantity  = 0
    qty_idx   = None
    for i, tok in enumerate(after):
        if _QTY_RE.match(tok):
            quantity = int(tok[1:])
            qty_idx  = i
            break

    # Finishing is everything after the quantity token
    if qty_idx is not None:
        finishing = " ".join(after[qty_idx + 1:]).strip()
    else:
        finishing = " ".join(after).strip()

    title = f"P{os_number} - {client_name}" if client_name else f"P{os_number}"

    notes_parts = [f"{material}{index}", f"x{quantity}"]
    if finishing:
        notes_parts.append(finishing)
    notes = " · ".join(notes_parts)

    return {
        "os_number":   os_number,
        "client_name": client_name,
        "material":    material,
        "index":       index,
        "quantity":    quantity,
        "finishing":   finishing,
        "urgent":      bool(pfx),
        "urgent_type": pfx,
        "title":       title,
        "notes":       notes,
    }


def _fallback(filename: str) -> dict:
    return {
        "os_number":   "",
        "client_name": filename,
        "material":    "",
        "index":       0,
        "quantity":    0,
        "finishing":   "",
        "urgent":      False,
        "urgent_type": "",
        "title":       filename,
        "notes":       "",
    }
