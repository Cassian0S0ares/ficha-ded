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

from . import services
from .forms import AmountForm, AvatarForm, DiceForm, FormulaForm
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

    abilities = [
        ('Força', character.strength, mod(character.strength)),
        ('Destreza', character.dexterity, mod(character.dexterity)),
        ('Constituição', character.constitution, mod(character.constitution)),
        ('Inteligência', character.intelligence, mod(character.intelligence)),
        ('Sabedoria', character.wisdom, mod(character.wisdom)),
        ('Carisma', character.charisma, mod(character.charisma)),
    ]

    context = {
        'character': character,
        'abilities': abilities,
        'spell_slots': character.spell_slots.all(),
        'cantrips': [s for s in spells if s.spell_level == 0],
        'domain_spells': [s for s in spells if s.is_domain_spell and s.spell_level > 0],
        'prepared_spells': [
            s for s in spells if not s.is_domain_spell and s.spell_level > 0
        ],
        'logs': character.logs.all()[:15],
        'dice_rolls': character.dice_rolls.all()[:10],
        'state': services.serialize_state(character),
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
def _json_action(request, fn, *, extra=None):
    """Executa uma ação de serviço e retorna o estado atualizado em JSON.

    `fn(character)` deve aplicar a regra de negócio. Pode retornar um dict
    (mesclado na resposta) ou None. `extra` é um dict opcional adicional.
    """
    character = services.get_sheet()
    try:
        payload_extra = fn(character) or {}
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
    return _json_action(request, lambda c: services.take_damage(c, amount) and None)


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
