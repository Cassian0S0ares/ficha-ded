# Ficha de Botticellius — Gerenciador de Ficha D&D 5e

Ficha web de **Botticellius** (Tortle · Clérigo · Domínio da Paz · nível 8),
com tema de fantasia, persistência no banco e atualização sem recarregar a página.
Back-end em **Django**, front-end em **JavaScript puro + Fetch API**.
O `requirements.txt` declara Django >= 5.2 e < 6.0 e psycopg >= 3.1.

A ficha principal **abre sem login**, com um personagem padrão compartilhado,
criado automaticamente no primeiro acesso. O vínculo com usuário existe no modelo,
mas a interface atual não oferece seleção de usuário ou de fichas.
O painel `/admin/` tem autenticação própria e uso opcional.

## Funcionalidades atuais

### Vida, defesa e recursos

- Dano e cura, com barra de PV e limites de vida.
- PV temporários, absorvidos antes dos PV normais.
- Dados de Vida: gastar um dado para recuperar PV e acompanhar os restantes.
- Testes contra a morte: rolagem, marcação manual de sucessos/falhas,
  estabilização e controle de morte; ação para reviver na ficha.
- Defesa de Concha com recálculo da CA (+4).
- Contadores de Canalizar Divindade e Vínculo Encorajador; ações de
  Expulsar Mortos-Vivos e Bálsamo da Paz.

### Magias, condições e rolagens

- Grimório com busca por nome, ignorando acentos e maiúsculas, dividido em
  truques, magias de domínio e magias preparadas.
- Conjuração com consumo do espaço do círculo original; truques não gastam
  espaços. Configuração inicial: 4/3/3/2 espaços do 1º ao 4º círculo.
- Concentração: início, substituição, encerramento e salvaguarda automática
  ao receber dano, considerando as condições aplicáveis.
- Condições de D&D 5e (2014), exaustão de níveis 1 a 6 e benefícios como
  Abençoado e Vínculo ativo, exibidos no topo.
- Duração editável em rodadas ou sem prazo. **Avançar rodada** desconta uma
  rodada completa de combate (6 segundos), avisa nas últimas duas e encerra
  efeitos ao chegar a zero. Não é um relógio em tempo real.
- Vínculo Encorajador começa com 100 rodadas; concentração usa a duração
  reconhecida no catálogo. Durações desconhecidas ficam sem prazo.
- Dados d4–d20; fórmulas de cura e dano, ataques, testes de atributo e salvaguardas.
- As 18 perícias abaixo da rolagem de dados, com proficiência editável,
  fórmula `D20 + bônus`, indicação de vantagem/desvantagem e dado clicável.
  Os atributos permanecem no próprio painel.
- Rolagens de d20 aplicam condições, bônus em dados, vantagens, desvantagens
  e falhas automáticas. Situações que dependem da mesa aparecem como avisos,
  incluindo alcance e limite de uso do Vínculo.
- Percepção passiva calculada a partir do bônus da perícia.
- **Inspiração Heroica (em desenvolvimento):** o código atual permite ganhar
  ou remover inspiração e escolher gastá-la para obter vantagem numa jogada
  compatível, incluindo concentração e testes contra a morte. Esta descrição
  registra o comportamento presente na implementação em andamento.

### Campanha e inventário

- Inventário com categorias, quantidades, descrições, fórmula de dano e
  marcação de equipado; usar um item desconta uma unidade.
- Moedas de cobre, prata, electro, ouro e platina.
- Notas com pastas, edição e salvamento automático; mover pelo seletor ou
  arrastando o bloco para uma pasta ou para **Sem pasta**.
- Modais no estilo da ficha para criar, renomear e confirmar exclusões nas notas.
- Personagens da campanha (NPCs) com busca por nome, foto, anotações e afeto
  de 0 a 3, com salvamento automático.
- Foto do personagem principal e fotos de NPCs, com placeholders quando vazias.
- Histórico persistido de atividades e rolagens; a tela mostra registros recentes.
- **Desfazer** pelo botão ou `Ctrl+Z` fora dos campos de edição: mantém até 20
  estados anteriores de vida, recursos, espaços, efeitos, proficiências,
  inspiração, inventário e moedas. Notas, NPCs e fotos ficam fora desse recurso;
  rolagens que não alteram o estado não criam ponto de desfazer.

### Descansos

- **Curto:** recupera Canalizar Divindade e limpa condições, efeitos e
  concentração. Não recupera espaços. Dados de Vida são gastos pelo controle próprio.
