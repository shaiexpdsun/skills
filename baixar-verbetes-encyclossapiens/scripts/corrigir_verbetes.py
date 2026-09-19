#!/usr/bin/env python3
"""
Align local verbete PDFs with the remote index: re-download mismatches, rename
to the stable filename contract.

Usage:
    python corrigir_verbetes.py --dry-run --out ./Verbetes
    python corrigir_verbetes.py --apply --out ./Verbetes
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import baixar_verbetes as bv  # noqa: E402

log = logging.getLogger("corrigir_verbetes")

DATE_PREFIX = re.compile(
    r"^\d+(?:\s*-\s*|\s+)(\d{2}\.\d{2}\.\d{4})\s*-\s*(.+)$"
)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("∕", "/").replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def titulo_no_arquivo(nome_arquivo: str) -> str:
    base = nome_arquivo[:-4] if nome_arquivo.lower().endswith(".pdf") else nome_arquivo
    m = DATE_PREFIX.match(base)
    if not m:
        return ""
    resto = m.group(2)
    return resto.split(" - ")[0] if " - " in resto else resto


def similaridade_titulo(nome_arquivo: str, titulo_indice: str) -> float:
    a = fold(titulo_no_arquivo(nome_arquivo))
    b = fold(bv.limpar_html(titulo_indice))
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def nome_quebrado(nome: str) -> bool:
    if " -  - " in nome or " -- " in nome or nome.endswith(" - .pdf"):
        return True
    if re.match(r"^\d+\s+\d{2}\.\d{2}\.", nome):  # 6522 13.12 sem hífen
        return True
    if re.search(r"\d{4}-\s", nome):  # 2007- Título colado
        return True
    if re.search(r"\d{2}\.\d{2}\.\d{3}\s", nome):  # data truncada .202
        return True
    if re.search(r"(ologia|ologia)(Homeo|Nosogra|Neutro)", nome, re.I):
        return True
    if re.search(r"(Nosogr[aá]fico|Homeost[aá]tico|Neutro)\s+[A-Z]\.", nome):
        return True
    if " – " in nome and " - " in nome:  # en-dash na sigla (7094)
        pass  # só cosmético
    return False


def baixar_forcado(
    session: requests.Session, v: dict, destino: Path, delay: float
) -> bool:
    pdf_url, _ = bv.buscar_link_pdf(session, v)
    if not pdf_url:
        return False
    tmp = destino.with_suffix(".pdf.part")
    if tmp.exists():
        tmp.unlink()
    ok = bv.baixar_pdf(session, pdf_url, tmp, tentativas=4)
    if not ok:
        if tmp.exists():
            tmp.unlink()
        return False
    if destino.exists():
        destino.unlink()
    tmp.rename(destino)
    time.sleep(delay)
    return True


def plano_correcao(por_num: dict, locais: dict[int, Path]) -> tuple[set[int], list[tuple[Path, str]]]:
    redownload: set[int] = set()
    renomear: list[tuple[Path, str]] = []

    for n, v in por_num.items():
        esperado = bv.montar_nome_arquivo(v)
        if n not in locais:
            redownload.add(n)
            continue
        atual = locais[n]
        if nfc(atual.name) == nfc(esperado):
            continue
        sim = similaridade_titulo(atual.name, v["titulo"])
        if sim < 0.55 or nome_quebrado(atual.name):
            redownload.add(n)
        else:
            renomear.append((atual, esperado))

    return redownload, renomear


def aplicar_renomeacoes(out_dir: Path, renomear: list[tuple[Path, str]]) -> tuple[int, int]:
    """Duas fases (.tmp) para evitar colisão em trocas."""
    ok = falha = 0
    # fase 1 → temp
    temps: list[tuple[Path, Path]] = []
    for src, novo_nome in renomear:
        if not src.exists():
            falha += 1
            continue
        if nfc(src.name) == nfc(novo_nome):
            continue
        tmp = out_dir / f".rename-{src.stem[:40]}.tmp.pdf"
        i = 0
        while tmp.exists():
            i += 1
            tmp = out_dir / f".rename-{src.stem[:30]}-{i}.tmp.pdf"
        src.rename(tmp)
        temps.append((tmp, out_dir / novo_nome))
    # fase 2 → final
    for tmp, dest in temps:
        if dest.exists():
            dest.unlink()
        tmp.rename(dest)
        ok += 1
        log.info("RENOMEADO → %s", dest.name)
    return ok, falha


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Align local verbete PDFs with the remote encyclopedia index."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="PDF directory (same resolution rules as baixar_verbetes.py)",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--dry-run", action="store_true", help="Plan only")
    parser.add_argument("--delay", type=float, default=0.12)
    parser.add_argument(
        "--fonte",
        choices=("api", "legado"),
        default="api",
        help="Index source (default: api)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    out_dir = (args.out or bv.default_out_dir()).expanduser().resolve()
    if args.apply:
        out_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = out_dir / ".meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    log.info("Output: %s", out_dir)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": bv.USER_AGENT,
            "Accept": "application/json,text/html,*/*",
            "Referer": f"{bv.SITE_BASE}/",
        }
    )

    verbetes = bv.baixar_indice(session, fonte=args.fonte)
    por_num = {v["tertulia"]: v for v in verbetes}
    locais = bv.numeros_locais(out_dir)

    redownload, renomear = plano_correcao(por_num, locais)

    # Depois dos re-downloads, renomear também os que foram baixados com nome certo
    # mas ainda faltam cosméticos nos que só precisavam rename
    log.info(
        "Plano: %d re-download | %d rename | %d já ok no índice",
        len(redownload),
        len(renomear),
        len(por_num) - len(redownload) - len(renomear),
    )

    if redownload:
        log.info("Re-download (conteúdo/nome crítico ou faltante):")
        for n in sorted(redownload)[:30]:
            log.info("  %s", bv.montar_nome_arquivo(por_num[n]))
        if len(redownload) > 30:
            log.info("  … +%d", len(redownload) - 30)

    if renomear:
        log.info("Rename (só nome, conteúdo parece certo): %d arquivos", len(renomear))

    if args.dry_run or not args.apply:
        log.info("Dry-run / sem --apply — nada alterado.")
        return

    # --- Re-download ---
    dl_ok = dl_fail = 0
    removidos: list[Path] = []
    for n in sorted(redownload):
        v = por_num[n]
        esperado = out_dir / bv.montar_nome_arquivo(v)
        antigo = locais.get(n)
        if baixar_forcado(session, v, esperado, args.delay):
            dl_ok += 1
            log.info("BAIXADO %s", esperado.name)
            if antigo and antigo.exists() and nfc(str(antigo)) != nfc(str(esperado)):
                antigo.unlink()
                removidos.append(antigo)
        else:
            dl_fail += 1
            log.error("FALHOU download n=%s %s", n, v["titulo"][:50])

    # Atualiza mapa local pós-download
    locais = bv.numeros_locais(out_dir)

    # Rename cosmético para TODOS que ainda divergem do esperado
    renomear_final: list[tuple[Path, str]] = []
    for n, v in por_num.items():
        if n not in locais:
            continue
        esperado = bv.montar_nome_arquivo(v)
        atual = locais[n]
        if nfc(atual.name) != nfc(esperado):
            renomear_final.append((atual, esperado))

    rn_ok, rn_fail = aplicar_renomeacoes(out_dir, renomear_final)

    # Relatório
    locais_final = bv.numeros_locais(out_dir)
    faltando = sorted(set(por_num) - set(locais_final))
    rel = meta_dir / "correcao_ultima.txt"
    rel.write_text(
        f"download_ok={dl_ok} download_fail={dl_fail}\n"
        f"rename_ok={rn_ok} rename_fail={rn_fail}\n"
        f"ainda_faltando={faltando}\n",
        encoding="utf-8",
    )

    log.info(
        "Concluído: %d baixados, %d falha download, %d renomeados. Faltando: %s",
        dl_ok,
        dl_fail,
        rn_ok,
        faltando or "nenhum",
    )


if __name__ == "__main__":
    main()
