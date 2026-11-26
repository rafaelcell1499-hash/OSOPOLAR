@echo off
REM Compilar localmente en Windows. Coloca ffmpeg.exe y ffprobe.exe en la carpeta bin\ antes de ejecutar.
python -m pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name ReelForge --exclude-module tkinter main.py
if not exist dist\ReelForge\bin mkdir dist\ReelForge\bin
copy /Y bin\ffmpeg.exe dist\ReelForge\bin\
copy /Y bin\ffprobe.exe dist\ReelForge\bin\
echo.
echo Listo: dist\ReelForge\ReelForge.exe
