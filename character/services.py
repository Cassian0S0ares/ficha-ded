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

from .models import ActivityLog, Character, DiceRoll, Spell, SpellSlot
from .seed_data import SPELL_SLOTS, SPELLS


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


# ======================================================================
# Vida
# ======================================================================
def take_damage(character, amount):
    """Aplica dano, sem deixar os PV abaixo de 0."""
    amount = max(0, int(amount))
    character.current_hp = max(0, character.current_hp - amount)
    character.save(update_fields=['current_hp', 'updated_at'])
    log(character, f'Recebeu {amount} de dano. PV: {character.current_hp}/{character.max_hp}.')
    return character


def heal(character, amount):
    """Cura PV, sem ultrapassar o máximo."""
    amount = max(0, int(amount))
    character.current_hp = min(character.max_hp, character.current_hp + amount)
    character.save(update_fields=['current_hp', 'updated_at'])
    log(character, f'Curou {amount} PV. PV: {character.current_hp}/{character.max_hp}.')
    return character


# ======================================================================
# Concentração
# ======================================================================
def set_concentration(character, spell_name):
    """Inicia concentração em uma magia, encerrando a anterior."""
    previous = character.concentration_spell
    character.concentration_spell = spell_name
    character.save(update_fields=['concentration_spell', 'updated_at'])
    if previous and previous != spell_name:
        log(character, f'Concentração em "{previous}" foi encerrada por "{spell_name}".')
    log(character, f'Concentrando em "{spell_name}".')
    return character


def end_concentration(character):
    """Encerra a concentração ativa, se houver."""
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


def use_emboldening_bond(character):
    """Consome 1 carga de Vínculo Encorajador."""
    if character.emboldening_bond_current <= 0:
        raise SpellCastError('Sem cargas de Vínculo Encorajador disponíveis.')
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
    character.channel_divinity_current = character.channel_divinity_max
    character.save(update_fields=['channel_divinity_current', 'updated_at'])
    log(character, 'Descanso curto: Canalizar Divindade recuperado.')
    return character


@transaction.atomic
def long_rest(character):
    """Descanso longo: restaura PV, recursos, espaços e zera concentração."""
    character.current_hp = character.max_hp
    character.channel_divinity_current = character.channel_divinity_max
    character.emboldening_bond_current = character.emboldening_bond_max
    character.concentration_spell = None
    character.shell_defense_active = False
    character.save()

    for slot in character.spell_slots.all():
        slot.current = slot.maximum
        slot.save(update_fields=['current'])

    log(character, 'Descanso longo concluído: PV, recursos e espaços de magia restaurados.')
    return character


# ======================================================================
# Serialização para AJAX
# ======================================================================
def serialize_state(character):
    """Snapshot completo da ficha em formato JSON-serializável.

    Consumido pelo front-end para atualizar o dashboard em tempo real.
    """
    return {
        'name': character.name,
        'current_hp': character.current_hp,
        'max_hp': character.max_hp,
        'hp_percent': character.hp_percent,
        'armor_class': character.armor_class,
        'effective_ac': character.effective_ac,
        'shell_defense_active': character.shell_defense_active,
        'channel_divinity_current': character.channel_divinity_current,
        'channel_divinity_max': character.channel_divinity_max,
        'emboldening_bond_current': character.emboldening_bond_current,
        'emboldening_bond_max': character.emboldening_bond_max,
        'concentration_spell': character.concentration_spell,
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
