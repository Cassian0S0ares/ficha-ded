"""Rotas do app character."""

from django.urls import path

from . import views

urlpatterns = [
    path('api/effects/change/', views.effect_change, name='effect_change'),
    path('api/effects/round/', views.effect_round, name='effect_round'),
    path('', views.dashboard, name='dashboard'),

    # Estado / refresh
    path('api/state/', views.state, name='state'),

    # Foto do personagem
    path('api/avatar/', views.upload_avatar, name='upload_avatar'),

    # Vida
    path('api/damage/', views.take_damage, name='take_damage'),
    path('api/heal/', views.heal, name='heal'),
    path('api/temp-hp/', views.temp_hp, name='temp_hp'),
    path('api/hit-die/', views.hit_die, name='hit_die'),
    path('api/death-save/', views.death_save, name='death_save'),
    path('api/death-set/', views.death_set, name='death_set'),
    path('api/revive/', views.revive, name='revive'),

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
    path('api/roll-d20/', views.roll_d20, name='roll_d20'),

    # Descansos
    path('api/short-rest/', views.short_rest, name='short_rest'),
    path('api/long-rest/', views.long_rest, name='long_rest'),

    # Desfazer a última ação
    path('api/undo/', views.undo_last, name='undo_last'),

    # Inventário
    path('api/inventory/', views.inventory, name='inventory'),
    path('api/inventory/new/', views.create_item, name='create_item'),
    path('api/inventory/coins/', views.set_coins, name='set_coins'),
    path('api/inventory/<int:item_id>/', views.update_item, name='update_item'),
    path('api/inventory/<int:item_id>/quantity/', views.item_quantity, name='item_quantity'),
    path('api/inventory/<int:item_id>/use/', views.use_item, name='use_item'),
    path('api/inventory/<int:item_id>/delete/', views.delete_item, name='delete_item'),

    # Personagens da campanha (NPCs)
    path('api/npcs/', views.npcs, name='npcs'),
    path('api/npcs/new/', views.create_npc, name='create_npc'),
    path('api/npcs/<int:npc_id>/', views.update_npc, name='update_npc'),
    path('api/npcs/<int:npc_id>/photo/', views.npc_photo, name='npc_photo'),
    path('api/npcs/<int:npc_id>/delete/', views.delete_npc, name='delete_npc'),

    # Notas da sessão
    path('api/notes/', views.notes, name='notes'),
    path('api/notes/folders/new/', views.create_folder, name='create_folder'),
    path('api/notes/folders/<int:folder_id>/rename/', views.rename_folder, name='rename_folder'),
    path('api/notes/folders/<int:folder_id>/delete/', views.delete_folder, name='delete_folder'),
    path('api/notes/new/', views.create_note, name='create_note'),
    path('api/notes/<int:note_id>/', views.update_note, name='update_note'),
    path('api/notes/<int:note_id>/delete/', views.delete_note, name='delete_note'),
]
