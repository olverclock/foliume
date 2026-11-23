"""Organização física do acervo e comparação de PDFs locais."""
import csv
import hashlib
import json
import re
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from baixar import BASE, CACHE, FILES, ROOT, key


def gravar(nomes):
    destino = CACHE / "nomes.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(nomes, ensure_ascii=False), encoding="utf8")
    tmp.replace(destino)


def pasta(pagina, layout):
    trecho = urlsplit(pagina).path.removeprefix(urlsplit(ROOT).path)
    partes = [x for x in trecho.split("/") if re.fullmatch("[a-z0-9-]+", x)]
    if layout == "unica":
        return Path()
    return Path(*(partes[:1] if layout == "categoria" else partes)) if partes else Path("geral")


def posicionar(url, titulo, pagina, nomes, layout):
    from baixar import named_path
    novo = url not in nomes
    atual = named_path(url, titulo, nomes)
    legado = FILES / (key(url) + ".pdf")
    origem = atual if atual.is_file() else legado
    aliases = [u for u, nome in nomes.items() if nome == nomes[url]]
    if url != aliases[0] and atual.is_file():
        return atual
    diretorio = FILES / pasta(pagina, layout)
    diretorio.mkdir(parents=True, exist_ok=True)
    alvo = diretorio / atual.name
    ocupados = {v.casefold() for u, v in nomes.items() if u not in aliases}
    i = 1
    while alvo != atual and (alvo.exists() or alvo.relative_to(FILES).as_posix().casefold() in ocupados):
        i += 1
        alvo = diretorio / f"{atual.stem} ({i}).pdf"
    if origem.exists() and origem != alvo and not alvo.exists():
        # Publica o novo caminho antes de remover a referência antiga.
        import os
        try:
            os.link(origem, alvo)
        except OSError:
            import shutil
            tmp = alvo.with_suffix(".movendo")
            shutil.copyfile(origem, tmp)
            tmp.replace(alvo)
        for u in aliases:
            nomes[u] = alvo.relative_to(FILES).as_posix()
        gravar(nomes)
        origem.unlink()
    elif novo or alvo != atual:
        for u in aliases:
            nomes[u] = alvo.relative_to(FILES).as_posix()
        gravar(nomes)
    return alvo


def indices():
    for arquivo in sorted(BASE.glob("resultado*/links.csv")):
        with arquivo.open(encoding="utf-8-sig", newline="") as f:
            yield arquivo, list(csv.DictReader(f, delimiter=";"))


def atualizar_zips(nomes):
    for indice, linhas in indices():
        destino = indice.parent / "InfoLivros.zip"
        if not destino.exists():
            continue
        caminhos = set()
        for linha in linhas:
            url = linha["URL do PDF"]
            path = FILES / nomes.get(url, key(url) + ".pdf")
            if path.is_file():
                caminhos.add(path)
        if caminhos:
            tmp = destino.with_suffix(".zip.part")
            with zipfile.ZipFile(tmp, "w", allowZip64=True) as z:
                for path in sorted(caminhos):
                    z.write(path, path.relative_to(FILES))
                for path in [indice, indice.parent / "pendencias.csv"]:
                    if path.exists():
                        z.write(path, path.name)
            tmp.replace(destino)


def organizar(layout, nomes):
    for _, linhas in indices():
        for linha in linhas:
            url = linha["URL do PDF"]
            if (FILES / nomes.get(url, key(url) + ".pdf")).is_file():
                posicionar(url, linha.get("Título") or Path(nomes.get(url, url)).stem,
                           linha["Página de origem"], nomes, layout)
    atualizar_zips(nomes)
    print("Organização concluída em", FILES)


def assinatura(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def mesmo_conteudo(a, b):
    with a.open("rb") as x, b.open("rb") as y:
        while True:
            bloco = x.read(1024 * 1024)
            if bloco != y.read(1024 * 1024):
                return False
            if not bloco:
                return True


def chave_nome(t):
    texto = unicodedata.normalize("NFKD", re.sub(r"\s*\(\d+\)$", "", t.casefold()))
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in texto if not unicodedata.combining(c))))


def duplicatas(nomes, remover, raiz=FILES, manual=False):
    import pypdfium2 as pdf
    from manual import arquivos
    paths = arquivos(raiz)
    associados = {FILES / v for v in nomes.values()}
    paths.sort(key=lambda p: (not p.is_relative_to(FILES), p not in associados, len(p.name), str(p)))
    tamanhos = defaultdict(list)
    candidatos = defaultdict(list)
    paginas = {}
    for p in paths:
        tamanhos[p.stat().st_size].append(p)
        try:
            with pdf.PdfDocument(str(p)) as doc:
                paginas[p] = len(doc)
        except Exception:
            paginas[p] = ""
        candidatos[chave_nome(p.stem)].append(p)
    linhas = []
    apagar = []
    for tamanho, grupo in tamanhos.items():
        if len(grupo) < 2:
            continue
        hashes = {}
        for p in grupo:
            sha = assinatura(p)
            outro = hashes.setdefault(sha, p)
            if p != outro and mesmo_conteudo(outro, p):
                apagar.append((outro, p, sha))
                linhas.append(("IDÊNTICO", outro, p, tamanho, tamanho, paginas[outro], paginas[p], sha))
    canonico = {p: outro for outro, p, _ in apagar}
    for grupo in candidatos.values():
        representantes = {}
        for p in grupo:
            representantes.setdefault(canonico.get(p, p), p)
        restantes = list(representantes.values())
        for p in restantes[1:]:
            a = restantes[0]
            linhas.append(("REVISAR", a, p, a.stat().st_size, p.stat().st_size, paginas[a], paginas[p], ""))
    report = raiz / "duplicatas-infolivros.csv" if manual else BASE / "duplicatas.csv"
    with report.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Resultado", "Manter", "Comparado", "Bytes A", "Bytes B", "Páginas A", "Páginas B", "SHA-256"])
        for status, a, b, *resto in linhas:
            w.writerow([status, a.relative_to(raiz), b.relative_to(raiz), *resto])
    print(len(paths), "PDFs analisados |", len(apagar), "cópias idênticas |", report, flush=True)
    if remover:
        gerenciado = any(p.is_relative_to(FILES) for _, p, _ in apagar)
        for _, registros in (indices() if gerenciado else ()):
            for registro in registros:
                u = registro["URL do PDF"]
                legado = key(u) + ".pdf"
                if u not in nomes and (FILES / legado).is_file():
                    nomes[u] = legado
        for manter, copia, sha in apagar:
            if assinatura(manter) != sha or not mesmo_conteudo(manter, copia):
                raise RuntimeError("Arquivo alterado durante a análise: " + str(copia))
            for u, nome in list(nomes.items()):
                if FILES / nome == copia:
                    nomes[u] = manter.relative_to(FILES).as_posix()
            if copia.is_relative_to(FILES):
                gravar(nomes)
            copia.unlink()
        if gerenciado:
            atualizar_zips(nomes)
        print(len(apagar), "cópias removidas")

if __name__ == "__main__":
    import sys
    db = CACHE / "nomes.json"
    duplicatas(json.loads(db.read_text(encoding="utf8")) if db.exists() else {}, sys.argv[1] == "limpar", Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else FILES, len(sys.argv) > 2)
