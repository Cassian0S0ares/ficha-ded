"""Registro dos modelos no admin do Django."""

from django.contrib import admin

from .models import ActivityLog, Character, DiceRoll, Spell, SpellSlot


class SpellSlotInline(admin.TabularInline):
    model = SpellSlot
    extra = 0


class SpellInline(admin.TabularInline):
    model = Spell
    extra = 0


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'class_name', 'subclass', 'level',
                    'current_hp', 'max_hp', 'effective_ac')
    list_filter = ('class_name', 'subclass', 'race')
    search_fields = ('name', 'owner__username')
    inlines = [SpellSlotInline, SpellInline]


@admin.register(Spell)
class SpellAdmin(admin.ModelAdmin):
    list_display = ('name', 'character', 'spell_level', 'is_domain_spell',
                    'requires_concentration')
    list_filter = ('spell_level', 'is_domain_spell', 'requires_concentration')
    search_fields = ('name',)


@admin.register(SpellSlot)
class SpellSlotAdmin(admin.ModelAdmin):
    list_display = ('character', 'level', 'current', 'maximum')
    list_filter = ('level',)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('character', 'action', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('action',)


@admin.register(DiceRoll)
class DiceRollAdmin(admin.ModelAdmin):
    list_display = ('character', 'dice', 'result', 'detail', 'created_at')
    list_filter = ('dice', 'created_at')
