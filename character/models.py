"""
Modelos de domínio da ficha de D&D 5e.

Entidades:
    Character    -> ficha completa do personagem (FK para User; o schema já
                    permite múltiplos personagens por usuário no futuro).
    SpellSlot    -> espaços de magia por círculo (nível).
    Spell        -> magias conhecidas/preparadas pelo personagem.
    ActivityLog  -> histórico de ações relevantes da campanha.
    DiceRoll     -> histórico de rolagens de dados.
    NoteFolder   -> pastas que agrupam blocos de notas da sessão.
    Note         -> blocos de notas da sessão.
    InventoryItem -> itens do inventário (moedas ficam em Character).
    Npc          -> personagens da campanha (afeto, anotações e foto).
    UndoSnapshot -> estado anterior a cada ação, para "Desfazer".
"""

from django.conf import settings
from django.db import models


class Character(models.Model):
    """Ficha completa de um personagem de D&D 5e."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='characters',
        verbose_name='Dono',
    )

    # Identidade
    avatar = models.FileField(
        'Foto', upload_to='avatars/', blank=True, null=True
    )
    name = models.CharField('Nome', max_length=100, default='Botticellius')
    race = models.CharField('Raça', max_length=50, default='Tortle')
    class_name = models.CharField('Classe', max_length=50, default='Cleric')
    subclass = models.CharField('Subclasse', max_length=50, default='Peace Domain')
    level = models.PositiveIntegerField('Nível', default=8)

    # Atributos
    strength = models.IntegerField('Força', default=15)
    dexterity = models.IntegerField('Destreza', default=8)
    constitution = models.IntegerField('Constituição', default=14)
    intelligence = models.IntegerField('Inteligência', default=10)
    wisdom = models.IntegerField('Sabedoria', default=20)
    charisma = models.IntegerField('Carisma', default=12)

    # Vida e defesa
    max_hp = models.IntegerField('PV máximo', default=59)
    current_hp = models.IntegerField('PV atual', default=59)
    armor_class = models.IntegerField('Classe de Armadura', default=19)
    temp_hp = models.PositiveIntegerField('PV temporários', default=0)

    # Dados de Vida (Clérigo: d8, um por nível) e testes contra a morte
    hit_dice_current = models.PositiveIntegerField('Dados de Vida disponíveis', default=8)
    death_successes = models.PositiveSmallIntegerField('Sucessos contra a morte', default=0)
    death_failures = models.PositiveSmallIntegerField('Falhas contra a morte', default=0)

    # Conjuração
    spell_save_dc = models.IntegerField('CD de resistência de magia', default=16)
    spell_attack_bonus = models.IntegerField('Bônus de ataque mágico', default=8)
    speed = models.IntegerField('Deslocamento (m)', default=9)
    proficiency_bonus = models.IntegerField('Bônus de proficiência', default=3)

    # Limite de preparação de magias (Peace Domain Cleric nível 8)
    prepared_spells_limit = models.IntegerField('Limite de magias preparadas', default=13)

    # Recursos de classe
    channel_divinity_max = models.IntegerField('Canalizar Divindade (máx)', default=2)
    channel_divinity_current = models.IntegerField('Canalizar Divindade (atual)', default=2)

    # Recursos do Domínio da Paz
    emboldening_bond_max = models.IntegerField('Vínculo Encorajador (máx)', default=3)
    emboldening_bond_current = models.IntegerField('Vínculo Encorajador (atual)', default=3)

    # Moedas
    copper = models.PositiveIntegerField('Peças de cobre (PC)', default=0)
    silver = models.PositiveIntegerField('Peças de prata (PP)', default=0)
    electrum = models.PositiveIntegerField('Peças de electro (PE)', default=0)
    gold = models.PositiveIntegerField('Peças de ouro (PO)', default=0)
    platinum = models.PositiveIntegerField('Peças de platina (PL)', default=0)

    # Estado dinâmico
    concentration_spell = models.CharField(
        'Concentração ativa', max_length=120, blank=True, null=True
    )
    shell_defense_active = models.BooleanField('Defesa de Concha ativa', default=False)

    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Personagem'
        verbose_name_plural = 'Personagens'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.class_name} {self.level})'

    # ------------------------------------------------------------------
    # Propriedades calculadas
    # ------------------------------------------------------------------
    @property
    def effective_ac(self):
        """CA efetiva considerando a Defesa de Concha (+4 quando ativa)."""
        bonus = 4 if self.shell_defense_active else 0
        return self.armor_class + bonus

    @property
    def hp_percent(self):
        """Percentual de vida atual, limitado entre 0 e 100."""
        if self.max_hp <= 0:
            return 0
        pct = round(self.current_hp / self.max_hp * 100)
        return max(0, min(100, pct))

    @staticmethod
    def ability_modifier(score):
        """Modificador de atributo no padrão D&D 5e."""
        return (score - 10) // 2

    @property
    def hit_die(self):
        """Faces do Dado de Vida da classe."""
        return {'Cleric': 8}.get(self.class_name, 8)

    @property
    def hit_dice_max(self):
        return self.level

    @property
    def is_dead(self):
        return self.death_failures >= 3

    @property
    def is_stable(self):
        return self.current_hp == 0 and self.death_successes >= 3 and not self.is_dead

    @property
    def is_concentrating(self):
        return bool(self.concentration_spell)


class ActiveEffect(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='active_effects')
    key = models.CharField(max_length=40)
    name = models.CharField(max_length=150)
    rounds_remaining = models.PositiveIntegerField(null=True, blank=True)
    exhaustion_level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['character', 'key'], name='unique_character_effect')]


class SpellSlot(models.Model):
    """Espaços de magia de um determinado círculo (nível)."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='spell_slots'
    )
    level = models.PositiveIntegerField('Círculo')
    maximum = models.PositiveIntegerField('Máximo')
    current = models.PositiveIntegerField('Atual')

    class Meta:
        verbose_name = 'Espaço de Magia'
        verbose_name_plural = 'Espaços de Magia'
        ordering = ['level']
        unique_together = ('character', 'level')

    def __str__(self):
        return f'{self.character.name} - {self.level}º círculo ({self.current}/{self.maximum})'


