@echo off
cd /d "%~dp0"
echo InfoLivros - Python 3.14
if not exist ".ocr-gpu-py314\Scripts\python.exe" py -3.14 -m venv .ocr-gpu-py314
if errorlevel 1 goto fim
.ocr-gpu-py314\Scripts\python -c "import torch, torchvision; assert torch.version.cuda" 2>nul || .ocr-gpu-py314\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto fim
.ocr-gpu-py314\Scripts\python -c "import easyocr, pypdfium2" 2>nul || .ocr-gpu-py314\Scripts\python -m pip install easyocr pypdfium2
if errorlevel 1 goto fim
.ocr-gpu-py314\Scripts\python conferir.py --gpu
:fim
pause
