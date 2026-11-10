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


class SkillTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def test_skill_formulas_follow_effects_and_render_under_dice(self):
        skills = services.serialize_skills(self.character)
        self.assertEqual(len(skills), 18)
        self.assertEqual(next(s for s in skills if s['key'] == 'medicine')['formula'], 'D20 + 8')
        services.change_effect(self.character, 'poisoned', toggle=True)
        services.change_effect(self.character, 'bond', toggle=True)
        formula = services.serialize_skills(self.character)[0]['formula']
        self.assertIn('+ 1D4', formula)
        self.assertIn('Desvantagem', formula)
        page = self.client.get('/').content.decode()
        self.assertLess(page.index('card-abilities'), page.index('card-slots'))
        self.assertLess(page.index('card-dice'), page.index('dice-skills'))
        self.assertEqual(page.count('data-kind="skill"'), 18)

    def test_default_proficiencies_from_sheet(self):
        bonus = {s['key']: s['bonus'] for s in services.serialize_skills(self.character)}
        self.assertEqual(bonus['survival'], 8)     # SAB +5, proficiente +3
        self.assertEqual(bonus['medicine'], 8)
        self.assertEqual(bonus['religion'], 3)     # INT +0 +3
        self.assertEqual(bonus['persuasion'], 4)   # CAR +1 +3
        self.assertEqual(bonus['perception'], 5)   # sem proficiência
        self.assertEqual(bonus['stealth'], -1)
        state = services.serialize_state(self.character)
        self.assertEqual(state['passive_perception'], 15)

    def test_skill_roll_uses_bonus_and_conditions(self):
        services.change_effect(self.character, 'poisoned', toggle=True)
        with mock.patch.object(services, '_roll_die', side_effect=[14, 6]):
            roll = services.roll_d20(self.character, 'skill', 'medicine')
        self.assertEqual((roll['label'], roll['mode'], roll['total']), ('Medicina', 'disadvantage', 14))

    def test_toggle_proficiency_endpoint_and_bad_skill(self):
        data = self.client.post('/api/skill-proficiency/', {'skill': 'insight'}).json()
        insight = next(s for s in data['state']['skills'] if s['key'] == 'insight')
        self.assertEqual((insight['proficient'], insight['bonus']), (True, 8))
        self.client.post('/api/skill-proficiency/', {'skill': 'insight'})
        self.character.refresh_from_db()
        self.assertNotIn('insight', self.character.skill_proficiencies)
        bad = self.client.post('/api/roll-d20/', {'kind': 'skill', 'ability': 'wis'})
        self.assertEqual(bad.status_code, 400)
