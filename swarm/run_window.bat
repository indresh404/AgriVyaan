@echo off
title AgriVyaan Visual Simulation Window
cd /d "%~dp0"
call .venv\Scripts\python.exe scripts\visual_simulation_window.py
pause
