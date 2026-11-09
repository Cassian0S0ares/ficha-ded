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
