@echo off
cd /d "%~dp0"
echo InfoLivros - Python 3.14
if not exist ".confere-py314\Scripts\python.exe" py -3.14 -m venv .confere-py314
if errorlevel 1 goto fim
.confere-py314\Scripts\python -c "import pypdfium2" 2>nul || .confere-py314\Scripts\python -m pip install pypdfium2
if errorlevel 1 goto fim
.confere-py314\Scripts\python conferir.py
:fim
pause
