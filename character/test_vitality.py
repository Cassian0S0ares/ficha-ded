"""Testes de PV temporários, Dados de Vida e testes contra a morte."""

from unittest import mock

from django.test import TestCase

from . import services
from .services import SpellCastError


class VitalityTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()  # 59 PV, CON 14 (+2), nível 8

    def dice(self, *values):
        return mock.patch.object(services, '_roll_die', side_effect=list(values))

    def down(self):
        services.take_damage(self.character, self.character.current_hp)
        self.assertEqual(self.character.current_hp, 0)

    # ------------------------------------------------ PV temporários
    def test_temp_hp_absorbs_damage_first(self):
        services.set_temp_hp(self.character, 8)
        services.take_damage(self.character, 5)
        self.assertEqual((self.character.temp_hp, self.character.current_hp), (3, 59))
        services.take_damage(self.character, 10)
        self.assertEqual((self.character.temp_hp, self.character.current_hp), (0, 52))

    def test_temp_hp_does_not_stack(self):
        services.set_temp_hp(self.character, 8)
        with self.assertRaises(ValueError):
            services.set_temp_hp(self.character, 5)
        services.set_temp_hp(self.character, 10)
        self.assertEqual(self.character.temp_hp, 10)
        services.set_temp_hp(self.character, 0)
        self.assertEqual(self.character.temp_hp, 0)

    # ------------------------------------------------ Dados de Vida
    def test_spend_hit_die_heals_and_long_rest_recovers_half(self):
        services.take_damage(self.character, 30)
        with self.dice(5):
            roll = services.spend_hit_die(self.character)
        self.assertEqual(roll['total'], 7)  # 5 + 2
        self.assertEqual((self.character.current_hp, self.character.hit_dice_current), (36, 7))
        for _ in range(7):
            with self.dice(1):
                services.spend_hit_die(self.character)
        with self.assertRaises(SpellCastError):
            services.spend_hit_die(self.character)
        services.long_rest(self.character)
        self.assertEqual(self.character.hit_dice_current, 4)  # metade de 8

    # ------------------------------------------------ Testes contra a morte
    def test_dropping_to_zero_makes_unconscious(self):
        self.down()
        self.assertTrue(self.character.active_effects.filter(key='unconscious').exists())
        services.heal(self.character, 5)
        self.assertFalse(self.character.active_effects.filter(key='unconscious').exists())

    def test_three_successes_stabilize(self):
        self.down()
        for _ in range(3):
            with self.dice(12):
                services.roll_death_save(self.character)
        self.assertTrue(self.character.is_stable)
        with self.assertRaises(SpellCastError):
            services.roll_death_save(self.character)

    def test_natural_one_counts_two_and_three_failures_kill(self):
        self.down()
        with self.dice(1):
            services.roll_death_save(self.character)
        self.assertEqual(self.character.death_failures, 2)
        with self.dice(5):
            services.roll_death_save(self.character)
        self.assertTrue(self.character.is_dead)
        with self.assertRaises(SpellCastError):
            services.heal(self.character, 10)
        services.revive(self.character)
        self.assertEqual((self.character.current_hp, self.character.death_failures), (1, 0))

    def test_natural_twenty_wakes_with_one_hp(self):
        self.down()
        with self.dice(20):
            services.roll_death_save(self.character)
        self.assertEqual(self.character.current_hp, 1)
        self.assertFalse(self.character.active_effects.filter(key='unconscious').exists())

    def test_damage_while_down_adds_failures(self):
        self.down()
        services.take_damage(self.character, 3)
        self.assertEqual(self.character.death_failures, 1)
        services.take_damage(self.character, 3, critical=True)
        self.assertTrue(self.character.is_dead)

    def test_massive_damage_kills_instantly(self):
        services.take_damage(self.character, 59 + 59)
        self.assertTrue(self.character.is_dead)

    def test_blessed_helps_death_save(self):
        self.down()
        services.change_effect(self.character, 'blessed', toggle=True)
        with self.dice(8, 3):  # 8 + 1d4(3) = 11
            roll = services.roll_death_save(self.character)
        self.assertEqual(roll['total'], 11)
        self.assertEqual(self.character.death_successes, 1)

    def test_endpoints_and_undo(self):
        self.client.post('/api/damage/', {'amount': 59})
        data = self.client.post('/api/death-set/', {'successes': 2, 'failures': 1}).json()
        self.assertEqual((data['state']['death_successes'], data['state']['death_failures']), (2, 1))
        self.client.post('/api/undo/')
        self.character.refresh_from_db()
        self.assertEqual((self.character.death_successes, self.character.death_failures), (0, 0))
        self.assertEqual(self.client.post('/api/death-set/', {'successes': 4, 'failures': 0}).status_code, 400)
