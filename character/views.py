"""
Views do app character.

A aplicação roda SEM login: existe uma única ficha padrão (Botticellius),
obtida via `services.get_sheet()`. O dashboard renderiza o HTML e os demais
endpoints (POST) respondem JSON para atualização em tempo real (AJAX).

As regras de negócio ficam em `character.services`; as views apenas
orquestram requisição/resposta.
"""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from . import rolls, services, undo
from .forms import (
    AmountForm, AvatarForm, CoinsForm, D20Form, DiceForm, FormulaForm, ItemForm, NameForm, NoteForm, NpcForm,
)
from .models import Spell


# ======================================================================
# Dashboard
# ======================================================================
def dashboard(request):
    """Página principal da ficha (sem login)."""
    character = services.get_sheet()

    spells = list(character.spells.all())

    def mod(score):
        m = character.ability_modifier(score)
        return f'+{m}' if m >= 0 else str(m)

    skills = services.serialize_skills(character)
    for skill in skills:
        skill['bonus_text'] = f'+{skill["bonus"]}' if skill['bonus'] >= 0 else str(skill['bonus'])
    abilities = [
        (key, label, getattr(character, field), mod(getattr(character, field)),
         [s for s in skills if s['ability'] == key])
        for key, (field, _, label) in rolls.ABILITIES.items()
    ]

    context = {
        'character': character,
        'class_label': {'Cleric': 'Clérigo'}.get(character.class_name, character.class_name),
        'subclass_label': {'Peace Domain': 'Domínio da Paz'}.get(character.subclass, character.subclass),
        'abilities': abilities,
        'con_mod': character.ability_modifier(character.constitution),
        'inventory': services.serialize_inventory(character),
        'claws_bonus': character.ability_modifier(character.strength) + character.proficiency_bonus,
        'spell_slots': character.spell_slots.all(),
        'cantrips': [s for s in spells if s.spell_level == 0],
        'domain_spells': [s for s in spells if s.is_domain_spell and s.spell_level > 0],
        'prepared_spells': [
            s for s in spells if not s.is_domain_spell and s.spell_level > 0
        ],
        'logs': character.logs.all()[:15],
        'dice_rolls': character.dice_rolls.all()[:10],
        'state': services.serialize_state(character),
        'conditions': services.CONDITIONS.items(),
    }
    return render(request, 'character/dashboard.html', context)


# ======================================================================
# Foto do personagem
# ======================================================================
@require_POST
def upload_avatar(request):
    """Recebe e salva a foto do personagem; responde com a URL da imagem."""
    form = AvatarForm(request.POST, request.FILES)
    if not form.is_valid():
        error = next(iter(form.errors.values()))[0]
        return JsonResponse({'ok': False, 'error': error}, status=400)

    character = services.get_sheet()
    services.set_avatar(character, form.cleaned_data['avatar'])
    return JsonResponse({'ok': True, 'avatar_url': character.avatar.url})


# ======================================================================
# Helper genérico de ação AJAX
# ======================================================================
def _wants_inspiration(request):
    """O jogador escolheu gastar a inspiração heroica nesta jogada?"""
    return request.POST.get('inspiration') in ('1', 'true', 'on')


