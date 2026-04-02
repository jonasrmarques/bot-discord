@echo off
REM Inicia o bot na pasta deste arquivo. Use no Agendador de Tarefas ou na pasta Inicializar.
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo Nao encontrei venv\ nem .venv\ — crie o ambiente virtual e instale: pip install -r requirements.txt
    pause
    exit /b 1
)

python main.py
if errorlevel 1 pause
