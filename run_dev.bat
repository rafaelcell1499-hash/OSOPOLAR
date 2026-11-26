@echo off
REM Ejecutar sin compilar (requiere Python 3.10+ y FFmpeg en la carpeta bin\ o en el PATH)
python -m pip install -r requirements.txt
python main.py
