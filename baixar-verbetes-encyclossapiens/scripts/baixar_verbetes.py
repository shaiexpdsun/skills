#!/usr/bin/env python3
"""
Baixa PDFs de verbetes da Enciclopédia da Conscienciologia — só os que faltam.

Fonte padrão (2026): API do site
  https://enciclopediadaconscienciologia.org/api/verbetes/search
PDFs: https://arquivos.enciclopediadaconscienciologia.org/<arquivo_pdf_path>

Legado (incompleto ~7114): --fonte legado → bancodedados.js no encyclossapiens.space

- Escaneia a pasta destino pelos números de tertúlia e baixa só os ausentes
- Limpa <i>…</i> e outros HTML do título antes de nomear
- Não transforma "/" do título em " - " (evita hífen-hífen / campos deslocados)
- Nome estável:
    "{N} - {DD.MM.YYYY} - {Título} - {Especialidade} - {Tema} - {Sigla} - {Nome}.pdf"

Pasta destino: --out → VERBETES_OUT → pasta canónica se existir → ./Verbetes

DEPENDÊNCIAS
    pip install requests

USO
    python baixar_verbetes.py --dry-run
    python baixar_verbetes.py --out ./meus-verbetes
    python baixar_verbetes.py --desde 7129
    python baixar_verbetes.py --fonte legado   # índice antigo
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path

import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

BANCO_DADOS_URL = "https://encyclossapiens.space/buscaverbete/bancodedados.js"
SITE_BASE = "https://enciclopediadaconscienciologia.org"
ARQUIVOS_BASE = "https://arquivos.enciclopediadaconscienciologia.org"
SEARCH_URL = f"{SITE_BASE}/api/verbetes/search"
CANONICAL_DIR_NAME = (
    "Verbetes da Enciclopédia da Conscienciologia (Encyclossapiens)"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def default_out_dir() -> Path:
    """Resolve output directory: VERBETES_OUT → existing canonical folder → ./Verbetes."""
    env = os.environ.get("VERBETES_OUT", "").strip()
    if env:
        return Path(env).expanduser()

    roots = [Path.cwd().resolve(), *Path(__file__).resolve().parents]
    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        candidate = root / CANONICAL_DIR_NAME
        if candidate.is_dir():
            return candidate

    return Path.cwd() / "Verbetes"


# Preferir default_out_dir() em runtime. Alias legado (não usar como Path).
DEFAULT_OUT = None

INVALID_CHARS = r'[\\:*?"<>|]'  # NÃO inclui / — tratado à parte no título
HTML_TAG_RE = re.compile(r"<[^>]+>")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TRAILING_COMMA_RE = re.compile(r",(\s*[\]\}])")
PDF_LINK_RE = re.compile(r'href="([^"]+?\.pdf)"', re.IGNORECASE)
NUM_PREFIX_RE = re.compile(r"^(\d+)(?:\s*-\s*|\s+)")
# verbetógrafo: "W. V. - Waldo Vieira" ou "R. M. – Rodrigo Marchioli"
VERBETOGRAFO_SPLIT_RE = re.compile(r"\s*[-–—−]\s*", re.UNICODE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("verbetes")


# --------------------------------------------------------------------------
# Nome de arquivo
# --------------------------------------------------------------------------

def limpar_html(texto: str) -> str:
    texto = unescape(str(texto))
    texto = HTML_TAG_RE.sub("", texto)
    return texto.strip()


def sanitize_campo(text: str) -> str:
    text = limpar_html(text)
    text = re.sub(INVALID_CHARS, "-", text)
    text = re.sub(r"\s+", " ", text)
    # só whitespace nas pontas — NÃO strip('.') senão "R. S. G." vira "R. S. G"
    return text.strip()


def sanitize_titulo(text: str) -> str:
    """
    Título pode ter Antagonismo A / B e <i>…</i>.
    Troca / por barra unicode (∕) para NÃO virar separador ' - ' no nome.
    """
    text = limpar_html(text)
    # Antipodias / binômios com en-dash tipográfico → manter en-dash sem espaços extras
    text = text.replace("–", "–").replace("—", "–")
    text = text.replace(" / ", "∕").replace("/", "∕")
    text = re.sub(INVALID_CHARS, "-", text)
    text = re.sub(r"\s+", " ", text)
    # nunca deixar pedaço vazio que gere " -  - "
    text = re.sub(r"\s*-\s*-\s*", " – ", text)
    return text.strip()


def split_verbetografo(texto: str) -> tuple[str, str]:
    texto = limpar_html(texto).strip()
    if not texto:
        return "", ""
    partes = VERBETOGRAFO_SPLIT_RE.split(texto, maxsplit=1)
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return "", texto


def montar_nome_arquivo(v: dict) -> str:
    partes = [
        str(v["tertulia"]).strip(),
        sanitize_campo(v["data"]),
        sanitize_titulo(v["titulo"]),
        sanitize_campo(v["especialidade"]),
        sanitize_campo(v["tema"]),
        sanitize_campo(v.get("sigla", "")),
        sanitize_campo(v.get("nome", "")),
    ]
    # drop empty (sigla/nome podem faltar); nunca juntar vazios → " -  - "
    nome = " - ".join(p for p in partes if p)
    nome = re.sub(r"(?:\s-\s){2,}", " - ", nome)
    return nome + ".pdf"


def slugify(titulo: str) -> str:
    titulo = limpar_html(titulo)
    normalizado = unicodedata.normalize("NFKD", titulo)
    sem_acento = "".join(c for c in normalizado if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower())
    return slug.strip("-")


# --------------------------------------------------------------------------
# Pasta local: números já baixados
# --------------------------------------------------------------------------

def numeros_locais(pasta: Path) -> dict[int, Path]:
    """Mapa tertúlia → Path. Aceita '7128 - ...' e bug legado '6522 13.12....'."""
    achados: dict[int, Path] = {}
    if not pasta.is_dir():
        return achados
    for f in pasta.iterdir():
        if not f.is_file() or f.suffix.lower() != ".pdf":
            continue
        m = NUM_PREFIX_RE.match(f.name)
        if not m:
            continue
        n = int(m.group(1))
        # se duplicar, fica o primeiro; logamos depois
        achados.setdefault(n, f)
    return achados


# --------------------------------------------------------------------------
# Índice remoto
# --------------------------------------------------------------------------

def normalizar_data(raw: str) -> str:
    """API nova: YYYY/MM/DD ou YYYY-MM-DD → DD.MM.YYYY. Legado já vem DD.MM.YYYY."""
    raw = str(raw or "").strip()
    m = re.match(r"^(\d{4})[/-](\d{2})[/-](\d{2})$", raw)
    if m:
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    return raw


def pdf_url_de_path(path: str | None) -> str:
    path = (path or "").strip().lstrip("/")
    if not path:
        return ""
    return f"{ARQUIVOS_BASE}/{path}"


def baixar_indice_api(session: requests.Session, rows_per_page: int = 1000) -> list[dict]:
    """Índice completo via /api/verbetes/search (site 2026, ~7513+)."""
    log.info("Baixando índice: %s", SEARCH_URL)
    session.headers.setdefault("Accept", "application/json")
    session.headers.setdefault("Referer", f"{SITE_BASE}/")

    verbetes: list[dict] = []
    page = 1
    total = None
    while True:
        resp = session.get(
            SEARCH_URL,
            params={
                "q": "",
                "filter": "titulo",
                "tematologia": "",
                "page": page,
                "rowsPerPage": rows_per_page,
                "sortBy": "tertulia_aula",
                "sortType": "asc",
                "posfilterEspecialidade": "",
                "posfilterVerbetografo": "",
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items") or []
        if total is None:
            total = int(data.get("total") or 0)
            log.info("Índice remoto (API): %d verbetes declarados", total)
        if not items:
            break
        for item in items:
            try:
                tertulia_n = int(item["tertulia_aula"])
            except (KeyError, TypeError, ValueError):
                continue
            titulo = limpar_html(item.get("verbete", ""))
            path = item.get("arquivo_pdf_path") or ""
            verbetes.append(
                {
                    "titulo": titulo,
                    "especialidade": limpar_html(item.get("especialidade", "")),
                    "tema": limpar_html(item.get("tematologia") or item.get("tema") or ""),
                    "sigla": limpar_html(item.get("iniciais", "")),
                    "nome": limpar_html(item.get("nome", "")),
                    "tertulia": tertulia_n,
                    "data": normalizar_data(item.get("tertulia_data", "")),
                    "pdf_url": pdf_url_de_path(path),
                    "pagina_url": f"{SITE_BASE}/{tertulia_n}-{slugify(titulo)}",
                    "arquivo_pdf_path": path,
                }
            )
        log.info("  página %d: +%d (acumulado %d)", page, len(items), len(verbetes))
        if total and len(verbetes) >= total:
            break
        if len(items) < rows_per_page:
            break
        page += 1

    # dedupe por tertúlia (fica o último)
    por_num = {v["tertulia"]: v for v in verbetes}
    out = [por_num[n] for n in sorted(por_num)]
    log.info("Índice útil: %d verbetes (máx tertúlia %d)", len(out), max(por_num) if por_num else 0)
    return out


def baixar_indice_legado(session: requests.Session) -> list[dict]:
    """Índice antigo bancodedados.js (desatualizado; ~7114)."""
    log.info("Baixando índice legado: %s", BANCO_DADOS_URL)
    resp = session.get(BANCO_DADOS_URL, timeout=60)
    resp.raise_for_status()
    texto = resp.content.decode("utf-8", errors="replace")

    m = re.search(r"global_data\s*=\s*(\[.*\])\s*;?\s*$", texto, re.S)
    if not m:
        log.error("Não achei global_data em bancodedados.js — formato mudou?")
        sys.exit(1)

    array_texto = m.group(1)

    def limpar_js(s: str) -> str:
        s = CTRL_RE.sub(" ", s)
        return TRAILING_COMMA_RE.sub(r"\1", s)

    try:
        bruto = json.loads(array_texto, strict=False)
    except json.JSONDecodeError as e:
        log.warning("JSON estrito falhou (%s); limpando e tentando de novo…", e)
        bruto = json.loads(limpar_js(array_texto), strict=False)

    linhas = bruto[1:]
    log.info("Índice legado: %d verbetes", len(linhas))

    verbetes: list[dict] = []
    for linha in linhas:
        try:
            titulo, especialidade, tema, verbetografo, tertulia, data = linha[0:6]
        except Exception:
            log.warning("Linha inesperada, pulando: %s", linha)
            continue
        try:
            tertulia_n = int(str(tertulia).strip())
        except ValueError:
            log.warning("Tertúlia não-numérica, pulando: %s", tertulia)
            continue
        sigla, nome = split_verbetografo(str(verbetografo))
        verbetes.append(
            {
                "titulo": limpar_html(titulo),
                "especialidade": limpar_html(especialidade),
                "tema": limpar_html(tema),
                "sigla": sigla,
                "nome": nome,
                "tertulia": tertulia_n,
                "data": normalizar_data(str(data).strip()),
                "pdf_url": "",
                "pagina_url": "",
                "arquivo_pdf_path": "",
            }
        )
    return verbetes


def baixar_indice(session: requests.Session, fonte: str = "api") -> list[dict]:
    if fonte == "legado":
        return baixar_indice_legado(session)
    return baixar_indice_api(session)


# --------------------------------------------------------------------------
# Links PDF + download
# --------------------------------------------------------------------------

def montar_urls_candidatas(v: dict) -> list[str]:
    slug = slugify(v["titulo"])
    tertulia = v["tertulia"]
    out = [f"{SITE_BASE}/{tertulia}-{slug}"]
    if slug:
        out.append(f"{SITE_BASE}/{tertulia}")
    return out


def buscar_link_pdf(session: requests.Session, v: dict, timeout: float = 20):
    """Usa arquivo_pdf_path da API; senão faz scrape da página HTML."""
    if v.get("pdf_url"):
        return v["pdf_url"], v.get("pagina_url") or ""
    path = v.get("arquivo_pdf_path") or ""
    if path:
        return pdf_url_de_path(path), v.get("pagina_url") or ""

    for url in montar_urls_candidatas(v):
        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException as e:
            log.debug("Erro %s: %s", url, e)
            continue
        if resp.status_code != 200:
            continue
        html = resp.content.decode("utf-8", errors="replace")
        m = PDF_LINK_RE.search(html)
        if m:
            return m.group(1), url
    return None, None


def baixar_pdf(session: requests.Session, url: str, destino: Path, tentativas: int = 3) -> bool:
    if destino.exists() and destino.stat().st_size > 0:
        return True
    for tentativa in range(1, tentativas + 1):
        try:
            resp = session.get(url, timeout=45)
            if resp.status_code == 200 and resp.content[:4] == b"%PDF":
                destino.write_bytes(resp.content)
                return True
            if resp.status_code == 200 and len(resp.content) > 1000:
                # alguns servidores não mandam magic limpo; aceita se grande
                destino.write_bytes(resp.content)
                return True
            log.warning(
                "HTTP %s ao baixar %s (tentativa %d/%d)",
                resp.status_code,
                url,
                tentativa,
                tentativas,
            )
        except requests.RequestException as e:
            log.warning("Rede %s (%d/%d): %s", url, tentativa, tentativas, e)
        time.sleep(1.5 * tentativa)
    return False


def salvar_csv(rows: list[dict], caminho: Path, campos: list[str]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in campos})


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa só os verbetes que faltam na pasta da Enciclopédia."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="PDF directory (default: VERBETES_OUT, canonical folder if found, else ./Verbetes)",
    )
    parser.add_argument("--workers", type=int, default=8, help="Paralelismo ao resolver links")
    parser.add_argument("--delay", type=float, default=0.15, help="Pausa entre downloads (s)")
    parser.add_argument(
        "--desde",
        type=int,
        default=None,
        help="Só considera tertúlias >= N (útil pra pegar só os novos no fim)",
    )
    parser.add_argument(
        "--tudo",
        action="store_true",
        help="Ignora filtro de faltantes (ainda assim pula PDF já existente com mesmo nome)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só lista o que faltaria baixar; não grava PDF",
    )
    parser.add_argument(
        "--meta-dir",
        type=Path,
        default=None,
        help="Onde salvar CSVs de faltantes/falhas (padrão: <out>/.meta)",
    )
    parser.add_argument(
        "--fonte",
        choices=("api", "legado"),
        default="api",
        help="api = site novo (~7513); legado = bancodedados.js antigo",
    )
    args = parser.parse_args()

    out_dir: Path = (args.out or default_out_dir()).expanduser().resolve()
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = (args.meta_dir or (out_dir / ".meta")).expanduser().resolve()
    meta_dir.mkdir(parents=True, exist_ok=True)
    log.info("Destino: %s", out_dir)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,*/*",
            "Referer": f"{SITE_BASE}/",
        }
    )

    verbetes = baixar_indice(session, fonte=args.fonte)
    por_num = {v["tertulia"]: v for v in verbetes}
    max_remoto = max(por_num) if por_num else 0
    locais = numeros_locais(out_dir)
    max_local = max(locais) if locais else 0

    log.info(
        "Local: %d PDFs numerados (máx %d) | Remoto: %d (máx %d)",
        len(locais),
        max_local,
        len(por_num),
        max_remoto,
    )

    if args.tudo:
        candidatos = sorted(por_num)
    else:
        candidatos = sorted(n for n in por_num if n not in locais)

    if args.desde is not None:
        candidatos = [n for n in candidatos if n >= args.desde]

    faltantes = [por_num[n] for n in candidatos]
    for v in faltantes:
        v["nome_arquivo"] = montar_nome_arquivo(v)

    campos = [
        "tertulia",
        "data",
        "titulo",
        "especialidade",
        "tema",
        "sigla",
        "nome",
        "nome_arquivo",
        "pdf_url",
        "pagina_url",
    ]
    salvar_csv(faltantes, meta_dir / "faltantes.csv", [c for c in campos if c != "pdf_url" and c != "pagina_url"] + ["nome_arquivo"])

    if not faltantes:
        log.info("Nada a fazer — pasta já cobre o índice remoto%s.",
                 f" a partir de {args.desde}" if args.desde else "")
        return

    log.info("Faltam %d verbete(s). Exemplos:", len(faltantes))
    for v in faltantes[:12]:
        log.info("  %s", v["nome_arquivo"])
    if len(faltantes) > 12:
        log.info("  … e mais %d", len(faltantes) - 12)

    if args.dry_run:
        log.info("Dry-run: nenhum download.")
        return

    # Resolver links só dos faltantes
    falhas_link: list[dict] = []

    def tarefa(v: dict):
        pdf_url, pagina_url = buscar_link_pdf(session, v)
        return v["tertulia"], pdf_url, pagina_url

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(tarefa, v): v for v in faltantes}
        done = 0
        for fut in as_completed(futs):
            n, pdf_url, pagina_url = fut.result()
            v = por_num[n]
            v["pdf_url"] = pdf_url
            v["pagina_url"] = pagina_url
            done += 1
            if not pdf_url:
                falhas_link.append(v)
            if done % 20 == 0 or done == len(faltantes):
                log.info("Links: %d/%d (sem PDF: %d)", done, len(faltantes), len(falhas_link))

    if falhas_link:
        salvar_csv(falhas_link, meta_dir / "falhas_links.csv", campos)
        log.warning("%d sem link de PDF → %s", len(falhas_link), meta_dir / "falhas_links.csv")

    ok, falhas_dl = 0, []
    validos = [v for v in faltantes if v.get("pdf_url")]
    for i, v in enumerate(validos, 1):
        destino = out_dir / v["nome_arquivo"]
        if baixar_pdf(session, v["pdf_url"], destino):
            ok += 1
            log.info("[%d/%d] OK  %s", i, len(validos), v["nome_arquivo"])
        else:
            falhas_dl.append(v)
            log.warning("[%d/%d] FALHOU %s", i, len(validos), v["nome_arquivo"])
        time.sleep(args.delay)

    if falhas_dl:
        salvar_csv(falhas_dl, meta_dir / "falhas_download.csv", campos)

    log.info("Concluído: %d/%d baixados. Meta em %s", ok, len(validos), meta_dir)


if __name__ == "__main__":
    main()