def _json_action(request, fn, *, extra=None):
    """Executa uma ação de serviço e retorna o estado atualizado em JSON.

    `fn(character)` deve aplicar a regra de negócio. Pode retornar um dict
    (mesclado na resposta) ou None. `extra` é um dict opcional adicional.
    """
    character = services.get_sheet()
    try:
        # Ações que mudam o estado ganham um ponto de "Desfazer".
        payload_extra = undo.track(character, fn) or {}
    except (services.SpellCastError, ValueError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    character.refresh_from_db()
    response = {'ok': True, 'state': services.serialize_state(character)}
    if isinstance(payload_extra, dict):
        response.update(payload_extra)
    if extra:
        response.update(extra)
    return JsonResponse(response)


# ======================================================================
# Vida
# ======================================================================
@require_POST
def take_damage(request):
    form = AmountForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Quantidade inválida.'}, status=400)
    amount = form.cleaned_data['amount']
    critical = request.POST.get('critical') in ('1', 'true', 'on')
    inspiration = _wants_inspiration(request)

    def action(c):
        save = services.take_damage(c, amount, critical=critical, inspiration=inspiration)
        return {'conc_save': save} if save else None

    return _json_action(request, action)


@require_POST
def heal(request):
    form = AmountForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Quantidade inválida.'}, status=400)
    amount = form.cleaned_data['amount']
    return _json_action(request, lambda c: services.heal(c, amount) and None)


# ======================================================================
# Conjuração
# ======================================================================
@require_POST
def cast_spell(request, spell_id):
    character = services.get_sheet()
    spell = get_object_or_404(Spell, id=spell_id, character=character)

    def action(c):
        return services.cast_spell(c, spell)

    return _json_action(request, action)


@require_POST
def end_concentration(request):
    return _json_action(request, lambda c: services.end_concentration(c) and None)


# ======================================================================
# Recursos de classe / raça
# ======================================================================
@require_POST
def use_channel_divinity(request):
    return _json_action(request, lambda c: services.use_channel_divinity(c) and None)


@require_POST
def turn_undead(request):
    return _json_action(request, lambda c: services.turn_undead(c) and None)


@require_POST
def balm_of_peace(request):
    def action(c):
        _, total, detail = services.balm_of_peace(c)
        return {'roll': {'formula': '2d6+5', 'total': total, 'detail': detail,
                         'label': 'Bálsamo da Paz'}}

    return _json_action(request, action)


@require_POST
def use_emboldening_bond(request):
    return _json_action(request, lambda c: services.use_emboldening_bond(c) and None)


@require_POST
def toggle_shell_defense(request):
    return _json_action(request, lambda c: services.toggle_shell_defense(c) and None)


# ======================================================================
# Rolagens
# ======================================================================
@require_POST
def roll_dice(request):
    form = DiceForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Dado inválido.'}, status=400)
    dice = form.cleaned_data['dice']

    def action(c):
        result = services.roll_dice(c, dice)
        return {'roll': {'formula': dice, 'total': result, 'detail': str(result),
                         'label': dice}}

    return _json_action(request, action)


@require_POST
def roll_formula(request):
    form = FormulaForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Fórmula inválida.'}, status=400)
    formula = form.cleaned_data['formula']
    label = form.cleaned_data.get('label', '')

    def action(c):
        total, detail = services.roll_formula(c, formula, label=label)
        return {'roll': {'formula': formula, 'total': total, 'detail': detail,
                         'label': label or formula}}

    return _json_action(request, action)


# ======================================================================
# Descansos
# ======================================================================
@require_POST
def short_rest(request):
    return _json_action(request, lambda c: services.short_rest(c) and None)


@require_POST
def long_rest(request):
    return _json_action(request, lambda c: services.long_rest(c) and None)


# ======================================================================
# Estado (refresh AJAX)
# ======================================================================
def state(request):
    """Retorna o snapshot atual da ficha (para polling/refresh)."""
    character = services.get_sheet()
    return JsonResponse({'ok': True, 'state': services.serialize_state(character)})


@require_POST
def effect_change(request):
    return _json_action(request, lambda c: services.change_effect(
        c, request.POST.get('key', ''), toggle=request.POST.get('toggle') == '1',
        rounds=request.POST.get('rounds') or None, level=request.POST.get('level', '1')))


@require_POST
def effect_round(request):
    return _json_action(request, services.advance_round)


# ======================================================================
# Notas da sessão
# ======================================================================
def _notes_action(request, fn):
    """Executa uma ação de notas e retorna pastas + blocos atualizados."""
    character = services.get_sheet()
    try:
        payload_extra = fn(character) or {}
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    response = {'ok': True, 'notes': services.serialize_notes(character)}
    response.update(payload_extra)
    return JsonResponse(response)


def _name_form(request):
    form = NameForm(request.POST)
    if not form.is_valid():
        raise ValueError('Informe um nome (até 120 caracteres).')
    return form.cleaned_data


def notes(request):
    """Lista pastas e blocos de notas."""
    return _notes_action(request, lambda c: None)


@require_POST
def create_folder(request):
    def action(c):
        data = _name_form(request)
        return {'folder_id': services.create_folder(c, data['name']).id}

    return _notes_action(request, action)


@require_POST
def rename_folder(request, folder_id):
    return _notes_action(request, lambda c: services.rename_folder(
        c, folder_id, _name_form(request)['name']) and None)


@require_POST
def delete_folder(request, folder_id):
    return _notes_action(request, lambda c: services.delete_folder(c, folder_id))


@require_POST
def create_note(request):
    def action(c):
        data = _name_form(request)
        note = services.create_note(c, data['name'], data['folder'])
        return {'note_id': note.id}

    return _notes_action(request, action)


@require_POST
def update_note(request, note_id):
    def action(c):
        form = NoteForm(request.POST)
        if not form.is_valid():
            raise ValueError('Dados do bloco de notas inválidos.')
        data = form.cleaned_data
        kwargs = {}
        if 'title' in request.POST:
            if not data['title']:
                raise ValueError('O título não pode ficar vazio.')
            kwargs['title'] = data['title']
        if 'content' in request.POST:
            kwargs['content'] = data['content']
        if 'folder' in request.POST:
            kwargs.update(folder_id=data['folder'], move=True)
        services.update_note(c, note_id, **kwargs)

    return _notes_action(request, action)


@require_POST
def delete_note(request, note_id):
    return _notes_action(request, lambda c: services.delete_note(c, note_id))


# ======================================================================
# Jogadas de d20 com condições (ataque, teste, salvaguarda)
# ======================================================================
@require_POST
def roll_d20(request):
    form = D20Form(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Jogada inválida.'}, status=400)
    kind, ability = form.cleaned_data['kind'], form.cleaned_data['ability']
    valid = {
        'attack': services.D20_ATTACKS, 'check': rolls.ABILITIES,
        'save': rolls.ABILITIES, 'skill': rolls.SKILLS,
    }[kind]
    if ability not in valid:
        return JsonResponse({'ok': False, 'error': 'Jogada inválida.'}, status=400)

    inspiration = _wants_inspiration(request)

    def action(c):
        return {'roll': services.roll_d20(c, kind, ability, inspiration=inspiration)}

    return _json_action(request, action)


# ======================================================================
# Inventário
# ======================================================================
def _inventory_action(request, fn):
    """Executa uma ação de inventário e retorna inventário + estado da ficha."""
    character = services.get_sheet()
    try:
        if request.method == 'POST':
            payload_extra = undo.track(character, fn) or {}
        else:
            payload_extra = fn(character) or {}
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    character.refresh_from_db()
    response = {
        'ok': True,
        'inventory': services.serialize_inventory(character),
        'state': services.serialize_state(character),
    }
    response.update(payload_extra)
    return JsonResponse(response)


def _item_fields(request, *, partial):
    """Campos válidos do item; em `partial`, só os enviados no POST."""
    form = ItemForm(request.POST)
    form.is_valid()
    sent = [f for f in form.fields if f in request.POST] if partial else list(form.fields)
    errors = [f for f in sent if f in form.errors]
    if errors:
        labels = {'name': 'nome', 'quantity': 'quantidade', 'category': 'categoria'}
        raise ValueError('Confira o campo ' + labels.get(errors[0], errors[0]) + '.')
    return {f: form.cleaned_data[f] for f in sent}


def inventory(request):
    return _inventory_action(request, lambda c: None)


@require_POST
def create_item(request):
    return _inventory_action(request, lambda c: {
        'item_id': services.create_item(c, **_item_fields(request, partial=False)).id})


@require_POST
def update_item(request, item_id):
    return _inventory_action(request, lambda c: services.update_item(
        c, item_id, **_item_fields(request, partial=True)) and None)


@require_POST
def item_quantity(request, item_id):
    try:
        delta = int(request.POST.get('delta', ''))
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Quantidade inválida.'}, status=400)
    return _inventory_action(request, lambda c: services.change_item_quantity(
        c, item_id, delta) and None)


@require_POST
def use_item(request, item_id):
    return _inventory_action(request, lambda c: services.use_item(c, item_id) and None)


@require_POST
def delete_item(request, item_id):
    return _inventory_action(request, lambda c: services.delete_item(c, item_id))


@require_POST
def set_coins(request):
    form = CoinsForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Valor de moedas inválido.'}, status=400)
    amounts = {k: v for k, v in form.cleaned_data.items() if k in request.POST}
    return _inventory_action(request, lambda c: services.set_coins(c, **amounts) and None)


# ======================================================================
# Personagens da campanha (NPCs)
# ======================================================================
def _npcs_action(request, fn):
    """Executa uma ação de personagens e retorna a lista atualizada."""
    character = services.get_sheet()
    try:
        payload_extra = fn(character) or {}
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    response = {'ok': True, 'npcs': services.serialize_npcs(character)}
    response.update(payload_extra)
    return JsonResponse(response)


def npcs(request):
    return _npcs_action(request, lambda c: None)


@require_POST
def create_npc(request):
    def action(c):
        return {'npc_id': services.create_npc(c, _name_form(request)['name']).id}

    return _npcs_action(request, action)


@require_POST
def update_npc(request, npc_id):
    def action(c):
        form = NpcForm(request.POST)
        if not form.is_valid():
            raise ValueError('Dados do personagem inválidos.')
        data = form.cleaned_data
        kwargs = {}
        if 'name' in request.POST:
            if not data['name']:
                raise ValueError('O nome não pode ficar vazio.')
            kwargs['name'] = data['name']
        if 'affection' in request.POST:
            if data['affection'] is None:
                raise ValueError('O afeto vai de 0 a 3.')
            kwargs['affection'] = data['affection']
        if 'notes' in request.POST:
            kwargs['notes'] = data['notes']
        services.update_npc(c, npc_id, **kwargs)

    return _npcs_action(request, action)


@require_POST
def npc_photo(request, npc_id):
    form = AvatarForm(request.POST, request.FILES)
    if not form.is_valid():
        error = next(iter(form.errors.values()))[0]
        return JsonResponse({'ok': False, 'error': error}, status=400)
    return _npcs_action(request, lambda c: services.set_npc_photo(
        c, npc_id, form.cleaned_data['avatar']) and None)


@require_POST
def delete_npc(request, npc_id):
    return _npcs_action(request, lambda c: services.delete_npc(c, npc_id))


# ======================================================================
# Desfazer
# ======================================================================
@require_POST
def undo_last(request):
    """Restaura o estado anterior à última ação que mudou a ficha."""
    character = services.get_sheet()
    try:
        label = undo.undo_last(character)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    character.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'undone': label,
        'state': services.serialize_state(character),
        'inventory': services.serialize_inventory(character),
    })


