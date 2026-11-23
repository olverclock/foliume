"""Terminal e interface gráfica para o catálogo InfoLivros."""
import argparse
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import venv
from pathlib import Path

BASE = Path(__file__).resolve().parent
WINDOWS = os.name == "nt"
ACTIONS = {
    "sites": "Buscar PDFs em sites…",
    "completo": "Baixar e conferir",
    "baixar": "Baixar e gerar ZIP",
    "organizar": "Reorganizar PDFs locais",
    "duplicatas": "Analisar duplicatas",
    "limpar": "Excluir cópias idênticas",
    "links": "Coletar links",
    "conferir": "Conferir PDFs locais",
    "renomear": "Renomear PDFs antigos",
}
MODES = {"auto": "Automático", "cpu": "CPU · texto", "cuda": "NVIDIA · texto e OCR"}


def run(*args):
    subprocess.run([str(a) for a in args], cwd=BASE, check=True)


def verifier(mode):
    detected = shutil.which("nvidia-smi")
    gpu = mode == "cuda" or (mode == "auto" and detected and
                              subprocess.run([detected, "-L"], capture_output=True).stdout.strip())
    if gpu:
        try:
            env = prepare(True)
            run(env, "-c", "import torch; print(torch.cuda.get_device_name()); torch.ones(1, device='cuda').sum().item()")
            return env, ["--gpu"]
        except (OSError, subprocess.CalledProcessError):
            if mode == "cuda":
                raise
            print("CUDA indisponível. Continuando com leitura de texto na CPU.", flush=True)
    return prepare(False), []


def prepare(gpu):
    version = f"{sys.version_info.major}{sys.version_info.minor}"
    folder = (".ocr-gpu" if gpu else ".confere") + "-py" + version
    if not WINDOWS:
        folder += "-linux-" + platform.machine()
    root = BASE / folder
    env = root / ("Scripts/python.exe" if WINDOWS else "bin/python")
    if not env.exists():
        print("Preparando ambiente Python em", root, flush=True)
        venv.EnvBuilder(with_pip=True).create(root)
    deps = [("import pypdfium2", ["pypdfium2"])]
    if gpu:
        deps = [
            ("import torch, torchvision; assert torch.version.cuda", ["torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu128"]),
            ("import pypdfium2, easyocr", ["easyocr", "pypdfium2"]),
        ]
    for check, packages in deps:
        if subprocess.run([env, "-c", check], capture_output=True).returncode:
            run(env, "-m", "pip", "install", *packages)
    return env


PASTAS = {"categoria": "Por categoria", "tema": "Categoria e tema", "unica": "Pasta única"}


def task(action, mode, pastas, confirmado):
    if action in ("organizar", "duplicatas", "limpar"):
        import json
        from biblioteca import CACHE, FILES, organizar
        FILES.mkdir(parents=True, exist_ok=True)
        if action == "organizar":
            db = CACHE / "nomes.json"
            organizar(pastas, json.loads(db.read_text(encoding="utf8")) if db.exists() else {})
        else:
            if action == "limpar" and not confirmado:
                raise SystemExit("Consulte duplicatas.csv e repita com --confirmar-exclusao.")
            run(prepare(False), BASE / "biblioteca.py", action)
        return
    print(platform.system(), platform.machine(), "| Python", platform.python_version(), flush=True)
    flags = {"completo": [], "baixar": [], "links": ["--somente-links"], "renomear": ["--renomear"]}
    if action in flags:
        run(sys.executable, "-u", BASE / "baixar.py", *flags[action], "--pastas", pastas)
    if action in ("conferir", "completo"):
        env, options = verifier(mode)
        run(env, "-u", BASE / "conferir.py", *options)


CREDITO = "Feito por olverlock em 22/11/2026 18:36"


