"""Rotas do app character."""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Estado / refresh
    path('api/state/', views.state, name='state'),

    # Foto do personagem
    path('api/avatar/', views.upload_avatar, name='upload_avatar'),

    # Vida
    path('api/damage/', views.take_damage, name='take_damage'),
    path('api/heal/', views.heal, name='heal'),

    # Conjuração
    path('api/cast/<int:spell_id>/', views.cast_spell, name='cast_spell'),
    path('api/concentration/end/', views.end_concentration, name='end_concentration'),

    # Recursos de classe / raça / domínio
    path('api/channel-divinity/', views.use_channel_divinity, name='use_channel_divinity'),
    path('api/turn-undead/', views.turn_undead, name='turn_undead'),
    path('api/balm-of-peace/', views.balm_of_peace, name='balm_of_peace'),
    path('api/emboldening-bond/', views.use_emboldening_bond, name='use_emboldening_bond'),
    path('api/shell-defense/', views.toggle_shell_defense, name='toggle_shell_defense'),

    # Rolagens
    path('api/roll-dice/', views.roll_dice, name='roll_dice'),
    path('api/roll-formula/', views.roll_formula, name='roll_formula'),

    # Descansos
    path('api/short-rest/', views.short_rest, name='short_rest'),
    path('api/long-rest/', views.long_rest, name='long_rest'),
]
