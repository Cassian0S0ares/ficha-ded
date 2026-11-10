@echo off
rem ============================================================
rem  Inicia a Ficha de Botticellius (D&D 5e) no Windows
rem  Basta dar dois cliques neste arquivo (ou rodar: run.bat)
rem ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo ==^> Preparando ambiente...

rem 1) Cria a venv na primeira vez e instala as dependencias
if not exist ".venv\Scripts\python.exe" (
    echo ==^> Criando ambiente virtual ^(.venv^)...
    where py >nul 2>&1 && (py -3 -m venv .venv) || (python -m venv .venv)
    if not exist ".venv\Scripts\python.exe" (
        echo ERRO: nao foi possivel criar a .venv. Instale o Python 3 em python.org.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo ERRO: falha ao instalar as dependencias.
        rmdir /s /q .venv
        pause
        exit /b 1
    )
)

rem 2) Banco: o settings.py le o arquivo .env (Supabase/PostgreSQL).
rem    Sem .env, usa o SQLite local (db.sqlite3).
set "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1"

rem 3) Aplica as migracoes
echo ==^> Aplicando migracoes...
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 (
    echo ERRO: falha ao aplicar as migracoes. Confira o .env e a conexao.
    pause
    exit /b 1
)

rem 4) Abre o navegador e sobe o servidor (a ficha abre SEM login)
set "URL=http://127.0.0.1:8000/"
echo.
echo ============================================================
echo   Abrindo a ficha em: %URL%
echo   (abre direto, sem login)
echo   Para encerrar, pressione CTRL+C nesta janela.
echo ============================================================
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul & start "" %URL%"

".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
pause
