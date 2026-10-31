@echo off
title AgriVyaan Streamlit Dashboard
cd /d "%~dp0"
call .venv\Scripts\streamlit.exe run src\agrivyaan_swarm\dashboard\app.py
pause
