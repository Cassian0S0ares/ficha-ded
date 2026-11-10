"""Condições de D&D 5e (2014) e benefícios acompanhados pela ficha.

Referência: https://www.dndbeyond.com/sources/dnd/basic-rules-2014/appendix-a-conditions
Resumos em português; condições não têm duração universal.
"""

CONDITIONS = {
    'poisoned': ('Envenenado', 'Desvantagem em ataques e testes de atributo.'),
    'prone': ('Caído', 'Ataques com desvantagem; ataques recebidos a até 1,5 m têm vantagem, os demais têm desvantagem. Levantar custa metade do deslocamento.'),
    'blinded': ('Cego', 'Falha em testes que exigem visão; ataques com desvantagem e ataques recebidos com vantagem.'),
    'charmed': ('Enfeitiçado', 'Não pode atacar ou prejudicar quem o enfeitiçou; essa criatura tem vantagem em interações sociais.'),
    'deafened': ('Surdo', 'Falha em testes que exigem audição.'),
    'frightened': ('Amedrontado', 'Desvantagem em ataques e testes enquanto vê a fonte do medo; não pode se aproximar dela voluntariamente.'),
    'grappled': ('Agarrado', 'Deslocamento zero. Termina se o agarrador ficar incapacitado ou se sair do alcance.'),
    'incapacitated': ('Incapacitado', 'Não pode realizar ações nem reações; encerra concentração.'),
    'invisible': ('Invisível', 'Não é visto sem magia ou sentido especial; ataques com vantagem e ataques recebidos com desvantagem.'),
    'paralyzed': ('Paralisado', 'Incapacitado, sem movimento ou fala; falha em resistências de Força e Destreza. Ataques recebidos com vantagem; acertos a até 1,5 m são críticos.'),
    'petrified': ('Petrificado', 'Incapacitado e imóvel; resistência a todo dano, imunidade a veneno e doença. Falha em resistências de Força e Destreza; ataques recebidos com vantagem.'),
    'restrained': ('Impedido', 'Deslocamento zero; ataques com desvantagem, ataques recebidos com vantagem e desvantagem em resistências de Destreza.'),
    'stunned': ('Atordoado', 'Incapacitado e imóvel; fala com dificuldade, falha em resistências de Força e Destreza; ataques recebidos com vantagem.'),
    'unconscious': ('Inconsciente', 'Incapacitado, sem perceber o entorno, solta objetos e cai. Falha em resistências de Força e Destreza; ataques recebidos com vantagem, acertos a até 1,5 m são críticos.'),
    'exhaustion': ('Exausto', 'Níveis cumulativos: 1 desvantagem em testes; 2 deslocamento pela metade; 3 desvantagem em ataques e resistências; 4 PV máximo pela metade; 5 deslocamento zero; 6 morte.'),
    'blessed': ('Abençoado', '+1d4 em ataques e salvaguardas. Marque quando receber Abençoar; não consome seus espaços ou concentração.'),
    'bond': ('Vínculo ativo', '+1d4 em ataque, teste ou salvaguarda, uma vez por turno, a até 9 m de outro vinculado. Não exige concentração.'),
}
DEFAULT_ROUNDS = {'blessed': 10, 'bond': 100}
INCAPACITATING = {'incapacitated', 'paralyzed', 'petrified', 'stunned', 'unconscious'}


def spell_rounds(name):
    from .seed_data import SPELLS
    description = next((s['description'] for s in SPELLS if s['name'] == name), '')
    import re
    match = re.search(r'até (\d+) (minuto|hora)', description)
    if match:
        return int(match[1]) * (600 if match[2] == 'hora' else 10)
    return None  # Duração desconhecida: o jogador informa, sem prazo inventado.
