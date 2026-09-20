# Cursor Agent Skills

Public [Agent Skills](https://cursor.com/docs/skills) for [Cursor](https://cursor.com).

Each folder is one skill (`SKILL.md` + optional scripts / assets).

## Skills

| Skill | Description |
|---|---|
| [`baixar-verbetes-encyclossapiens`](./baixar-verbetes-encyclossapiens/) | Download missing Conscienciologia encyclopedia verbete PDFs (Encyclossapiens API) |
| [`html-report`](./html-report/) | Standalone dark HTML reports (canal B: black + cold gray, Cursor-like chrome) |

## Install

### Option A — copy into Cursor skills

```bash
git clone https://github.com/shaiexpdsun/skills.git
cp -R skills/baixar-verbetes-encyclossapiens ~/.cursor/skills/
cp -R skills/html-report ~/.cursor/skills/
```

Or copy into a project’s `.cursor/skills/`.

### Option B — HTML report demo only

Open [`html-report/design-system.html`](./html-report/design-system.html) in a browser. Copy the `<style>` from [`html-report/tokens.html`](./html-report/tokens.html) into new reports under `./reports/`.

### Option C — verbetes CLI only

```bash
cd baixar-verbetes-encyclossapiens
pip install -r scripts/requirements.txt
python3 scripts/baixar_verbetes.py --dry-run --out ./Verbetes
```

## License

MIT