# ======================================================================
# PV temporários, Dados de Vida e testes contra a morte
# ======================================================================
@require_POST
def temp_hp(request):
    form = AmountForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Quantidade inválida.'}, status=400)
    amount = form.cleaned_data['amount']
    return _json_action(request, lambda c: services.set_temp_hp(c, amount) and None)


@require_POST
def hit_die(request):
    return _json_action(request, lambda c: {'roll': services.spend_hit_die(c)})


@require_POST
def death_save(request):
    inspiration = _wants_inspiration(request)
    return _json_action(request, lambda c: {
        'roll': services.roll_death_save(c, inspiration=inspiration)})


@require_POST
def death_set(request):
    try:
        successes = int(request.POST.get('successes', ''))
        failures = int(request.POST.get('failures', ''))
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Valores inválidos.'}, status=400)
    return _json_action(request, lambda c: services.set_death_saves(c, successes, failures) and None)


@require_POST
def revive(request):
    return _json_action(request, lambda c: services.revive(c) and None)


# ======================================================================
# Perícias
# ======================================================================
@require_POST
def skill_proficiency(request):
    skill = request.POST.get('skill', '')
    return _json_action(request, lambda c: services.toggle_skill_proficiency(c, skill) and None)


# ======================================================================
# Inspiração heroica
# ======================================================================
@require_POST
def inspiration(request):
    value = request.POST.get('value') in ('1', 'true', 'on')
    return _json_action(request, lambda c: services.set_inspiration(c, value) and None)
