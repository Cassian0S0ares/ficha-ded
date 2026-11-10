"""Testes do "Desfazer a última ação"."""

from django.test import TestCase

from . import services
from .models import Spell


class UndoTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def post(self, url, data=None):
        return self.client.post(url, data or {}).json()

    def undo(self):
        return self.post('/api/undo/')

    def test_undo_damage_restores_hp_and_concentration(self):
        services.set_concentration(self.character, 'Abençoar')
        hp = self.character.current_hp
        self.post('/api/damage/', {'amount': 200})  # 0 PV derruba a concentração
        data = self.undo()
        self.assertTrue(data['ok'])
        self.assertIn('Recebeu 200 de dano', data['undone'])
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_hp, hp)
        self.assertEqual(self.character.concentration_spell, 'Abençoar')
        self.assertTrue(self.character.active_effects.filter(key='concentration').exists())

    def test_undo_spell_slot_spent_by_mistake(self):
        bless = Spell.objects.get(character=self.character, name='Abençoar')
        self.post(f'/api/cast/{bless.id}/')
        self.assertEqual(self.character.spell_slots.get(level=1).current, 3)
        self.undo()
        self.assertEqual(self.character.spell_slots.get(level=1).current, 4)

    def test_undo_consumable_and_deleted_item(self):
        item_id = self.post('/api/inventory/new/', {'name': 'Poção', 'category': 'consumable',
                                                   'quantity': 2})['item_id']
        self.post(f'/api/inventory/{item_id}/use/')
        data = self.undo()
        self.assertEqual(data['inventory']['items'][0]['quantity'], 2)

        self.post(f'/api/inventory/{item_id}/delete/')
        self.assertFalse(self.character.inventory.exists())
        self.undo()
        self.assertEqual(self.character.inventory.get(id=item_id).quantity, 2)

    def test_undo_long_rest_and_multiple_steps(self):
        self.post('/api/damage/', {'amount': 10})
        self.post('/api/heal/', {'amount': 3})
        self.post('/api/long-rest/')
        self.character.refresh_from_db()
        full = self.character.max_hp
        self.assertEqual(self.character.current_hp, full)
        self.undo()  # desfaz descanso
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_hp, full - 7)
        self.undo()  # desfaz cura
        self.undo()  # desfaz dano
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_hp, full)
        self.assertFalse(self.undo()['ok'])

    def test_pure_rolls_and_failed_actions_do_not_create_undo(self):
        self.post('/api/roll-dice/', {'dice': 'd20'})
        self.post('/api/roll-d20/', {'kind': 'save', 'ability': 'wis'})
        for _ in range(3):
            self.post('/api/channel-divinity/')  # 3ª falha: só há 2 usos
        self.assertEqual(self.character.undo_snapshots.count(), 2)
        label = self.client.get('/api/state/').json()['state']['undo_label']
        self.assertIn('Canalizar Divindade', label)

    def test_keeps_only_last_20(self):
        for _ in range(25):
            self.post('/api/damage/', {'amount': 1})
        self.assertEqual(self.character.undo_snapshots.count(), 20)
