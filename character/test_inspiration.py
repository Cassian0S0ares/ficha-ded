"""Testes da inspiração heroica (o jogador escolhe quando gastar)."""

from unittest import mock

from django.test import TestCase

from . import services


class InspirationTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def post(self, url, data=None):
        return self.client.post(url, data or {})

    def gain(self):
        self.assertEqual(self.post('/api/inspiration/', {'value': '1'}).status_code, 200)

    def has(self):
        self.character.refresh_from_db()
        return self.character.heroic_inspiration

    def test_gain_and_remove(self):
        self.gain()
        self.assertTrue(self.has())
        self.assertEqual(self.post('/api/inspiration/', {'value': '1'}).status_code, 400)
        self.post('/api/inspiration/', {'value': '0'})
        self.assertFalse(self.has())

    def test_spending_gives_advantage_once(self):
        self.gain()
        with mock.patch.object(services, '_roll_die', side_effect=[3, 17]):
            data = self.post('/api/roll-d20/', {'kind': 'skill', 'ability': 'survival',
                                                'inspiration': '1'}).json()
        self.assertEqual((data['roll']['mode'], data['roll']['total']), ('advantage', 25))
        self.assertTrue(data['roll']['inspiration'])
        self.assertFalse(data['state']['heroic_inspiration'])
        # Sem inspiração, pedir para usar falha e não rola.
        self.assertEqual(self.post('/api/roll-d20/', {'kind': 'check', 'ability': 'wis',
                                                      'inspiration': '1'}).status_code, 400)

    def test_not_spent_without_asking_or_on_auto_fail(self):
        self.gain()
        self.post('/api/roll-d20/', {'kind': 'check', 'ability': 'wis'})
        self.assertTrue(self.has())
        services.change_effect(self.character, 'stunned', toggle=True)
        data = self.post('/api/roll-d20/', {'kind': 'save', 'ability': 'dex', 'inspiration': '1'}).json()
        self.assertTrue(data['roll']['auto_fail'])
        self.assertTrue(self.has())

    def test_concentration_and_death_saves(self):
        self.gain()
        services.set_concentration(self.character, 'Abençoar')
        with mock.patch.object(services, '_roll_die', side_effect=[2, 15]):
            data = self.post('/api/damage/', {'amount': 4, 'inspiration': '1'}).json()
        self.assertTrue(data['conc_save']['advantage'])
        self.assertFalse(self.has())

        self.character.refresh_from_db()
        services.take_damage(self.character, self.character.current_hp)  # cai a 0 PV
        self.gain()
        with mock.patch.object(services, '_roll_die', side_effect=[4, 12]):
            data = self.post('/api/death-save/', {'inspiration': '1'}).json()
        self.assertEqual(data['state']['death_successes'], 1)
        self.assertFalse(self.has())

    def test_undo_returns_inspiration(self):
        self.gain()
        self.post('/api/roll-d20/', {'kind': 'check', 'ability': 'wis', 'inspiration': '1'})
        self.assertFalse(self.has())
        self.post('/api/undo/')
        self.assertTrue(self.has())
