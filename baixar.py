"""Baixa os PDFs públicos vinculados no catálogo InfoLivros. Python 3.9+."""
import argparse
import csv
import hashlib
import json
from http.client import HTTPException
import re
import shutil
import time
import zipfile
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = "https://infolivros.org/livros-pdf-gratis/"
BASE = Path(__file__).resolve().parent
CACHE = BASE / "dados"
FILES = CACHE / "pdfs"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.heading = None
        self.title = ""

    def handle_data(self, data):
        if self.heading:
            self.title += data

    def handle_endtag(self, tag):
        if tag == self.heading:
            self.heading = None
        if tag == "li":
            self.title = ""


    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if "pdf-card" in classes:
            self.title = ""
        if "pdf-card__title" in classes:
            self.title = ""
            self.heading = tag
        if tag == "a":
            if attrs.get("href"):
                self.items.append((attrs["href"], attrs.get("class") or "", " ".join(self.title.split())))


def fetch(url):
    encoded = quote(url, safe=":/?#[]@!$&'()*+,;=%")
    for attempt in range(3):
        time.sleep(1)
        try:
            return urlopen(Request(encoded, headers={"User-Agent": "InfoLivrosOffline/1.0"}), timeout=45)
        except HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            delay = err.headers.get("Retry-After", "")
            time.sleep(int(delay) if delay.isdigit() else 10 * (attempt + 1))


