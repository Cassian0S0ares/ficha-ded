"""Storage do Django que grava arquivos no Supabase Storage (REST)."""
import mimetypes
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class SupabaseStorage(Storage):
    def __init__(self):
        self.base = settings.SUPABASE_URL.rstrip('/')
        self.key = settings.SUPABASE_SECRET_KEY
        self.bucket = settings.SUPABASE_BUCKET

    def _req(self, method, path, data=None, ctype=None):
        headers = {'apikey': self.key, 'Authorization': f'Bearer {self.key}'}
        if ctype:
            headers['Content-Type'] = ctype
        req = urllib.request.Request(
            f'{self.base}/storage/v1/{path}', data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=30)

    def _obj(self, name):
        return f'{self.bucket}/{urllib.parse.quote(name)}'

    def _save(self, name, content):
        ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        self._req('POST', f'object/{self._obj(name)}', content.read(), ctype)
        return name

    def _open(self, name, mode='rb'):
        with self._req('GET', f'object/{self._obj(name)}') as r:
            return ContentFile(r.read(), name=name)

    def exists(self, name):
        try:
            self._req('HEAD', f'object/{self._obj(name)}').close()
            return True
        except urllib.error.HTTPError:
            return False

    def delete(self, name):
        try:
            self._req('DELETE', f'object/{self._obj(name)}').close()
        except urllib.error.HTTPError:
            pass

    def url(self, name):
        return f'{self.base}/storage/v1/object/public/{self._obj(name)}'

    def size(self, name):
        with self._req('HEAD', f'object/{self._obj(name)}') as r:
            return int(r.headers.get('Content-Length', 0))
