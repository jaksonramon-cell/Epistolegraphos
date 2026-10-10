# Version 1 (used in production)

The original scripts, kept for reference. They worked, but each tool had its own copy of the
helpers, file lookups were by name only, and problems were silent. Version 2 (the
`epistolegraphos/` package) replaces all of them; see the main README for what changed.

| v1 script        | v2 equivalent                                   |
|------------------|-------------------------------------------------|
| `epis.py`        | `cartas.py` + `render.py` (one engine)          |
| `epis_multi.py`  | same engine, donors grouped by CRM contact ID   |
| `egresos.py`     | `cartas.py` (departure letters)                 |
| `Extractor.py`   | `utilidades.dividir_pdf`                        |
| `Logo.py`        | `utilidades.poner_logo`                         |
| `app.py`         | `interfaz.py` (NiceGUI web interface)           |

These files are not imported by version 2 and need folders that are not in this repository.