def key(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def page_links(page):
    cache = CACHE / ("titulos-" + key(page) + ".json")
    if cache.exists():
        items = json.loads(cache.read_text(encoding="utf8"))
    else:
        with fetch(page) as response:
            doc = Links()
            doc.feed(response.read().decode("utf8", "replace"))
            items = doc.items
        if not items:
            raise ValueError("página sem links")
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(json.dumps(items), encoding="utf8")
        tmp.replace(cache)
    return items


def discover(start, errors):
    queue = deque([start])
    seen = {start}
    books = {}
    while queue:
        page = queue.popleft()
        try:
            for href, classes, title in page_links(page):
                url = urldefrag(urljoin(page, href)).url
                parsed = urlsplit(url)
                if parsed.scheme not in ("http", "https"):
                    continue
                if parsed.path.lower().endswith(".pdf") or "pdf-download" in classes.split():
                    if title or url not in books:
                        books[url] = (page, title)
                elif url.startswith(start) and not parsed.query and parsed.path.endswith("/") and url not in seen:
                    queue.append(url)
                    seen.add(url)
            print(f"PDFs {len(books)} | páginas pendentes {len(queue)} | {page}", flush=True)
        except (OSError, ValueError, HTTPException) as err:
            errors.append((page, str(err)))
    return books


def table(path, header, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


def download(url, path):
    if path.exists():
        return
    tmp = path.with_suffix(".part")
    try:
        with fetch(url) as response, tmp.open("wb") as out:
            head = response.read(1024)
            if b"%PDF-" not in head:
                raise ValueError("resposta sem assinatura PDF")
            out.write(head)
            shutil.copyfileobj(response, out)
            size = response.headers.get("Content-Length")
            if size and out.tell() != int(size):
                raise ValueError("transferência incompleta")
        with tmp.open("rb") as f:
            f.seek(max(0, tmp.stat().st_size - 4096))
            if b"%%EOF" not in f.read():
                raise ValueError("fim do PDF ausente")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def existing_books(errors):
    by_page = {}
    for index in sorted(BASE.glob("resultado*/links.csv")):
        with index.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                url = row["URL do PDF"]
                if (FILES / (key(url) + ".pdf")).is_file():
                    by_page.setdefault(row["Página de origem"], set()).add(url)
    books = {}
    for page, urls in by_page.items():
        try:
            for href, _, title in page_links(page):
                url = urldefrag(urljoin(page, href)).url
                if url in urls and title:
                    books[url] = (page, title)
        except (OSError, ValueError, HTTPException) as err:
            errors.append((page, str(err)))
    return books


def named_path(url, title, names):
    if url in names:
        return FILES / names[url]
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    stem = " ".join(stem.split())[:120].rstrip(". ") or "Livro"
    if stem.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(10)), *("LPT" + str(i) for i in range(10))}:
        stem = "_" + stem
    candidate = stem + ".pdf"
    occupied = {name.casefold() for name in names.values()}
    number = 1
    while candidate.casefold() in occupied or (FILES / candidate).exists():
        number += 1
        candidate = f"{stem} ({number}).pdf"
    names[url] = candidate
    tmp = CACHE / "nomes.tmp"
    tmp.write_text(json.dumps(names, ensure_ascii=False), encoding="utf8")
    tmp.replace(CACHE / "nomes.json")
    return FILES / candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--somente-links", action="store_true")
    parser.add_argument("--categoria", default="", help="Exemplo: matematica/algebra")
    parser.add_argument("--renomear", action="store_true")
    parser.add_argument("--pastas", choices=["categoria", "tema", "unica"], default="categoria")
    args = parser.parse_args()
    from biblioteca import posicionar
    part = args.categoria.strip("/")
    if part and not re.fullmatch(r"[a-z0-9-]+(/[a-z0-9-]+)*", part):
        parser.error("categoria inválida")
    start = ROOT + (part + "/" if part else "")
    dest = BASE / ("resultado-" + part.replace("/", "-") if part else "resultado")
    dest.mkdir(exist_ok=True)
    FILES.mkdir(parents=True, exist_ok=True)
    errors = []
    names_file = CACHE / "nomes.json"
    names = json.loads(names_file.read_text(encoding="utf8")) if names_file.exists() else {}
    if args.renomear:
        books = existing_books(errors)
        for url, (_, title) in books.items():
            old = FILES / (key(url) + ".pdf")
            path = named_path(url, title, names)
            if not path.exists():
                old.rename(path)
        for old in FILES.glob("*.pdf"):
            if re.fullmatch(r"[0-9a-f]{20}", old.stem):
                errors.append((old.name, "Sem correspondência confirmada. Arquivo preservado."))
        table(BASE / "pendencias-renomeacao.csv", ["Arquivo ou URL", "Problema"], errors)
        print(f"{len(books)} títulos localizados | {len(errors)} pendências | {FILES}")
        return
    books = discover(start, errors)
    index = dest / "links.csv"
    report = dest / "pendencias.csv"
    table(index, ["URL do PDF", "Página de origem", "Título"], ((u, p, t) for u, (p, t) in books.items()))
    table(report, ["URL", "Problema"], errors)
    if args.somente_links or not books:
        print(f"{len(books)} links | {len(errors)} pendências | {dest}")
        return
    saved = []
    for i, (url, (page, title)) in enumerate(books.items(), 1):
        try:
            if not title:
                errors.append((url, "Título indisponível na página. Usado nome do link."))
                title = Path(unquote(urlsplit(url).path)).stem or "Livro"
            path = posicionar(url, title, page, names, args.pastas)
            download(url, path)
            saved.append((path, path.relative_to(FILES).as_posix()))
        except (OSError, ValueError, EOFError, HTTPException) as err:
            errors.append((url, str(err)))
        print(f"{i}/{len(books)} | baixados {len(saved)} | pendências {len(errors)}", flush=True)
    table(report, ["URL", "Problema"], errors)
    if saved:
        tmp = dest / "InfoLivros.zip.part"
        with zipfile.ZipFile(tmp, "w", allowZip64=True) as archive:
            for path, name in dict.fromkeys(saved):
                archive.write(path, name)
            for path in (index, report):
                archive.write(path, path.name)
        tmp.replace(dest / "InfoLivros.zip")
    print(f"{len(saved)} PDFs | {len(errors)} pendências | {dest}")


if __name__ == "__main__":
    main()