class Spell(models.Model):
    """Magia conhecida ou preparada pelo personagem."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='spells'
    )
    name = models.CharField('Nome', max_length=120)
    spell_level = models.PositiveIntegerField('Círculo da magia')  # 0 = truque
    description = models.TextField('Descrição', blank=True)
    is_domain_spell = models.BooleanField('Magia de domínio', default=False)
    requires_concentration = models.BooleanField('Requer concentração', default=False)
    healing_formula = models.CharField('Fórmula de cura', max_length=50, blank=True)
    damage_formula = models.CharField('Fórmula de dano', max_length=50, blank=True)

    class Meta:
        verbose_name = 'Magia'
        verbose_name_plural = 'Magias'
        ordering = ['spell_level', 'name']

    def __str__(self):
        kind = 'Truque' if self.spell_level == 0 else f'{self.spell_level}º círculo'
        return f'{self.name} ({kind})'

    @property
    def is_cantrip(self):
        return self.spell_level == 0


class ActivityLog(models.Model):
    """Registro de histórico de ações da campanha."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='logs'
    )
    action = models.CharField('Ação', max_length=255)
    created_at = models.DateTimeField('Quando', auto_now_add=True)

    class Meta:
        verbose_name = 'Registro de Atividade'
        verbose_name_plural = 'Registros de Atividade'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.created_at:%d/%m %H:%M}] {self.action}'


class DiceRoll(models.Model):
    """Histórico de rolagens de dados."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='dice_rolls'
    )
    dice = models.CharField('Dado/Fórmula', max_length=50)
    result = models.IntegerField('Resultado')
    detail = models.CharField('Detalhe', max_length=120, blank=True)
    created_at = models.DateTimeField('Quando', auto_now_add=True)

    class Meta:
        verbose_name = 'Rolagem de Dado'
        verbose_name_plural = 'Rolagens de Dados'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.dice} = {self.result}'


class NoteFolder(models.Model):
    """Pasta que agrupa blocos de notas da sessão."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='note_folders'
    )
    name = models.CharField('Nome', max_length=120)
    created_at = models.DateTimeField('Criada em', auto_now_add=True)

    class Meta:
        verbose_name = 'Pasta de Notas'
        verbose_name_plural = 'Pastas de Notas'
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class Note(models.Model):
    """Bloco de notas da sessão (opcionalmente dentro de uma pasta)."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='notes'
    )
    folder = models.ForeignKey(
        NoteFolder, on_delete=models.CASCADE, related_name='notes',
        blank=True, null=True, verbose_name='Pasta',
    )
    title = models.CharField('Título', max_length=120)
    content = models.TextField('Conteúdo', blank=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Bloco de Notas'
        verbose_name_plural = 'Blocos de Notas'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class InventoryItem(models.Model):
    """Item do inventário do personagem (sem controle de peso/carga)."""

    CATEGORIES = [
        ('weapon', 'Arma'),
        ('armor', 'Armadura'),
        ('gear', 'Equipamento'),
        ('consumable', 'Consumível'),
        ('treasure', 'Tesouro'),
        ('other', 'Outro'),
    ]

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='inventory'
    )
    name = models.CharField('Nome', max_length=120)
    category = models.CharField('Categoria', max_length=20, choices=CATEGORIES, default='gear')
    quantity = models.PositiveIntegerField('Quantidade', default=1)
    description = models.TextField('Descrição', blank=True)
    damage_formula = models.CharField('Fórmula de dano', max_length=50, blank=True)
    equipped = models.BooleanField('Equipado', default=False)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Item do Inventário'
        verbose_name_plural = 'Itens do Inventário'
        ordering = ['name', 'id']

    def __str__(self):
        return f'{self.name} ×{self.quantity}'


class Npc(models.Model):
    """Personagem encontrado na campanha (NPC), com afeto e anotações."""

    AFFECTION_MAX = 3

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='npcs'
    )
    name = models.CharField('Nome', max_length=120)
    affection = models.PositiveSmallIntegerField('Afeto (0 a 3)', default=0)
    notes = models.TextField('Anotações', blank=True)
    photo = models.FileField('Foto', upload_to='npcs/', blank=True, null=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Personagem (NPC)'
        verbose_name_plural = 'Personagens (NPCs)'
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class UndoSnapshot(models.Model):
    """Estado da ficha antes de uma ação, para permitir desfazê-la."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='undo_snapshots'
    )
    label = models.CharField('Ação', max_length=255)
    data = models.JSONField('Estado anterior')
    created_at = models.DateTimeField('Quando', auto_now_add=True)

    class Meta:
        verbose_name = 'Ponto de desfazer'
        verbose_name_plural = 'Pontos de desfazer'
        ordering = ['-id']

    def __str__(self):
        return self.label
