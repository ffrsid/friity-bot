import os
import re
import uuid
import json
import random
import asyncio
import pathlib
import discord
import aiohttp
from discord import app_commands
from groq import AsyncGroq
from datetime import datetime, timezone
from collections import defaultdict
from threading import Thread
from flask import Flask

# ─────────────────────────────────────────────
#  C O N F I G
# ─────────────────────────────────────────────

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GROQ_API_KEY      = os.environ["GROQ_API_KEY"]
APPLICATION_ID    = int(os.environ.get("APPLICATION_ID", "1484975523510747348"))
GUILD_ID          = 1497005878153449634

groq_client = AsyncGroq(api_key=GROQ_API_KEY)
DISCORD_API_BASE   = "https://discord.com/api/v10"
COMPONENTS_V2_FLAG = 32768

CHANNEL_RULES       = 1497011818055467069
CHANNEL_PUNISHMENTS = 1497364541024112720
CHANNEL_OVERVIEW    = 1497364673379700848

STAFF_ALLOWED = {1162798183068467220, 1025178585104920656, 1497342710481420324, 1497342394499072080}
EMBED_ALLOWED = {1162798183068467220, 1025178585104920656}
ALLOWED_ROLES = {1497009109101183107}

TRYOUTER_ROLE_ID  = 1447060651003346995
POLL_ROLE_ID      = 1490466480318582804
POLL_PING_ROLE_ID = 1490463201450655835
POLL_CHANNEL_ID   = 1490463944245117108
POLL_NOTIF_CH     = 1490463201450655835
REQUIRED_ROLE_ID  = 1497010109824499923

# ─────────────────────────────────────────────
#  F L A S K
# ─────────────────────────────────────────────

flask_app = Flask('')

@flask_app.route('/')
def home(): return "Friity — Awaken Reborns — Online"

def keep_alive():
    t = Thread(target=lambda: flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))))
    t.daemon = True; t.start()

# ─────────────────────────────────────────────
#  B O T
# ─────────────────────────────────────────────

class FriityBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"[SYNC] Slash commands synced to guild {GUILD_ID}")

client = FriityBot()
BOT_OWNER_ID: int | None = None

@client.tree.error
async def on_app_command_error(interaction, error):
    print(f"[TREE ERROR] {type(error).__name__}: {error}")
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)
    except:
        pass

def has_perm(member):
    if member.guild_permissions.administrator: return True
    return any(r.id in ALLOWED_ROLES for r in member.roles) or member.id in STAFF_ALLOWED

# ─────────────────────────────────────────────
#  A P I   H E L P E R S
# ─────────────────────────────────────────────

async def api_post(channel_id, payload):
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            try: return await r.json()
            except: return {}

async def ia_respond(interaction, payload):
    url = f"{DISCORD_API_BASE}/interactions/{interaction.id}/{interaction.token}/callback"
    async with aiohttp.ClientSession() as s:
        await s.post(url, json={"type": 4, "data": payload}, headers={"Content-Type": "application/json"})

async def ia_update(interaction, payload):
    url = f"{DISCORD_API_BASE}/interactions/{interaction.id}/{interaction.token}/callback"
    async with aiohttp.ClientSession() as s:
        await s.post(url, json={"type": 7, "data": payload}, headers={"Content-Type": "application/json"})

async def ia_defer(interaction):
    url = f"{DISCORD_API_BASE}/interactions/{interaction.id}/{interaction.token}/callback"
    async with aiohttp.ClientSession() as s:
        await s.post(url, json={"type": 6}, headers={"Content-Type": "application/json"})

async def ia_followup(interaction, content):
    url = f"{DISCORD_API_BASE}/webhooks/{APPLICATION_ID}/{interaction.token}"
    async with aiohttp.ClientSession() as s:
        await s.post(url, json={"content": content, "flags": 64}, headers={"Content-Type": "application/json"})

async def ia_edit(interaction, payload):
    url = f"{DISCORD_API_BASE}/webhooks/{APPLICATION_ID}/{interaction.token}/messages/@original"
    async with aiohttp.ClientSession() as s:
        await s.patch(url, json=payload, headers={"Content-Type": "application/json"})

async def ia_modal(interaction, custom_id, title, components):
    url = f"{DISCORD_API_BASE}/interactions/{interaction.id}/{interaction.token}/callback"
    async with aiohttp.ClientSession() as s:
        await s.post(url, json={"type": 9, "data": {"custom_id": custom_id, "title": title, "components": components}}, headers={"Content-Type": "application/json"})

async def ia_followup_rich(interaction, payload):
    url = f"{DISCORD_API_BASE}/webhooks/{APPLICATION_ID}/{interaction.token}"
    async with aiohttp.ClientSession() as s:
        await s.post(url, json=payload, headers={"Content-Type": "application/json"})

# ─────────────────────────────────────────────
#  W E B H O O K   H E L P E R S
# ─────────────────────────────────────────────

async def get_or_create_webhook(channel_id):
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/webhooks"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            webhooks = await r.json()
            if isinstance(webhooks, list):
                for wh in webhooks:
                    if wh.get("name") == "Friity Embed":
                        return wh["id"], wh["token"]
        async with s.post(url, json={"name": "Friity Embed"}, headers=headers) as r:
            wh = await r.json()
            return wh.get("id"), wh.get("token")

async def webhook_send(channel_id, payload, username=None, avatar_url=None):
    wh_id, wh_token = await get_or_create_webhook(channel_id)
    if not wh_id or not wh_token:
        return await api_post(channel_id, payload)
    url = f"{DISCORD_API_BASE}/webhooks/{wh_id}/{wh_token}?wait=true"
    data = {**payload}
    if username: data["username"] = username
    if avatar_url: data["avatar_url"] = avatar_url
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=data, headers={"Content-Type": "application/json"}) as r:
            try: return await r.json()
            except: return {}

# ─────────────────────────────────────────────
#  E M B E D   P A Y L O A D S
# ─────────────────────────────────────────────

LANG_OPTIONS = [
    {"label": "English",   "value": "en", "emoji": {"id": "1499826848035766454", "name": "emoji_3"}},
    {"label": "Español",   "value": "es", "emoji": {"id": "1499826873226629241", "name": "emoji_5"}},
    {"label": "Português", "value": "pt", "emoji": {"id": "1499826860794708069", "name": "emoji_4"}},
]

PUNISHMENTS_CONTENT = {
    "en": (
        "## CELESTIALS DRAGONS  ╱  SANCTIONS SYSTEM\n"
        "-# ╰─ All sanctions are applied based on severity and member history.\n\n"
        "**I.  WARNING** ─ Formal warning. Three warns = blacklist 1 month.\n"
        "**II.  MUTE** ─ Temporary removal of communication privileges.\n"
        "**III.  TEMP BAN** ─ First = 1 month. Increases until permanent.\n"
        "**IV.  PERM BAN** ─ No appeal. For severe violations.\n\n"
        "**─ Strict violations (immediate perm ban) ─**\n"
        "Leaks · Doxxing · Grooming · CP jokes · Threats\n\n"
        "-# ╰─ Awaken Reborns  ·  Punishments"
    ),
    "es": (
        "## CELESTIALS DRAGONS  ╱  SISTEMA DE SANCIONES\n"
        "-# ╰─ Todas las sanciones se aplican según gravedad e historial.\n\n"
        "**I.  ADVERTENCIA** ─ Advertencia formal. Tres = blacklist 1 mes.\n"
        "**II.  MUTE** ─ Eliminación temporal de privilegios de comunicación.\n"
        "**III.  BAN TEMP** ─ Primera = 1 mes. Incrementa hasta permanente.\n"
        "**IV.  BAN PERM** ─ Sin apelación. Para violaciones graves.\n\n"
        "**─ Violaciones estrictas (ban inmediato) ─**\n"
        "Leaks · Doxxing · Grooming · CP jokes · Amenazas\n\n"
        "-# ╰─ Awaken Reborns  ·  Punishments"
    ),
    "pt": (
        "## CELESTIALS DRAGONS  ╱  SISTEMA DE SANÇÕES\n"
        "-# ╰─ Todas as sanções são aplicadas com base na gravidade e histórico.\n\n"
        "**I.  AVISO** ─ Aviso formal. Três = blacklist 1 mês.\n"
        "**II.  MUTE** ─ Remoção temporária dos privilégios de comunicação.\n"
        "**III.  BAN TEMP** ─ Primeira = 1 mês. Aumenta até permanente.\n"
        "**IV.  BAN PERM** ─ Sem apelação. Para violações graves.\n\n"
        "**─ Violações estritas (ban imediato) ─**\n"
        "Leaks · Doxxing · Grooming · CP jokes · Ameaças\n\n"
        "-# ╰─ Awaken Reborns  ·  Punishments"
    ),
}

def build_pun_accept():
    return {"flags": 1 << 15, "components": [{"type": 17, "components": [
        {"type": 10, "content": "─ By accepting, you acknowledge that you have read and understood the punishment system of **Awaken Reborns**.\n╰─ Violations will result in the sanctions described ─ ignorance is __not__ an excuse."},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 9, "components": [{"type": 10, "content": "-# ╰─ Tap to confirm you understand."}],
         "accessory": {"type": 2, "style": 3, "label": "Accepted", "custom_id": "accept_punishments", "emoji": {"id": "1497991468584014025", "name": "emoji_2"}}}
    ]}]}

def build_pun_lang():
    return {"flags": 1 << 15, "components": [
        {"type": 17, "components": [
            {"type": 10, "content": "─ Choose your language to view the punishment system.\n╰─ The content will be shown below."},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": "-# ╰─ Select your language below."}
        ]},
        {"type": 1, "components": [{"type": 3, "custom_id": "punish_lang_select", "placeholder": "Select your language...", "options": LANG_OPTIONS}]}
    ]}

def build_pun_content(lang):
    return {"flags": 1 << 15, "components": [
        {"type": 17, "components": [{"type": 10, "content": PUNISHMENTS_CONTENT[lang]}]},
        {"type": 1, "components": [{"type": 2, "style": 1, "label": "Back", "custom_id": "back_to_langs"}]}
    ]}

