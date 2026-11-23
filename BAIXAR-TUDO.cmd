@echo off
cd /d "%~dp0"
echo 1. Por categoria
echo 2. Por categoria e tema
echo 3. Pasta unica
choice /c 123 /m "Como organizar os PDFs?"
if errorlevel 4 exit /b 1
set "pastas=categoria"
if errorlevel 2 set "pastas=tema"
if errorlevel 3 set "pastas=unica"
py -3.14 acervo.py completo --pastas %pastas%
pause
