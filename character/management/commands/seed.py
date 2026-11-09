"""
Comando de seed manual.

Uso:
    python manage.py seed --user <username>

Cria (se necessário) o personagem Botticellius completo — atributos, espaços
de magia e catálogo de magias — para o usuário informado. Se nenhum usuário
for informado, aplica para todos os usuários existentes sem personagem.

Observação: a aplicação também cria a ficha automaticamente no primeiro
acesso ao dashboard, então este comando é apenas uma conveniência.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from character.services import create_default_character

User = get_user_model()


class Command(BaseCommand):
    help = 'Cria o personagem Botticellius (e seus dados) para um ou todos os usuários.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            dest='username',
            help='Username do dono da ficha. Se omitido, aplica a todos os usuários.',
        )

    def handle(self, *args, **options):
        username = options.get('username')

        if username:
            users = User.objects.filter(username=username)
            if not users.exists():
                self.stderr.write(self.style.ERROR(f'Usuário "{username}" não encontrado.'))
                return
        else:
            users = User.objects.all()
            if not users.exists():
                self.stderr.write(self.style.WARNING(
                    'Nenhum usuário existe. Crie um com "python manage.py createsuperuser".'
                ))
                return

        for user in users:
            had = user.characters.exists()
            character = create_default_character(user)
            status = 'já existia' if had else 'criado'
            self.stdout.write(self.style.SUCCESS(
                f'Personagem "{character.name}" {status} para {user.username}.'
            ))