- **Longo:** restaura PV, recursos e espaços; recupera até metade do máximo
  de Dados de Vida (mínimo de um), limpa PV temporários, testes contra a morte,
  efeitos e concentração e desativa Defesa de Concha.

Limpar todas as condições nos dois descansos é uma escolha desta ficha,
conforme solicitado para o uso na campanha.

## Como executar

### Windows

Com Python instalado, dê dois cliques em **`run.bat`**. Na primeira execução,
o script cria `.venv` e instala dependências; depois aplica as migrações e inicia
o servidor em **http://127.0.0.1:8000/**. Encerre com `Ctrl+C` no terminal.

Instalação ou atualização manual no PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

### Linux/macOS

No Linux, execute `bash run.sh` para preparar o ambiente, instalar dependências
na primeira execução, aplicar migrações e iniciar o servidor. A abertura automática
do navegador depende de `xdg-open`; o endereço pode ser aberto manualmente.

Execução manual em Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Não é necessário criar usuário para abrir a ficha. Para usar o admin, execute
`python manage.py createsuperuser` no ambiente virtual.

## Configuração e armazenamento

O `settings.py` lê o `.env` na raiz sem sobrescrever variáveis já definidas
no ambiente. O `.env.example` contém exemplos para serviços remotos; substitua
os valores antes de usá-los.

- **SQLite é o padrão:** sem `USE_POSTGRES=1`, os dados ficam em `db.sqlite3`.
  A variável antiga `USE_SQLITE` não seleciona o banco no código atual.
- **PostgreSQL é opcional:** use `USE_POSTGRES=1` e configure `DB_NAME`,
  `DB_USER`, `DB_PASSWORD`, `DB_HOST` e `DB_PORT`. `DB_SSLMODE` tem padrão
  `require`; ajuste conforme a configuração do seu servidor.
- **Fotos locais:** sem configuração de armazenamento remoto, ficam em `media/`.
- **Supabase Storage opcional:** quando `SUPABASE_URL` e `SUPABASE_SECRET_KEY`
  estão definidos, o backend `character.storage.SupabaseStorage` é usado para
  uploads. `SUPABASE_BUCKET` tem padrão `avatars`; o backend gera URLs públicas
  para exibir fotos. Banco e armazenamento de fotos são configurações separadas.
- Outras opções: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (padrão ligado),
  `DJANGO_ALLOWED_HOSTS` e `DJANGO_TIME_ZONE` (padrão `America/Sao_Paulo`).

O servidor de desenvolvimento e a ficha sem login destinam-se ao uso local.
O login do admin não restringe o dashboard nem seus endpoints.

Para preservar uma instalação local com SQLite, guarde `db.sqlite3` e `media/`
com o servidor parado. Banco ou fotos remotos precisam ser preservados
separadamente nos serviços configurados.

## Estrutura

```text
botticellius_sheet/       Configurações e rotas do projeto
character/
  models.py              Ficha, magias, efeitos, histórico, notas, itens, NPCs e desfazer
  services.py            Regras de negócio e serialização do estado
  rolls.py               Regras de d20, atributos, perícias e condições
  effects.py             Catálogo de condições e durações de concentração
  undo.py                Captura e restauração de estados anteriores
  views.py / urls.py     Dashboard e endpoints JSON
  forms.py               Validação dos dados recebidos
  seed_data.py           Valores e catálogo iniciais
  storage.py             Backend opcional de fotos no Supabase Storage
  admin.py               Administração dos modelos
  management/commands/seed.py  Criação manual opcional de fichas
  migrations/            Evolução do banco
  templates/character/   Dashboard e componentes da interface
  static/character/      CSS, imagens e JavaScript por funcionalidade
  tests.py / test_*.py    Testes de serviços e endpoints
run.bat / run.sh         Inicialização local
```

## Verificações

Com o ambiente virtual ativo:

```bash
python manage.py check
python manage.py test --noinput
python manage.py makemigrations --check --dry-run
```

Para testar com SQLite independentemente do `.env`, defina `USE_POSTGRES=0`
antes do comando: `$env:USE_POSTGRES='0'` no PowerShell ou
`USE_POSTGRES=0 python manage.py test --noinput` em Linux/macOS.

O comando opcional `python manage.py seed --user NOME` cria a ficha inicial
para um usuário já existente. Isso não adiciona seleção de usuário ao dashboard.
