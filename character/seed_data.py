"""
Catálogo de dados iniciais (seed) do personagem Botticellius.

Centraliza:
    * Espaços de magia padrão (SPELL_SLOTS).
    * Catálogo completo de magias (SPELLS) com fórmulas de cura/dano e
      indicação de concentração e magia de domínio.

Usado por:
    * character.services.create_default_character (criação automática por usuário)
    * character.management.commands.seed (comando manual de seed)
"""

# Espaços de magia por círculo: (nível, máximo)
SPELL_SLOTS = [
    (1, 4),
    (2, 3),
    (3, 3),
    (4, 2),
]


# Catálogo de magias.
# Cada dicionário vira um registro Spell ligado ao personagem.
SPELLS = [
    # ------------------------------------------------------------------ Truques
    {
        'name': 'Orientação',
        'spell_level': 0,
        'requires_concentration': True,
        'description': 'Toca uma criatura disposta. +1d4 em um teste de atributo à escolha. Concentração, até 1 minuto.',
    },
    {
        'name': 'Luz',
        'spell_level': 0,
        'description': 'Um objeto emite luz plena num raio de 6m e penumbra por mais 6m. Duração 1 hora.',
    },
    {
        'name': 'Estabilizar Moribundo',
        'spell_level': 0,
        'description': 'Toca uma criatura com 0 PV e a estabiliza. Alcance toque.',
    },
    {
        'name': 'Taumaturgia',
        'spell_level': 0,
        'description': 'Manifesta um pequeno prodígio sobrenatural (voz amplificada, tremores, abrir/fechar portas, etc.). Duração até 1 minuto.',
    },

    # ----------------------------------------------------------- Magias de Domínio
    {
        'name': 'Santuário',
        'spell_level': 1,
        'is_domain_spell': True,
        'description': 'Protege uma criatura: atacantes precisam passar em uma salvaguarda de Sabedoria ou escolher outro alvo. Bônus de ação. Duração 1 minuto.',
    },
    {
        'name': 'Heroísmo',
        'spell_level': 1,
        'is_domain_spell': True,
        'requires_concentration': True,
        'description': 'Uma criatura fica imune a medo e ganha PV temporários iguais ao seu mod. de conjuração no início de cada turno. Concentração, até 1 minuto.',
    },
    {
        'name': 'Auxílio',
        'spell_level': 2,
        'is_domain_spell': True,
        'description': 'Até 3 criaturas têm o PV máximo e atual aumentados em 5 por 8 horas.',
    },
    {
        'name': 'Vínculo de Proteção',
        'spell_level': 2,
        'is_domain_spell': True,
        'description': 'Cria um vínculo: a criatura alvo ganha +1 na CA e nas salvaguardas, e você sofre metade do dano que ela recebe. Duração 1 hora.',
    },
    {
        'name': 'Farol da Esperança',
        'spell_level': 3,
        'is_domain_spell': True,
        'requires_concentration': True,
        'description': 'Criaturas escolhidas têm vantagem em salvaguardas de Sab. e testes de morte, e recuperam o máximo em cura. Concentração, até 1 minuto.',
    },
    {
        'name': 'Enviar Mensagem',
        'spell_level': 3,
        'is_domain_spell': True,
        'description': 'Envia uma mensagem curta (25 palavras) a uma criatura conhecida em qualquer distância, no mesmo plano.',
    },
    {
        'name': 'Proteção contra a Morte',
        'spell_level': 4,
        'is_domain_spell': True,
        'description': 'Por 8 horas, a primeira vez que o alvo cairia a 0 PV ele fica com 1 PV; também previne morte instantânea e efeitos de dreno.',
    },
    {
        'name': 'Aura de Pureza',
        'spell_level': 4,
        'is_domain_spell': True,
        'requires_concentration': True,
        'description': 'Aura de 9m: aliados têm resistência a dano de veneno e vantagem em salvaguardas contra diversas condições. Concentração, até 10 minutos.',
    },

    # ----------------------------------------------------------- Magias Preparadas
    {
        'name': 'Abençoar',
        'spell_level': 1,
        'requires_concentration': True,
        'description': 'Até 3 criaturas adicionam 1d4 em jogadas de ataque e salvaguardas. Concentração, até 1 minuto.',
    },
    {
        'name': 'Curar Ferimentos',
        'spell_level': 1,
        'healing_formula': '1d8+5',
        'description': 'Toca uma criatura e recupera 1d8 + mod. de conjuração PV. Não afeta mortos-vivos nem construtos.',
    },
    {
        'name': 'Flecha Guia',
        'spell_level': 1,
        'damage_formula': '4d6',
        'description': 'Ataque mágico à distância. 4d6 de dano radiante e o próximo ataque contra o alvo tem vantagem.',
    },
    {
        'name': 'Escudo da Fé',
        'spell_level': 1,
        'requires_concentration': True,
        'description': '+2 na CA de uma criatura. Bônus de ação. Concentração, até 10 minutos.',
    },
    {
        'name': 'Restauração Menor',
        'spell_level': 2,
        'description': 'Toca uma criatura e encerra uma condição: cego, surdo, paralisado, envenenado ou doente.',
    },
    {
        'name': 'Imobilizar Pessoa',
        'spell_level': 2,
        'requires_concentration': True,
        'description': 'Um humanoide deve passar em salvaguarda de Sab. ou fica paralisado. Concentração, até 1 minuto.',
    },
    {
        'name': 'Intensificar Habilidade',
        'spell_level': 2,
        'requires_concentration': True,
        'description': 'Concede vantagem em testes de um atributo (e benefícios extras). Concentração, até 1 hora.',
    },
    {
        'name': 'Guardiões Espirituais',
        'spell_level': 3,
        'requires_concentration': True,
        'damage_formula': '3d8',
        'description': 'Espíritos giram em 4,5m ao redor. Inimigos sofrem 3d8 de dano radiante (metade se passarem) e têm o deslocamento reduzido à metade. Concentração, até 10 minutos.',
    },
    {
        'name': 'Reviver',
        'spell_level': 3,
        'description': 'Retorna à vida uma criatura morta há até 1 minuto, com 1 PV. Requer componente de 300 po.',
    },
    {
        'name': 'Dissipar Magia',
        'spell_level': 3,
        'description': 'Encerra um efeito mágico de até 3º círculo automaticamente (testes para níveis superiores).',
    },
    {
        'name': 'Conceder Maldição',
        'spell_level': 3,
        'requires_concentration': True,
        'description': 'Amaldiçoa uma criatura tocada com desvantagens diversas à escolha. Concentração, até 1 minuto.',
    },
    {
        'name': 'Aura da Vida',
        'spell_level': 4,
        'requires_concentration': True,
        'description': 'Aura de 9m: resistência a dano necrótico, redução de máximo de PV é anulada e aliados a 0 PV recuperam 1 PV. Concentração, até 10 minutos.',
    },
    {
        'name': 'Controlar Água',
        'spell_level': 4,
        'requires_concentration': True,
        'description': 'Controla grandes volumes de água (inundar, redirecionar, separar, criar redemoinhos). Concentração, até 10 minutos.',
    },
]
