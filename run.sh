#!/usr/bin/env bash
# ============================================================
#  Inicia a Ficha de Botticellius (D&D 5e)
#  Basta executar:  ./iniciar.sh
# ============================================================
set -e
cd "$(dirname "$0")"

echo "==> Preparando ambiente..."

# 1) Cria a venv na primeira vez e instala dependências
if [ ! -d ".venv" ]; then
    echo "==> Criando ambiente virtual (.venv)..."
    python3 -m venv .venv
    ./.venv/bin/pip install --quiet --upgrade pip
    ./.venv/bin/pip install --quiet -r requirements.txt
fi

source .venv/bin/activate

# 2) Banco: usa SQLite por padrão para abrir sem instalar PostgreSQL.
#    Para usar PostgreSQL, defina USE_POSTGRES=1 e as variáveis DB_*
#    (veja .env.example) antes de rodar este script.
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"

# 3) Aplica as migrações
echo "==> Aplicando migrações..."
python manage.py migrate --noinput

# 4) Abre o navegador e sobe o servidor (a ficha abre SEM login)
URL="http://127.0.0.1:8000/"
echo ""
echo "============================================================"
echo "  Abrindo a ficha em: $URL"
echo "  (abre direto, sem login)"
echo "  Para encerrar, pressione CTRL+C nesta janela."
echo "============================================================"
echo ""

( sleep 2; xdg-open "$URL" >/dev/null 2>&1 || true ) &

python manage.py runserver
