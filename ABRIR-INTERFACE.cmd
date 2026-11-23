@echo off
cd /d "%~dp0"
py -3.14 acervo.py gui
if errorlevel 1 pause