def build_rules_embed():
    return {"flags": COMPONENTS_V2_FLAG, "components": [
        {"type": 17, "components": [
            {"type": 12, "items": [{"media": {"url": "https://cdn.discordapp.com/attachments/1451654847408373947/1495469836598378576/1776618183605.jpg"}}]},
            {"type": 14, "spacing": 2},
            {"type": 10, "content": "## <:emoji_57:1495457372691365899> Awaken Reborns | Rules\n*** Welcome to Awaken Reborns! Please select your language to read the clan rules. ***\n[Discord Terms of Service](https://discord.com/terms)"},
            {"type": 14, "spacing": 2},
            {"type": 9, "components": [{"type": 10, "content": "<:emoji_44:1489765823533809674>  ** Selecciona Español **"}], "accessory": {"type": 2, "style": 5, "label": "Español", "emoji": {"id": "1489666661228347526", "name": "Esp"}, "url": f"https://discord.com/channels/{GUILD_ID}/1489768820632588419"}},
            {"type": 14, "divider": False},
            {"type": 9, "components": [{"type": 10, "content": "<:emoji_44:1489765823533809674> ** Select English **"}], "accessory": {"type": 2, "style": 5, "label": "English", "emoji": {"id": "1489667788820971730", "name": "EEUU"}, "url": f"https://discord.com/channels/{GUILD_ID}/1489768537982500895"}},
            {"type": 14},
            {"type": 9, "components": [{"type": 10, "content": "<:emoji_44:1489765823533809674> ** Selecione Português **"}], "accessory": {"type": 2, "style": 5, "label": "Português", "emoji": {"id": "1489666119689306276", "name": "emoji_40"}, "url": f"https://discord.com/channels/{GUILD_ID}/1489769065135214704"}},
            {"type": 14},
            {"type": 10, "content": "** Check the other channels for more information. **"},
        ]},
        {"type": 17, "components": [{"type": 1, "components": [{"type": 3, "custom_id": "menu_canales", "placeholder": "Channels", "min_values": 1, "max_values": 1, "options": [
            {"label": "punishments", "value": str(CHANNEL_PUNISHMENTS), "description": "Go to Punishments"},
            {"label": "overview",    "value": str(CHANNEL_OVERVIEW),    "description": "Go to Overview"},
        ]}]}]}
    ]}

def build_overview_embed():
    return {"flags": 1 << 15, "components": [{"type": 17, "components": [{"type": 10, "content": (
        "## CELESTIALS DRAGONS  ╱  OVERVIEW\n"
        "-# ╰─ Welcome to Awaken Reborns.\n\n"
        "─ Official competitive TSB clan in **TSBL** (TSB LATAM).\n"
        "─ Competing in SAE (East) and SAW (West) regions.\n\n"
        f"**─ Channels ─**\n<#{CHANNEL_RULES}> ─ Rules\n<#{CHANNEL_PUNISHMENTS}> ─ Punishments\n\n"
        "-# ╰─ Awaken Reborns  ·  Overview"
    )}]}]}

# ─────────────────────────────────────────────
#  S T A F F   P A N E L   P A Y L O A D S
# ─────────────────────────────────────────────

CMD_DETAILS = {
    "tier": {
        "en": "## `>tier` ─ Assign Phases\n```\n>tier <phase> <subtier> <class> [@user] <region> [note: text]\n```\n**Phases:** `0` `1` `2` `3` `4` `5` `app`\n**Subtiers:** `low` `mid` `high`\n**Classes:** `weak` `stable` `strong`\n**Regions:** `sp` `mi` `da` `la`\n\n**Example:**\n```\n>tier 1 high stable @player sp note: great performance\n```\n╰─ Requires **TRYOUTER** role.",
        "es": "## `>tier` ─ Asignar Phases\n```\n>tier <phase> <subtier> <clase> [@user] <región> [note: texto]\n```\n**Phases:** `0` `1` `2` `3` `4` `5` `app`\n**Subtiers:** `low` `mid` `high`\n**Clases:** `weak` `stable` `strong`\n**Regiones:** `sp` `mi` `da` `la`\n\n**Ejemplo:**\n```\n>tier 1 high stable @jugador sp note: gran rendimiento\n```\n╰─ Requiere rol **TRYOUTER**.",
        "pt": "## `>tier` ─ Atribuir Phases\n```\n>tier <phase> <subtier> <classe> [@user] <região> [note: texto]\n```\n**Phases:** `0` `1` `2` `3` `4` `5` `app`\n**Subtiers:** `low` `mid` `high`\n**Classes:** `weak` `stable` `strong`\n**Regiões:** `sp` `mi` `da` `la`\n\n**Exemplo:**\n```\n>tier 1 high stable @jogador sp note: ótimo desempenho\n```\n╰─ Requer papel **TRYOUTER**.",
    },
    "mods": {
        "en": "## `>mods` ─ Staff Help\n```\n>mods <question>\n```\nAsk Friity about any staff command.\n\n**Examples:**\n```\n>mods how do I use the tier command?\n>mods how do I create a poll?\n>mods how does activity check work?\n```\n╰─ Instant hardcoded answers ─ no AI.",
        "es": "## `>mods` ─ Ayuda de Staff\n```\n>mods <pregunta>\n```\nPreguntale a Friity sobre cualquier comando de staff.\n\n**Ejemplos:**\n```\n>mods cómo uso el comando tier?\n>mods cómo creo una encuesta?\n>mods cómo funciona el activity check?\n```\n╰─ Respuestas instantáneas ─ sin IA.",
        "pt": "## `>mods` ─ Ajuda de Staff\n```\n>mods <pergunta>\n```\nPergunte ao Friity sobre qualquer comando de staff.\n\n**Exemplos:**\n```\n>mods como uso o comando tier?\n>mods como crio uma enquete?\n>mods como funciona o activity check?\n```\n╰─ Respostas instantâneas ─ sem IA.",
    },
    "poll": {
        "en": "## `>poll` ─ Create Polls\n```\n>poll <question> | <opt1> | <opt2> vote: N\n>poll <question> | <opt1> | <opt2> time: N unit\n```\n**Time units:** `second` `minute` `hour` `day` `week`\n\n**Examples:**\n```\n>poll Best region? | SAE | SAW vote: 20\n>poll Active this week? | Yes | No time: 24 hours\n```\n╰─ Requires **PollsEvent** role. Polls channel only.",
        "es": "## `>poll` ─ Crear Encuestas\n```\n>poll <pregunta> | <op1> | <op2> vote: N\n>poll <pregunta> | <op1> | <op2> time: N unidad\n```\n**Unidades:** `second` `minute` `hour` `day` `week`\n\n**Ejemplos:**\n```\n>poll Mejor región? | SAE | SAW vote: 20\n>poll Activos? | Sí | No time: 24 hours\n```\n╰─ Requiere rol **PollsEvent**. Solo canal de polls.",
        "pt": "## `>poll` ─ Criar Enquetes\n```\n>poll <pergunta> | <op1> | <op2> vote: N\n>poll <pergunta> | <op1> | <op2> time: N unidade\n```\n**Unidades:** `second` `minute` `hour` `day` `week`\n\n**Exemplos:**\n```\n>poll Melhor região? | SAE | SAW vote: 20\n>poll Ativos? | Sim | Não time: 24 hours\n```\n╰─ Requer papel **PollsEvent**. Apenas canal de polls.",
    },
    "activity": {
        "en": "## `?activity check` ─ Activity Checks\n```\n?activity check <message> @everyone\n```\n**How it works:**\n```\nReact  ─  streak +1\nMiss   ─  streak resets to 0\n```\n**Example:**\n```\n?activity check Weekly check! @everyone\n```\n╰─ Only **bot owner** can launch activity checks.",
        "es": "## `?activity check` ─ Activity Checks\n```\n?activity check <mensaje> @everyone\n```\n**Cómo funciona:**\n```\nReaccionar  ─  streak +1\nSaltarse    ─  streak vuelve a 0\n```\n**Ejemplo:**\n```\n?activity check Activity semanal! @everyone\n```\n╰─ Solo el **owner del bot** puede lanzarlo.",
        "pt": "## `?activity check` ─ Activity Checks\n```\n?activity check <mensagem> @everyone\n```\n**Como funciona:**\n```\nReagir   ─  streak +1\nPerder   ─  streak volta a 0\n```\n**Exemplo:**\n```\n?activity check Activity semanal! @everyone\n```\n╰─ Apenas o **dono do bot** pode lançar.",
    },
}

SETTINGS_CONTENT = {
    "en": (
        "## SETTINGS  ╱  Command Reference\n"
        "-# ╰─ All available staff commands.\n\n"
        "```\n"
        "/staffpanel     ─  Open this panel\n"
        ">tier           ─  Assign competitive phase\n"
        ">mods           ─  Ask about any command\n"
        ">ask            ─  AI assistant (clan/TSBL info)\n"
        ">poll           ─  Create a poll\n"
        ">info           ─  View Roblox profile\n"
        "?activity check ─  Launch activity check\n"
        "/setuppunishments ─  Send punishments embed\n"
        "/setuprules       ─  Send rules embed\n"
        "/setupoverview    ─  Send overview embed\n"
        "```\n"
        "-# ╰─ Awaken Reborns  ·  Friity Staff"
    ),
    "es": (
        "## SETTINGS  ╱  Referencia de Comandos\n"
        "-# ╰─ Todos los comandos de staff disponibles.\n\n"
        "```\n"
        "/staffpanel     ─  Abrir este panel\n"
        ">tier           ─  Asignar phase competitiva\n"
        ">mods           ─  Preguntar sobre un comando\n"
        ">ask            ─  Asistente IA (info clan/TSBL)\n"
        ">poll           ─  Crear una encuesta\n"
        ">info           ─  Ver perfil de Roblox\n"
        "?activity check ─  Lanzar activity check\n"
        "/setuppunishments ─  Enviar embed de sanciones\n"
        "/setuprules       ─  Enviar embed de reglas\n"
        "/setupoverview    ─  Enviar embed de overview\n"
        "```\n"
        "-# ╰─ Awaken Reborns  ·  Friity Staff"
    ),
    "pt": (
        "## SETTINGS  ╱  Referência de Comandos\n"
        "-# ╰─ Todos os comandos de staff disponíveis.\n\n"
        "```\n"
        "/staffpanel     ─  Abrir este painel\n"
        ">tier           ─  Atribuir phase competitiva\n"
        ">mods           ─  Perguntar sobre um comando\n"
        ">ask            ─  Assistente IA (info clã/TSBL)\n"
        ">poll           ─  Criar uma enquete\n"
        ">info           ─  Ver perfil Roblox\n"
        "?activity check ─  Lançar activity check\n"
        "/setuppunishments ─  Enviar embed de punições\n"
        "/setuprules       ─  Enviar embed de regras\n"
        "/setupoverview    ─  Enviar embed de overview\n"
        "```\n"
        "-# ╰─ Awaken Reborns  ·  Friity Staff"
    ),
}

def build_settings(lang):
    return {
        "flags": COMPONENTS_V2_FLAG | 64,
        "components": [{"type": 17, "components": [
            {"type": 10, "content": SETTINGS_CONTENT[lang]},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "Back", "custom_id": f"sp:back:{lang}"},
            ]},
            {"type": 1, "components": [{"type": 3, "custom_id": f"sp:lang:{lang}", "placeholder": "Language / Idioma / Língua", "options": LANG_OPTIONS}]},
        ]}]
    }

