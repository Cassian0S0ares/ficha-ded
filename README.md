# Ficha de Botticellius — Gerenciador de Ficha D&D 5e

Aplicação web em **Django 5 + PostgreSQL** para gerenciar a ficha de D&D 5e do
personagem **Botticellius** (Tortle · Clérigo · Domínio da Paz, nível 8) durante
campanhas longas, com persistência imediata no banco e interface com tema de
fantasia medieval.

## Funcionalidades

- **Vida**: barra gráfica, receber dano e curar (limites 0 / PV máximo).
- **Defesa**: CA com recálculo automático da **Defesa de Concha** (+4).
- **Espaços de magia**: 1º=4, 2º=3, 3º=3, 4º=2, com indicadores visuais.
- **Conjuração**: cada magia tem botão *Conjurar* que valida e consome o espaço
  do círculo correto via AJAX (truques não gastam espaço).
- **Concentração**: inicia/substitui/encerra a magia concentrada.
- **Recursos de classe/domínio**: Canalizar Divindade, Expulsar Mortos-Vivos,
  Bálsamo da Paz (2d6+5) e Vínculo Encorajador, com contadores no banco.
- **Rolagens**: d4–d20 e calculadora de cura/dano (1d8+5, 4d6, 3d8, 2d6+5,
  1d4+2…), com histórico salvo.
- **Descansos**: curto (recupera Canalizar Divindade) e longo (restaura PV,
  recursos, espaços, zera concentração e Defesa de Concha).
- **Histórico** completo de atividades e rolagens.
- **Autenticação** do Django (cada usuário tem sua própria ficha; o schema já
  suporta múltiplos personagens por usuário).

## Estrutura

```
botticellius_sheet/        # projeto Django
  settings.py              # configuração (PostgreSQL via env; USE_SQLITE p/ dev)
  urls.py                  # admin, login/logout, app character
character/                 # app principal
  models.py                # Character, SpellSlot, Spell, ActivityLog, DiceRoll
  services.py              # regras de negócio (camada de serviços)
  views.py                 # dashboard + endpoints AJAX (JSON)
  urls.py                  # rotas do app
  forms.py                 # validação de payloads / cadastro
  seed_data.py             # catálogo de magias e espaços iniciais
  admin.py                 # admin do Django
  management/commands/seed.py   # seed manual opcional
  migrations/              # migrações
  templates/character/     # base, login, signup, dashboard, _spell
  static/character/        # CSS (tema medieval) e JS (Fetch API)
```

## Como executar

### 1. Dependências

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Banco de dados PostgreSQL (padrão)

Crie o banco e o usuário (ajuste a senha conforme desejar):

```bash
sudo -u postgres psql <<'SQL'
CREATE USER botticellius WITH PASSWORD 'botticellius';
CREATE DATABASE botticellius OWNER botticellius;
SQL
```

Configure as variáveis de ambiente (veja `.env.example`):

```bash
export DB_NAME=botticellius DB_USER=botticellius DB_PASSWORD=botticellius \
       DB_HOST=localhost DB_PORT=5432
```

> **Sem PostgreSQL à mão?** Para um teste rápido use SQLite:
> `export USE_SQLITE=1` antes dos comandos abaixo.

### 3. Migrar, criar usuário e rodar

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse **http://127.0.0.1:8000/**, faça login e a ficha do Botticellius é criada
automaticamente no primeiro acesso (atributos, espaços de magia e todas as
magias já populados). Nenhum passo manual adicional é necessário.

O admin do Django fica em **/admin/**.

## Notas técnicas

- Todas as ações persistem imediatamente e registram histórico.
- O front-end usa **JavaScript puro + Fetch API**; o back-end responde JSON e o
  dashboard é re-renderizado em tempo real sem recarregar a página.
- A **CA efetiva** é uma propriedade calculada: `armor_class + 4` quando a
  Defesa de Concha está ativa.
- Regras de negócio ficam isoladas em `character/services.py`.
