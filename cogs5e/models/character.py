"""
{'type': 'dicecloud',
 'version': 6, #v6: added stat cvars
 'stats': stats,
 'levels': levels,
 'hp': int(hp),
 'armor': int(armor),
 'attacks': attacks,
 'skills': skills,
 'resist': resistances,
 'immune': immunities,
 'vuln': vulnerabilities,
 'saves': saves,
 'stat_cvars': stat_vars,
 'overrides': {},
 'cvars': {}}
"""
import asyncio
import logging
import random
import re

import MeteorClient
import discord

from cogs5e.funcs.dice import roll
from cogs5e.funcs.scripting import ScriptingEvaluator
from cogs5e.models.caster import Spellcaster, Spellcasting
from cogs5e.models.dicecloud.client import DicecloudClient
from cogs5e.models.errors import ConsumableNotFound, CounterOutOfBounds, InvalidArgument, InvalidSpellLevel, \
    NoCharacter, NoReset, OutdatedSheet
from utils.functions import get_selection

log = logging.getLogger(__name__)

SKILL_MAP = {'acrobatics': 'dexterity', 'animalHandling': 'wisdom', 'arcana': 'intelligence', 'athletics': 'strength',
             'deception': 'charisma', 'history': 'intelligence', 'initiative': 'dexterity', 'insight': 'wisdom',
             'intimidation': 'charisma', 'investigation': 'intelligence', 'medicine': 'wisdom',
             'nature': 'intelligence', 'perception': 'wisdom', 'performance': 'charisma',
             'persuasion': 'charisma', 'religion': 'intelligence', 'sleightOfHand': 'dexterity', 'stealth': 'dexterity',
             'survival': 'wisdom', 'strengthSave': 'strength', 'dexteritySave': 'dexterity',
             'constitutionSave': 'constitution', 'intelligenceSave': 'intelligence', 'wisdomSave': 'wisdom',
             'charismaSave': 'charisma',
             'strength': 'strength', 'dexterity': 'dexterity', 'constitution': 'constitution',
             'intelligence': 'intelligence', 'wisdom': 'wisdom', 'charisma': 'charisma'}
CLASS_RESOURCES = ("expertiseDice", "ki", "rages", "sorceryPoints", "superiorityDice")

#rekaj generated skill aliases
SKILL_ALIASES = {'investigate':'investigation', 'persuade':'persuasion', 'intimidate':'intimidation',
                 'deceive':"deception","lie":"deception", "survive":"survival",
                 "swim":"athletics", "grapple":"athletics", "climb": "athletics",
                 "act":"performance","paint":"performance","sculpt":"performance","play":"performance"}