def build_cmd_detail(cmd, lang):
    content = CMD_DETAILS.get(cmd, {}).get(lang, "## Updating...\n─ This section is being updated.")
    return {
        "flags": COMPONENTS_V2_FLAG | 64,
        "components": [{"type": 17, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "Back", "custom_id": f"sp:back:{lang}"}]},
            {"type": 1, "components": [{"type": 3, "custom_id": f"sp:lang:{lang}", "placeholder": "Language / Idioma / Língua", "options": LANG_OPTIONS}]},
        ]}]
    }

def build_embeds_panel(lang, user_id):
    if user_id not in EMBED_ALLOWED:
        locked = {"en": "## Embeds / Containers\n-# ╰─ Access Denied\n\n─ This section is **locked**.\n╰─ Only **Sid** and **Space** can launch embeds.", "es": "## Embeds / Containers\n-# ╰─ Acceso Denegado\n\n─ Esta sección está **bloqueada**.\n╰─ Solo **Sid** y **Space** pueden lanzar embeds.", "pt": "## Embeds / Containers\n-# ╰─ Acesso Negado\n\n─ Esta seção está **bloqueada**.\n╰─ Apenas **Sid** e **Space** podem lançar embeds."}
        return {"flags": COMPONENTS_V2_FLAG | 64, "components": [{"type": 17, "components": [
            {"type": 10, "content": locked[lang]},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "Back", "custom_id": f"sp:back:{lang}"}]},
        ]}]}

    labels = {
        "en": {"title": "## Embeds / Containers", "sub": "-# ╰─ Launch official clan embeds.", "lr": "Launch Rules", "lp": "Launch Punishments", "lo": "Launch Overview", "back": "Back", "ft": "-# ╰─ Only Sid and Space can launch embeds."},
        "es": {"title": "## Embeds / Containers", "sub": "-# ╰─ Lanzar embeds oficiales del clan.", "lr": "Lanzar Reglas", "lp": "Lanzar Sanciones", "lo": "Lanzar Overview", "back": "Volver", "ft": "-# ╰─ Solo Sid y Space pueden lanzar embeds."},
        "pt": {"title": "## Embeds / Containers", "sub": "-# ╰─ Lançar embeds oficiais do clã.", "lr": "Lançar Regras", "lp": "Lançar Punições", "lo": "Lançar Overview", "back": "Voltar", "ft": "-# ╰─ Apenas Sid e Space podem lançar embeds."},
    }
    L = labels[lang]
    return {"flags": COMPONENTS_V2_FLAG | 64, "components": [{"type": 17, "components": [
        {"type": 10, "content": L["title"]},
        {"type": 10, "content": L["sub"]},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": f"─ **Rules** ─ <#{CHANNEL_RULES}>\n─ **Punishments** ─ <#{CHANNEL_PUNISHMENTS}>\n─ **Overview** ─ <#{CHANNEL_OVERVIEW}>"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": L["lr"], "custom_id": f"sp:launch_rules:{lang}"},
            {"type": 2, "style": 3, "label": L["lp"], "custom_id": f"sp:launch_pun:{lang}"},
            {"type": 2, "style": 3, "label": L["lo"], "custom_id": f"sp:launch_ov:{lang}"},
        ]},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 2, "style": 2, "label": L["back"], "custom_id": f"sp:back:{lang}"}]},
        {"type": 10, "content": L["ft"]},
    ]}]}

def build_main_panel(lang="en"):
    labels = {
        "en": {"title": "## CELESTIALS DRAGONS  ╱  STAFF PANEL", "sub": "-# ╰─ Type a keyword in the modal to navigate.",
               "body": "```\ncreate_embed  ─  Custom embed / container creator\n```\n-# ╰─ Other sections coming soon.",
               "ft": "-# ╰─ Awaken Reborns  ·  Friity Staff", "lang": "-# ╰─ Language:"},
        "es": {"title": "## CELESTIALS DRAGONS  ╱  PANEL DE STAFF", "sub": "-# ╰─ Escribí una palabra clave en el modal para navegar.",
               "body": "```\ncreate_embed  ─  Creador de embed / container custom\n```\n-# ╰─ Otras secciones próximamente.",
               "ft": "-# ╰─ Awaken Reborns  ·  Friity Staff", "lang": "-# ╰─ Idioma:"},
        "pt": {"title": "## CELESTIALS DRAGONS  ╱  PAINEL DE STAFF", "sub": "-# ╰─ Digite uma palavra-chave no modal para navegar.",
               "body": "```\ncreate_embed  ─  Criador de embed / container custom\n```\n-# ╰─ Outras seções em breve.",
               "ft": "-# ╰─ Awaken Reborns  ·  Friity Staff", "lang": "-# ╰─ Idioma:"},
    }
    L = labels[lang]
    return {"flags": COMPONENTS_V2_FLAG | 64, "components": [{"type": 17, "components": [
        {"type": 10, "content": L["title"]},
        {"type": 10, "content": L["sub"]},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": L["body"]},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": L["lang"]},
        {"type": 1, "components": [{"type": 3, "custom_id": f"sp:lang:{lang}", "placeholder": "Language / Idioma / Língua", "options": LANG_OPTIONS}]},
        {"type": 10, "content": L["ft"]},
    ]}]}

def build_create_embed_result(title, description, color_hex, channel_id):
    try: color = int(color_hex.lstrip("#"), 16)
    except: color = 0x5865F2
    return {"flags": COMPONENTS_V2_FLAG, "components": [{"type": 17, "accent_color": color, "components": [
        {"type": 10, "content": f"## {title}\n{description}"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": f"-# ╰─ Sent to <#{channel_id}>  ·  Awaken Reborns"},
    ]}]}

# ─────────────────────────────────────────────
#  M O D A L S
# ─────────────────────────────────────────────

SECTION_MAP = {
    "panel": "main", "main": "main",
    "settings": "placeholder",
    "tier": "placeholder", "mods": "placeholder", "poll": "placeholder", "activity": "placeholder",
    "embeds": "placeholder", "containers": "placeholder",
    "create_embed": "create_embed", "create": "create_embed",
    "rules": "placeholder", "reglas": "placeholder",
    "punishments": "placeholder", "sanciones": "placeholder", "pun": "placeholder",
    "overview": "placeholder",
}

# ─────────────────────────────────────────────
#  E M B E D   B U I L D E R
# ─────────────────────────────────────────────

COLOR_PRESETS = [
    {"label": "None (no color)", "value": "000001"},
    {"label": "Blurple",  "value": "5865F2"},
    {"label": "Red",      "value": "ED4245"},
    {"label": "Green",    "value": "57F287"},
    {"label": "Yellow",   "value": "FEE75C"},
    {"label": "Orange",   "value": "E67E22"},
    {"label": "Pink",     "value": "EB459E"},
    {"label": "White",    "value": "FFFFFF"},
    {"label": "Black",    "value": "000000"},
    {"label": "Aqua",     "value": "1ABC9C"},
    {"label": "Purple",   "value": "9B59B6"},
]

embed_builders = {}

def new_embed_state():
    return {"title": None, "description": None, "color": 0x5865F2, "color_name": "Blurple",
            "image_url": None, "thumbnail_url": None, "footer_text": None,
            "channel_id": None, "json_mode": False, "raw_json": None,
            "webhook_name": None, "webhook_avatar": None,
            "container_parts": [],
            "author_name": None, "author_icon": None, "author_url": None,
            "fields": [], "timestamp": False}

def _trunc(s, n):
    if not s: return "─"
    return (s[:n] + "…") if len(s) > n else s

def build_embed_builder(state):
    t = _trunc(state["title"], 40)
    d = _trunc(state["description"], 50)
    c = state["color_name"]
    ch = f"<#{state['channel_id']}>" if state["channel_id"] else "─"
    img = "Yes" if state["image_url"] else "No"
    thumb = "Yes" if state["thumbnail_url"] else "No"
    ft = _trunc(state["footer_text"], 30)
    mode = "JSON (discohook)" if state["json_mode"] else "Manual"
    parts = len(state.get("container_parts", []))
    wn = state.get("webhook_name") or "Default"
    wa = "Yes" if state.get("webhook_avatar") else "No"
    au = _trunc(state.get("author_name"), 25)
    flds = len(state.get("fields", []))
    ts = "Yes" if state.get("timestamp") else "No"

    status = (
        "## Create Custom Embed\n"
        "-# ╰─ Build your embed step by step.\n\n"
        "```\n"
        f"Title:       {t}\n"
        f"Description: {d}\n"
        f"Author:      {au}\n"
        f"Color:       #{state['color']:06X} ({c})\n"
        f"Channel:     {ch}\n"
        f"Image:       {img}  ·  Thumbnail: {thumb}\n"
        f"Footer:      {ft}  ·  Timestamp: {ts}\n"
        f"Fields:      {flds}\n"
        f"Mode:        {mode}\n"
        f"Components:  {parts}\n"
        f"Profile:     {wn}  ·  Avatar: {wa}\n"
        "```"
    )

    return {"flags": COMPONENTS_V2_FLAG | 64, "components": [
        {"type": 17, "accent_color": state["color"], "components": [
            {"type": 10, "content": status},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": "-# ╰─ Awaken Reborns  ·  Embed Builder"},
        ]},
        {"type": 1, "components": [{"type": 3, "custom_id": "ce:color", "placeholder": "Select Color", "options": COLOR_PRESETS}]},
        {"type": 1, "components": [{"type": 8, "custom_id": "ce:channel", "placeholder": "Select Channel", "channel_types": [0]}]},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Edit Text", "custom_id": "ce:text"},
            {"type": 2, "style": 1, "label": "Images", "custom_id": "ce:image"},
            {"type": 2, "style": 1, "label": "Author", "custom_id": "ce:author"},
            {"type": 2, "style": 1, "label": "Fields", "custom_id": "ce:field"},
            {"type": 2, "style": 2, "label": "Paste JSON", "custom_id": "ce:json"},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Container", "custom_id": "ce:container"},
            {"type": 2, "style": 2, "label": "Profile", "custom_id": "ce:profile"},
            {"type": 2, "style": 2, "label": "Timestamp", "custom_id": "ce:timestamp"},
            {"type": 2, "style": 3, "label": "Preview", "custom_id": "ce:preview"},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Send", "custom_id": "ce:send"},
            {"type": 2, "style": 4, "label": "Back", "custom_id": "ce:back"},
        ]},
    ]}

