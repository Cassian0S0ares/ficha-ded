"""Testes das condições aplicadas às jogadas de d20."""

from unittest import mock

from django.test import TestCase

from . import rolls, services
from .services import SpellCastError


class D20ContextTests(TestCase):
    def test_invisible_attacks_with_advantage(self):
        ctx = rolls.d20_context({'invisible': 1}, 'attack')
        self.assertEqual(rolls.roll_mode(ctx), 'advantage')

    def test_advantage_and_disadvantage_cancel(self):
        ctx = rolls.d20_context({'invisible': 1, 'poisoned': 1}, 'attack')
        self.assertEqual(rolls.roll_mode(ctx), 'normal')

    def test_stunned_auto_fails_str_dex_saves_only(self):
        self.assertTrue(rolls.d20_context({'stunned': 1}, 'save', 'dex')['auto_fail'])
        self.assertIsNone(rolls.d20_context({'stunned': 1}, 'save', 'wis')['auto_fail'])

    def test_exhaustion_levels(self):
        self.assertEqual(rolls.roll_mode(rolls.d20_context({'exhaustion': 1}, 'check')), 'disadvantage')
        self.assertEqual(rolls.roll_mode(rolls.d20_context({'exhaustion': 2}, 'attack')), 'normal')
        self.assertEqual(rolls.roll_mode(rolls.d20_context({'exhaustion': 3}, 'save', 'wis')), 'disadvantage')

    def test_shell_defense_advantage_on_str_con_saves(self):
        ctx = rolls.d20_context({}, 'save', 'con', shell_defense=True)
        self.assertEqual(rolls.roll_mode(ctx), 'advantage')
        ctx = rolls.d20_context({}, 'save', 'wis', shell_defense=True)
        self.assertEqual(rolls.roll_mode(ctx), 'normal')

    def test_summary_mentions_attacks_against(self):
        lines = rolls.roll_summary({'invisible': 1})
        self.assertIn('Ataques: vantagem (Invisível)', lines)
        self.assertIn('Ataques contra você: desvantagem (Invisível)', lines)
        self.assertEqual(rolls.roll_summary({}), [])


class RollD20Tests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def roll(self, dice, *args, **kwargs):
        with mock.patch.object(services, '_roll_die', side_effect=dice):
            return services.roll_d20(self.character, *args, **kwargs)

    def test_invisible_spell_attack_takes_higher_die(self):
        services.change_effect(self.character, 'invisible', toggle=True)
        roll = self.roll([4, 17], 'attack', 'spell')
        self.assertEqual((roll['mode'], roll['natural'], roll['total']), ('advantage', 17, 25))

    def test_poisoned_check_takes_lower_die(self):
        services.change_effect(self.character, 'poisoned', toggle=True)
        roll = self.roll([4, 17], 'check', 'wis')  # SAB 20 -> +5
        self.assertEqual((roll['mode'], roll['total']), ('disadvantage', 9))

    def test_save_proficiency_and_blessed_bonus(self):
        services.change_effect(self.character, 'blessed', toggle=True)
        roll = self.roll([10, 3], 'save', 'wis')  # 10 + 5 + 3 (prof.) + 1d4(3)
        self.assertEqual(roll['total'], 21)

    def test_auto_fail_does_not_roll(self):
        services.change_effect(self.character, 'paralyzed', toggle=True)
        roll = self.roll([], 'save', 'str')
        self.assertTrue(roll['auto_fail'])

    def test_incapacitated_cannot_attack(self):
        services.change_effect(self.character, 'stunned', toggle=True)
        with self.assertRaises(SpellCastError):
            self.roll([], 'attack', 'claws')

    def test_concentration_save_uses_exhaustion(self):
        services.change_effect(self.character, 'exhaustion', rounds=None, level=3)
        services.set_concentration(self.character, 'Abençoar')
        with mock.patch.object(services, '_roll_die', side_effect=[15, 5]):
            save = services.take_damage(self.character, 10)
        self.assertEqual(save['total'], 7)  # desvantagem: 5 + 2
        self.assertFalse(save['success'])

    def test_endpoint_and_state_summary(self):
        services.change_effect(self.character, 'invisible', toggle=True)
        with mock.patch.object(services, '_roll_die', side_effect=[2, 19]):
            data = self.client.post('/api/roll-d20/', {'kind': 'attack', 'ability': 'spell'}).json()
        self.assertEqual(data['roll']['total'], 27)
        self.assertIn('Ataques: vantagem (Invisível)', data['state']['roll_effects'])
        bad = self.client.post('/api/roll-d20/', {'kind': 'attack', 'ability': 'wis'})
        self.assertEqual(bad.status_code, 400)
