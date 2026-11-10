"""Testes dos personagens da campanha (NPCs)."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from . import services

# Fotos ficam em memória nos testes (nunca vão para o Supabase).
IN_MEMORY = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(STORAGES=IN_MEMORY)
class NpcTests(TestCase):
    def setUp(self):
        self.character = services.get_sheet()

    def post(self, path, data=None):
        return self.client.post('/api/npcs/' + path, data or {})

    def test_create_edit_and_delete(self):
        npc_id = self.post('new/', {'name': 'Velkor'}).json()['npc_id']
        self.post(f'{npc_id}/', {'name': 'Velkor, o Mago', 'affection': 2, 'notes': 'Deve 200 po.'})
        npc = self.character.npcs.get()
        self.assertEqual((npc.name, npc.affection, npc.notes), ('Velkor, o Mago', 2, 'Deve 200 po.'))
        self.post(f'{npc_id}/delete/')
        self.assertFalse(self.character.npcs.exists())

    def test_affection_limits_and_empty_name(self):
        npc_id = self.post('new/', {'name': 'Lira'}).json()['npc_id']
        self.assertEqual(self.post(f'{npc_id}/', {'affection': 4}).status_code, 400)
        self.assertEqual(self.post(f'{npc_id}/', {'affection': -1}).status_code, 400)
        self.assertEqual(self.post(f'{npc_id}/', {'name': ''}).status_code, 400)
        self.assertEqual(self.post('new/', {'name': ''}).status_code, 400)
        self.assertEqual(self.character.npcs.get().affection, 0)

    def test_photo_upload(self):
        npc_id = self.post('new/', {'name': 'Lira'}).json()['npc_id']
        photo = SimpleUploadedFile('lira.png', b'\x89PNG fake', content_type='image/png')
        data = self.client.post(f'/api/npcs/{npc_id}/photo/', {'avatar': photo}).json()
        self.assertIn('npcs/', data['npcs'][0]['photo'])
        bad = SimpleUploadedFile('lira.txt', b'x', content_type='text/plain')
        self.assertEqual(self.client.post(f'/api/npcs/{npc_id}/photo/', {'avatar': bad}).status_code, 400)

    def test_list_is_sorted_by_name(self):
        for name in ('Zara', 'Aldo'):
            self.post('new/', {'name': name})
        names = [n['name'] for n in self.client.get('/api/npcs/').json()['npcs']]
        self.assertEqual(names, ['Aldo', 'Zara'])