def build_container_panel(state):
    parts = state.get("container_parts", [])
    lines = []
    for i, p in enumerate(parts):
        t = p.get("_type", "?")
        preview = p.get("_preview", "")
        lines.append(f"{i+1}. [{t}] {preview}")
    comp_list = "\n".join(lines) if lines else "─ empty"

    status = (
        "## Container Builder\n"
        "-# ╰─ Add raw components to your container.\n\n"
        f"```\n{comp_list}\n```"
    )

    return {"flags": COMPONENTS_V2_FLAG | 64, "components": [
        {"type": 17, "accent_color": state["color"], "components": [
            {"type": 10, "content": status},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": "-# ╰─ Awaken Reborns  ·  Container Builder"},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Add Text", "custom_id": "ce:ct_text"},
            {"type": 2, "style": 1, "label": "Add Image", "custom_id": "ce:ct_image"},
            {"type": 2, "style": 2, "label": "Add Separator", "custom_id": "ce:ct_sep"},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Add Button", "custom_id": "ce:ct_btn"},
            {"type": 2, "style": 4, "label": "Clear All", "custom_id": "ce:ct_clear"},
            {"type": 2, "style": 2, "label": "Back", "custom_id": "ce:ct_back"},
        ]},
    ]}

def build_final_embed(state):
    if state.get("json_mode") and state.get("raw_json"):
        raw = state["raw_json"]
        if isinstance(raw, dict):
            msg = raw.get("messages", [{}])[0].get("data", raw) if "messages" in raw else raw
            embeds = msg.get("embeds", [])
            if embeds:
                comps = []
                for e in embeds:
                    inner = []
                    if e.get("image"): inner.append({"type": 12, "items": [{"media": {"url": e["image"]["url"]}}]})
                    txt = ""
                    if e.get("title"): txt += f"## {e['title']}\n"
                    if e.get("description"): txt += e["description"]
                    if txt: inner.append({"type": 10, "content": txt})
                    if e.get("fields"):
                        for f in e["fields"]: inner.append({"type": 10, "content": f"**{f['name']}**\n{f.get('value','')}" })
                    if e.get("author"):
                        a_txt = e["author"].get("name", "")
                        if e["author"].get("url"): a_txt = f"[{a_txt}]({e['author']['url']})"
                        if e["author"].get("icon_url"):
                            inner.insert(0, {"type": 9, "components": [{"type": 10, "content": f"-# {a_txt}"}], "accessory": {"type": 11, "media": {"url": e["author"]["icon_url"]}}})
                        else:
                            inner.insert(0, {"type": 10, "content": f"-# {a_txt}"})
                    if e.get("thumbnail"):
                        if inner and inner[-1].get("type") == 10:
                            last = inner.pop()
                            inner.append({"type": 9, "components": [{"type": 10, "content": last["content"]}], "accessory": {"type": 11, "media": {"url": e["thumbnail"]["url"]}}})
                    if e.get("timestamp"):
                        ts_raw = e["timestamp"]
                        inner.append({"type": 10, "content": f"-# {ts_raw}"})
                    if e.get("footer"):
                        inner.append({"type": 14, "divider": True, "spacing": 1})
                        inner.append({"type": 10, "content": f"-# {e['footer'].get('text','')}" })
                    col = e.get("color", 0x5865F2)
                    comps.append({"type": 17, "accent_color": col, "components": inner or [{"type": 10, "content": "*(empty embed)*"}]})
                return {"flags": COMPONENTS_V2_FLAG, "components": comps}
            if "components" in msg: return {"flags": COMPONENTS_V2_FLAG, "components": msg["components"]}
        return None

    inner = []
    # Author
    if state.get("author_name"):
        a_txt = state["author_name"]
        if state.get("author_url"): a_txt = f"[{a_txt}]({state['author_url']})"
        if state.get("author_icon"):
            inner.append({"type": 9, "components": [{"type": 10, "content": f"-# {a_txt}"}], "accessory": {"type": 11, "media": {"url": state["author_icon"]}}})
        else:
            inner.append({"type": 10, "content": f"-# {a_txt}"})
    # Image
    if state.get("image_url"): inner.append({"type": 12, "items": [{"media": {"url": state["image_url"]}}]})
    # Title + Description
    txt = ""
    if state.get("title"): txt += f"## {state['title']}\n"
    if state.get("description"): txt += state["description"]
    if txt:
        if state.get("thumbnail_url"):
            inner.append({"type": 9, "components": [{"type": 10, "content": txt}], "accessory": {"type": 11, "media": {"url": state["thumbnail_url"]}}})
        else:
            inner.append({"type": 10, "content": txt})
    # Fields
    for f in state.get("fields", []):
        inner.append({"type": 10, "content": f"**{f['name']}**\n{f.get('value', '')}"})

    for part in state.get("container_parts", []):
        pt = part.get("_type")
        if pt == "text":
            inner.append({"type": 10, "content": part.get("content", "")})
        elif pt == "image":
            inner.append({"type": 12, "items": [{"media": {"url": part.get("url", "")}}]})
        elif pt == "separator":
            inner.append({"type": 14, "divider": True, "spacing": 1})
        elif pt == "button":
            btn = {"type": 2, "style": int(part.get("style", 5)), "label": part.get("label", "Button")}
            if part.get("url"): btn["url"] = part["url"]
            else: btn["custom_id"] = f"ce_custom_{uuid.uuid4().hex[:8]}"
            if part.get("emoji_id"):
                btn["emoji"] = {"id": part["emoji_id"], "name": part.get("emoji_name", "emoji")}
            inner.append({"type": 1, "components": [btn]})

    if state.get("footer_text") or state.get("timestamp"):
        inner.append({"type": 14, "divider": True, "spacing": 1})
        ft_parts = []
        if state.get("footer_text"): ft_parts.append(state["footer_text"])
        if state.get("timestamp"): ft_parts.append(datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M UTC"))
        inner.append({"type": 10, "content": f"-# {' · '.join(ft_parts)}"})

    if not inner: return None
    container = {"type": 17, "components": inner}
    if state["color"] != 0x000001:
        container["accent_color"] = state["color"]
    return {"flags": COMPONENTS_V2_FLAG, "components": [container]}

async def _ce_text_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            cid = c.get("custom_id", ""); val = (c.get("value") or "").strip() or None
            if cid == "ce_f_title": state["title"] = val
            elif cid == "ce_f_desc": state["description"] = val
            elif cid == "ce_f_footer": state["footer_text"] = val
    await ia_update(interaction, build_embed_builder(state))

async def _ce_image_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            cid = c.get("custom_id", ""); val = (c.get("value") or "").strip() or None
            if cid == "ce_f_image": state["image_url"] = val
            elif cid == "ce_f_thumb": state["thumbnail_url"] = val
    await ia_update(interaction, build_embed_builder(state))

async def _ce_json_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    raw_text = ""
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            if c.get("custom_id") == "ce_f_json": raw_text = (c.get("value") or "").strip()
    if not raw_text: await ia_respond(interaction, {"content": "─ No JSON provided.", "flags": 64}); return
    try:
        data = json.loads(raw_text)
        state["raw_json"] = data; state["json_mode"] = True
        await ia_update(interaction, build_embed_builder(state))
    except json.JSONDecodeError:
        await ia_respond(interaction, {"content": "─ Invalid JSON. Copy it correctly from discohook.app.", "flags": 64})

async def _ce_author_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            cid = c.get("custom_id", ""); val = (c.get("value") or "").strip() or None
            if cid == "ce_f_author_name": state["author_name"] = val
            elif cid == "ce_f_author_icon": state["author_icon"] = val
            elif cid == "ce_f_author_url": state["author_url"] = val
    await ia_update(interaction, build_embed_builder(state))

async def _ce_field_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    name = ""; value = ""; inline = False
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            cid = c.get("custom_id", ""); val = (c.get("value") or "").strip()
            if cid == "ce_f_field_name": name = val
            elif cid == "ce_f_field_value": value = val
            elif cid == "ce_f_field_inline": inline = val.lower() in ("yes", "true", "si", "sí", "1")
    if not name: await ia_respond(interaction, {"content": "─ Field needs a name.", "flags": 64}); return
    state.setdefault("fields", []).append({"name": name, "value": value, "inline": inline})
    await ia_update(interaction, build_embed_builder(state))

async def _ce_profile_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            cid = c.get("custom_id", ""); val = (c.get("value") or "").strip() or None
            if cid == "ce_f_wh_name": state["webhook_name"] = val
            elif cid == "ce_f_wh_avatar": state["webhook_avatar"] = val
    await ia_update(interaction, build_embed_builder(state))

async def _ce_ct_text_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            if c.get("custom_id") == "ce_f_ct_text":
                val = (c.get("value") or "").strip()
                if val:
                    state.setdefault("container_parts", []).append({"_type": "text", "_preview": val[:30], "content": val})
    await ia_update(interaction, build_container_panel(state))

async def _ce_ct_image_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            if c.get("custom_id") == "ce_f_ct_image":
                val = (c.get("value") or "").strip()
                if val:
                    state.setdefault("container_parts", []).append({"_type": "image", "_preview": "img", "url": val})
    await ia_update(interaction, build_container_panel(state))

async def _ce_ct_btn_submit(interaction):
    uid = interaction.user.id; state = embed_builders.get(uid)
    if not state: await ia_respond(interaction, {"content": "─ Session expired.", "flags": 64}); return
    label = ""; url = ""; emoji_id = ""
    for row in (interaction.data or {}).get("components", []):
        for c in row.get("components", []):
            cid = c.get("custom_id", ""); val = (c.get("value") or "").strip()
            if cid == "ce_f_ct_btn_label": label = val
            elif cid == "ce_f_ct_btn_url": url = val
            elif cid == "ce_f_ct_btn_emoji": emoji_id = val
    if not label: await ia_respond(interaction, {"content": "─ Button needs a label.", "flags": 64}); return
    btn = {"_type": "button", "_preview": label[:20], "label": label, "style": 5 if url else 2}
    if url: btn["url"] = url
    if emoji_id: btn["emoji_id"] = emoji_id; btn["emoji_name"] = "emoji"
    state.setdefault("container_parts", []).append(btn)
    await ia_update(interaction, build_container_panel(state))

class StaffPanelModal(discord.ui.Modal, title="Awaken Reborns  ╱  Staff Panel"):
    keyword = discord.ui.TextInput(
        label="Section",
        placeholder="create_embed",
        min_length=1,
        max_length=30,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not has_perm(interaction.user):
            await interaction.response.send_message("─ No permission.", ephemeral=True)
            return

        key = self.keyword.value.strip().lower()
        section = SECTION_MAP.get(key)
        lang = "en"

        if section is None:
            await interaction.response.send_message(
                f"─ Unknown section `{key}`.\n\nAvailable:\n```\ncreate_embed\n```\n-# ╰─ Other sections coming soon.",
                ephemeral=True
            )
            return

        if section == "placeholder":
            msgs = {"en": "This section is coming soon.", "es": "Esta sección estará disponible próximamente.", "pt": "Esta seção estará disponível em breve."}
            await interaction.response.send_message(f"─ **Placeholder**\n{msgs[lang]}", ephemeral=True)
            return

        if section == "main":
            payload = build_main_panel(lang)
        elif section == "create_embed":
            if interaction.user.id not in EMBED_ALLOWED:
                await interaction.response.send_message("─ Only Sid and Space can use this.", ephemeral=True)
                return
            embed_builders[interaction.user.id] = new_embed_state()
            await ia_respond(interaction, build_embed_builder(embed_builders[interaction.user.id]))
            return
        else:
            payload = build_main_panel(lang)

        await ia_respond(interaction, payload)


# ─────────────────────────────────────────────
#  M O D S   R E S P O N S E S
# ─────────────────────────────────────────────

MODS_DATA = {
    "tier":       {"kw": ["tier","phase","fase","asignar","assign","tryout"], "en": "**`>tier`:** `>tier <phase 0-5|app> <low|mid|high> <weak|stable|strong> [@user] <sp|mi|da|la> [note: text]`\nExample: `>tier 1 high stable @user sp`\nRequires **TRYOUTER** role.", "es": "**`>tier`:** `>tier <phase 0-5|app> <low|mid|high> <weak|stable|strong> [@user] <sp|mi|da|la> [note: texto]`\nEjemplo: `>tier 1 high stable @user sp`\nRequiere rol **TRYOUTER**.", "pt": "**`>tier`:** `>tier <phase 0-5|app> <low|mid|high> <weak|stable|strong> [@user] <sp|mi|da|la> [note: texto]`\nExemplo: `>tier 1 high stable @user sp`\nRequer **TRYOUTER**."},
    "poll":       {"kw": ["poll","encuesta","enquete","votacion"], "en": "**`>poll`:** `>poll <question> | <opt1> | <opt2> vote: N` or `time: N unit`\nExample: `>poll Best region? | SAE | SAW vote: 10`\nRequires **PollsEvent**. Polls channel only.", "es": "**`>poll`:** `>poll <pregunta> | <op1> | <op2> vote: N` o `time: N unidad`\nEjemplo: `>poll Mejor región? | SAE | SAW vote: 10`\nRequiere **PollsEvent**. Solo canal de polls.", "pt": "**`>poll`:** `>poll <pergunta> | <op1> | <op2> vote: N` ou `time: N unidade`\nExemplo: `>poll Melhor região? | SAE | SAW vote: 10`\nRequer **PollsEvent**. Apenas canal de polls."},
    "activity":   {"kw": ["activity","actividad","atividade","check","streak"], "en": "**`?activity check`:** `?activity check <message> @everyone`\nMembers react to increase streak. Missing a check resets to 0.\nOnly **bot owner**.", "es": "**`?activity check`:** `?activity check <mensaje> @everyone`\nLos miembros reaccionan para subir streak. Saltarse uno lo resetea a 0.\nSolo el **owner del bot**.", "pt": "**`?activity check`:** `?activity check <mensagem> @everyone`\nMembros reagem para subir streak. Perder um check reseta para 0.\nApenas o **dono do bot**."},
    "staffpanel": {"kw": ["staffpanel","panel","staff panel"], "en": "**`/staffpanel`:** Opens the staff panel (modal). Type a keyword to navigate sections.\nAllowed: Sid, Space, and the 2 extra staff IDs.", "es": "**`/staffpanel`:** Abre el panel de staff (modal). Escribí una palabra clave para navegar.\nPermitidos: Sid, Space y los 2 IDs de staff extra.", "pt": "**`/staffpanel`:** Abre o painel de staff (modal). Digite uma palavra-chave para navegar.\nPermitidos: Sid, Space e os 2 IDs extras de staff."},
}

def detect_lang(text):
    t = f" {text.lower()} "
    pt = sum(1 for m in ["você","não","obrigad","clã","também","jogador"] if m in t)
    en = sum(1 for m in [" the "," and "," how "," what "," is "," do "] if m in t)
    if pt > en: return "pt"
    if en > pt: return "en"
    return "es"

def get_mods_response(question):
    lang = detect_lang(question); q = question.lower()
    for data in MODS_DATA.values():
        if any(kw in q for kw in data["kw"]): return data[lang]
    fb = {"en": "No specific info. Try: `>tier` · `>poll` · `?activity check` · `/staffpanel`", "es": "Sin info específica. Probá: `>tier` · `>poll` · `?activity check` · `/staffpanel`", "pt": "Sem info específica. Tente: `>tier` · `>poll` · `?activity check` · `/staffpanel`"}
    return fb[detect_lang(question)]

# ─────────────────────────────────────────────
#  P O L L S
# ─────────────────────────────────────────────

_POLL_COLORS = [0x5865F2, 0x57F287, 0xED4245, 0x9B59B6, 0xE67E22]
_POLL_UNITS  = {"second":1,"minute":60,"hour":3600,"day":86400,"week":604800}
active_polls: dict = {}

class PollState:
    def __init__(self,pid,q,opts,vg,ca,ch,col):
        self.poll_id=pid;self.question=q;self.options=opts;self.vote_goal=vg
        self.close_at=ca;self.channel_id=ch;self.accent_color=col
        self.message_id=None;self.votes={i:set() for i in range(len(opts))};self.user_vote={};self.closed=False
    def winner_text(self):
        mx=max((len(v) for v in self.votes.values()),default=0)
        if mx==0: return "No votes"
        w=[self.options[i] for i,v in self.votes.items() if len(v)==mx]
        return f"{', '.join(w)} ({mx} vote{'s' if mx!=1 else ''})"
    def winner_ann(self):
        mx=max((len(v) for v in self.votes.values()),default=0)
        if mx==0: return "The poll has closed with no votes."
        w=[self.options[i] for i,v in self.votes.items() if len(v)==mx]
        return f"Winner: {', '.join(f'**{x}**' for x in w)} — {'Tie!' if len(w)>1 else 'Congratulations!'}"

def _tr(ca):
    rem=max(0,int(ca-datetime.now(timezone.utc).timestamp()))
    h,r=divmod(rem,3600);m,s=divmod(r,60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

def build_poll_comps(state,final=False):
    inner=[{"type":10,"content":f"### {state.question}"},{"type":14,"spacing":1}]
    for i,opt in enumerate(state.options):
        cnt=len(state.votes[i])
        inner.append({"type":9,"components":[{"type":10,"content":f"{opt} ─ {cnt} vote{'s' if cnt!=1 else ''}"}],"accessory":{"type":2,"style":2,"label":f"{opt} ({cnt})","custom_id":f"poll:{state.poll_id}:vote:{i}","disabled":final}})
    inner.append({"type":14,"spacing":1})
    total=sum(len(v) for v in state.votes.values())
    if final: inner.append({"type":10,"content":f"─ Poll closed | Winner: {state.winner_text()}"})
    elif state.vote_goal: inner.append({"type":10,"content":f"─ Vote goal: {total}/{state.vote_goal}"})
    elif state.close_at: inner.append({"type":10,"content":f"─ Time remaining: {_tr(state.close_at)}"})
    inner.append({"type":10,"content":f"||<@&{POLL_PING_ROLE_ID}>||"})
    return [{"type":17,"accent_color":state.accent_color,"components":inner},{"type":1,"components":[{"type":2,"style":2,"label":"Close Poll","custom_id":f"poll:{state.poll_id}:close","disabled":final}]}]

async def close_poll(state,interaction=None):
    if state.closed:
        if interaction: await ia_respond(interaction,{"content":"Already closed.","flags":64})
        return
    state.closed=True;active_polls.pop(state.poll_id,None)
    comps=build_poll_comps(state,final=True)
    if interaction: await ia_update(interaction,{"flags":COMPONENTS_V2_FLAG,"components":comps})
    elif state.message_id:
        url=f"{DISCORD_API_BASE}/channels/{state.channel_id}/messages/{state.message_id}"
        headers={"Authorization":f"Bot {DISCORD_BOT_TOKEN}","Content-Type":"application/json"}
        async with aiohttp.ClientSession() as s: await s.patch(url,json={"flags":COMPONENTS_V2_FLAG,"components":comps},headers=headers)
    ch=client.get_channel(state.channel_id)
    if ch: await ch.send(state.winner_ann())

async def auto_close_poll(pid,secs):
    await asyncio.sleep(secs)
    s=active_polls.get(pid)
    if s and not s.closed: await close_poll(s)

# ─────────────────────────────────────────────
#  A C T I V I T Y   C H E C K
# ─────────────────────────────────────────────

STREAKS_FILE  = pathlib.Path("streaks.json")
ACTIVITY_FILE = pathlib.Path("activity_state.json")
EXCLUDED_IDS  = {1162798183068467220, 1025178585104920656}
_STREAK_RE    = re.compile(r"^Streak (\d+)$")
active_checks: dict = {}
current_check_id: str | None = None
streak_lock = asyncio.Lock()

def load_streaks():
    if STREAKS_FILE.exists():
        try: return json.loads(STREAKS_FILE.read_text())
        except: return {}
    return {}

def save_streaks(data): STREAKS_FILE.write_text(json.dumps(data,indent=2))
def get_streak(uid): return load_streaks().get(str(uid),{}).get("streak",0)

class AState:
    def __init__(self,cid,gid,ch): self.check_id=cid;self.guild_id=gid;self.original_channel_id=ch;self.original_message_id=None;self.checkers={}

def save_activity():
    try: ACTIVITY_FILE.write_text(json.dumps({"current_check_id":current_check_id,"checks":{mid:{"check_id":st.check_id,"guild_id":st.guild_id,"original_channel_id":st.original_channel_id,"original_message_id":st.original_message_id,"checkers":{str(uid):n for uid,n in st.checkers.items()}} for mid,st in active_checks.items()}},indent=2))
    except: pass

def load_activity():
    global current_check_id
    try:
        if not ACTIVITY_FILE.exists(): return
        data=json.loads(ACTIVITY_FILE.read_text()); current_check_id=data.get("current_check_id")
        for mid,info in (data.get("checks") or {}).items():
            st=AState(info["check_id"],int(info["guild_id"]),int(info["original_channel_id"]))
            st.original_message_id=info.get("original_message_id")
            st.checkers={int(uid):n for uid,n in (info.get("checkers") or {}).items()}
            active_checks[mid]=st
    except: pass

async def assign_streak_role(member,streak):
    guild=member.guild; target=f"Streak {streak}" if streak>0 else None
    to_rm=[r for r in member.roles if _STREAK_RE.match(r.name) and r.name!=target]
    tr=None
    if target:
        tr=discord.utils.get(guild.roles,name=target)
        if not tr:
            try: tr=await guild.create_role(name=target)
            except: pass
    try:
        if to_rm: await member.remove_roles(*to_rm)
        if tr and tr not in member.roles: await member.add_roles(tr)
    except: pass

def build_activity_container(cid):
    return [{"type":17,"components":[{"type":10,"content":"Tap here"}]},{"type":1,"components":[{"type":2,"style":2,"label":"Users","emoji":{"name":"emoji_49","id":"1491920857134530783"},"custom_id":"activity:users"},{"type":2,"style":2,"label":"Streak","emoji":{"name":"emoji_50","id":"1491941471249764453"},"custom_id":"activity:streak"}]}]

# ─────────────────────────────────────────────
#  A S K
# ─────────────────────────────────────────────

conv_history: dict = defaultdict(list)
MAX_HIST = 20
MODELS = ["llama-3.3-70b-versatile","meta-llama/llama-4-maverick-17b-128e-instruct","qwen/qwen3-32b","deepseek-r1-distill-llama-70b","llama-3.1-8b-instant","gemma2-9b-it"]
SYS = (
    "You are Friity, the official staff assistant bot for the clan 'Awaken Reborns'.\n\n"
    "RULES:\n"
    "- Detect the user's language (Spanish, English, Portuguese) and ALWAYS reply in that language.\n"
    "- Keep answers concise: 1-4 sentences max unless the user asks for detail.\n"
    "- You are ONLY knowledgeable about STAFF topics. If someone asks about competitive play, tournaments, "
    "game strategies, or anything not related to staff duties, reply: 'I only handle staff-related topics.'\n"
    "- Never invent data, stats, or information you don't have.\n"
    "- Be professional but friendly.\n\n"
    "STAFF KNOWLEDGE:\n"
    "- Tier system: Tiers 0-5 classify members by skill/rank. Use `>tier set @user <tier>` to assign tiers. "
    "Sub-tiers: high/mid/low. Classes: strong/stable/weak.\n"
    "- Activity checks: Staff can run `?activity check` to verify member activity. Inactivity may result in demotion.\n"
    "- Polls: Use `>poll` to create staff votes with options, vote goals, and time limits.\n"
    "- Punishments: The clan has a structured punishment system (warn → mute → kick → ban). Staff must follow proper escalation.\n"
    "- Embed builder: Staff with permissions can use `/staffpanel` → `create_embed` to create custom announcements.\n"
    "- Rules panel: Staff can deploy the rules embed to the designated channel.\n"
    "- Moderation commands: Available through the staff panel.\n\n"
    "PERSONALITY:\n"
    "- You represent Awaken Reborns professionally.\n"
    "- If unsure about something, say so honestly instead of guessing.\n"
    "- Help staff members understand their tools and duties."
)

async def handle_ask(message):
    q=message.content[len(">ask"):].strip()
    if not q: await message.channel.send("Usage: `>ask <question>`"); return
    uid=message.author.id; hist=conv_history[uid]
    hist.append({"role":"user","content":q})
    if len(hist)>MAX_HIST: hist=hist[-MAX_HIST:]; conv_history[uid]=hist
    status=await message.channel.send("Buscando…"); answer=None
    for model in MODELS:
        try:
            r=await groq_client.chat.completions.create(model=model,messages=[{"role":"system","content":SYS},*hist])
            answer=r.choices[0].message.content; break
        except Exception as e:
            if getattr(e,"status_code",None)==429: await asyncio.sleep(1)
            continue
    if not answer: await status.edit(content="Temporarily overloaded."); hist.pop(); return
    hist.append({"role":"assistant","content":answer})
    if len(answer)>2000:
        await status.delete()
        for i in range(0,len(answer),2000): await message.channel.send(answer[i:i+2000])
    else: await status.edit(content=answer)

# ─────────────────────────────────────────────
#  T I E R
# ─────────────────────────────────────────────

ALL_TIER=[1447047863736602777,1447049414051889234,1453228943283982469,1447050940187283648,1447049536781418619,1485358209760886894,1485358385389113476,1447056922158039062,1447056940856377434,1447056957868478554,1447056974934966353,1447056992358105190,1447057117533048985]
TIER_R={"0":1447047863736602777,"1":1447049414051889234,"app":1453228943283982469,"aplicant":1453228943283982469,"2":1447050940187283648,"3":1447049536781418619,"4":1485358209760886894,"5":1485358385389113476}
SUBTIER_R={"high":1447056957868478554,"mid":1447056940856377434,"low":1447056922158039062}
CLASS_R={"strong":1447057117533048985,"stable":1447056992358105190,"weak":1447056974934966353}
TIER_COL={"0":0x000000,"1":0x0055FF,"app":0x0055FF,"aplicant":0x0055FF,"2":0x8000FF,"3":0xFF1493,"4":0xFF4500,"5":0xFFD700}
V_TIERS={"0","1","app","aplicant","2","3","4","5"}; V_SUB={"low","mid","high"}; V_CLASS={"weak","stable","strong"}; V_REG={"sp","mi","da","cl","la"}
REG_DISP={"sp":"São Paulo, Brazil","mi":"Miami, Florida","da":"Dallas, Texas","cl":"Los Angeles, California","la":"Los Angeles, California"}
REG_ROLES={1451256254445129939:"São Paulo, Brazil",1490499594575020214:"Dallas, Texas",1451256372971704411:"Miami, Florida",1490500556203098263:"Los Angeles, California"}

async def handle_tier(message):
    if TRYOUTER_ROLE_ID not in [r.id for r in message.author.roles]:
        await message.channel.send("You need the **TRYOUTER** role."); return
    raw=message.content; note=""
    nm=re.search(r"note:\s*(.+)",raw,re.IGNORECASE)
    if nm: note=nm.group(1).strip(); raw=raw[:nm.start()].strip()
    parts=re.sub(r"<@!?\d+>","",raw).strip().split()
    tier=parts[1].lower() if len(parts)>1 else ""; sub=parts[2].lower() if len(parts)>2 else ""; cls=parts[3].lower() if len(parts)>3 else ""
    _U="Usage: `>tier <0-5|app> <low|mid|high> <weak|stable|strong> [@user] <sp|mi|da|cl|la> [note: text]`"
    if tier not in V_TIERS or sub not in V_SUB or cls not in V_CLASS: await message.channel.send(_U); return
    reg=next((REG_DISP.get(w.lower()) for w in parts[4:] if w.lower() in V_REG),None)
    if not reg: await message.channel.send(_U); return
    target=message.mentions[0] if message.mentions else message.author; guild=message.guild
    await target.remove_roles(*[guild.get_role(r) for r in ALL_TIER if guild.get_role(r)],reason="Tier reset")
    await target.add_roles(*[r for r in [guild.get_role(TIER_R[tier]),guild.get_role(SUBTIER_R[sub]),guild.get_role(CLASS_R[cls])] if r],reason="Tier set")
    disp="App" if tier in ("app","aplicant") else tier
    embed=discord.Embed(title="New Tier",description=f"**New Tier:**\n{target.mention} has been evaluated!\n\n**Tier:** {disp} {sub.capitalize()} {cls.capitalize()}\n\n**Region:** {reg}\n\n**Notes:** {note or '-'}",color=TIER_COL[tier],timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=f"Evaluated by {message.author.display_name}",icon_url=message.author.display_avatar.url)
    await message.channel.send(embed=embed)

# ─────────────────────────────────────────────
#  I N F O   /   R O B L O X
# ─────────────────────────────────────────────

roblox_links: dict = {}

async def fetch_roblox(username):
    async with aiohttp.ClientSession() as s:
        async with s.post("https://users.roblox.com/v1/usernames/users",json={"usernames":[username],"excludeBannedUsers":False}) as r:
            data=await r.json()
            if not data.get("data"): return None
            u=data["data"][0]; uid=u["id"]; name=u["name"]
        async with s.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=420x420&format=Png&isCircular=false") as r:
            td=await r.json()
            avatar=td["data"][0].get("imageUrl") if td.get("data") else None
    return {"name":name,"avatar":avatar}

def build_profile(user,rdata,rusername):
    rids={r.id for r in getattr(user,"roles",[])}
    phase=next((v for k,v in {1447047863736602777:"0",1447049414051889234:"1",1447050940187283648:"2",1447049536781418619:"3",1485358209760886894:"4",1485358385389113476:"5"}.items() if k in rids),None)
    sub=next((v for k,v in {1447056957868478554:"High",1447056940856377434:"Mid",1447056922158039062:"Low"}.items() if k in rids),None)
    cls=next((v for k,v in {1447057117533048985:"Strong",1447056992358105190:"Stable",1447056974934966353:"Weak"}.items() if k in rids),None)
    region=next((v for k,v in REG_ROLES.items() if k in rids),None)
    embed=discord.Embed(title=user.display_name,color=0xFFB6C1)
    if rdata and rdata.get("avatar"): embed.set_thumbnail(url=rdata["avatar"])
    dn=rdata["name"] if rdata else rusername
    embed.add_field(name="Roblox",value=f"[{dn}](https://www.roblox.com/users/search?keyword={dn})",inline=True)
    embed.add_field(name="Discord",value=user.name,inline=True)
    if phase: embed.add_field(name="Tier",value=" ".join(filter(None,[phase,sub,cls])),inline=False)
    if region: embed.add_field(name="Region",value=region,inline=False)
    embed.add_field(name="Streak",value=str(get_streak(user.id)),inline=False)
    return embed

class LinkModal(discord.ui.Modal,title="Link Roblox Account"):
    roblox_input=discord.ui.TextInput(label="Enter your Roblox username",placeholder="Your exact Roblox username",min_length=1,max_length=50)
    async def on_submit(self,interaction:discord.Interaction):
        username=self.roblox_input.value.strip(); roblox_links[interaction.user.id]=username
        await interaction.response.defer()
        rdata=await fetch_roblox(username)
        await interaction.followup.send(embed=build_profile(interaction.user,rdata,username))

class LinkView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Link Roblox Account",style=discord.ButtonStyle.danger,custom_id="link_roblox")
    async def link(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.send_modal(LinkModal())

# ─────────────────────────────────────────────
#  S L A S H   C O M M A N D S
# ─────────────────────────────────────────────

@client.tree.command(name="staffpanel", description="Open the Awaken Reborns staff control panel.")
async def slash_staffpanel(interaction: discord.Interaction):
    if not has_perm(interaction.user):
        await interaction.response.send_message("─ No permission.", ephemeral=True); return
    await interaction.response.send_modal(StaffPanelModal())

@client.tree.command(name="setuppunishments", description="Send the punishments panel to its channel.")
async def slash_setuppunishments(interaction: discord.Interaction):
    if not has_perm(interaction.user):
        await interaction.response.send_message("─ No permission.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    await api_post(CHANNEL_PUNISHMENTS, build_pun_accept())
    await interaction.followup.send("Punishments panel sent.", ephemeral=True)

@client.tree.command(name="setuprules", description="Send the rules panel to its channel.")
async def slash_setuprules(interaction: discord.Interaction):
    if not has_perm(interaction.user):
        await interaction.response.send_message("─ No permission.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    await api_post(CHANNEL_RULES, build_rules_embed())
    await interaction.followup.send("Rules panel sent.", ephemeral=True)

@client.tree.command(name="setupoverview", description="Send the overview panel to its channel.")
async def slash_setupoverview(interaction: discord.Interaction):
    if not has_perm(interaction.user):
        await interaction.response.send_message("─ No permission.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    await api_post(CHANNEL_OVERVIEW, build_overview_embed())
    await interaction.followup.send("Overview panel sent.", ephemeral=True)

# ─────────────────────────────────────────────
#  B O T   E V E N T S
# ─────────────────────────────────────────────

async def self_ping():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not render_url:
        print("[PING] No RENDER_EXTERNAL_URL found, skipping self-ping")
        return
    await asyncio.sleep(30)
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(render_url) as r:
                    print(f"[PING] {r.status}")
        except Exception as e:
            print(f"[PING] Error: {e}")
        await asyncio.sleep(300)

@client.event
async def on_ready():
    global BOT_OWNER_ID
    app_info = await client.application_info()
    BOT_OWNER_ID = app_info.owner.id
    client.add_view(LinkView())
    load_activity()
    asyncio.create_task(self_ping())
    print(f"[ONLINE] {client.user} — Owner: {BOT_OWNER_ID}")

@client.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    c = message.content.strip()
    if c.startswith(">mods"):
        q=c[len(">mods"):].strip()
        if not q: await message.channel.send("Usage: `>mods <question>`"); return
        await message.channel.send(get_mods_response(q)); return
    if c.startswith(">ask"): await handle_ask(message); return
    if c.startswith(">tier"): await handle_tier(message); return
    if c.startswith(">poll"): await handle_poll(message); return
    if c.startswith(">info"):
        uid=message.author.id
        if uid not in roblox_links:
            await message.channel.send(embed=discord.Embed(description="You don't have a Roblox account linked yet.",color=0xFFB6C1),view=LinkView()); return
        rdata=await fetch_roblox(roblox_links[uid])
        await message.channel.send(embed=build_profile(message.author,rdata,roblox_links[uid])); return
    if c.lower().startswith("?activity"): await handle_activity(message); return

@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command: return

    if interaction.type == discord.InteractionType.modal_submit:
        cid = (interaction.data or {}).get("custom_id", "")
        if cid == "ce_text_modal": await _ce_text_submit(interaction)
        elif cid == "ce_image_modal": await _ce_image_submit(interaction)
        elif cid == "ce_json_modal": await _ce_json_submit(interaction)
        elif cid == "ce_profile_modal": await _ce_profile_submit(interaction)
        elif cid == "ce_ct_text_modal": await _ce_ct_text_submit(interaction)
        elif cid == "ce_ct_image_modal": await _ce_ct_image_submit(interaction)
        elif cid == "ce_ct_btn_modal": await _ce_ct_btn_submit(interaction)
        elif cid == "ce_author_modal": await _ce_author_submit(interaction)
        elif cid == "ce_field_modal": await _ce_field_submit(interaction)
        return

    if interaction.type != discord.InteractionType.component: return
    cid = (interaction.data or {}).get("custom_id", "")

    # Staff panel buttons
    if cid.startswith("sp:"):
        parts = cid.split(":"); action = parts[1] if len(parts)>1 else ""; lang = parts[2] if len(parts)>2 else "en"
        if lang not in ("en","es","pt"): lang="en"
        if action == "back": await ia_update(interaction, build_main_panel(lang)); return
        if action == "lang":
            new_lang=(interaction.data or {}).get("values",["en"])[0]
            await ia_update(interaction, build_main_panel(new_lang)); return
        if action in ("tier","mods","poll","activity"): await ia_update(interaction, build_cmd_detail(action,lang)); return
        if action == "embeds": await ia_update(interaction, build_embeds_panel(lang,interaction.user.id)); return
        if action == "launch_rules":
            if interaction.user.id not in EMBED_ALLOWED: await ia_respond(interaction,{"content":"─ No permission.","flags":64}); return
            await ia_defer(interaction); await api_post(CHANNEL_RULES,build_rules_embed()); await ia_followup(interaction,"Rules launched."); return
        if action == "launch_pun":
            if interaction.user.id not in EMBED_ALLOWED: await ia_respond(interaction,{"content":"─ No permission.","flags":64}); return
            await ia_defer(interaction); await api_post(CHANNEL_PUNISHMENTS,build_pun_accept()); await ia_followup(interaction,"Punishments launched."); return
        if action == "launch_ov":
            if interaction.user.id not in EMBED_ALLOWED: await ia_respond(interaction,{"content":"─ No permission.","flags":64}); return
            await ia_defer(interaction); await api_post(CHANNEL_OVERVIEW,build_overview_embed()); await ia_followup(interaction,"Overview launched."); return
        return

    # Embed builder
    if cid.startswith("ce:"):
        action = cid.split(":")[1] if len(cid.split(":")) > 1 else ""
        uid = interaction.user.id
        if uid not in EMBED_ALLOWED:
            await ia_respond(interaction, {"content": "─ No permission.", "flags": 64}); return
        state = embed_builders.get(uid)
        if not state and action not in ("back",):
            await ia_respond(interaction, {"content": "─ Session expired. Use `/staffpanel` then type `create_embed`.", "flags": 64}); return

        if action == "color":
            val = (interaction.data or {}).get("values", ["5865F2"])[0]
            cmap = {p["value"]: p["label"] for p in COLOR_PRESETS}
            state["color"] = int(val, 16); state["color_name"] = cmap.get(val, "Custom")
            await ia_update(interaction, build_embed_builder(state)); return

        if action == "channel":
            vals = (interaction.data or {}).get("values", [])
            if vals: state["channel_id"] = int(vals[0])
            await ia_update(interaction, build_embed_builder(state)); return

        if action == "text":
            comps = [{"type": 1, "components": [{"type": 4, "custom_id": "ce_f_title", "label": "Title", "style": 1, "max_length": 256, "required": False, "value": state.get("title") or "", "placeholder": "Embed title"}]},
                     {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_desc", "label": "Description", "style": 2, "max_length": 4000, "required": False, "value": state.get("description") or "", "placeholder": "Embed description (supports markdown)"}]},
                     {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_footer", "label": "Footer", "style": 1, "max_length": 200, "required": False, "value": state.get("footer_text") or "", "placeholder": "Footer text"}]}]
            await ia_modal(interaction, "ce_text_modal", "Edit Embed Text", comps); return

        if action == "image":
            comps = [{"type": 1, "components": [{"type": 4, "custom_id": "ce_f_image", "label": "Image URL", "style": 1, "max_length": 500, "required": False, "value": state.get("image_url") or "", "placeholder": "https://example.com/image.png"}]},
                     {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_thumb", "label": "Thumbnail URL", "style": 1, "max_length": 500, "required": False, "value": state.get("thumbnail_url") or "", "placeholder": "https://example.com/thumb.png"}]}]
            await ia_modal(interaction, "ce_image_modal", "Add Images", comps); return

        if action == "author":
            comps = [
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_author_name", "label": "Author Name", "style": 1, "max_length": 256, "required": False, "value": state.get("author_name") or "", "placeholder": "Author display name"}]},
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_author_icon", "label": "Author Icon URL", "style": 1, "max_length": 500, "required": False, "value": state.get("author_icon") or "", "placeholder": "https://example.com/icon.png"}]},
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_author_url", "label": "Author URL (clickable link)", "style": 1, "max_length": 500, "required": False, "value": state.get("author_url") or "", "placeholder": "https://example.com"}]},
            ]
            await ia_modal(interaction, "ce_author_modal", "Author Settings", comps); return

        if action == "field":
            comps = [
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_field_name", "label": "Field Name", "style": 1, "max_length": 256, "required": True, "placeholder": "Field title"}]},
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_field_value", "label": "Field Value", "style": 2, "max_length": 1024, "required": False, "placeholder": "Field content (supports markdown)"}]},
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_field_inline", "label": "Inline? (yes/no)", "style": 1, "max_length": 3, "required": False, "value": "no", "placeholder": "yes or no"}]},
            ]
            await ia_modal(interaction, "ce_field_modal", "Add Field", comps); return

        if action == "json":
            comps = [{"type": 1, "components": [{"type": 4, "custom_id": "ce_f_json", "label": "Discohook JSON", "style": 2, "max_length": 4000, "required": True, "placeholder": "Paste your discohook.app JSON here..."}]}]
            await ia_modal(interaction, "ce_json_modal", "Paste Discohook JSON", comps); return

        if action == "timestamp":
            state["timestamp"] = not state.get("timestamp", False)
            await ia_update(interaction, build_embed_builder(state)); return

        if action == "container":
            await ia_update(interaction, build_container_panel(state)); return

        if action == "profile":
            comps = [
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_wh_name", "label": "Display Name", "style": 1, "max_length": 80, "required": False, "value": state.get("webhook_name") or "", "placeholder": "Custom name (empty = bot default)"}]},
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_wh_avatar", "label": "Avatar URL", "style": 1, "max_length": 500, "required": False, "value": state.get("webhook_avatar") or "", "placeholder": "https://example.com/avatar.png"}]},
            ]
            await ia_modal(interaction, "ce_profile_modal", "Profile Settings", comps); return

        if action == "preview":
            payload = build_final_embed(state)
            if not payload:
                await ia_respond(interaction, {"content": "─ Set at least a title/description, paste JSON, or add container parts.", "flags": 64}); return
            preview = {**payload, "flags": payload.get("flags", 0) | 64}
            await ia_respond(interaction, preview); return

        if action == "send":
            if not state.get("channel_id"):
                await ia_respond(interaction, {"content": "─ Select a channel first.", "flags": 64}); return
            payload = build_final_embed(state)
            if not payload:
                await ia_respond(interaction, {"content": "─ Add content first (title/description, JSON, or container parts).", "flags": 64}); return
            await ia_defer(interaction)
            wh_name = state.get("webhook_name")
            wh_avatar = state.get("webhook_avatar")
            if wh_name or wh_avatar:
                result = await webhook_send(state["channel_id"], payload, username=wh_name, avatar_url=wh_avatar)
            else:
                result = await api_post(state["channel_id"], payload)
            if result.get("id"):
                ch = state["channel_id"]; embed_builders.pop(uid, None)
                await ia_edit(interaction, {"flags": COMPONENTS_V2_FLAG | 64, "components": [{"type": 17, "components": [
                    {"type": 10, "content": f"## Embed Sent\n-# ╰─ Sent to <#{ch}>  ·  Awaken Reborns"},
                ]}]})
            else:
                await ia_followup(interaction, f"─ Failed. Check bot permissions.\n```{str(result)[:200]}```")
            return

        if action == "back":
            embed_builders.pop(uid, None)
            await ia_update(interaction, build_main_panel("en")); return

        # Container sub-actions
        if action == "ct_text":
            comps = [{"type": 1, "components": [{"type": 4, "custom_id": "ce_f_ct_text", "label": "Text Content", "style": 2, "max_length": 4000, "required": True, "placeholder": "Text content (supports markdown)"}]}]
            await ia_modal(interaction, "ce_ct_text_modal", "Add Text Component", comps); return

        if action == "ct_image":
            comps = [{"type": 1, "components": [{"type": 4, "custom_id": "ce_f_ct_image", "label": "Image URL", "style": 1, "max_length": 500, "required": True, "placeholder": "https://example.com/image.png"}]}]
            await ia_modal(interaction, "ce_ct_image_modal", "Add Image Component", comps); return

        if action == "ct_sep":
            state.setdefault("container_parts", []).append({"_type": "separator", "_preview": "───"})
            await ia_update(interaction, build_container_panel(state)); return

        if action == "ct_btn":
            comps = [
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_ct_btn_label", "label": "Button Label", "style": 1, "max_length": 80, "required": True, "placeholder": "Click me!"}]},
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_ct_btn_url", "label": "Button URL (optional)", "style": 1, "max_length": 500, "required": False, "placeholder": "https://example.com"}]},
                {"type": 1, "components": [{"type": 4, "custom_id": "ce_f_ct_btn_emoji", "label": "Custom Emoji ID (optional)", "style": 1, "max_length": 30, "required": False, "placeholder": "1234567890"}]},
            ]
            await ia_modal(interaction, "ce_ct_btn_modal", "Add Button Component", comps); return

        if action == "ct_clear":
            state["container_parts"] = []
            await ia_update(interaction, build_container_panel(state)); return

        if action == "ct_back":
            await ia_update(interaction, build_embed_builder(state)); return

        return

    # Punishments
    if cid == "accept_punishments":
        url=f"{DISCORD_API_BASE}/interactions/{interaction.id}/{interaction.token}/callback"
        async with aiohttp.ClientSession() as s: await s.post(url,json={"type":6},headers={"Content-Type":"application/json"})
        await asyncio.sleep(1)
        has_role=any(r.id==REQUIRED_ROLE_ID for r in interaction.user.roles)
        url2=f"{DISCORD_API_BASE}/webhooks/{APPLICATION_ID}/{interaction.token}/messages/@original"
        async with aiohttp.ClientSession() as s: await s.patch(url2,json=build_pun_lang() if has_role else build_pun_accept(),headers={"Content-Type":"application/json"})
        url3=f"{DISCORD_API_BASE}/webhooks/{APPLICATION_ID}/{interaction.token}"
        async with aiohttp.ClientSession() as s: await s.post(url3,json={"content":"Accepted" if has_role else "Rejected ─ No required role.","flags":64},headers={"Content-Type":"application/json"})
        return
    if cid == "punish_lang_select":
        lang=(interaction.data or {}).get("values",["en"])[0]; await ia_update(interaction,build_pun_content(lang)); return
    if cid == "back_to_langs": await ia_update(interaction,build_pun_lang()); return
    if cid == "menu_canales":
        vals=(interaction.data or {}).get("values") or []
        if vals: await ia_respond(interaction,{"content":f"Go to: <#{vals[0]}>","flags":64}); return

    # Polls
    parts=cid.split(":")
    if parts[0]=="poll" and len(parts)>=3:
        pid=parts[1]; act=parts[2]; state=active_polls.get(pid)
        if not state or state.closed: await ia_respond(interaction,{"content":"Poll no longer active.","flags":64}); return
        if act=="vote" and len(parts)>=4:
            idx=int(parts[3]); uid=interaction.user.id; prev=state.user_vote.get(uid)
            if prev==idx: state.votes[idx].discard(uid); del state.user_vote[uid]
            else:
                if prev is not None: state.votes[prev].discard(uid)
                state.votes[idx].add(uid); state.user_vote[uid]=idx
            total=sum(len(v) for v in state.votes.values())
            if state.vote_goal and total>=state.vote_goal: await close_poll(state,interaction)
            else: await ia_update(interaction,{"flags":COMPONENTS_V2_FLAG,"components":build_poll_comps(state)})
        elif act=="close":
            if POLL_ROLE_ID not in {r.id for r in getattr(interaction.user,"roles",[])}: await ia_respond(interaction,{"content":"No permission.","flags":64}); return
            await close_poll(state,interaction)
        return

    # Activity
    if parts[0]=="activity" and len(parts)>1:
        act=parts[1]; EV2=64|COMPONENTS_V2_FLAG
        if act=="users":
            state=next((s for s in active_checks.values() if s.check_id==current_check_id),None) if current_check_id else None
            rows=[{"type":10,"content":f"**{n}**"} for n in state.checkers.values()] if state and state.checkers else [{"type":10,"content":"*No one checked in yet.*"}]
            await ia_respond(interaction,{"flags":EV2,"components":[{"type":17,"components":[{"type":10,"content":"### Activity Check ─ Users"},{"type":14},*rows]}]}); return
        if act=="streak":
            data=load_streaks()
            lb=sorted([(int(uid),e.get("streak",0)) for uid,e in data.items() if int(uid) not in EXCLUDED_IDS and e.get("streak",0)>0],key=lambda x:x[1],reverse=True)[:5]
            guild=client.get_guild(interaction.guild_id) if interaction.guild_id else None
            rows=[]
            for uid,cnt in lb:
                m=guild.get_member(uid) if guild else None
                rows.append({"type":10,"content":f"─ **{m.display_name if m else uid}** ─ {cnt} streak{'s' if cnt!=1 else ''}"})
            if not rows: rows=[{"type":10,"content":"*No streak data yet.*"}]
            await ia_respond(interaction,{"flags":EV2,"components":[{"type":17,"components":[{"type":10,"content":"### Streak Top 5"},{"type":14},*rows]}]}); return

@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id==client.user.id or str(payload.emoji)!="✅" or payload.user_id in EXCLUDED_IDS: return
    mid=str(payload.message_id); state=active_checks.get(mid)
    if not state: return
    state.checkers[payload.user_id]=payload.member.display_name if payload.member else str(payload.user_id)
    async with streak_lock:
        data=load_streaks(); uid_str=str(payload.user_id); entry=data.setdefault(uid_str,{"streak":0})
        if entry.get("last_check_id")!=state.check_id: entry["streak"]=entry.get("streak",0)+1; entry["last_check_id"]=state.check_id
        new_streak=entry["streak"]; save_streaks(data)
    save_activity()
    if payload.member: asyncio.create_task(assign_streak_role(payload.member,new_streak))

@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.user_id==client.user.id or str(payload.emoji)!="✅" or payload.user_id in EXCLUDED_IDS: return
    mid=str(payload.message_id); state=active_checks.get(mid)
    if not state: return
    state.checkers.pop(payload.user_id,None); save_activity()
    async with streak_lock:
        data=load_streaks(); uid_str=str(payload.user_id); entry=data.get(uid_str)
        if entry and entry.get("last_check_id")==state.check_id:
            entry["streak"]=max(0,entry.get("streak",1)-1); entry.pop("last_check_id",None); new_streak=entry["streak"]; save_streaks(data)
        else: new_streak=entry.get("streak",0) if entry else 0
    guild=client.get_guild(payload.guild_id)
    if guild:
        member=guild.get_member(payload.user_id)
        if member: asyncio.create_task(assign_streak_role(member,new_streak))

async def handle_activity(message):
    global current_check_id
    if message.author.id!=BOT_OWNER_ID or "@everyone" not in message.content: return
    if not re.match(r"\?activity\s+check",message.content,re.IGNORECASE): return
    cid=str(uuid.uuid4())[:8]
    async with streak_lock:
        data=load_streaks(); prev=current_check_id
        if prev:
            for uid_str,entry in data.items():
                if int(uid_str) in EXCLUDED_IDS: continue
                if entry.get("last_check_id")!=prev and entry.get("streak",0)>0: entry["streak"]=0; entry.pop("last_check_id",None)
        current_check_id=cid; save_streaks(data)
    state=AState(cid,message.guild.id,message.channel.id); state.original_message_id=str(message.id)
    active_checks[str(message.id)]=state; save_activity()
    await api_post(message.channel.id,{"flags":COMPONENTS_V2_FLAG,"components":build_activity_container(cid)})

async def handle_poll(message):
    if message.channel.id!=POLL_CHANNEL_ID:
        try: await message.delete()
        except: pass
        await message.channel.send("Polls only in the polls channel.",delete_after=5); return
    if POLL_ROLE_ID not in {r.id for r in message.author.roles}: await message.channel.send("No permission.",delete_after=5); return
    raw=message.content[len(">poll"):].strip()
    vm=re.search(r"\bvote:\s*(\d+)",raw,re.IGNORECASE); tm=re.search(r"\btime:\s*(\d+)\s*(second|minute|hour|day|week)s?",raw,re.IGNORECASE)
    if vm and tm: await message.channel.send("Use either `vote:` or `time:`.",delete_after=5); return
    if not vm and not tm: await message.channel.send("Specify `vote: N` or `time: N unit`.",delete_after=5); return
    vg=None; ts=None
    if vm: vg=int(vm.group(1)); raw=(raw[:vm.start()]+raw[vm.end():]).strip()
    if tm: ts=float(int(tm.group(1))*_POLL_UNITS[tm.group(2).lower()]); raw=(raw[:tm.start()]+raw[tm.end():]).strip()
    parts=[p.strip() for p in raw.split("|")]
    if len(parts)<3: await message.channel.send("Need question + 2 options separated by `|`.",delete_after=5); return
    if len(parts)>5: await message.channel.send("Max 4 options.",delete_after=5); return
    try: await message.delete()
    except: pass
    pid=str(uuid.uuid4())[:8]; ca=datetime.now(timezone.utc).timestamp()+ts if ts else None
    state=PollState(pid,parts[0],parts[1:],vg,ca,message.channel.id,random.choice(_POLL_COLORS))
    data=await api_post(message.channel.id,{"flags":COMPONENTS_V2_FLAG,"components":build_poll_comps(state)})
    state.message_id=data.get("id"); active_polls[pid]=state
    if ts: asyncio.create_task(auto_close_poll(pid,ts))

if __name__ == "__main__":
    keep_alive()
    client.run(DISCORD_BOT_TOKEN)