def gui():
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
    root = tk.Tk()
    from tkinter import messagebox
    root.title("Foliúme · Biblioteca local")
    menu = tk.Menu(root)
    ajuda = tk.Menu(menu, tearoff=False)
    ajuda.add_command(label="Sobre o Foliúme", command=lambda: messagebox.showinfo("Sobre o Foliúme", CREDITO, parent=root))
    menu.add_cascade(label="Ajuda", menu=ajuda)
    root.configure(menu=menu)
    root.geometry("820x600")
    root.minsize(580, 450)
    root.configure(bg="#eef1ee")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background="#eef1ee")
    style.configure("TLabel", background="#eef1ee", foreground="#193c34", font=("Arial", 11))
    style.configure("Primary.TButton", background="#16634e", foreground="white", padding=(20, 10))
    style.map("Primary.TButton", background=[("active", "#124c3d"), ("disabled", "#64746e")])
    box = ttk.Frame(root, padding=24)
    box.pack(fill="both", expand=True)
    ttk.Label(box, text="Foliúme", font=("Georgia", 27, "bold")).pack(anchor="w")
    ttk.Label(box, text=f"{platform.system()} · {platform.machine()} · Python {platform.python_version()}").pack(anchor="w", pady=(3, 18))
    options = ttk.Frame(box)
    options.pack(fill="x")
    def select(label, values, col):
        ttk.Label(options, text=label).grid(row=0, column=col, sticky="w")
        field = ttk.Combobox(options, values=list(values.values()), state="readonly")
        field.current(0)
        field.grid(row=1, column=col, sticky="ew", padx=(0, 10), pady=(4, 12))
        options.columnconfigure(col, weight=1)
        return field
    action = select("Operação", ACTIONS, 0)
    mode = select("Conferência", MODES, 1)
    layout = select("Organização", PASTAS, 2)
    bar = ttk.Frame(box)
    bar.pack(fill="x")
    state = tk.StringVar(value="Pronto")
    events = queue.Queue()
    running = False
    def worker(a, m, layout_key, extras):
        try:
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
            with subprocess.Popen([sys.executable, __file__, a, "--modo", m, "--pastas", layout_key] + extras + (["--confirmar-exclusao"] if a == "limpar" else []), cwd=BASE, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                  encoding="utf8", errors="replace") as proc:
                for line in proc.stdout:
                    events.put(line)
                events.put(proc.wait())
        except OSError as error:
            events.put(str(error)+"\n")
            events.put(1)
    def start():
        nonlocal running
        a = list(ACTIONS)[action.current()]
        extras = []
        if a == "sites":
            from sites import editar
            extras = editar(root)
            if not extras:
                return
        if a == "limpar":
            from tkinter import messagebox
            if not (BASE / "duplicatas.csv").exists():
                messagebox.showinfo("Duplicatas", "Execute Analisar duplicatas e consulte duplicatas.csv primeiro.")
                return
            if not messagebox.askyesno("Excluir cópias idênticas?", "A análise será refeita. Excluir uma cópia de cada par idêntico e atualizar os ZIPs?"):
                return
        running = True
        button.state(["disabled"])
        manual_btn.state(["disabled"])
        state.set("Em execução")
        progress.start()
        threading.Thread(target=worker, args=(list(ACTIONS)[action.current()], list(MODES)[mode.current()], list(PASTAS)[layout.current()], extras), daemon=True).start()
    button = ttk.Button(bar, text="Iniciar", style="Primary.TButton", command=start)
    button.pack(side="left")
    from manual import janela
    manual_btn = ttk.Button(bar, text="Organizar uma pasta…", command=lambda: janela(root))
    manual_btn.pack(side="left", padx=8)
    ttk.Label(bar, textvariable=state).pack(side="left", padx=14)
    progress = ttk.Progressbar(box, mode="indeterminate")
    progress.pack(fill="x", pady=12)
    log = ScrolledText(box, bg="#172a25", fg="#ebf4ea", font=("Courier", 10), wrap="word", padx=12, pady=10, state="disabled")
    log.pack(fill="both", expand=True)
    def poll():
        nonlocal running
        for _ in range(120):
            try:
                item = events.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, int):
                running = False
                progress.stop()
                state.set("Finalizado · consulte o registro" if item == 0 else "Falha · veja o registro")
                button.state(["!disabled"])
                manual_btn.state(["!disabled"])
            else:
                log.configure(state="normal")
                log.insert("end", item)
                if int(log.index("end-1c").split(".")[0]) > 1500:
                    log.delete("1.0", "100.0")
                log.see("end")
                log.configure(state="disabled")
        root.after(100, poll)
    def close():
        if running:
            state.set("Aguarde o término para fechar a janela")
        else:
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    poll()
    root.mainloop()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operacao", choices=["gui", "sobre", *ACTIONS], default="gui", nargs="?")
    p.add_argument("--modo", choices=MODES, default="auto")
    p.add_argument("--pastas", choices=PASTAS, default="categoria")
    p.add_argument("--confirmar-exclusao", action="store_true")
    p.add_argument("--site", action="append", help="URL inicial, opção repetível")
    p.add_argument("--limite", type=int, default=100)
    p.add_argument("--profundidade", type=int, default=3)
    args = p.parse_args()
    try:
        if args.operacao == "sobre":
            print("Foliúme\n" + CREDITO)
        elif args.operacao == "sites":
            from sites import coletar, configurados
            coletar(args.site or configurados(), args.limite, args.profundidade)
        elif args.operacao == "gui":
            gui()
        else:
            task(args.operacao, args.modo, args.pastas, args.confirmar_exclusao)
    except (ValueError, ImportError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f"Falha: {exc}")
