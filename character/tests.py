"""Testes da camada de serviços e das regras de negócio da ficha."""

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from . import services
from .models import Character, Spell
from .services import SpellCastError


class CharacterSetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('aventureiro', password='x')
        self.character = services.create_default_character(self.user)

    def test_seed_creates_full_sheet(self):
        self.assertEqual(self.character.name, 'Botticellius')
        self.assertEqual(self.character.spell_slots.count(), 4)
        self.assertEqual(self.character.spells.count(), 25)
        slot1 = self.character.spell_slots.get(level=1)
        self.assertEqual((slot1.current, slot1.maximum), (4, 4))

    def test_get_or_create_is_idempotent(self):
        again = services.get_or_create_character(self.user)
        self.assertEqual(again.pk, self.character.pk)
        self.assertEqual(Character.objects.filter(owner=self.user).count(), 1)

    def test_effective_ac_with_shell_defense(self):
        self.assertEqual(self.character.effective_ac, 19)
        services.toggle_shell_defense(self.character)
        self.assertEqual(self.character.effective_ac, 23)


class HealthTests(TestCase):
    def setUp(self):
        self.character = services.create_default_character(
            User.objects.create_user('u', password='x')
        )

    def test_damage_floors_at_zero(self):
        services.take_damage(self.character, 999)
        self.assertEqual(self.character.current_hp, 0)

    def test_heal_caps_at_max(self):
        services.take_damage(self.character, 20)
        services.heal(self.character, 999)
        self.assertEqual(self.character.current_hp, self.character.max_hp)


class SpellCastingTests(TestCase):
    def setUp(self):
        self.character = services.create_default_character(
            User.objects.create_user('u', password='x')
        )

    def test_cantrip_does_not_consume_slot(self):
        cantrip = Spell.objects.get(character=self.character, name='Luz')
        services.cast_spell(self.character, cantrip)
        self.assertEqual(self.character.spell_slots.get(level=1).current, 4)

    def test_casting_consumes_correct_slot(self):
        bless = Spell.objects.get(character=self.character, name='Abençoar')
        services.cast_spell(self.character, bless)
        self.assertEqual(self.character.spell_slots.get(level=1).current, 3)

    def test_casting_without_slot_raises(self):
        bless = Spell.objects.get(character=self.character, name='Abençoar')
        for _ in range(4):
            services.cast_spell(self.character, bless)
        with self.assertRaises(SpellCastError):
            services.cast_spell(self.character, bless)

    def test_concentration_replaces_previous(self):
        bless = Spell.objects.get(character=self.character, name='Abençoar')
        shield = Spell.objects.get(character=self.character, name='Escudo da Fé')
        services.cast_spell(self.character, bless)
        self.assertEqual(self.character.concentration_spell, 'Abençoar')
        services.cast_spell(self.character, shield)
        self.assertEqual(self.character.concentration_spell, 'Escudo da Fé')


class ResourcesAndRestTests(TestCase):
    def setUp(self):
        self.character = services.create_default_character(
            User.objects.create_user('u', password='x')
        )

    def test_channel_divinity_cannot_go_negative(self):
        services.use_channel_divinity(self.character)
        services.use_channel_divinity(self.character)
        with self.assertRaises(SpellCastError):
            services.use_channel_divinity(self.character)

    def test_short_rest_restores_channel_divinity_not_slots(self):
        bless = Spell.objects.get(character=self.character, name='Abençoar')
        services.cast_spell(self.character, bless)
        services.use_channel_divinity(self.character)
        services.short_rest(self.character)
        self.assertEqual(self.character.channel_divinity_current, 2)
        self.assertEqual(self.character.spell_slots.get(level=1).current, 3)

    def test_long_rest_restores_everything(self):
        bless = Spell.objects.get(character=self.character, name='Abençoar')
        services.cast_spell(self.character, bless)
        services.take_damage(self.character, 30)
        services.use_emboldening_bond(self.character)
        services.toggle_shell_defense(self.character)
        services.long_rest(self.character)
        self.assertEqual(self.character.current_hp, self.character.max_hp)
        self.assertEqual(self.character.channel_divinity_current, 2)
        self.assertEqual(self.character.emboldening_bond_current, 3)
        self.assertIsNone(self.character.concentration_spell)
        self.assertFalse(self.character.shell_defense_active)
        self.assertEqual(self.character.spell_slots.get(level=1).current, 4)


