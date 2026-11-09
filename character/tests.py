"""Testes da camada de serviços e das regras de negócio da ficha."""

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
