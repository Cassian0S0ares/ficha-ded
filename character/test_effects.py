from django.test import TestCase
from django.urls import reverse

from . import services


class EffectTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def test_bond_counts_down_and_expires_without_refunding(self):
        services.use_emboldening_bond(self.character)
        self.assertEqual(self.character.active_effects.get(key='bond').rounds_remaining, 100)
        services.change_effect(self.character, 'bond', rounds=3)
        result = services.advance_round(self.character)
        self.assertIn('restam 2', result['effect_notices'][0])
        services.advance_round(self.character)
        self.assertIn('terminou', services.advance_round(self.character)['effect_notices'][0])
        self.assertFalse(self.character.active_effects.exists())
        self.character.refresh_from_db()
        self.assertEqual(self.character.emboldening_bond_current, 2)

    def test_concentration_replaces_timer_and_expiration_ends_spell(self):
        services.set_concentration(self.character, 'Abençoar')
        self.assertEqual(self.character.active_effects.get(key='concentration').rounds_remaining, 10)
        services.set_concentration(self.character, 'Guardiões Espirituais')
        self.assertEqual(self.character.active_effects.get(key='concentration').rounds_remaining, 100)
        self.assertEqual(self.character.active_effects.count(), 1)
        services.change_effect(self.character, 'concentration', rounds=1)
        services.advance_round(self.character)
        self.character.refresh_from_db()
        self.assertIsNone(self.character.concentration_spell)

    def test_conditions_indefinite_and_incapacitation_breaks_concentration(self):
        services.change_effect(self.character, 'poisoned', toggle=True)
        services.advance_round(self.character)
        self.assertIsNone(self.character.active_effects.get(key='poisoned').rounds_remaining)
        services.set_concentration(self.character, 'Abençoar')
        services.change_effect(self.character, 'paralyzed', toggle=True)
        self.character.refresh_from_db()
        self.assertIsNone(self.character.concentration_spell)
        self.assertFalse(self.character.active_effects.filter(key='concentration').exists())
        with self.assertRaises(services.SpellCastError):
            services.set_concentration(self.character, 'Abençoar')

    def test_both_rests_clear_effects(self):
        for rest in (services.short_rest, services.long_rest):
            services.change_effect(self.character, 'poisoned', toggle=True)
            services.set_concentration(self.character, 'Abençoar')
            rest(self.character)
            self.assertFalse(self.character.active_effects.exists())
            self.assertIsNone(self.character.concentration_spell)

    def test_endpoints_validate_and_persist(self):
        url = reverse('effect_change')
        self.assertEqual(self.client.get(url).status_code, 405)
        for rounds in ('0', '-1', '1.5', 'no', '100001'):
            self.assertEqual(self.client.post(url, {'key': 'bond', 'rounds': rounds}).status_code, 400)
        self.assertEqual(self.client.post(url, {'key': 'unknown', 'toggle': '1'}).status_code, 400)
        response = self.client.post(url, {'key': 'exhaustion', 'rounds': 8, 'level': 3})
        self.assertEqual(response.status_code, 200)
        effects = self.client.get(reverse('state')).json()['state']['effects']
        self.assertEqual((effects[0]['rounds'], effects[0]['level']), (8, 3))
        page = self.client.get(reverse('dashboard'))
        self.assertContains(page, 'Avançar rodada')
        self.assertContains(page, 'Envenenado')
        self.assertEqual(self.client.post(reverse('effect_round')).status_code, 200)