class DiceTests(TestCase):
    def setUp(self):
        self.character = services.create_default_character(
            User.objects.create_user('u', password='x')
        )

    def test_roll_formula_within_bounds(self):
        total, _ = services.parse_and_roll('2d6+5')
        self.assertTrue(7 <= total <= 17)

    def test_invalid_formula_raises(self):
        with self.assertRaises(ValueError):
            services.parse_and_roll('not-a-dice')

    def test_roll_dice_records_history(self):
        services.roll_dice(self.character, 'd20')
        self.assertEqual(self.character.dice_rolls.count(), 1)


class NotesTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def post(self, path, data=None):
        return self.client.post('/api/notes/' + path, data or {}).json()

    def test_create_rename_and_delete_folder_with_notes(self):
        folder_id = self.post('folders/new/', {'name': 'Campanha'})['folder_id']
        self.post('new/', {'name': 'Sessão 1', 'folder': folder_id})
        notes = self.post(f'folders/{folder_id}/rename/', {'name': 'Arco 1'})['notes']
        self.assertEqual(notes['folders'][0]['name'], 'Arco 1')
        self.assertEqual(notes['notes'][0]['folder_id'], folder_id)

        notes = self.post(f'folders/{folder_id}/delete/')['notes']
        self.assertEqual(notes, {'folders': [], 'notes': []})

    def test_edit_move_and_delete_note(self):
        folder_id = self.post('folders/new/', {'name': 'Pasta'})['folder_id']
        note_id = self.post('new/', {'name': 'Rascunho'})['note_id']

        self.post(f'{note_id}/', {'title': 'Sessão 2', 'content': 'Dragão!\n'})
        note = self.character.notes.get()
        self.assertEqual((note.title, note.content, note.folder), ('Sessão 2', 'Dragão!\n', None))

        self.post(f'{note_id}/', {'folder': folder_id})
        self.assertEqual(self.character.notes.get().folder_id, folder_id)
        self.post(f'{note_id}/', {'folder': ''})
        self.assertIsNone(self.character.notes.get().folder_id)

        self.post(f'{note_id}/delete/')
        self.assertFalse(self.character.notes.exists())

    def test_rejects_empty_title_and_unknown_ids(self):
        note_id = self.post('new/', {'name': 'Nota'})['note_id']
        self.assertFalse(self.post(f'{note_id}/', {'title': ''})['ok'])
        self.assertFalse(self.post('new/', {'name': ''})['ok'])
        self.assertFalse(self.post('new/', {'name': 'X', 'folder': 999})['ok'])
        self.assertFalse(self.post('999/delete/')['ok'])


class ConcentrationSaveTests(TestCase):
    def setUp(self):
        self.character = services.create_default_character(
            User.objects.create_user('u', password='x')
        )
        services.set_concentration(self.character, 'Abençoar')

    def damage(self, amount, rolls):
        with mock.patch.object(services, '_roll_die', side_effect=rolls):
            return services.take_damage(self.character, amount)

    def test_dc_is_10_or_half_damage(self):
        self.assertEqual(self.damage(12, [8])['dc'], 10)
        self.assertEqual(self.damage(31, [20])['dc'], 15)

    def test_success_keeps_concentration(self):
        save = self.damage(10, [8])  # 8 + 2 (CON 14) = 10 vs CD 10
        self.assertTrue(save['success'])
        self.assertEqual(save['total'], 10)
        self.assertEqual(self.character.concentration_spell, 'Abençoar')

    def test_failure_ends_concentration(self):
        save = self.damage(10, [7])
        self.assertFalse(save['success'])
        self.assertIsNone(self.character.concentration_spell)

    def test_shell_defense_gives_advantage(self):
        services.toggle_shell_defense(self.character)
        save = self.damage(10, [3, 15])
        self.assertTrue(save['advantage'])
        self.assertEqual((save['rolls'], save['total']), ([3, 15], 17))
        self.assertTrue(save['success'])

    def test_no_save_without_concentration_or_damage(self):
        self.assertIsNone(self.damage(0, []))
        services.end_concentration(self.character)
        self.assertIsNone(self.damage(10, []))

    def test_dropping_to_zero_hp_ends_concentration(self):
        save = self.damage(999, [])
        self.assertTrue(save['unconscious'])
        self.assertIsNone(self.character.concentration_spell)

    def test_damage_endpoint_returns_save(self):
        sheet = services.get_sheet()
        services.set_concentration(sheet, 'Abençoar')
        with mock.patch.object(services, '_roll_die', side_effect=[20]):
            data = self.client.post('/api/damage/', {'amount': 5}).json()
        self.assertEqual(data['conc_save']['total'], 22)
        self.assertEqual(data['state']['concentration_spell'], 'Abençoar')
