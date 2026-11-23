"""Coleta de PDFs em páginas HTML públicas, com várias origens."""
import csv
import json
import re
import shutil
import tempfile
import time
import zipfile
from collections import deque
from datetime import datetime
from html.parser import HTMLParser
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from baixar import BASE, ROOT, Links, key

CONFIG = BASE / "sites.json"
AGENT = "InfoLivrosOffline"
ERRORS = (OSError, ValueError, HTTPException)


def url_valida(s):
    s = s.strip()
    if "://" not in s:
        s = "https://" + s
    u = urlsplit(s)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password or re.search(r"\s", u.netloc):
        raise ValueError("URL inválida: " + s)
    return urldefrag(s).url


def configurados():
    return json.loads(CONFIG.read_text(encoding="utf8")) if CONFIG.exists() else [ROOT]


def salvar(urls):
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(urls, indent=2, ensure_ascii=False), encoding="utf8")
    tmp.replace(CONFIG)


class Pagina(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.anchor = None
        self.base = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "base" and not self.base:
            self.base = a.get("href") or ""
        if tag == "a" and a.get("href"):
            self.anchor = [a["href"], a.get("title") or "", "download" in a or a.get("type") == "application/pdf"]
            self.links.append(self.anchor)
        if tag in ("embed", "object", "iframe"):
            src = a.get("src") or a.get("data")
            if src:
                self.links.append([src, a.get("title") or "", a.get("type") == "application/pdf"])

    def handle_endtag(self, tag):
        if tag == "a":
            self.anchor = None

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor[1] += " " + data


def abrir(url):
    return urlopen(Request(quote(url, safe=":/?#[]@!$&'()*+,;=%"), headers={"User-Agent": AGENT}), timeout=35)


class Acesso:
    def __init__(self):
        self.regras = {}
        self.ultimo = {}

    def obter(self, url):
        u = urlsplit(url)
        origem = f"{u.scheme}://{u.netloc}"
        if origem not in self.regras:
            robot = RobotFileParser()
            try:
                with abrir(origem + "/robots.txt") as r:
                    robot.parse(r.read(512000).decode("utf8", "replace").splitlines())
            except HTTPError as exc:
                if exc.code in (404, 410):
                    robot.allow_all = True
                elif exc.code in (401, 403):
                    robot.disallow_all = True
                else:
                    raise
            self.regras[origem] = robot
        regra = self.regras[origem]
        if not regra.can_fetch(AGENT, url):
            raise ValueError("Acesso restrito pelo robots.txt")
        intervalo = max(0.5, regra.crawl_delay(AGENT) or 0)
        time.sleep(max(0, intervalo - (time.monotonic() - self.ultimo.get(origem, 0))))
        self.ultimo[origem] = time.monotonic()
        return abrir(url)


def nome_pdf(label, url):
    t = " ".join(label.split())
    if not t or t.lower() in ("pdf", "download", "baixar", "baixar pdf") or len(t) > 180:
        t = Path(unquote(urlsplit(url).path)).stem or "Documento"
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", t).strip(" .")[:110] or "Documento"
    if t.split(".")[0].upper() in {"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(10)),*(f"LPT{i}" for i in range(10))}:
        t = "_" + t
    return t


def coletar(urls, limite, profundidade, saida=None):
    urls = list(dict.fromkeys(url_valida(x) for x in urls))
    if not urls or limite < 1 or profundidade < 0:
        raise ValueError("Informe pelo menos um site, limite positivo e profundidade a partir de zero.")
    dest = saida or BASE / "resultado-sites"
    dest.mkdir(parents=True, exist_ok=True)
    pasta = Path(tempfile.mkdtemp(prefix=datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=dest))
    acesso = Acesso()
    baixados, falhas = {}, []
    for inicio in urls:
        fila = deque([(inicio, 0, "", "", False)])
        vistos = {inicio}
        paginas = 0
        limite_atingido = False
        host = urlsplit(inicio).hostname
        while fila:
            url, nivel, origem, titulo, pdf = fila.popleft()
            if url in baixados:
                continue
            if not pdf and paginas >= limite:
                limite_atingido = True
                continue
            if not pdf:
                paginas += 1
            try:
                with acesso.obter(url) as r:
                    final = r.geturl()
                    head = r.read(1024)
                    if b"%PDF-" in head:
                        if final in baixados:
                            continue
                        sub = pasta / re.sub(r"[^a-zA-Z0-9.-]", "_", host)
                        sub.mkdir(exist_ok=True)
                        nome = nome_pdf(titulo, final)
                        path = sub / (nome + ".pdf")
                        if path.exists():
                            path = sub / (nome + "-" + key(final) + ".pdf")
                        with tempfile.NamedTemporaryFile(dir=sub, delete=False) as f:
                            tmp = Path(f.name)
                            try:
                                f.write(head)
                                shutil.copyfileobj(r, f)
                            except BaseException:
                                f.close()
                                tmp.unlink(missing_ok=True)
                                raise
                        try:
                            with tmp.open("rb") as f:
                                f.seek(max(0, tmp.stat().st_size - 4096))
                                if b"%%EOF" not in f.read():
                                    raise ValueError("PDF incompleto")
                            tmp.replace(path)
                        finally:
                            tmp.unlink(missing_ok=True)
                        baixados[final] = (origem or inicio, url, final, titulo, path.relative_to(pasta).as_posix())
                        print("PDF:", path.name, flush=True)
                        continue
                    if pdf:
                        raise ValueError("O link de download retornou outro formato")
                    if r.headers.get_content_type() not in ("text/html","application/xhtml+xml"):
                        continue
                    html = (head + r.read(4_000_000)).decode(r.headers.get_content_charset() or "utf8", "replace")
                parser = Pagina()
                parser.feed(html)
                base = urljoin(final, parser.base)
                if urlsplit(final).hostname == "infolivros.org":
                    cards = Links()
                    cards.feed(html)
                    parser.links[:0] = [(href, title, True) for href, classes, title in cards.items if "pdf-download" in classes.split()]
                for href, label, hint in parser.links:
                    link = urldefrag(urljoin(base, href)).url
                    u = urlsplit(link)
                    if u.scheme not in ("https","http") or not u.hostname or u.username or u.password or link in vistos:
                        continue
                    direto = hint or u.path.lower().endswith(".pdf")
                    if not direto:
                        if u.hostname != urlsplit(final).hostname or nivel >= profundidade:
                            continue
                        if inicio.startswith(ROOT) and not link.startswith(inicio):
                            continue
                        if re.search(r"\.(jpg|jpeg|png|svg|gif|webp|zip|mp[34]|css|js)$", u.path, re.I):
                            continue
                    vistos.add(link)
                    fila.append((link, nivel+1, final, " ".join(label.split()), direto))
                print(f"{host} | páginas {paginas}/{limite} | PDFs {len(baixados)}", flush=True)
            except ERRORS as exc:
                falhas.append((url,str(exc)))
        if limite_atingido:
            falhas.append((inicio,"Limite de páginas atingido. Aumente o limite para ampliar a busca."))
    for nome, header, rows in [("links.csv",["Página","Link","URL final","Texto do site","Arquivo"],baixados.values()),("pendencias.csv",["URL","Motivo"],falhas)]:
        with (pasta/nome).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f,delimiter=";")
            w.writerow(header)
            w.writerows(rows)
    if baixados:
        with zipfile.ZipFile(pasta/"PDFs.zip","w",allowZip64=True) as z:
            for *_, nome in baixados.values():
                z.write(pasta/nome,nome)
            for nome in ("links.csv","pendencias.csv"):
                z.write(pasta/nome,nome)
    print(f"{len(baixados)} PDFs | {len(falhas)} pendências | {pasta}", flush=True)
    return pasta


def editar(parent):
    import tkinter as tk
    from tkinter import ttk, messagebox
    win = tk.Toplevel(parent)
    win.title("Sites para baixar PDFs")
    win.transient(parent)
    win.grab_set()
    box = ttk.Frame(win,padding=16)
    box.pack(fill="both",expand=True)
    ttk.Label(box,text="Endereços dos sites · um por linha").pack(anchor="w")
    entrada = tk.Text(box,height=8,width=65,wrap="none")
    entrada.pack(fill="both",expand=True,pady=8)
    entrada.insert("1.0","\n".join(configurados()))
    limites = ttk.Frame(box)
    limites.pack(fill="x")
    valores = []
    for texto, valor in [("Páginas por endereço",100),("Profundidade",3)]:
        ttk.Label(limites,text=texto).pack(side="left")
        var = tk.StringVar(value=str(valor))
        ttk.Entry(limites,textvariable=var,width=6).pack(side="left",padx=8)
        valores.append(var)
    resultado = []
    def aplicar(iniciar):
        try:
            urls = list(dict.fromkeys(url_valida(x) for x in entrada.get("1.0","end").splitlines() if x.strip()))
            n, d = [int(v.get()) for v in valores]
            if n < 1 or d < 0 or (iniciar and not urls):
                raise ValueError("Informe pelo menos um endereço para iniciar, páginas ≥ 1 e profundidade ≥ 0.")
            salvar(urls)
        except (OSError,ValueError) as exc:
            messagebox.showerror("Sites",str(exc),parent=win)
            return
        if iniciar:
            resultado.extend(["--limite",str(n),"--profundidade",str(d)])
        win.destroy()
    botoes = ttk.Frame(box)
    botoes.pack(fill="x",pady=(12,0))
    ttk.Button(botoes,text="Salvar lista",command=lambda:aplicar(False)).pack(side="left")
    ttk.Button(botoes,text="Salvar e baixar",command=lambda:aplicar(True)).pack(side="right")
    entrada.focus_set()
    parent.wait_window(win)
    return resultado
