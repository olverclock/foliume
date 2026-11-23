"""Confere a origem, os bytes e o título dos PDFs locais."""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urldefrag, urljoin

import pypdfium2 as pdfium
from baixar import BASE, CACHE, FILES, Links, fetch, key


def digest(stream):
    total = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        total.update(block)
    return total.hexdigest()


def normalized(text):
    plain = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in plain if not unicodedata.combining(c))))


def evidence(text, title):
    lines = [s.strip() for s in text.splitlines() if s.strip()][:20]
    for i in range(len(lines)):
        for length in range(1, min(4, len(lines) - i) + 1):
            block = " ".join(lines[i:i + length])
            if normalized(block) == normalized(title):
                return block
    return ""


def inspect_pdf(path, title, reader):
    with pdfium.PdfDocument(str(path)) as doc:
        for method in (["Texto", "OCR CUDA"] if reader else ["Texto"]):
            for i in range(min(3, len(doc))):
                page = doc[i]
                try:
                    if method == "Texto":
                        tp = page.get_textpage()
                        try:
                            text = tp.get_text_bounded()
                        finally:
                            tp.close()
                    else:
                        import numpy as np
                        scale = min(2, 2000 / max(page.get_size()))
                        bitmap = page.render(scale=scale)
                        try:
                            pixels = np.array(bitmap.to_pil().convert("RGB"))
                        finally:
                            bitmap.close()
                        text = "\n".join(reader.readtext(pixels, detail=0, batch_size=1))
                finally:
                    page.close()
                match = evidence(text, title)
                if match:
                    return method, i + 1, match
    return "", "", ""


def live_titles(page):
    if not page.startswith("https://infolivros.org/"):
        raise ValueError("Página de origem fora do catálogo")
    with fetch(page) as response:
        html = response.read().decode("utf8", "replace")
    parser = Links()
    parser.feed(html)
    return {urldefrag(urljoin(page, href)).url: title
            for href, classes, title in parser.items
            if title and "pdf-download" in classes.split()}


def verify(path, url, page, titles, reader):
    title = titles.get(url, "")
    row = dict(Arquivo=path.name, Página_site=page, URL=url, Título_site=title)
    if not title:
        return dict(row, Resultado="REVISAR", Motivo="Link e título ausentes na página atual")
    with path.open("rb") as local:
        row["SHA256_local"] = digest(local)
    with fetch(url) as remote:
        row["SHA256_site"] = digest(remote)
    if row["SHA256_local"] != row["SHA256_site"]:
        return dict(row, Resultado="DIVERGENTE", Motivo="Arquivo local diferente do servido pelo site")
    method, number, excerpt = inspect_pdf(path, title, reader)
    row.update(Método=method, Página_PDF=number, Trecho=excerpt)
    if not excerpt:
        return dict(row, Resultado="REVISAR", Motivo="Título exato não localizado nas primeiras três páginas")
    if len(normalized(title).split()) < 2:
        return dict(row, Resultado="REVISAR", Motivo="Título curto exige confirmação adicional")
    return dict(row, Resultado="CONFIRMADO")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    reader = None
    if args.gpu:
        import torch
        import easyocr
        if not torch.cuda.is_available():
            raise SystemExit("CUDA indisponível. Verifique o driver NVIDIA e a instalação do PyTorch.")
        test = torch.ones((4, 4), device="cuda")
        (test @ test).sum().item()
        print("OCR CUDA:", torch.cuda.get_device_name(), flush=True)
        reader = easyocr.Reader(["pt", "en"], gpu=True)
    names = CACHE / "nomes.json"
    mapping = json.loads(names.read_text(encoding="utf8")) if names.exists() else {}
    items = {}
    for index in sorted(BASE.glob("resultado*/links.csv")):
        with index.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                u = r["URL do PDF"]
                for name in (mapping.get(u), key(u) + ".pdf"):
                    if name and (FILES / name).is_file():
                        items[(FILES / name, u)] = r["Página de origem"]
    fields = "Arquivo Resultado Motivo Título_site Página_site URL SHA256_local SHA256_site Método Página_PDF Trecho".split()
    counts = Counter()
    last_page, titles, error = None, {}, ""
    report = BASE / "conferencia-titulos.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fields, delimiter=";")
        writer.writeheader()
        conhecidos = {path for path, u in items}
        for path in FILES.rglob("*.pdf"):
            if path not in conhecidos:
                items[(path, "")] = ""
        for (path, url), page in sorted(items.items(), key=lambda item: item[1]):
            try:
                if not url:
                    raise ValueError("Arquivo sem correspondência no índice local")
                if page != last_page:
                    last_page, error, titles = page, "", {}
                    try:
                        titles = live_titles(page)
                    except Exception as exc:
                        error = str(exc)
                if error:
                    raise ValueError(error)
                row = verify(path, url, page, titles, reader)
            except Exception as exc:
                row = dict(Arquivo=path.name, Página_site=page, URL=url, Resultado="REVISAR", Motivo=str(exc))
            row["Arquivo"] = path.relative_to(FILES).as_posix()
            counts[row["Resultado"]] += 1
            writer.writerow(row)
            output.flush()
            print(row["Resultado"], path.name, flush=True)
    print(dict(counts), report)


if __name__ == "__main__":
    main()
