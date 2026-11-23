"""Análise e organização manual de uma pasta de PDFs."""
import argparse
import json
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from biblioteca import BASE, FILES, CACHE, gravar, indices, key, atualizar_zips


def arquivos(raiz):
    return sorted(p for p in raiz.rglob("*") if p.suffix.casefold() == ".pdf"
                  and p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(raiz))


def nomes_atuais():
    db = CACHE / "nomes.json"
    return json.loads(db.read_text(encoding="utf8")) if db.exists() else {}


def mover(raiz, selecionados, destino):
    raiz = raiz.resolve(strict=True)
    destino = (raiz / destino).resolve()
    if not destino.is_relative_to(raiz):
        raise ValueError("Escolha uma categoria dentro da pasta aberta.")
    nomes = nomes_atuais()
    gerenciada = FILES.resolve()
    legados = {}
    if gerenciada.is_relative_to(raiz) or raiz.is_relative_to(gerenciada):
        for _, rows in indices():
            for row in rows:
                u = row["URL do PDF"]
                legados[key(u) + ".pdf"] = u
    total = 0
    atualizar = False
    try:
        for item in selecionados:
            origem = raiz / item
            if origem.is_symlink() or not origem.resolve().is_relative_to(raiz) or origem.suffix.lower() != ".pdf" or not origem.is_file():
                raise ValueError(f"PDF inválido: {item}")
            origem = origem.resolve()
            if origem.parent == destino:
                continue
            if origem.is_relative_to(gerenciada) and not destino.is_relative_to(gerenciada):
                raise ValueError("Para livros do baixador, escolha uma categoria dentro de dados/pdfs.")
            destino.mkdir(parents=True, exist_ok=True)
            numero = 1
            while True:
                nome = origem.name if numero == 1 else f"{origem.stem} ({numero}){origem.suffix}"
                alvo = destino / nome
                try:
                    saida = alvo.open("xb")
                    break
                except FileExistsError:
                    numero += 1
            try:
                with saida, origem.open("rb") as entrada:
                    shutil.copyfileobj(entrada, saida)
                if origem.is_relative_to(gerenciada):
                    antigo = origem.relative_to(gerenciada).as_posix()
                    u = legados.get(antigo)
                    if u:
                        nomes.setdefault(u, antigo)
                    for u, n in list(nomes.items()):
                        if n == antigo:
                            nomes[u] = alvo.relative_to(gerenciada).as_posix()
                            atualizar = True
                    gravar(nomes)
            except Exception:
                alvo.unlink(missing_ok=True)
                raise
            origem.unlink()
            total += 1
    finally:
        if atualizar:
            atualizar_zips(nomes)
    return total


def executar(acao, raiz, destino="", itens=(), confirmar=False):
    raiz = Path(raiz).expanduser().resolve(strict=True)
    if not raiz.is_dir():
        raise ValueError("Escolha uma pasta existente.")
    if acao == "listar":
        for p in arquivos(raiz):
            print(p.relative_to(raiz))
    elif acao == "mover":
        if not itens or not destino:
            raise ValueError("Informe os PDFs e a categoria de destino.")
        print(mover(raiz, itens, destino), "PDF(s) movido(s).")
    else:
        if acao == "limpar" and not confirmar:
            raise ValueError("Use --confirmar-exclusao para excluir cópias idênticas.")
        from acervo import prepare
        subprocess.run([prepare(False), str(BASE / "biblioteca.py"), acao, str(raiz)], check=True)


