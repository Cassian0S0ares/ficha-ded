"""
Camada de serviços: concentra TODAS as regras de negócio da ficha.

As views ficam finas e delegam para estas funções. Toda alteração é
persistida no banco imediatamente (save) e, quando relevante, registra
um ActivityLog.

Funções principais:
    create_default_character  -> cria Botticellius + slots + magias para um User
    get_or_create_character   -> garante que o usuário tenha uma ficha
    serialize_state           -> snapshot JSON da ficha (consumido via AJAX)
    cast_spell / heal / take_damage / use_channel_divinity / ...
    short_rest / long_rest
    roll_dice / roll_formula
"""

import random
import re

from django.db import transaction

from .models import (
    ActivityLog, Character, DiceRoll, InventoryItem, Note, NoteFolder, Npc,
    Spell, SpellSlot,
)
from .seed_data import SPELL_SLOTS, SPELLS
from .effects import CONDITIONS, DEFAULT_ROUNDS, INCAPACITATING, spell_rounds
from . import rolls, undo


# ======================================================================
# Criação / obtenção da ficha
# ======================================================================
@transaction.atomic
def create_default_character(user):
    """Cria o personagem Botticellius completo para o usuário informado.

    Gera a ficha com os valores padrão, os espaços de magia e o catálogo
    de magias. Idempotente o suficiente para uso em seed: se o usuário já
    tiver um personagem, retorna o existente.
    """
    existing = user.characters.first()
    if existing:
        return existing

    character = Character.objects.create(owner=user)

    # Espaços de magia (current = maximum inicialmente)
    SpellSlot.objects.bulk_create([
        SpellSlot(character=character, level=level, maximum=mx, current=mx)
        for level, mx in SPELL_SLOTS
    ])

    # Catálogo de magias
    Spell.objects.bulk_create([
        Spell(
            character=character,
            name=data['name'],
            spell_level=data['spell_level'],
            description=data.get('description', ''),
            is_domain_spell=data.get('is_domain_spell', False),
            requires_concentration=data.get('requires_concentration', False),
            healing_formula=data.get('healing_formula', ''),
            damage_formula=data.get('damage_formula', ''),
        )
        for data in SPELLS
    ])

    log(character, 'Ficha criada: Botticellius, o Tortle Clérigo do Domínio da Paz.')
    return character


def get_or_create_character(user):
    """Retorna a ficha do usuário, criando-a (com seed) se necessário."""
    character = user.characters.first()
    if character is None:
        character = create_default_character(user)
    return character


