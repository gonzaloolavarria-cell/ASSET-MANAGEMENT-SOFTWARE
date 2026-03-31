# Equipment Manuals Directory

Place equipment manuals here, organized by **equipment_type_id** from `data/libraries/equipment_library.json`.

## Directory Structure

```
manuals/
  ET-SAG-MILL/          # Folder name = equipment_type_id
    operations-manual.pdf
    maintenance-manual.pdf
    troubleshooting.md
  ET-BALL-MILL/
    manual.pdf
  _shared/              # Cross-equipment docs (safety standards, general procedures)
    general-safety.pdf
```

## Supported File Types

- `.pdf` — requires `pymupdf` (text-based PDFs only, no OCR)
- `.txt` — plain text
- `.md` — Markdown

## How It Works

The Equipment Chat page (Page 20) loads all files from the selected equipment type's folder + `_shared/` into Claude's context window. The equipment library data is always included as a baseline.

## Naming Convention

Use descriptive filenames. The filename (without extension) becomes the section title in the chat context.