def janela(parent):
    import tkinter as tk
    from tkinter import ttk, filedialog, simpledialog, messagebox
    win = tk.Toplevel(parent)
    win.title("Organizar pasta de PDFs")
    win.geometry("760x500")
    win.transient(parent)
    win.grab_set()
    caixa = ttk.Frame(win, padding=16)
    caixa.pack(fill="both", expand=True)
    pasta = tk.StringVar(value="")
    status = tk.StringVar(value="Escolha a pasta onde estão os PDFs.")
    barra = ttk.Frame(caixa)
    barra.pack(fill="x")
    ttk.Label(caixa, textvariable=pasta, wraplength=680).pack(anchor="w", pady=6)
    lista = tk.Listbox(caixa, selectmode="extended", exportselection=False)
    scroll = ttk.Scrollbar(caixa, command=lista.yview)
    lista.configure(yscrollcommand=scroll.set)
    rodape = ttk.Label(caixa, textvariable=status, wraplength=700)
    rodape.pack(side="bottom", fill="x", pady=8)
    scroll.pack(side="right", fill="y")
    lista.pack(fill="both", expand=True)
    eventos = queue.Queue()
    ocupado = False
    def trabalho(func):
        nonlocal ocupado
        ocupado = True
        for botao in botoes:
            botao.state(["disabled"])
        status.set("Processando…")
        def rodar():
            try:
                eventos.put((True, func()))
            except Exception as exc:
                eventos.put((False, str(exc)))
        threading.Thread(target=rodar, daemon=True).start()
    def conteudo(msg):
        raiz = Path(pasta_atual[0])
        return msg, [str(p.relative_to(raiz)) for p in arquivos(raiz)]
    pasta_atual = [""]
    def abrir():
        valor = filedialog.askdirectory(parent=win, mustexist=True)
        if valor:
            lista.delete(0, "end")
            pasta.set(valor)
            pasta_atual[0] = valor
            trabalho(lambda: conteudo("Selecione os PDFs com Ctrl ou Shift."))
    def acao(tipo):
        raiz = Path(pasta.get())
        if not pasta.get():
            return abrir()
        if tipo == "mover":
            itens = [lista.get(i) for i in lista.curselection()]
            if not itens:
                return status.set("Selecione pelo menos um PDF na lista.")
            dest = simpledialog.askstring("Categoria", "Subpasta de destino (ex.: História/Brasil):", parent=win)
            if dest:
                trabalho(lambda: conteudo(f"{mover(raiz,itens,dest)} PDF(s) movido(s)."))
        else:
            if tipo == "limpar" and not messagebox.askyesno("Excluir cópias idênticas", f"Excluir cópias byte a byte idênticas dentro de {raiz}?", parent=win):
                return
            def processar():
                executar(tipo, raiz, confirmar=tipo=="limpar")
                return conteudo(f"Relatório: {raiz / 'duplicatas-infolivros.csv'}")
            trabalho(processar)
    botoes = []
    for titulo, cmd in [("Escolher pasta…", abrir), ("Analisar duplicatas", lambda: acao("duplicatas")), ("Mover seleção…", lambda: acao("mover")), ("Excluir idênticas…", lambda: acao("limpar"))]:
        btn = ttk.Button(barra, text=titulo, command=cmd)
        btn.pack(side="left", padx=2)
        botoes.append(btn)
    def poll():
        nonlocal ocupado
        try:
            ok, resultado = eventos.get_nowait()
            if ok:
                msg, itens = resultado
                lista.delete(0, "end")
                for item in itens:
                    lista.insert("end", item)
                status.set(f"{len(itens)} PDF(s). {msg}")
            else:
                status.set(resultado)
            ocupado = False
            for btn in botoes:
                btn.state(["!disabled"])
        except queue.Empty:
            pass
        win.after(100, poll)
    win.protocol("WM_DELETE_WINDOW", lambda: status.set("Aguarde o término da operação.") if ocupado else win.destroy())
    poll()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("acao", choices=["listar", "duplicatas", "limpar", "mover"])
    p.add_argument("--pasta", required=True)
    p.add_argument("--destino", default="")
    p.add_argument("--arquivos", nargs="+", default=[])
    p.add_argument("--confirmar-exclusao", action="store_true")
    args = p.parse_args()
    try:
        executar(args.acao, args.pasta, args.destino, args.arquivos, args.confirmar_exclusao)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