def get_sheet():
    """Retorna a ficha padrão (sem login).

    Garante a existência de um usuário "dono" padrão e da ficha de
    Botticellius vinculada a ele, criando ambos na primeira chamada.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username='botticellius',
        defaults={'is_staff': False, 'is_active': True},
    )
    return get_or_create_character(user)


# ======================================================================
# Foto do personagem
# ======================================================================
def set_avatar(character, upload):
    """Substitui a foto do personagem, removendo a anterior."""
    if character.avatar:
        character.avatar.delete(save=False)
    character.avatar = upload
    character.save(update_fields=['avatar', 'updated_at'])
    log(character, 'Foto do personagem atualizada.')
    return character


# ======================================================================
# Histórico
# ======================================================================
def log(character, action):
    """Cria um registro de histórico."""
    return ActivityLog.objects.create(character=character, action=action)


# ======================================================================
# Rolagem de dados
# ======================================================================
DICE_FACES = {'d4': 4, 'd6': 6, 'd8': 8, 'd10': 10, 'd12': 12, 'd20': 20}
FORMULA_RE = re.compile(r'^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$', re.IGNORECASE)


def _roll_die(faces):
    return random.randint(1, faces)


def parse_and_roll(formula):
    """Interpreta uma fórmula tipo '3d8+5' e retorna (total, detalhe).

    Levanta ValueError se a fórmula for inválida.
    """
    match = FORMULA_RE.match(formula or '')
    if not match:
        raise ValueError(f'Fórmula de dados inválida: {formula!r}')

    qty = int(match.group(1)) if match.group(1) else 1
    faces = int(match.group(2))
    modifier = int(match.group(3).replace(' ', '')) if match.group(3) else 0

    if qty < 1 or qty > 100 or faces < 2 or faces > 1000:
        raise ValueError('Fórmula de dados fora dos limites permitidos.')

    rolls = [_roll_die(faces) for _ in range(qty)]
    total = sum(rolls) + modifier

    detail = ' + '.join(str(r) for r in rolls)
    if modifier:
        detail = f'({detail}) {"+" if modifier > 0 else "-"} {abs(modifier)}'
    return total, detail


def roll_dice(character, dice):
    """Rola um único dado padrão (d4..d20) e salva no histórico."""
    if dice not in DICE_FACES:
        raise ValueError(f'Dado não suportado: {dice!r}')
    result = _roll_die(DICE_FACES[dice])
    DiceRoll.objects.create(character=character, dice=dice, result=result)
    log(character, f'Rolagem {dice}: {result}.')
    return result


def roll_formula(character, formula, label=''):
    """Rola uma fórmula (ex.: cura/dano de magia) e salva no histórico."""
    total, detail = parse_and_roll(formula)
    DiceRoll.objects.create(
        character=character, dice=formula, result=total, detail=detail
    )
    prefix = f'{label}: ' if label else ''
    log(character, f'{prefix}{formula} = {total} [{detail}].')
    return total, detail


def skill_bonus(character, skill):
    """Modificador do atributo + proficiência, se proficiente."""
    _, ability = rolls.SKILLS[skill]
    field = rolls.ABILITIES[ability][0]
    bonus = character.ability_modifier(getattr(character, field))
    if skill in (character.skill_proficiencies or []):
        bonus += character.proficiency_bonus
    return bonus


def serialize_skills(character):
    """Perícias com bônus e proficiência, na ordem da ficha."""
    proficient = set(character.skill_proficiencies or [])
    skills = [
        {'key': key, 'name': name, 'ability': ability,
         'bonus': skill_bonus(character, key), 'proficient': key in proficient}
        for key, (name, ability) in rolls.SKILLS.items()
    ]
    effects = effects_map(character)
    for skill in skills:
        ctx = rolls.d20_context(effects, 'check', skill['ability'])
        mode = rolls.roll_mode(ctx)
        bonus = skill['bonus']
        formula = f'D20 {"+" if bonus >= 0 else "−"} {abs(bonus)}'
        formula += ''.join(' + ' + dice.upper() for dice, _ in ctx['bonus'])
        if mode != 'normal':
            formula += ' · ' + ('Vantagem' if mode == 'advantage' else 'Desvantagem')
        skill.update(formula=formula, warnings=ctx['warnings'])
    return skills


def toggle_skill_proficiency(character, skill):
    if skill not in rolls.SKILLS:
        raise ValueError('Perícia desconhecida.')
    skills = list(character.skill_proficiencies or [])
    name = rolls.SKILLS[skill][0]
    if skill in skills:
        skills.remove(skill)
        log(character, f'Proficiência removida: {name}.')
    else:
        skills.append(skill)
        log(character, f'Proficiência adicionada: {name}.')
    character.skill_proficiencies = skills
    character.save(update_fields=['skill_proficiencies', 'updated_at'])
    return character


def effects_map(character):
    """Condições ativas como {chave: nível} (nível só vale para exaustão)."""
    return {e.key: e.exhaustion_level for e in character.active_effects.all()}


D20_ATTACKS = {
    'spell': 'Ataque mágico',
    'claws': 'Garras (ataque)',
}


INSPIRATION = 'Inspiração heroica'


def _spend_inspiration(character, ctx):
    """Gasta a inspiração heroica para ganhar vantagem nesta jogada."""
    if not character.heroic_inspiration:
        raise ValueError('Sem inspiração heroica para usar.')
    ctx['advantage'].append(INSPIRATION)
    character.heroic_inspiration = False
    character.save(update_fields=['heroic_inspiration', 'updated_at'])


def set_inspiration(character, value):
    """Ganha (True) ou remove (False) a inspiração heroica."""
    if character.heroic_inspiration == value:
        raise ValueError('Já tem inspiração heroica.' if value else 'Não tem inspiração heroica.')
    character.heroic_inspiration = value
    character.save(update_fields=['heroic_inspiration', 'updated_at'])
    log(character, 'Ganhou inspiração heroica.' if value else 'Inspiração heroica removida.')
    return character


def roll_d20(character, kind, ability=None, *, label='', dc=None, inspiration=False):
    """Rola d20 de ataque, teste ou salvaguarda aplicando as condições ativas.

    kind: 'attack' (ability = 'spell' ou 'claws'), 'check' ou 'save'
    (ability = chave de rolls.ABILITIES) ou 'skill' (ability = chave de
    rolls.SKILLS; é um teste de atributo). Vantagem e desvantagem vêm das
    condições (ver character.rolls); bônus como +1d4 de Abençoar e do
    Vínculo são somados. Levanta SpellCastError se a condição impede a jogada.
    inspiration=True gasta a inspiração heroica para rolar com vantagem
    (não é gasta em falha automática).
    """
    if kind == 'attack':
        if ability not in D20_ATTACKS:
            raise ValueError('Ataque desconhecido.')
        if ability == 'spell':
            modifier = character.spell_attack_bonus
        else:  # Garras: Força + proficiência (ataque desarmado)
            modifier = character.ability_modifier(character.strength) + character.proficiency_bonus
        label = label or D20_ATTACKS[ability]
    elif kind in ('check', 'save'):
        if ability not in rolls.ABILITIES:
            raise ValueError('Atributo desconhecido.')
        field, short, _ = rolls.ABILITIES[ability]
        modifier = character.ability_modifier(getattr(character, field))
        if kind == 'save' and ability in rolls.SAVE_PROFICIENCIES:
            modifier += character.proficiency_bonus
        label = label or (('Teste de ' if kind == 'check' else 'Salv. ') + short)
    elif kind == 'skill':
        if ability not in rolls.SKILLS:
            raise ValueError('Perícia desconhecida.')
        modifier = skill_bonus(character, ability)
        label = label or rolls.SKILLS[ability][0]
    else:
        raise ValueError('Tipo de jogada desconhecido.')

    # Perícia é um teste do atributo dela (mesmas condições).
    rule_kind, rule_ability = (('check', rolls.SKILLS[ability][1]) if kind == 'skill'
                               else (kind, ability))
    ctx = rolls.d20_context(effects_map(character), rule_kind, rule_ability,
                            shell_defense=character.shell_defense_active)
    if ctx['blocked']:
        raise SpellCastError(ctx['blocked'])
    if inspiration and not ctx['auto_fail']:
        _spend_inspiration(character, ctx)
    mode = rolls.roll_mode(ctx)
    sign = '+' if modifier >= 0 else '-'

    if ctx['auto_fail']:
        dice, total, natural, bonus_total = [], 0, None, 0
        detail = ctx['auto_fail']
        success = False if dc is not None else None
    else:
        dice = [_roll_die(20) for _ in range(1 if mode == 'normal' else 2)]
        natural = (max if mode == 'advantage' else min)(dice)
        bonus = [(_roll_die(int(d[2:])), source) for d, source in ctx['bonus']]
        bonus_total = sum(value for value, _ in bonus)
        total = natural + modifier + bonus_total
        if mode == 'normal':
            detail = f'd20 ({natural})'
        else:
            word = 'vantagem' if mode == 'advantage' else 'desvantagem'
            reasons = ', '.join(ctx[mode])
            detail = f'2d20 com {word} de {reasons} ({dice[0]}, {dice[1]})'
        detail += f' {sign} {abs(modifier)}'
        detail += ''.join(f' + 1d4 {source} ({value})' for value, source in bonus)
        if dc is not None:
            detail += f' vs CD {dc}'
        success = total >= dc if dc is not None else None

    DiceRoll.objects.create(character=character, dice=label[:50], result=total, detail=detail[:120])
    log(character, f'{label}: {total} [{detail}].' if not ctx['auto_fail'] else f'{label}: {detail}')
    return {
        'label': label, 'total': total, 'detail': detail, 'mode': mode,
        'rolls': dice, 'natural': natural, 'modifier': modifier,
        'bonus_total': bonus_total, 'auto_fail': bool(ctx['auto_fail']),
        'success': success, 'warnings': ctx['warnings'],
        'inspiration': INSPIRATION in ctx['advantage'],
        'critical': natural == 20 if kind == 'attack' else False,
        'fumble': natural == 1 if kind == 'attack' else False,
    }


# ======================================================================
# Vida
# ======================================================================
def _fall_unconscious(character):
    """0 PV: fica Inconsciente (perde a concentração) e zera os testes contra a morte."""
    character.death_successes = 0
    character.death_failures = 0
    character.active_effects.update_or_create(key='unconscious', defaults={
        'name': CONDITIONS['unconscious'][0], 'rounds_remaining': None,
    })


def _wake_up(character):
    """Recuperou PV: zera os testes contra a morte e sai da inconsciência."""
    character.death_successes = 0
    character.death_failures = 0
    character.active_effects.filter(key='unconscious').delete()


def take_damage(character, amount, critical=False, inspiration=False):
    """Aplica dano: gasta primeiro os PV temporários e não deixa os PV abaixo de 0.

    Ao chegar a 0 PV fica Inconsciente; se o dano que sobrar for igual ou
    maior que o PV máximo, é morte instantânea. Já com 0 PV, cada dano
    conta 1 falha contra a morte (2 se for crítico).
    Se o personagem estiver concentrando, faz a salvaguarda de
    concentração e retorna o resultado dela (ou None se não houve teste).
    """
    amount = max(0, int(amount))
    absorbed = min(character.temp_hp, amount)
    character.temp_hp -= absorbed
    remaining = amount - absorbed
    was_down = character.current_hp == 0
    overflow = max(0, remaining - character.current_hp)
    character.current_hp = max(0, character.current_hp - remaining)

    notes = []
    if absorbed:
        notes.append(f'{absorbed} absorvido(s) pelos PV temporários')
    if remaining and was_down and not character.is_dead:
        if remaining >= character.max_hp:
            character.death_failures = 3
            notes.append('dano massivo: morte instantânea')
        else:
            character.death_failures = min(3, character.death_failures + (2 if critical else 1))
            character.death_successes = 0 if character.death_failures >= 3 else character.death_successes
            notes.append(f'falha contra a morte ({character.death_failures}/3)')
    elif remaining and character.current_hp == 0 and not was_down:
        if overflow >= character.max_hp:
            character.death_failures = 3
            notes.append('dano massivo: morte instantânea')
        else:
            _fall_unconscious(character)
            notes.append('caiu inconsciente')
    character.save()
    extra = f' ({"; ".join(notes)})' if notes else ''
    temp = f' + {character.temp_hp} temp.' if character.temp_hp else ''
    log(character, f'Recebeu {amount} de dano{extra}. PV: {character.current_hp}/{character.max_hp}{temp}.')
    if character.is_dead:
        log(character, f'{character.name} morreu.')

    if not (character.concentration_spell and amount):
        return None
    if character.current_hp == 0:
        spell = character.concentration_spell
        end_concentration(character)
        return {'spell': spell, 'unconscious': True, 'success': False}
    return concentration_save(character, amount, inspiration=inspiration)


def heal(character, amount):
    """Cura PV, sem ultrapassar o máximo. Com 0 PV, acorda e zera os testes."""
    amount = max(0, int(amount))
    if character.is_dead and amount:
        raise SpellCastError(f'{character.name} está morto: cura não funciona. Use "Reviver".')
    was_down = character.current_hp == 0
    character.current_hp = min(character.max_hp, character.current_hp + amount)
    if was_down and character.current_hp > 0:
        _wake_up(character)
    character.save()
    woke = ' Recuperou a consciência.' if was_down and character.current_hp > 0 else ''
    log(character, f'Curou {amount} PV. PV: {character.current_hp}/{character.max_hp}.{woke}')
    return character


# ======================================================================
# PV temporários, Dados de Vida e testes contra a morte
# ======================================================================
def set_temp_hp(character, amount):
    """PV temporários não se somam: fica o maior valor. 0 remove os atuais."""
    amount = max(0, int(amount))
    if amount == 0:
        character.temp_hp = 0
        log(character, 'PV temporários removidos.')
    elif amount > character.temp_hp:
        character.temp_hp = amount
        log(character, f'Recebeu {amount} PV temporários.')
    else:
        raise ValueError(f'Já tem {character.temp_hp} PV temporários; eles não se somam (fica o maior).')
    character.save(update_fields=['temp_hp', 'updated_at'])
    return character


def spend_hit_die(character):
    """Gasta um Dado de Vida (descanso curto): cura 1dX + mod. de Constituição."""
    if character.is_dead:
        raise SpellCastError(f'{character.name} está morto.')
    if character.hit_dice_current < 1:
        raise SpellCastError('Sem Dados de Vida disponíveis. Eles voltam no descanso longo.')
    faces = character.hit_die
    con = character.ability_modifier(character.constitution)
    die = _roll_die(faces)
    total = max(0, die + con)
    character.hit_dice_current -= 1
    character.save(update_fields=['hit_dice_current', 'updated_at'])
    detail = f'd{faces} ({die}) {"+" if con >= 0 else "-"} {abs(con)}'
    DiceRoll.objects.create(character=character, dice=f'Dado de Vida 1d{faces}', result=total, detail=detail)
    log(character, f'Gastou 1 Dado de Vida: {total} [{detail}]. '
                   f'Restam {character.hit_dice_current}/{character.hit_dice_max}.')
    heal(character, total)
    return {'label': 'Dado de Vida', 'total': total, 'detail': detail}


def roll_death_save(character, inspiration=False):
    """Teste contra a morte (0 PV): 10+ sucesso; 20 natural volta com 1 PV;
    1 natural conta 2 falhas. Condições como Abençoado e Exausto 3 se aplicam."""
    if character.current_hp > 0:
        raise SpellCastError('Testes contra a morte só com 0 PV.')
    if character.is_dead:
        raise SpellCastError(f'{character.name} está morto.')
    if character.is_stable:
        raise SpellCastError('Já está estável: não precisa mais rolar.')

    ctx = rolls.d20_context(effects_map(character), 'save')
    if inspiration:
        _spend_inspiration(character, ctx)
    mode = rolls.roll_mode(ctx)
    dice = [_roll_die(20) for _ in range(1 if mode == 'normal' else 2)]
    natural = (max if mode == 'advantage' else min)(dice)
    bonus = [(_roll_die(int(d[2:])), source) for d, source in ctx['bonus']]
    total = natural + sum(v for v, _ in bonus)
    detail = f'd20 ({natural})' if mode == 'normal' else (
        f'2d20 com {"vantagem" if mode == "advantage" else "desvantagem"} ({dice[0]}, {dice[1]})')
    detail += ''.join(f' + 1d4 {source} ({value})' for value, source in bonus)

    if natural == 20:
        character.current_hp = 1
        _wake_up(character)
        outcome = '20 natural: recupera 1 PV e acorda!'
    elif natural == 1:
        character.death_failures = min(3, character.death_failures + 2)
        outcome = f'1 natural: 2 falhas ({character.death_failures}/3).'
    elif total >= 10:
        character.death_successes = min(3, character.death_successes + 1)
        outcome = f'Sucesso ({character.death_successes}/3).'
    else:
        character.death_failures = min(3, character.death_failures + 1)
        outcome = f'Falha ({character.death_failures}/3).'
    if character.is_dead:
        outcome += f' {character.name} morreu.'
    elif character.is_stable:
        outcome += ' Estável (inconsciente, mas fora de perigo).'
    character.save()
    DiceRoll.objects.create(character=character, dice='Teste contra a morte', result=total, detail=detail[:120])
    log(character, f'Teste contra a morte: {total} [{detail}]. {outcome}')
    return {'label': 'Teste contra a morte', 'total': total, 'detail': detail + ' · ' + outcome,
            'mode': mode, 'natural': natural}


def set_death_saves(character, successes, failures):
    """Ajuste manual dos testes contra a morte (ex.: Poupar os Moribundos estabiliza)."""
    if character.current_hp > 0:
        raise SpellCastError('Testes contra a morte só com 0 PV.')
    successes, failures = int(successes), int(failures)
    if not (0 <= successes <= 3 and 0 <= failures <= 3):
        raise ValueError('Sucessos e falhas vão de 0 a 3.')
    character.death_successes = successes
    character.death_failures = failures
    character.save(update_fields=['death_successes', 'death_failures', 'updated_at'])
    log(character, f'Testes contra a morte ajustados: {successes} sucesso(s), {failures} falha(s).')
    return character


def revive(character):
    """Trazido de volta (ex.: Reviver): volta com 1 PV, testes zerados."""
    if not character.is_dead:
        raise SpellCastError(f'{character.name} não está morto.')
    character.current_hp = 1
    _wake_up(character)
    character.save()
    log(character, f'{character.name} foi trazido de volta à vida com 1 PV.')
    return character


# ======================================================================
# Concentração
# ======================================================================
@transaction.atomic
def set_concentration(character, spell_name):
    """Inicia concentração em uma magia, encerrando a anterior."""
    if character.active_effects.filter(key__in=INCAPACITATING).exists():
        raise SpellCastError('Uma condição incapacitante impede a concentração.')
    previous = character.concentration_spell
    character.active_effects.update_or_create(key='concentration', defaults={
        'name': 'Concentração: ' + spell_name, 'rounds_remaining': spell_rounds(spell_name),
    })
    character.concentration_spell = spell_name
    character.save(update_fields=['concentration_spell', 'updated_at'])
    if previous and previous != spell_name:
        log(character, f'Concentração em "{previous}" foi encerrada por "{spell_name}".')
    log(character, f'Concentrando em "{spell_name}".')
    return character


def concentration_save(character, damage, inspiration=False):
    """Salvaguarda de Constituição para manter a concentração após dano.

    CD = 10 ou metade do dano (arredondada para baixo), o que for maior.
    A Defesa de Concha dá vantagem em salvaguardas de Constituição.
    Em caso de falha, a concentração é encerrada.
    """
    spell = character.concentration_spell
    dc = max(10, damage // 2)
    roll = roll_d20(character, 'save', 'con', label='Salv. CON (concentração)', dc=dc,
                    inspiration=inspiration)
    outcome = 'mantida' if roll['success'] else 'perdida'
    log(character, f'Concentração em "{spell}" {outcome}.')
    if not roll['success']:
        end_concentration(character)

    return {
        'spell': spell, 'dc': dc, 'rolls': roll['rolls'], 'modifier': roll['modifier'],
        'total': roll['total'], 'advantage': roll['mode'] == 'advantage',
        'success': roll['success'], 'detail': roll['detail'], 'unconscious': False,
        'warnings': roll['warnings'],
    }


@transaction.atomic
def end_concentration(character):
    """Encerra a concentração ativa, se houver."""
    character.active_effects.filter(key='concentration').delete()
    if character.concentration_spell:
        previous = character.concentration_spell
        character.concentration_spell = None
        character.save(update_fields=['concentration_spell', 'updated_at'])
        log(character, f'Concentração em "{previous}" encerrada.')
    return character


# ======================================================================
# Conjuração de magias
# ======================================================================
class SpellCastError(Exception):
    """Erro de regra ao tentar conjurar uma magia (ex.: sem espaço)."""


@transaction.atomic
def cast_spell(character, spell):
    """Conjura uma magia seguindo as regras de slot e concentração.

    Retorna um dicionário com informações do resultado (para a resposta AJAX).
    Levanta SpellCastError se não houver espaço de magia disponível.
    """
    result = {'spell': spell.name, 'level': spell.spell_level, 'slot_used': False}

    if spell.is_cantrip:
        # Truques não consomem espaços.
        log(character, f'Conjurou o truque "{spell.name}".')
    else:
        slot = character.spell_slots.filter(level=spell.spell_level).first()
        if slot is None or slot.current <= 0:
            raise SpellCastError(
                f'Sem espaços de {spell.spell_level}º círculo disponíveis.'
            )
        slot.current -= 1
        slot.save(update_fields=['current'])
        result['slot_used'] = True
        result['slot_remaining'] = slot.current
        log(
            character,
            f'Conjurou "{spell.name}" ({spell.spell_level}º círculo). '
            f'Espaços restantes: {slot.current}/{slot.maximum}.',
        )

    # Concentração
    if spell.requires_concentration:
        set_concentration(character, spell.name)
        result['concentration'] = spell.name

    return result


# ======================================================================
# Recursos de classe / raça
# ======================================================================
def use_channel_divinity(character, reason='Canalizar Divindade'):
    """Consome 1 uso de Canalizar Divindade."""
    if character.channel_divinity_current <= 0:
        raise SpellCastError('Sem usos de Canalizar Divindade disponíveis.')
    character.channel_divinity_current -= 1
    character.save(update_fields=['channel_divinity_current', 'updated_at'])
    log(
        character,
        f'Usou {reason}. Restam '
        f'{character.channel_divinity_current}/{character.channel_divinity_max}.',
    )
    return character


def turn_undead(character):
    """Expulsar Mortos-Vivos: consome Canalizar Divindade."""
    return use_channel_divinity(character, reason='Expulsar Mortos-Vivos')


def balm_of_peace(character):
    """Bálsamo da Paz: consome Canalizar Divindade e cura 2d6+5 por criatura.

    Retorna (character, total_curado, detalhe).
    """
    use_channel_divinity(character, reason='Bálsamo da Paz')
    total, detail = roll_formula(character, '2d6+5', label='Bálsamo da Paz (cura por criatura)')
    return character, total, detail


@transaction.atomic
def use_emboldening_bond(character):
    """Consome 1 carga de Vínculo Encorajador."""
    if character.emboldening_bond_current <= 0:
        raise SpellCastError('Sem cargas de Vínculo Encorajador disponíveis.')
    character.active_effects.update_or_create(key='bond', defaults={
        'name': CONDITIONS['bond'][0], 'rounds_remaining': 100,
    })
    character.emboldening_bond_current -= 1
    character.save(update_fields=['emboldening_bond_current', 'updated_at'])
    log(
        character,
        f'Usou Vínculo Encorajador. Restam '
        f'{character.emboldening_bond_current}/{character.emboldening_bond_max}.',
    )
    return character


def toggle_shell_defense(character):
    """Liga/desliga a Defesa de Concha (recalcula a CA)."""
    character.shell_defense_active = not character.shell_defense_active
    character.save(update_fields=['shell_defense_active', 'updated_at'])
    estado = 'ativada' if character.shell_defense_active else 'desativada'
    log(character, f'Defesa de Concha {estado}. CA efetiva: {character.effective_ac}.')
    return character


# ======================================================================
# Descansos
# ======================================================================
@transaction.atomic
def short_rest(character):
    """Descanso curto: recupera Canalizar Divindade. Não recupera espaços."""
    clear_effects(character)
    character.channel_divinity_current = character.channel_divinity_max
    character.save(update_fields=['channel_divinity_current', 'updated_at'])
    log(character, 'Descanso curto: Canalizar Divindade recuperado.')
    return character


@transaction.atomic
def long_rest(character):
    """Descanso longo: restaura PV, recursos, espaços e zera concentração."""
    clear_effects(character)
    character.current_hp = character.max_hp
    character.temp_hp = 0
    character.death_successes = 0
    character.death_failures = 0
    recovered = min(character.hit_dice_max - character.hit_dice_current,
                    max(1, character.hit_dice_max // 2))
    character.hit_dice_current += recovered
    character.channel_divinity_current = character.channel_divinity_max
    character.emboldening_bond_current = character.emboldening_bond_max
    character.concentration_spell = None
    character.shell_defense_active = False
    character.save()

    for slot in character.spell_slots.all():
        slot.current = slot.maximum
        slot.save(update_fields=['current'])

    log(character, 'Descanso longo concluído: PV, recursos e espaços de magia restaurados; '
                   f'{recovered} Dado(s) de Vida recuperado(s) '
                   f'({character.hit_dice_current}/{character.hit_dice_max}).')
    return character


# ======================================================================
# Serialização para AJAX
# ======================================================================
def serialize_effects(character):
    return [dict(id=e.id, key=e.key, name=e.name, rounds=e.rounds_remaining,
                 level=e.exhaustion_level, description=CONDITIONS.get(e.key, ('', ''))[1])
            for e in character.active_effects.all()]


def clear_effects(character):
    end_concentration(character)
    character.active_effects.all().delete()


@transaction.atomic
def change_effect(character, key, *, toggle=False, rounds=None, level=1):
    character = Character.objects.select_for_update().get(pk=character.pk)
    if key not in CONDITIONS and key != 'concentration':
        raise ValueError('Condição desconhecida.')
    effect = character.active_effects.filter(key=key).first()
    if toggle and effect:
        if key == 'concentration':
            end_concentration(character)
        else:
            effect.delete()
        return
    if key == 'concentration' and not effect:
        raise ValueError('Sem concentração ativa.')
    if rounds is not None:
        try:
            rounds = int(rounds)
        except (TypeError, ValueError):
            raise ValueError('Informe rodadas inteiras ou deixe vazio para duração indefinida.')
        if not 1 <= rounds <= 100000:
            raise ValueError('Use de 1 a 100000 rodadas.')
    try:
        level = int(level)
    except (TypeError, ValueError):
        raise ValueError('Nível de exaustão inválido.')
    if not 1 <= level <= 6:
        raise ValueError('Exaustão deve estar entre 1 e 6.')
    character.active_effects.update_or_create(key=key, defaults={
        'name': effect.name if effect else CONDITIONS[key][0],
        'rounds_remaining': DEFAULT_ROUNDS.get(key) if toggle else rounds,
        'exhaustion_level': level,
    })
    if key in INCAPACITATING:
        end_concentration(character)
    log(character, f'Efeito atualizado: {key}.')


@transaction.atomic
def advance_round(character):
    character = Character.objects.select_for_update().get(pk=character.pk)
    notices = []
    for effect in character.active_effects.all():
        if effect.rounds_remaining is None:
            continue
        effect.rounds_remaining -= 1
        if effect.rounds_remaining <= 0:
            notices.append(f'{effect.name}: terminou.')
            if effect.key == 'concentration':
                end_concentration(character)
            else:
                effect.delete()
        else:
            effect.save(update_fields=['rounds_remaining'])
            if effect.rounds_remaining <= 2:
                notices.append(f'{effect.name}: restam {effect.rounds_remaining} rodada(s)!')
    log(character, 'Rodada avançada.' + (' ' + ' '.join(notices) if notices else ''))
    return {'effect_notices': notices}


def serialize_state(character):
    """Snapshot completo da ficha em formato JSON-serializável.

    Consumido pelo front-end para atualizar o dashboard em tempo real.
    """
    return {
        'name': character.name,
        'current_hp': character.current_hp,
        'max_hp': character.max_hp,
        'hp_percent': character.hp_percent,
        'temp_hp': character.temp_hp,
        'heroic_inspiration': character.heroic_inspiration,
        'skills': serialize_skills(character),
        'passive_perception': 10 + skill_bonus(character, 'perception'),
        'hit_die': character.hit_die,
        'hit_dice_current': character.hit_dice_current,
        'hit_dice_max': character.hit_dice_max,
        'hit_die_bonus': character.ability_modifier(character.constitution),
        'death_successes': character.death_successes,
        'death_failures': character.death_failures,
        'is_down': character.current_hp == 0,
        'is_dead': character.is_dead,
        'is_stable': character.is_stable,
        'armor_class': character.armor_class,
        'effective_ac': character.effective_ac,
        'shell_defense_active': character.shell_defense_active,
        'channel_divinity_current': character.channel_divinity_current,
        'channel_divinity_max': character.channel_divinity_max,
        'emboldening_bond_current': character.emboldening_bond_current,
        'emboldening_bond_max': character.emboldening_bond_max,
        'concentration_spell': character.concentration_spell,
        'effects': serialize_effects(character),
        'undo_label': undo_label(character),
        'roll_effects': rolls.roll_summary(
            effects_map(character), shell_defense=character.shell_defense_active),
        'spell_slots': [
            {'level': s.level, 'current': s.current, 'maximum': s.maximum}
            for s in character.spell_slots.all()
        ],
        'logs': [
            {'action': l.action, 'when': l.created_at.strftime('%d/%m %H:%M')}
            for l in character.logs.all()[:15]
        ],
        'dice_rolls': [
            {
                'dice': d.dice,
                'result': d.result,
                'detail': d.detail,
                'when': d.created_at.strftime('%H:%M'),
            }
            for d in character.dice_rolls.all()[:10]
        ],
    }


# ======================================================================
# Notas da sessão (blocos de notas e pastas)
# ======================================================================
def _get_folder(character, folder_id):
    """Pasta do personagem, ou None quando folder_id é vazio."""
    if not folder_id:
        return None
    try:
        return character.note_folders.get(id=folder_id)
    except NoteFolder.DoesNotExist:
        raise ValueError('Pasta não encontrada.')


def _get_note(character, note_id):
    try:
        return character.notes.get(id=note_id)
    except Note.DoesNotExist:
        raise ValueError('Bloco de notas não encontrado.')


def create_folder(character, name):
    return NoteFolder.objects.create(character=character, name=name)


def rename_folder(character, folder_id, name):
    folder = _get_folder(character, folder_id)
    folder.name = name
    folder.save(update_fields=['name'])
    return folder


def delete_folder(character, folder_id):
    """Apaga a pasta e todos os blocos de notas dentro dela."""
    _get_folder(character, folder_id).delete()


def create_note(character, title, folder_id=None):
    folder = _get_folder(character, folder_id)
    return Note.objects.create(character=character, folder=folder, title=title)


def update_note(character, note_id, *, title=None, content=None,
                folder_id=None, move=False):
    """Atualiza título, conteúdo e/ou pasta (move=True aplica folder_id)."""
    note = _get_note(character, note_id)
    if title is not None:
        note.title = title
    if content is not None:
        note.content = content
    if move:
        note.folder = _get_folder(character, folder_id)
    note.save()
    return note


def delete_note(character, note_id):
    _get_note(character, note_id).delete()


def serialize_notes(character):
    """Snapshot das pastas e blocos de notas (consumido via AJAX)."""
    return {
        'folders': [
            {'id': f.id, 'name': f.name}
            for f in character.note_folders.all()
        ],
        'notes': [
            {
                'id': n.id,
                'title': n.title,
                'content': n.content,
                'folder_id': n.folder_id,
                'updated': n.updated_at.strftime('%d/%m %H:%M'),
            }
            for n in character.notes.all()
        ],
    }


# ======================================================================
# Inventário (itens e moedas; sem controle de peso/carga)
# ======================================================================
COINS = [
    ('copper', 'PC', 'cobre'),
    ('silver', 'PP', 'prata'),
    ('electrum', 'PE', 'electro'),
    ('gold', 'PO', 'ouro'),
    ('platinum', 'PL', 'platina'),
]
ITEM_FIELDS = ('name', 'category', 'quantity', 'description', 'damage_formula', 'equipped')


def _get_item(character, item_id):
    try:
        return character.inventory.get(id=item_id)
    except InventoryItem.DoesNotExist:
        raise ValueError('Item não encontrado.')


def _check_formula(formula):
    if formula:
        parse_and_roll(formula)  # levanta ValueError se for inválida


def create_item(character, **fields):
    _check_formula(fields.get('damage_formula'))
    item = InventoryItem.objects.create(
        character=character, **{k: v for k, v in fields.items() if k in ITEM_FIELDS}
    )
    log(character, f'Inventário: adicionou {item.name} ×{item.quantity}.')
    return item


def update_item(character, item_id, **fields):
    """Atualiza só os campos informados."""
    item = _get_item(character, item_id)
    if 'damage_formula' in fields:
        _check_formula(fields['damage_formula'])
    for key, value in fields.items():
        if key in ITEM_FIELDS:
            setattr(item, key, value)
    item.save()
    return item


def change_item_quantity(character, item_id, delta):
    """Soma delta à quantidade (mínimo 0)."""
    item = _get_item(character, item_id)
    item.quantity = max(0, item.quantity + int(delta))
    item.save(update_fields=['quantity'])
    return item


def use_item(character, item_id):
    """Gasta uma unidade de um item (ex.: poção, pergaminho)."""
    item = _get_item(character, item_id)
    if item.quantity < 1:
        raise ValueError(f'{item.name}: não há mais unidades.')
    item.quantity -= 1
    item.save(update_fields=['quantity'])
    log(character, f'Usou {item.name}. Restam {item.quantity}.')
    return item


def delete_item(character, item_id):
    item = _get_item(character, item_id)
    log(character, f'Inventário: removeu {item.name}.')
    item.delete()


def set_coins(character, **amounts):
    """Define as quantidades de moedas informadas (nunca negativas)."""
    changed = []
    for field, short, _ in COINS:
        if field in amounts and amounts[field] is not None:
            value = int(amounts[field])
            if value < 0:
                raise ValueError('Moedas não podem ficar negativas.')
            if value != getattr(character, field):
                changed.append(f'{short} {getattr(character, field)} → {value}')
                setattr(character, field, value)
    if changed:
        character.save(update_fields=[f for f, _, _ in COINS] + ['updated_at'])
        log(character, 'Moedas: ' + ', '.join(changed) + '.')
    return character


def serialize_inventory(character):
    labels = dict(InventoryItem.CATEGORIES)
    return {
        'coins': [
            {'field': field, 'short': short, 'name': name, 'amount': getattr(character, field)}
            for field, short, name in COINS
        ],
        'items': [
            {
                'id': i.id, 'name': i.name, 'category': i.category,
                'category_label': labels.get(i.category, i.category),
                'quantity': i.quantity, 'description': i.description,
                'damage_formula': i.damage_formula, 'equipped': i.equipped,
            }
            for i in character.inventory.all()
        ],
        'categories': [{'key': k, 'label': v} for k, v in InventoryItem.CATEGORIES],
    }


# ======================================================================
# Personagens da campanha (NPCs)
# ======================================================================
def _get_npc(character, npc_id):
    try:
        return character.npcs.get(id=npc_id)
    except Npc.DoesNotExist:
        raise ValueError('Personagem não encontrado.')


def _check_affection(value):
    value = int(value)
    if not 0 <= value <= Npc.AFFECTION_MAX:
        raise ValueError(f'O afeto vai de 0 a {Npc.AFFECTION_MAX}.')
    return value


def create_npc(character, name):
    npc = Npc.objects.create(character=character, name=name)
    log(character, f'Personagem adicionado: {npc.name}.')
    return npc


def update_npc(character, npc_id, *, name=None, affection=None, notes=None):
    """Atualiza só os campos informados."""
    npc = _get_npc(character, npc_id)
    if name is not None:
        npc.name = name
    if affection is not None:
        affection = _check_affection(affection)
        if affection != npc.affection:
            log(character, f'Afeto com {npc.name}: {npc.affection} → {affection}.')
        npc.affection = affection
    if notes is not None:
        npc.notes = notes
    npc.save()
    return npc


def set_npc_photo(character, npc_id, upload):
    """Substitui a foto do personagem, removendo a anterior."""
    npc = _get_npc(character, npc_id)
    if npc.photo:
        npc.photo.delete(save=False)
    npc.photo = upload
    npc.save()
    return npc


def delete_npc(character, npc_id):
    npc = _get_npc(character, npc_id)
    if npc.photo:
        npc.photo.delete(save=False)
    log(character, f'Personagem removido: {npc.name}.')
    npc.delete()


def serialize_npcs(character):
    return [
        {
            'id': n.id, 'name': n.name, 'affection': n.affection, 'notes': n.notes,
            'photo': n.photo.url if n.photo else '',
            'updated': n.updated_at.strftime('%d/%m %H:%M'),
        }
        for n in character.npcs.all()
    ]


def undo_label(character):
    """Nome da ação que o botão "Desfazer" vai reverter (ou None)."""
    return undo.next_label(character)
