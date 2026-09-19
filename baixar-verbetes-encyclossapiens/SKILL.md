---
name: baixar-verbetes-encyclossapiens
description: >-
  Downloads missing Conscienciologia encyclopedia verbete PDFs via the public
  API at enciclopediadaconscienciologia.org (PDFs on
  arquivos.enciclopediadaconscienciologia.org). Incremental by tertúlia number;
  stable filename contract. Use when asked to baixar verbetes, atualizar a
  enciclopédia, sync Encyclossapiens PDFs, or run baixar_verbetes /
  corrigir_verbetes.
---

# Encyclossapiens verbete downloader

Agent skill + CLI to keep a local PDF library in sync with the Conscienciologia
encyclopedia repository.

## When to use

- Download missing verbetes / update the encyclopedia PDF set
- Run `baixar_verbetes.py` or `corrigir_verbetes.py`

## Hard stops

- Download **only** entries present in the remote index (default: missing locally).
- Do not invent tertúlia numbers outside the index.
- Prefer `--dry-run` unless the user explicitly asked to download or apply.
- Do not mass-rename or move the library without explicit authorization.
- Legacy index (`--fonte legado`) is incomplete; use only if requested.

## Data sources

| Role | URL |
|---|---|
| Index (default) | `GET /api/verbetes/search` on `https://enciclopediadaconscienciologia.org` |
| PDF files | `https://arquivos.enciclopediadaconscienciologia.org/<arquivo_pdf_path>` |
| Verbete page | `https://enciclopediadaconscienciologia.org/{tertulia}-{slug}` |
| Legacy index | `https://encyclossapiens.space/buscaverbete/bancodedados.js` (`--fonte legado`) |

Example (tertúlia 7526):

- Page: `https://enciclopediadaconscienciologia.org/7526-conjectura-parapercepciologica-cosmoetica`
- PDF: `https://arquivos.enciclopediadaconscienciologia.org/verbetes/Conjectura_Parapercepciologica_Cosmoetica.pdf`

## Output directory

Resolution order in the scripts:

1. `--out DIR`
2. Environment variable `VERBETES_OUT`
3. Existing folder named `Verbetes da Enciclopédia da Conscienciologia (Encyclossapiens)` found walking up from cwd / script
4. `./Verbetes`

## Commands

Scripts live in `scripts/` next to this file. Dependency: `pip install -r scripts/requirements.txt` (or `pip install requests`).

```bash
# Inventory only
python3 scripts/baixar_verbetes.py --dry-run --out ./Verbetes

# Download missing PDFs
python3 scripts/baixar_verbetes.py --out ./Verbetes

# Only tertúlias >= N
python3 scripts/baixar_verbetes.py --out ./Verbetes --desde 7129

# Plan renames / re-downloads vs index
python3 scripts/corrigir_verbetes.py --dry-run --out ./Verbetes
python3 scripts/corrigir_verbetes.py --apply --out ./Verbetes
```

Report: missing count, tertúlia range, OK/fail. CSVs under `<out>/.meta/`.

## Filename contract

```
{tertulia} - {DD.MM.YYYY} - {title} - {specialty} - {theme} - {initials} - {author}.pdf
```

Implemented by the downloader: strip HTML; `/` in titles → `∕`; empty fields omitted (no ` -  - `).

## Gaps in numbering

Tertúlia numbers are not a contiguous range. Only download what the API returns.
