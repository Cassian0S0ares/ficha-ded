"""
Formulários do app character.

Usados para validar os pequenos payloads das ações AJAX (quantidade de
dano/cura, dado escolhido e fórmulas de rolagem).
"""

from django import forms


class AmountForm(forms.Form):
    """Valida uma quantidade inteira positiva (dano ou cura)."""

    amount = forms.IntegerField(min_value=0, max_value=10000)


class DiceForm(forms.Form):
    """Valida a escolha de um dado padrão."""

    dice = forms.ChoiceField(
        choices=[(d, d) for d in ('d4', 'd6', 'd8', 'd10', 'd12', 'd20')]
    )


class FormulaForm(forms.Form):
    """Valida uma fórmula de rolagem (ex.: 3d8+5) e um rótulo opcional."""

    formula = forms.CharField(max_length=50)
    label = forms.CharField(max_length=120, required=False)


class AvatarForm(forms.Form):
    """Valida a foto enviada para o personagem."""

    ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
    MAX_SIZE = 5 * 1024 * 1024  # 5 MB

    avatar = forms.FileField()

    def clean_avatar(self):
        f = self.cleaned_data['avatar']
        name = (f.name or '').lower()
        if not name.endswith(self.ALLOWED_EXTENSIONS):
            raise forms.ValidationError(
                'Formato inválido. Use JPG, PNG, GIF ou WEBP.'
            )
        if f.size > self.MAX_SIZE:
            raise forms.ValidationError('A imagem deve ter no máximo 5 MB.')
        return f


class NameForm(forms.Form):
    """Valida o nome de uma pasta ou o título de um bloco de notas."""

    name = forms.CharField(max_length=120)
    folder = forms.IntegerField(required=False)


class NoteForm(forms.Form):
    """Valida a edição de um bloco de notas (campos ausentes não mudam)."""

    title = forms.CharField(max_length=120, required=False)
    content = forms.CharField(required=False, strip=False, max_length=200000)
    folder = forms.IntegerField(required=False)


class D20Form(forms.Form):
    """Valida uma jogada de d20 (ataque, teste de atributo ou salvaguarda)."""

    kind = forms.ChoiceField(choices=[(k, k) for k in ('attack', 'check', 'save')])
    ability = forms.ChoiceField(choices=[
        (k, k) for k in ('str', 'dex', 'con', 'int', 'wis', 'cha', 'spell', 'claws')
    ])


class ItemForm(forms.Form):
    """Valida um item do inventário (na edição, campos ausentes não mudam)."""

    CATEGORIES = ('weapon', 'armor', 'gear', 'consumable', 'treasure', 'other')

    name = forms.CharField(max_length=120)
    category = forms.ChoiceField(choices=[(c, c) for c in CATEGORIES])
    quantity = forms.IntegerField(min_value=0, max_value=1000000)
    description = forms.CharField(required=False, max_length=5000)
    damage_formula = forms.CharField(required=False, max_length=50)
    equipped = forms.BooleanField(required=False)


class CoinsForm(forms.Form):
    """Valida as moedas (campos ausentes não mudam)."""

    copper = forms.IntegerField(min_value=0, max_value=10000000, required=False)
    silver = forms.IntegerField(min_value=0, max_value=10000000, required=False)
    electrum = forms.IntegerField(min_value=0, max_value=10000000, required=False)
    gold = forms.IntegerField(min_value=0, max_value=10000000, required=False)
    platinum = forms.IntegerField(min_value=0, max_value=10000000, required=False)


class NpcForm(forms.Form):
    """Valida a edição de um personagem (campos ausentes não mudam)."""

    name = forms.CharField(max_length=120, required=False)
    affection = forms.IntegerField(min_value=0, max_value=3, required=False)
    notes = forms.CharField(required=False, strip=False, max_length=200000)
