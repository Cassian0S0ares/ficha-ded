"""Como as condições ativas afetam as jogadas de d20 (D&D 5e 2014).

`d20_context` recebe as condições ativas e diz, para um tipo de jogada
(ataque, teste de atributo ou salvaguarda), se ela tem vantagem,
desvantagem, falha automática, bônus em dados (+1d4) ou se está impedida,
além de avisos situacionais que o app não consegue decidir sozinho.

`roll_summary` descreve o mesmo em texto para o painel da ficha.
"""

from .effects import CONDITIONS, INCAPACITATING

ABILITIES = {
    'str': ('strength', 'FOR', 'Força'),
    'dex': ('dexterity', 'DES', 'Destreza'),
    'con': ('constitution', 'CON', 'Constituição'),
    'int': ('intelligence', 'INT', 'Inteligência'),
    'wis': ('wisdom', 'SAB', 'Sabedoria'),
    'cha': ('charisma', 'CAR', 'Carisma'),
}
# Clérigo: proficiência em salvaguardas de Sabedoria e Carisma.
SAVE_PROFICIENCIES = {'wis', 'cha'}

AUTO_FAIL_STR_DEX = ('paralyzed', 'petrified', 'stunned', 'unconscious')


def _name(key):
    return CONDITIONS[key][0] if key in CONDITIONS else key


def d20_context(effects, kind, ability=None, *, shell_defense=False):
    """Modificadores de uma jogada de d20.

    effects: dict {chave_da_condição: nível} (nível só importa para exaustão).
    kind: 'attack' | 'check' | 'save'. ability: chave de ABILITIES.
    """
    ctx = {'advantage': [], 'disadvantage': [], 'bonus': [], 'warnings': [],
           'auto_fail': None, 'blocked': None}
    has = effects.__contains__
    exhaustion = effects.get('exhaustion', 0)

    if kind == 'attack':
        blocked = [k for k in sorted(INCAPACITATING) if has(k)]
        if blocked:
            ctx['blocked'] = f'{_name(blocked[0])}: não pode realizar ações nem atacar.'
        if has('invisible'):
            ctx['advantage'].append(_name('invisible'))
        for key in ('blinded', 'poisoned', 'prone', 'restrained', 'frightened'):
            if has(key):
                ctx['disadvantage'].append(_name(key))
        if has('frightened'):
            ctx['warnings'].append('Amedrontado: desvantagem só enquanto vê a fonte do medo.')
        if exhaustion >= 3:
            ctx['disadvantage'].append(f'Exausto {exhaustion}')
        if has('charmed'):
            ctx['warnings'].append('Enfeitiçado: não pode atacar quem o enfeitiçou.')
        if has('blessed'):
            ctx['bonus'].append(('1d4', _name('blessed')))

    elif kind == 'check':
        for key in ('poisoned', 'frightened'):
            if has(key):
                ctx['disadvantage'].append(_name(key))
        if has('frightened'):
            ctx['warnings'].append('Amedrontado: desvantagem só enquanto vê a fonte do medo.')
        if exhaustion >= 1:
            ctx['disadvantage'].append(f'Exausto {exhaustion}')
        if has('blinded'):
            ctx['warnings'].append('Cego: falha automática se o teste exigir visão.')
        if has('deafened'):
            ctx['warnings'].append('Surdo: falha automática se o teste exigir audição.')

    elif kind == 'save':
        if ability in ('str', 'dex'):
            failing = [k for k in AUTO_FAIL_STR_DEX if has(k)]
            if failing:
                ctx['auto_fail'] = f'{_name(failing[0])}: falha automática em salvaguardas de Força e Destreza.'
        if ability == 'dex' and has('restrained'):
            ctx['disadvantage'].append(_name('restrained'))
        if exhaustion >= 3:
            ctx['disadvantage'].append(f'Exausto {exhaustion}')
        if shell_defense and ability in ('str', 'con'):
            ctx['advantage'].append('Defesa de Concha')
        if has('blessed'):
            ctx['bonus'].append(('1d4', _name('blessed')))

    if has('bond'):
        ctx['bonus'].append(('1d4', _name('bond')))
        ctx['warnings'].append('Vínculo: +1d4 só uma vez por turno e com outro vinculado a até 9 m.')
    return ctx


def roll_mode(ctx):
    """'advantage', 'disadvantage' ou 'normal' (vantagem e desvantagem se anulam)."""
    if ctx['advantage'] and ctx['disadvantage']:
        return 'normal'
    if ctx['advantage']:
        return 'advantage'
    if ctx['disadvantage']:
        return 'disadvantage'
    return 'normal'


def _describe(ctx):
    parts = []
    mode = roll_mode(ctx)
    if mode == 'advantage':
        parts.append('vantagem (' + ', '.join(ctx['advantage']) + ')')
    elif mode == 'disadvantage':
        parts.append('desvantagem (' + ', '.join(ctx['disadvantage']) + ')')
    elif ctx['advantage']:
        parts.append('vantagem e desvantagem se anulam')
    parts += ['+' + dice + ' (' + source + ')' for dice, source in ctx['bonus']]
    return ', '.join(parts)


def roll_summary(effects, *, shell_defense=False):
    """Linhas de texto: como as condições ativas mudam as jogadas agora."""
    lines = []
    attack = d20_context(effects, 'attack')
    if attack['blocked']:
        lines.append('Ataques: impedidos. ' + attack['blocked'])
    elif _describe(attack):
        lines.append('Ataques: ' + _describe(attack))
    check = d20_context(effects, 'check')
    if _describe(check):
        lines.append('Testes de atributo: ' + _describe(check))

    saves = {}
    for key, (_, short, _) in ABILITIES.items():
        ctx = d20_context(effects, 'save', key, shell_defense=shell_defense)
        text = ('falha automática' if ctx['auto_fail'] else _describe(ctx))
        if text:
            saves.setdefault(text, []).append(short)
    for text, shorts in saves.items():
        lines.append('Salvaguardas de ' + '/'.join(shorts) + ': ' + text)

    against_adv = [_name(k) for k in ('blinded', 'paralyzed', 'petrified', 'restrained',
                                      'stunned', 'unconscious') if k in effects]
    against_dis = [_name('invisible')] if 'invisible' in effects else []
    if against_adv and against_dis:
        lines.append('Ataques contra você: vantagem e desvantagem se anulam')
    elif against_adv:
        lines.append('Ataques contra você: vantagem (' + ', '.join(against_adv) + ')')
    elif against_dis:
        lines.append('Ataques contra você: desvantagem (' + ', '.join(against_dis) + ')')
    if 'prone' in effects:
        lines.append('Caído: ataques contra você a até 1,5 m têm vantagem; de mais longe, desvantagem.')
    if 'paralyzed' in effects or 'unconscious' in effects:
        lines.append('Acertos contra você a até 1,5 m são críticos.')

    seen = set()
    for kind in ('attack', 'check'):
        for warning in d20_context(effects, kind)['warnings']:
            if warning not in seen:
                seen.add(warning)
                lines.append('Atenção: ' + warning)
    return lines
