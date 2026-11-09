"""
URLs do projeto botticellius_sheet.

A ficha abre sem login. Inclui:
    * admin do Django (com seu próprio login, opcional)
    * app character (dashboard + endpoints AJAX)
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('character.urls')),
]

# Em desenvolvimento, o próprio Django serve os arquivos enviados (fotos).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
