"""Desfazer: guarda o estado da ficha antes de cada ação e o restaura.

`track(character, fn)` tira uma foto do estado (PV, recursos, espaços de
magia, concentração, condições, inventário e moedas), executa a ação e,
se algo mudou, salva a foto com o nome da ação (os registros de
histórico criados por ela). `undo_last` restaura a foto mais recente.

Rolagens puras não mudam o estado e, por isso, não geram ponto de desfazer.
Notas e personagens da campanha ficam de fora (já são salvos ao digitar).
"""

from django.db import transaction

from .models import ActivityLog, InventoryItem, UndoSnapshot

MAX_SNAPSHOTS = 20

CHARACTER_FIELDS = (
    'current_hp', 'max_hp', 'temp_hp', 'armor_class', 'concentration_spell', 'shell_defense_active',
    'hit_dice_current', 'death_successes', 'death_failures', 'skill_proficiencies',
    'heroic_inspiration',
    'channel_divinity_current', 'emboldening_bond_current',
    'copper', 'silver', 'electrum', 'gold', 'platinum',
)
EFFECT_FIELDS = ('key', 'name', 'rounds_remaining', 'exhaustion_level')
ITEM_FIELDS = ('id', 'name', 'category', 'quantity', 'description', 'damage_formula', 'equipped')


def capture(character):
    """Foto JSON do estado que pode ser desfeito."""
    character.refresh_from_db()
    return {
        'character': {f: getattr(character, f) for f in CHARACTER_FIELDS},
        'slots': {str(s.level): s.current for s in character.spell_slots.all()},
        'effects': [{f: getattr(e, f) for f in EFFECT_FIELDS}
                    for e in character.active_effects.order_by('id')],
        'items': [{f: getattr(i, f) for f in ITEM_FIELDS}
                  for i in character.inventory.order_by('id')],
    }


def _short(text):
    return text if len(text) <= 255 else text[:252] + '…'


def track(character, fn):
    """Executa fn(character) registrando um ponto de desfazer se o estado mudar."""
    with transaction.atomic():
        before = capture(character)
        last_log = character.logs.order_by('-id').values_list('id', flat=True).first() or 0
        result = fn(character)
        if capture(character) != before:
            new_logs = character.logs.filter(id__gt=last_log).order_by('id')
            label = ' · '.join(new_logs.values_list('action', flat=True)) or 'Última ação'
            UndoSnapshot.objects.create(character=character, data=before, label=_short(label))
            stale = character.undo_snapshots.values_list('id', flat=True)[MAX_SNAPSHOTS:]
            UndoSnapshot.objects.filter(id__in=list(stale)).delete()
        return result


def next_label(character):
    """Nome da ação que será desfeita, ou None."""
    return character.undo_snapshots.values_list('label', flat=True).first()


@transaction.atomic
def undo_last(character):
    """Restaura o estado anterior à última ação. Retorna o nome dela."""
    snapshot = character.undo_snapshots.select_for_update().first()
    if snapshot is None:
        raise ValueError('Nada para desfazer.')
    data = snapshot.data

    for field, value in data['character'].items():
        setattr(character, field, value)
    character.save()

    for slot in character.spell_slots.all():
        if str(slot.level) in data['slots']:
            slot.current = data['slots'][str(slot.level)]
            slot.save(update_fields=['current'])

    character.active_effects.all().delete()
    for effect in data['effects']:
        character.active_effects.create(**effect)

    keep = {item['id'] for item in data['items']}
    character.inventory.exclude(id__in=keep).delete()
    for item in data['items']:
        fields = {k: v for k, v in item.items() if k != 'id'}
        InventoryItem.objects.update_or_create(id=item['id'], character=character, defaults=fields)

    snapshot.delete()
    ActivityLog.objects.create(character=character, action=_short('Desfeito: ' + snapshot.label))
    return snapshot.label