class Character(Spellcaster):
    def __init__(self, _dict, _id):
        self.character = _dict
        self.id = _id
        self.live = self.character.get('live') and self.character.get('type') == 'dicecloud'

        spellcasting = Spellcasting(self.get_spell_list(), self.get_save_dc(), self.get_spell_ab(), self.get_level())
        super(Character, self).__init__(spellcasting)

    @classmethod
    async def from_ctx(cls, ctx):
        active_character = await ctx.bot.mdb.characters.find_one({"owner": str(ctx.author.id), "active": True})
        if active_character is None:
            raise NoCharacter()
        return cls(active_character, active_character['upstream'])

    @classmethod
    async def from_bot_and_ids(cls, bot, author_id, character_id):
        character = await bot.mdb.characters.find_one({"owner": author_id, "upstream": character_id})
        if character is None:
            raise NoCharacter()
        return cls(character, character_id)

    def get_name(self):
        return self.character.get('stats', {}).get('name', "Unnamed")

    def get_image(self):
        return self.character.get('stats', {}).get('image', '')

    def get_color(self):
        return self.character.get('settings', {}).get('color') or random.randint(0, 0xffffff)

    def get_ac(self):
        return self.character['armor']

    def get_resists(self):
        """
        Gets the resistances of a character.
        :return: The resistances, immunities, and vulnerabilites of a character.
        :rtype: dict
        """
        return {'resist': self.character['resist'], 'immune': self.character['immune'], 'vuln': self.character['vuln']}

    def get_max_hp(self):
        return self.character.get('hp', 0)

    def get_level(self):
        """@:returns int - the character's total level."""
        return self.character.get('levels', {}).get('level', 0)

    def get_prof_bonus(self):
        """@:returns int - the character's proficiency bonus."""
        return self.character.get('stats', {}).get('proficiencyBonus', 0)

    def get_stats(self):
        """@:returns dict - the character's stats."""
        return self.character.get('stats', {})

    def get_mod(self, stat):
        """
        Gets the character's stat modifier for a core stat.
        :param stat: The core stat to get. Can be of the form "cha", "charisma", or "charismaMod".
        :return: The character's relevant stat modifier.
        """
        valid = ["strengthMod", "dexterityMod", "constitutionMod", "intelligenceMod", "wisdomMod", "charismaMod"]
        if not any(stat in s for s in valid):
            raise ValueError(f"{stat} is not a valid stat.")
        return self.get_stats()[next(s for s in valid if stat in s)]

    def get_saves(self):
        """@:returns dict - the character's saves and modifiers."""
        return self.character.get('saves', {})

    def get_skills(self):
        """@:returns dict - the character's skills and modifiers."""
        return self.character.get('skills', {})

    def get_skill_effects(self):
        """@:returns dict - the character's skill effects and modifiers."""
        return self.character.get('skill_effects', {})

    def get_attacks(self):
        """@:returns list - the character's list of attack dicts."""
        return self.character.get('attacks', []) + self.get_override('attacks', [])

    def get_max_spellslots(self, level: int):
        """@:returns the maximum number of spellslots of level level a character has.
        @:returns 0 if none.
        @:raises OutdatedSheet if character does not have spellbook."""
        try:
            assert 'spellbook' in self.character
        except AssertionError:
            raise OutdatedSheet()

        return int(self.character.get('spellbook', {}).get('spellslots', {}).get(str(level), 0))

    def get_raw_spells(self):
        return self.character.get('spellbook', {}).get('spells', [])

    def get_spell_list(self):
        """@:returns list - a list of the names of all spells the character can cast.
        @:raises OutdatedSheet if character does not have spellbook."""
        try:
            assert 'spellbook' in self.character
        except AssertionError:
            raise OutdatedSheet()
        spells = self.get_raw_spells()
        out = []
        for spell in spells:
            if isinstance(spell, dict):
                out.append(spell['name'])
            else:
                out.append(spell)
        return out

    def get_cached_spell_list_id(self):
        """Gets the Dicecloud ID of the most recently used spell list ID.
        Returns None if v12 or earlier, not a DC sheet, or not set."""
        return self.character.get('spellbook', {}).get('dicecloud_id')

    def update_cached_spell_list_id(self, new_id):
        """Updates the cached Dicecloud spell list ID."""
        if not 'spellbook' in self.character:
            raise OutdatedSheet()
        self.character['spellbook']['dicecloud_id'] = new_id

    def get_save_dc(self):
        """@:returns int - the character's spell save DC.
        @:raises OutdatedSheet if character does not have spellbook."""
        try:
            assert 'spellbook' in self.character
        except AssertionError:
            raise OutdatedSheet()

        return self.character.get('spellbook', {}).get('dc', 0)

    def get_spell_ab(self):
        """@:returns int - the character's spell attack bonus.
        @:raises OutdatedSheet if character does not have spellbook."""
        try:
            assert 'spellbook' in self.character
        except AssertionError:
            raise OutdatedSheet()

        return self.character.get('spellbook', {}).get('attackBonus', 0)

    def get_setting(self, setting, default=None):
        """Gets the value of a csetting.
        @:returns the csetting's value, or default."""
        setting = self.character.get('settings', {}).get(setting)
        if setting is None: return default
        return setting

    def set_setting(self, setting, value):
        """Sets the value of a csetting.
                @:returns self"""
        if self.character.get('settings') is None:
            self.character['settings'] = {}
        self.character['settings'][setting] = value
        return self

    def get_override(self, override, default):
        return self.character.get('overrides', {}).get(override, default)

    def set_override(self, override, value):
        if not 'overrides' in self.character:
            self.character['overrides'] = {}
        self.character['overrides'][override] = value

    async def parse_cvars(self, cstr, ctx):
        """Parses cvars.
        :param ctx: The Context the cvar is parsed in.
        :param cstr: The string to parse.
        :returns string - the parsed string."""
        evaluator = await (await ScriptingEvaluator.new(ctx)).with_character(self)

        out = await asyncio.get_event_loop().run_in_executor(None, evaluator.parse, cstr)
        await evaluator.run_commits()

        return out

    def evaluate_cvar(self, varstr):
        """Evaluates a cvar.
        :param varstr - the name of the cvar to parse.
        :returns int - the value of the cvar, or 0 if evaluation failed."""
        ops = r"([-+*/().<>=])"
        varstr = str(varstr).strip('<>{}')

        cvars = self.character.get('cvars', {})
        stat_vars = self.character.get('stat_cvars', {})
        stat_vars['spell'] = self.get_spell_ab() - self.get_prof_bonus()
        out = ""
        tempout = ''
        for substr in re.split(ops, varstr):
            temp = substr.strip()
            tempout += str(cvars.get(temp, temp)) + " "
        for substr in re.split(ops, tempout):
            temp = substr.strip()
            out += str(stat_vars.get(temp, temp)) + " "
        return roll(out).total

    def get_cvar(self, name):
        return self.character.get('cvars', {}).get(name)

    def set_cvar(self, name, val: str):
        """Sets a cvar to a string value."""
        if any(c in name for c in '/()[]\\.^$*+?|{}'):
            raise InvalidArgument("Cvar contains invalid character.")
        self.character['cvars'] = self.character.get('cvars', {})  # set value
        self.character['cvars'][name] = str(val)
        return self

    def get_cvars(self):
        return self.character.get('cvars', {})

    def get_stat_vars(self):
        return self.character.get('stat_cvars', {})

    async def commit(self, ctx):
        """Writes a character object to the database, under the contextual author."""
        data = self.character
        if 'active' not in data:
            data['active'] = False
        if 'upstream' not in data:
            data['upstream'] = self.id
        if 'owner' not in data:
            data['owner'] = str(ctx.author.id)
        if '_id' in data:
            del data['_id']  # potential duplicate issues in transferchar
        await ctx.bot.mdb.characters.update_one(
            {"owner": str(ctx.author.id), "upstream": self.id},
            {"$set": data},
            upsert=True
        )

    async def manual_commit(self, bot, author_id):
        data = self.character
        if 'active' not in data:
            data['active'] = False
        if 'upstream' not in data:
            data['upstream'] = self.id
        data['owner'] = author_id
        if '_id' in data:
            del data['_id']
        await bot.mdb.characters.update_one(
            {"owner": author_id, "upstream": self.id},
            {"$set": data},
            upsert=True
        )

    async def set_active(self, ctx):
        """Sets the character as active."""
        await ctx.bot.mdb.characters.update_many(
            {"owner": str(ctx.author.id), "active": True},
            {"$set": {"active": False}}
        )
        await ctx.bot.mdb.characters.update_one(
            {"owner": str(ctx.author.id), "upstream": self.id},
            {"$set": {"active": True}}
        )

    def initialize_consumables(self):
        """Initializes a character's consumable counters. Returns self."""
        try:
            assert self.character.get('consumables') is not None
        except AssertionError:
            self.character['consumables'] = {}
        self._initialize_hp()
        self._initialize_deathsaves()
        self._initialize_spellslots()
        return self

    def _initialize_hp(self):
        try:
            assert self.character.get('consumables') is not None
        except AssertionError:
            self.character['consumables'] = {}
        try:
            assert self.character['consumables'].get('hp') is not None
        except AssertionError:
            self.character['consumables']['hp'] = {'value': self.get_max_hp(), 'reset': 'long',
                                                   'max': self.get_max_hp(), 'min': 0}
        if self.character['consumables'].get('temphp') is None:
            self.character['consumables']['temphp'] = {'value': 0, 'reset': 'long',
                                                       'max': None, 'min': 0}

    def get_hp(self):
        """Returns the Counter dictionary."""
        self._initialize_hp()
        return self.character['consumables']['hp']

    def get_current_hp(self):
        """Returns the integer value of the remaining HP."""
        return self.get_hp()['value']

    def get_hp_str(self):
        hp = self.get_current_hp() - self.get_temp_hp()
        out = f"{hp}/{self.get_max_hp()}"
        if self.get_temp_hp():
            out += f' ({self.get_temp_hp()} temp)'
        return out

    def set_hp(self, newValue, ignore_temp=False):
        """Sets the character's hit points. Returns the Character object."""
        self._initialize_hp()
        hp = self.get_hp()
        if not ignore_temp:
            if self.get_temp_hp():
                delta = newValue - hp['value']  # hp includes all temp hp
                if delta < 0:  # don't add thp by adding to hp
                    self.set_temp_hp(max(self.get_temp_hp() + delta, 0))
        else:
            if self.get_temp_hp():
                newValue = newValue + self.get_temp_hp()
        self.character['consumables']['hp']['value'] = max(hp['min'], int(newValue))  # bounding

        self.on_hp()

        if self.live:
            self._sync_hp()

        return self

    def _sync_hp(self):
        def update_callback(error, data):
            if error:
                log.warning(error)
                if error.get('error') == 403:  # character no longer shared
                    self.character['live'] = False
                    self.live = False
            else:
                log.debug(data)

        try:
            DicecloudClient.getInstance().meteor_client.update('characters',
                                                               {'_id': self.id[10:]},
                                                               {'$set': {
                                                                   "hitPoints.adjustment":
                                                                       (self.get_current_hp() - self.get_max_hp())
                                                                       - self.get_temp_hp()}
                                                               }, callback=update_callback)
        except MeteorClient.MeteorClientException:
            pass

    def modify_hp(self, value, ignore_temp=False):
        """Modifies the character's hit points. Returns the Character object."""
        self.set_hp(self.get_current_hp() + value, ignore_temp)
        return self

    def reset_hp(self):
        """Resets the character's HP to max and THP to 0. Returns the Character object."""
        self.set_temp_hp(0)
        self.set_hp(self.get_max_hp())
        return self

    def get_temp_hp(self):
        self._initialize_hp()
        return self.character['consumables']['temphp']['value']

    def set_temp_hp(self, temp_hp):
        self._initialize_hp()
        hp = self.get_hp()
        delta = max(temp_hp - (self.get_temp_hp() or 0), -self.get_temp_hp())
        self.character['consumables']['temphp']['value'] = max(temp_hp, 0)
        self.character['consumables']['hp']['value'] = max(hp['min'], hp['value'] + delta)  # bounding
        return self

    def _initialize_deathsaves(self):
        try:
            assert self.character.get('consumables') is not None
        except AssertionError:
            self.character['consumables'] = {}
        try:
            assert self.character['consumables'].get('deathsaves') is not None
        except AssertionError:
            self.character['consumables']['deathsaves'] = {'fail': {'value': 0, 'reset': 'hp', 'max': 3, 'min': 0},
                                                           'success': {'value': 0, 'reset': 'hp', 'max': 3, 'min': 0}}

    def get_deathsaves(self):
        self._initialize_deathsaves()
        return self.character['consumables']['deathsaves']

    def get_ds_str(self):
        """
        :rtype: str
        :return: A bubble representation of a character's death saves.
        """
        ds = self.get_deathsaves()
        successes = '\u25c9' * ds['success']['value'] + '\u3007' * (3 - ds['success']['value'])
        fails = '\u3007' * (3 - ds['fail']['value']) + '\u25c9' * ds['fail']['value']
        return f"F {fails} | {successes} S"

    def add_successful_ds(self):
        """Adds a successful death save to the character.
        Returns True if the character is stable."""
        self._initialize_deathsaves()
        self.character['consumables']['deathsaves']['success']['value'] = min(3, self.character['consumables'][
            'deathsaves']['success']['value'] + 1)
        return self.character['consumables']['deathsaves']['success']['value'] == 3

    def add_failed_ds(self):
        """Adds a failed death save to the character.
        Returns True if the character is dead."""
        self._initialize_deathsaves()
        self.character['consumables']['deathsaves']['fail']['value'] = min(3, self.character['consumables'][
            'deathsaves']['fail']['value'] + 1)
        return self.character['consumables']['deathsaves']['fail']['value'] == 3

    def reset_death_saves(self):
        """Resets successful and failed death saves to 0. Returns the Character object."""
        self._initialize_deathsaves()
        self.character['consumables']['deathsaves']['success']['value'] = 0
        self.character['consumables']['deathsaves']['fail']['value'] = 0
        return self

    def _initialize_spellslots(self):
        """Sets up a character's spellslot consumables.
        @:raises OutdatedSheet if sheet does not have spellbook."""
        try:
            assert self.character.get('consumables') is not None
        except AssertionError:
            self.character['consumables'] = {}
        try:
            assert self.character['consumables'].get('spellslots') is not None
        except AssertionError:
            ss = {}
            for lvl in range(1, 10):
                m = self.get_max_spellslots(lvl)
                ss[str(lvl)] = {'value': m, 'reset': 'long', 'max': m, 'min': 0}
            self.character['consumables']['spellslots'] = ss

    def get_spellslots(self):
        """Returns the Counter dictionary."""
        self._initialize_spellslots()
        return self.character['consumables']['spellslots']

    def get_remaining_slots(self, level: int):
        """@:param level - The spell level.
        @:returns the integer value representing the number of spellslots remaining."""
        try:
            assert 0 <= level < 10
        except AssertionError:
            raise InvalidSpellLevel()
        if level == 0: return 1  # cantrips
        return int(self.get_spellslots()[str(level)]['value'])

    def get_remaining_slots_str(self, level: int = None):
        """@:param level: The level of spell slot to return.
        @:returns A string representing the character's remaining spell slots."""
        out = ''
        if level:
            assert 0 < level < 10
            _max = self.get_max_spellslots(level)
            remaining = self.get_remaining_slots(level)
            numEmpty = _max - remaining
            filled = '\u25c9' * remaining
            empty = '\u3007' * numEmpty
            out += f"`{level}` {filled}{empty}\n"
        else:
            for level in range(1, 10):
                _max = self.get_max_spellslots(level)
                remaining = self.get_remaining_slots(level)
                if _max:
                    numEmpty = _max - remaining
                    filled = '\u25c9' * remaining
                    empty = '\u3007' * numEmpty
                    out += f"`{level}` {filled}{empty}\n"
        if out == '':
            out = "No spell slots."
        return out

    def set_remaining_slots(self, level: int, value: int, sync: bool = True):
        """Sets the character's remaining spell slots of level level.
        @:param level - The spell level.
        @:param value - The number of remaining spell slots.
        @:returns self"""
        try:
            assert 0 < level < 10
        except AssertionError:
            raise InvalidSpellLevel()
        try:
            assert 0 <= value <= self.get_max_spellslots(level)
        except AssertionError:
            raise CounterOutOfBounds()

        self._initialize_spellslots()
        self.character['consumables']['spellslots'][str(level)]['value'] = int(value)

        if self.live and sync:
            self._sync_slots()

        return self

    def _sync_slots(self):
        def update_callback(error, data):
            if error:
                log.warning(error)
                if error.get('error') == 403:  # character no longer shared
                    self.character['live'] = False
                    self.live = False
            else:
                log.debug(data)

        spell_dict = {}
        for lvl in range(1, 10):
            spell_dict[f'level{lvl}SpellSlots.adjustment'] = self.get_remaining_slots(lvl) - self.get_max_spellslots(
                lvl)
        try:
            DicecloudClient.getInstance().meteor_client.update('characters', {'_id': self.id[10:]},
                                                               {'$set': spell_dict},
                                                               callback=update_callback)
        except MeteorClient.MeteorClientException:
            pass

    def use_slot(self, level: int):
        """Uses one spell slot of level level.
        @:returns self
        @:raises CounterOutOfBounds if there are no remaining slots of the requested level."""
        try:
            assert 0 <= level < 10
        except AssertionError:
            raise InvalidSpellLevel()
        if level == 0: return self
        ss = self.get_spellslots()
        val = ss[str(level)]['value'] - 1
        if val < ss[str(level)]['min']: raise CounterOutOfBounds()
        self.set_remaining_slots(level, val)
        return self

    def reset_spellslots(self):
        """Resets all spellslots to their max value.
        @:returns self"""
        for level in range(1, 10):
            self.set_remaining_slots(level, self.get_max_spellslots(level), False)
        self._sync_slots()
        return self

    def can_cast(self, spell, level) -> bool:
        return self.get_remaining_slots(level) > 0 and spell.name in self.spellcasting.spells

    def cast(self, spell, level):
        self.use_slot(level)

    def remaining_casts_of(self, spell, level):
        return self.get_remaining_slots_str(level)

    def _initialize_spellbook(self):
        """Sets up a character's spellbook override.
        @:raises OutdatedSheet if sheet does not have spellbook."""
        try:
            assert self.character.get('spellbook') is not None
        except AssertionError:
            raise OutdatedSheet()

    def _initialize_spell_overrides(self):
        """Sets up a character's spell overrides."""
        try:
            assert self.character.get('overrides') is not None
        except AssertionError:
            self.character['overrides'] = {}
        if not 'spells' in self.character['overrides']:
            self.character['overrides']['spells'] = []

    def add_known_spell(self, spell):
        """Adds a spell to the character's known spell list.
        :param spell (Spell) - the Spell.
        :returns self"""
        self._initialize_spellbook()
        self.character['spellbook']['spells'].append({
            'name': spell.name,
            'strict': spell.source != 'homebrew'
        })

        if not self.live:
            self._initialize_spell_overrides()
            self.character['overrides']['spells'].append({
                'name': spell.name,
                'strict': spell.source != 'homebrew'
            })
        return self

    def remove_known_spell(self, spell_name):
        """
        Removes a spell from the character's spellbook override.
        :param spell_name: (str) The name of the spell to remove.
        :return: (str) The name of the removed spell.
        """
        self._initialize_spellbook()
        self._initialize_spell_overrides()

        override = next((s for s in self.character['overrides'].get('spells', [])
                         if isinstance(s, str) and spell_name.lower() == s.lower() or
                         isinstance(s, dict) and s['name'].lower() == spell_name.lower()), None)
        if override:
            self.character['overrides']['spells'].remove(override)
            if override in self.character['spellbook']['spells']:
                self.character['spellbook']['spells'].remove(override)
        return override

    def _initialize_custom_counters(self):
        try:
            assert self.character.get('consumables') is not None
        except AssertionError:
            self.character['consumables'] = {}
        try:
            assert self.character['consumables'].get('custom') is not None
        except AssertionError:
            self.character['consumables']['custom'] = {}

    def create_consumable(self, name, **kwargs):
        """Creates a custom consumable, returning the character object."""
        self._initialize_custom_counters()
        _max = kwargs.get('maxValue')
        _min = kwargs.get('minValue')
        _reset = kwargs.get('reset')
        _type = kwargs.get('displayType')
        _live_id = kwargs.get('live')
        if not (_reset in ('short', 'long', 'none') or _reset is None):
            raise InvalidArgument("Invalid reset.")
        if any(c in name for c in ".$"):
            raise InvalidArgument("Invalid character in CC name.")
        if _max is not None and _min is not None:
            maxV = self.evaluate_cvar(_max)
            try:
                assert maxV >= self.evaluate_cvar(_min)
            except AssertionError:
                raise InvalidArgument("Max value is less than min value.")
            if maxV == 0:
                raise InvalidArgument("Max value cannot be 0.")
        if _reset and _max is None: raise InvalidArgument("Reset passed but no maximum passed.")
        if _type == 'bubble' and (_max is None or _min is None): raise InvalidArgument(
            "Bubble display requires a max and min value.")
        newCounter = {'value': self.evaluate_cvar(_max) or 0}
        if _max is not None: newCounter['max'] = _max
        if _min is not None: newCounter['min'] = _min
        if _reset and _max is not None: newCounter['reset'] = _reset
        newCounter['type'] = _type
        newCounter['live'] = _live_id
        log.debug(f"Creating new counter {newCounter}")

        self.character['consumables']['custom'][name] = newCounter

        return self

    def set_consumable(self, name, newValue: int, strict=False):
        """Sets the value of a character's consumable, returning the Character object.
        Raises CounterOutOfBounds if newValue is out of bounds."""
        self._initialize_custom_counters()
        try:
            assert self.character['consumables']['custom'].get(name) is not None
        except AssertionError:
            raise ConsumableNotFound()
        try:
            _min = self.evaluate_cvar(self.character['consumables']['custom'][name].get('min', str(-(2 ** 32))))
            _max = self.evaluate_cvar(self.character['consumables']['custom'][name].get('max', str(2 ** 32 - 1)))
            if strict:
                assert _min <= int(newValue) <= _max
            else:
                newValue = min(max(_min, int(newValue)), _max)

        except AssertionError:
            raise CounterOutOfBounds()
        self.character['consumables']['custom'][name]['value'] = int(newValue)

        if self.character['consumables']['custom'][name].get('live') and self.live:
            used = _max - newValue
            self._sync_consumable(self.character['consumables']['custom'][name], used)

        return self

    def _sync_consumable(self, counter, used):
        """Syncs a consumable's uses with dicecloud."""

        def update_callback(error, data):
            if error:
                log.warning(error)
                if error.get('error') == 403:  # character no longer shared
                    self.character['live'] = False  # this'll be committed since we're modifying something to sync
                    self.live = False
            else:
                log.debug(data)

        try:
            if counter['live'] in CLASS_RESOURCES:
                DicecloudClient.getInstance().meteor_client.update('characters', {'_id': self.id[10:]},
                                                                   {'$set': {f"{counter['live']}.adjustment": -used}},
                                                                   callback=update_callback)
            else:
                DicecloudClient.getInstance().meteor_client.update('features', {'_id': counter['live']},
                                                                   {'$set': {"used": used}},
                                                                   callback=update_callback)
        except MeteorClient.MeteorClientException:
            pass

    def get_consumable(self, name):
        """Returns the dict object of the consumable, or raises NoConsumable."""
        custom_counters = self.character.get('consumables', {}).get('custom', {})
        counter = custom_counters.get(name)
        if counter is None: raise ConsumableNotFound()
        return counter

    def get_consumable_value(self, name):
        """@:returns int - the integer value of the consumable."""
        return int(self.get_consumable(name).get('value', 0))

    async def select_consumable(self, ctx, name):
        """@:param name (str): The name of the consumable to search for.
        @:returns dict - the consumable.
        @:raises ConsumableNotFound if the consumable does not exist."""
        custom_counters = self.character.get('consumables', {}).get('custom', {})
        choices = [(cname, counter) for cname, counter in custom_counters.items() if cname.lower() == name.lower()]
        if not choices:
            choices = [(cname, counter) for cname, counter in custom_counters.items() if name.lower() in cname.lower()]
        if not choices:
            raise ConsumableNotFound()
        else:
            return await get_selection(ctx, choices, return_name=True)

    def get_all_consumables(self):
        """Returns the dict object of all custom counters."""
        custom_counters = self.character.get('consumables', {}).get('custom', {})
        return custom_counters

    def delete_consumable(self, name):
        """Deletes a consumable. Returns the Character object."""
        custom_counters = self.character.get('consumables', {}).get('custom', {})
        try:
            del custom_counters[name]
        except KeyError:
            raise ConsumableNotFound()
        self.character['consumables']['custom'] = custom_counters
        return self

    def reset_consumable(self, name):
        """Resets a consumable to its maximum value, if applicable.
        Returns the Character object."""
        counter = self.get_consumable(name)
        if counter.get('reset') == 'none': raise NoReset()
        if counter.get('max') is None: raise NoReset()

        self.set_consumable(name, self.evaluate_cvar(counter.get('max')))

        return self

    def _reset_custom(self, scope):
        """Resets custom counters with given scope."""
        reset = []
        for name, value in self.character.get('consumables', {}).get('custom', {}).items():
            if value.get('reset') == scope:
                try:
                    self.reset_consumable(name)
                except NoReset:
                    pass
                else:
                    reset.append(name)
        return reset

    def on_hp(self):
        """Resets all applicable consumables.
        Returns a list of the names of all reset counters."""
        reset = []
        reset.extend(self._reset_custom('hp'))
        if self.get_current_hp() > 0:  # lel
            self.reset_death_saves()
            reset.append("Death Saves")
        return reset

    def short_rest(self):
        """Resets all applicable consumables.
        Returns a list of the names of all reset counters."""
        reset = []
        reset.extend(self.on_hp())
        reset.extend(self._reset_custom('short'))
        if self.get_setting('srslots', False):
            self.reset_spellslots()
            reset.append("Spell Slots")
        return reset

    def long_rest(self):
        """Resets all applicable consumables.
        Returns a list of the names of all reset counters."""
        reset = []
        reset.extend(self.on_hp())
        reset.extend(self.short_rest())
        reset.extend(self._reset_custom('long'))
        self.reset_hp()
        reset.append("HP")
        if not self.get_setting('srslots', False):
            self.reset_spellslots()
            reset.append("Spell Slots")
        return reset

    def reset_all_consumables(self):
        """Resets all applicable consumables.
        Returns a list of the names of all reset counters."""
        reset = []
        reset.extend(self.on_hp())
        reset.extend(self.short_rest())
        reset.extend(self.long_rest())
        reset.extend(self._reset_custom(None))
        return reset

    def join_combat(self, channel_id):
        """
        Puts the character into combat.
        :param channel_id: The channel id of the combat
        :return: self
        """
        self.character['combat'] = channel_id
        return self

    def leave_combat(self):
        """
        Removes the character from all combats.
        :return: self
        """
        if 'combat' in self.character:
            del self.character['combat']
        return self

    def get_combat_id(self):
        """
        :return: The channel id if the character is in combat, or None.
        """
        return self.character.get('combat')

    def get_sheet_embed(self):
        stats = self.get_stats()
        hp = self.get_max_hp()
        skills = self.get_skills()
        attacks = self.get_attacks()
        saves = self.get_saves()
        skill_effects = self.get_skill_effects()

        resists = self.get_resists()
        resist = resists['resist']
        immune = resists['immune']
        vuln = resists['vuln']
        resistStr = ''
        if len(resist) > 0:
            resistStr += "\nResistances: " + ', '.join(resist).title()
        if len(immune) > 0:
            resistStr += "\nImmunities: " + ', '.join(immune).title()
        if len(vuln) > 0:
            resistStr += "\nVulnerabilities: " + ', '.join(vuln).title()

        embed = discord.Embed()
        embed.colour = self.get_color()
        embed.title = self.get_name()
        embed.set_thumbnail(url=self.get_image())

        embed.add_field(name="HP/Level", value=f"**HP:** ||{hp}\nLevel {self.get_level()}{resistStr}||")
        embed.add_field(name="AC", value="||"+str(self.get_ac())+"||")

        embed.add_field(name="Stats", value="||**STR:** {strength} ({strengthMod:+})\n" \
                                            "**DEX:** {dexterity} ({dexterityMod:+})\n" \
                                            "**CON:** {constitution} ({constitutionMod:+})\n" \
                                            "**INT:** {intelligence} ({intelligenceMod:+})\n" \
                                            "**WIS:** {wisdom} ({wisdomMod:+})\n" \
                                            "**CHA:** {charisma} ({charismaMod:+})||".format(**stats))

        savesStr = ''
        for save in ('strengthSave', 'dexteritySave', 'constitutionSave', 'intelligenceSave', 'wisdomSave',
                     'charismaSave'):
            if skill_effects.get(save):
                skill_effect = f"({skill_effects.get(save)})"
            else:
                skill_effect = ''
            savesStr += '**{}**: ||{:+} {}\n||'.format(save[:3].upper(), saves.get(save), skill_effect)

        embed.add_field(name="Saves", value=savesStr)

        def cc_to_normal(string):
            return re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', string)

        skillsStr = '||'
        for skill, mod in sorted(skills.items()):
            if 'Save' not in skill:
                if skill_effects.get(skill):
                    skill_effect = f"({skill_effects.get(skill)})"
                else:
                    skill_effect = ''
                skillsStr += '**{}**: {:+} {}\n'.format(cc_to_normal(skill), mod, skill_effect)
        skillsStr = skillsStr + "||"

        embed.add_field(name="Skills", value=skillsStr.title())

        tempAttacks = []
        for a in attacks:
            damage = a['damage'] if a['damage'] is not None else 'no'
            if a['attackBonus'] is not None:
                bonus = a['attackBonus']
                tempAttacks.append(f"**{a['name']}:** +{bonus} To Hit, {damage} damage.")
            else:
                tempAttacks.append(f"**{a['name']}:** {damage} damage.")
        if not tempAttacks:
            tempAttacks = ['No attacks.']
        a = '\n'.join(tempAttacks)
        if len(a) > 1023:
            a = ', '.join(atk['name'] for atk in attacks)
        if len(a) > 1023:
            a = "Too many attacks, values hidden!"
        hide_a = "||"+a+"||"
        embed.add_field(name="Attacks", value=hide_a)

        return embed
