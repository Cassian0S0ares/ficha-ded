"""Testes do inventário (itens e moedas)."""

from django.test import TestCase

from . import services


class InventoryTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def post(self, path, data=None):
        return self.client.post('/api/inventory/' + path, data or {})

    def test_create_edit_and_delete_item(self):
        data = self.post('new/', {'name': 'Maça', 'category': 'weapon', 'quantity': 1,
                                  'damage_formula': '1d6+2', 'equipped': 'on'}).json()
        item_id = data['item_id']
        item = data['inventory']['items'][0]
        self.assertEqual((item['name'], item['equipped'], item['category_label']), ('Maça', True, 'Arma'))

        self.post(f'{item_id}/', {'name': 'Maça +1', 'equipped': ''})
        item = self.character.inventory.get()
        self.assertEqual((item.name, item.equipped, item.damage_formula), ('Maça +1', False, '1d6+2'))

        self.post(f'{item_id}/delete/')
        self.assertFalse(self.character.inventory.exists())

    def test_quantity_and_use(self):
        item_id = self.post('new/', {'name': 'Poção de Cura', 'category': 'consumable',
                                     'quantity': 1}).json()['item_id']
        self.post(f'{item_id}/quantity/', {'delta': 1})
        self.post(f'{item_id}/use/')
        self.post(f'{item_id}/use/')
        self.assertEqual(self.character.inventory.get().quantity, 0)
        response = self.post(f'{item_id}/use/')
        self.assertEqual(response.status_code, 400)
        self.post(f'{item_id}/quantity/', {'delta': -5})
        self.assertEqual(self.character.inventory.get().quantity, 0)

    def test_invalid_item_is_rejected(self):
        self.assertEqual(self.post('new/', {'name': '', 'category': 'gear', 'quantity': 1}).status_code, 400)
        self.assertEqual(self.post('new/', {'name': 'X', 'category': 'gear', 'quantity': 1,
                                            'damage_formula': 'banana'}).status_code, 400)
        self.assertEqual(self.post('999/delete/').status_code, 400)

    def test_coins(self):
        data = self.post('coins/', {'gold': 25, 'silver': 3}).json()
        coins = {c['field']: c['amount'] for c in data['inventory']['coins']}
        self.assertEqual((coins['gold'], coins['silver'], coins['copper']), (25, 3, 0))
        self.assertEqual(self.post('coins/', {'gold': -1}).status_code, 400)
        self.character.refresh_from_db()
        self.assertEqual(self.character.gold, 25)

    def test_dashboard_renders_inventory(self):
        services.create_item(self.character, name='Símbolo sagrado', category='gear', quantity=1)
        html = self.client.get('/').content.decode()
        self.assertIn('id="inventory"', html)
        self.assertIn('Símbolo sagrado', html)
