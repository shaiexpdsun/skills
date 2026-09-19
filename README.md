# Cursor Agent Skills

Public [Agent Skills](https://cursor.com/docs/skills) for [Cursor](https://cursor.com).

Each folder is one skill (`SKILL.md` + optional `scripts/`).

## Skills

| Skill | Description |
|---|---|
| [`baixar-verbetes-encyclossapiens`](./baixar-verbetes-encyclossapiens/) | Download missing Conscienciologia encyclopedia verbete PDFs (Encyclossapiens API) |

## Install

### Option A — copy into Cursor skills

```bash
git clone https://github.com/shaiexpdsun/skills.git
cp -R skills/baixar-verbetes-encyclossapiens ~/.cursor/skills/
```

Or copy into a project’s `.cursor/skills/`.

### Option B — run the CLI only

```bash
cd baixar-verbetes-encyclossapiens
pip install -r scripts/requirements.txt
python3 scripts/baixar_verbetes.py --dry-run --out ./Verbetes
```

## License

MIT
