import discord
import os
import asyncio
import aiohttp

TOKEN = os.environ["DISCORD_TOKEN"]
APPLICATION_ID = int(os.environ.get("APPLICATION_ID", "0"))
CHANNEL_PUNISHMENTS = 1497364541024112720
REQUIRED_ROLE_ID = 1497010109824499923
ALLOWED_ROLES = {1497009109101183107}  # Co-Owner (agregá más IDs acá si hace falta)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ─────────────────────────────────────────────
#  C O N T E N T
# ─────────────────────────────────────────────

PUNISHMENTS_CONTENT = {
    "en": (
        "## ◈ CELESTIALS DRAGONS  ╱  SANCTIONS SYSTEM\n"
        "-# ╰─ All sanctions are applied based on severity and member history.\n\n"

        "**𝐈.  𝗪𝗔𝗥𝗡𝗜𝗡𝗚**\n"
        "▸ A formal written warning issued by staff.\n"
        "▸ Warnings are logged and __accumulate__ — **three warnings** escalate automatically to a mute.\n"
        "▸ Minor or moderate offenses result in a warn.\n"
        "▸ Sanctions increase in severity with each warn.\n"
        "▸ Reaching 3 warns = temporary blacklist of 1 month.\n"
        "╰─ Regular warns expire after 1 month.\n\n"

        "**𝐈𝐈.  𝗠𝗨𝗧𝗘**\n"
        "▸ Temporary removal of communication privileges.\n"
        "╰─ Duration is determined by staff based on __severity__ and prior history.\n\n"

        "**𝐈𝐈𝐈.  𝗧𝗘𝗠𝗣𝗢𝗥𝗔𝗥𝗬 𝗕𝗔𝗡 / 𝗕𝗟𝗔𝗖𝗞𝗟𝗜𝗦𝗧**\n"
        "▸ Temporary removal from the server.\n"
        "▸ Applied when a mute has proven __insufficient__ or the offense is of **considerable severity**.\n"
        "▸ First blacklist → 1 month duration.\n"
        "▸ Each new blacklist increases until permanent.\n"
        "╰─ Can be applied without warns if offense is severe.\n\n"

        "**𝐈𝐕.  𝗣𝗘𝗥𝗠𝗔𝗡𝗘𝗡𝗧 𝗕𝗔𝗡**\n"
        "▸ Permanent removal from the server with __no appeal__.\n"
        "╰─ Reserved for **severe violations** or repeated offenses after all prior sanctions are exhausted.\n\n"

        "**— Strict violations —**\n"
        "› Leaks / Private information sharing\n"
        "› Doxxing / Sensitive personal data exposure\n"
        "› Grooming / Manipulation toward minors\n"
        "› CP Joking / Child abuse references\n"
        "› Threats / Harassment / Extortion\n"
        "╰─ **These result in immediate permanent action. No exceptions.**\n\n"

        "-# ▸ Please review the rules for more information.\n"
        "-# ╰─ Celestials Dragons  ·  Punishments"
    ),
    "es": (
        "## ◈ CELESTIALS DRAGONS  ╱  SISTEMA DE SANCIONES\n"
        "-# ╰─ Todas las sanciones se aplican según la gravedad y el historial del miembro.\n\n"

        "**𝐈.  𝗔𝗗𝗩𝗘𝗥𝗧𝗘𝗡𝗖𝗜𝗔**\n"
        "▸ Una advertencia formal emitida por el staff.\n"
        "▸ Las advertencias se registran y __acumulan__ — **tres advertencias** escalan automáticamente a un mute.\n"
        "▸ Las infracciones menores o moderadas resultan en una advertencia.\n"
        "▸ Las sanciones aumentan en gravedad con cada advertencia.\n"
        "▸ Alcanzar 3 advertencias = blacklist temporal de 1 mes.\n"
        "╰─ Las advertencias regulares expiran después de 1 mes.\n\n"

        "**𝐈𝐈.  𝗠𝗨𝗧𝗘**\n"
        "▸ Eliminación temporal de privilegios de comunicación.\n"
        "╰─ La duración es determinada por el staff según la __gravedad__ e historial previo.\n\n"

        "**𝐈𝐈𝐈.  𝗕𝗔𝗡 𝗧𝗘𝗠𝗣𝗢𝗥𝗔𝗟 / 𝗕𝗟𝗔𝗖𝗞𝗟𝗜𝗦𝗧**\n"
        "▸ Expulsión temporal del servidor.\n"
        "▸ Se aplica cuando el mute ha sido __insuficiente__ o la infracción es de **gravedad considerable**.\n"
        "▸ Primera blacklist → 1 mes de duración.\n"
        "▸ Cada nueva blacklist incrementa hasta ser permanente.\n"
        "╰─ Puede aplicarse sin advertencias si la infracción es grave.\n\n"

        "**𝐈𝐕.  𝗕𝗔𝗡 𝗣𝗘𝗥𝗠𝗔𝗡𝗘𝗡𝗧𝗘**\n"
        "▸ Expulsión permanente del servidor __sin apelación__.\n"
        "╰─ Reservado para **violaciones graves** o infracciones repetidas tras agotar todas las sanciones previas.\n\n"

        "**— Violaciones estrictas —**\n"
        "› Filtraciones / Compartir información privada\n"
        "› Doxxing / Exposición de datos personales sensibles\n"
        "› Grooming / Manipulación hacia menores\n"
        "› Bromas sobre CP / Referencias a abuso infantil\n"
        "› Amenazas / Acoso / Extorsión\n"
        "╰─ **Resultan en acción permanente inmediata. Sin excepciones.**\n\n"

        "-# ▸ Revisa las reglas para más información.\n"
        "-# ╰─ Celestials Dragons  ·  Punishments"
    ),
    "pt": (
        "## ◈ CELESTIALS DRAGONS  ╱  SISTEMA DE SANÇÕES\n"
        "-# ╰─ Todas as sanções são aplicadas com base na gravidade e no histórico do membro.\n\n"

        "**𝐈.  𝗔𝗩𝗜𝗦𝗢**\n"
        "▸ Um aviso formal emitido pela staff.\n"
        "▸ Os avisos são registrados e __acumulam__ — **três avisos** escalam automaticamente para um mute.\n"
        "▸ Infrações menores ou moderadas resultam em um aviso.\n"
        "▸ As sanções aumentam em gravidade com cada aviso.\n"
        "▸ Atingir 3 avisos = blacklist temporária de 1 mês.\n"
        "╰─ Avisos regulares expiram após 1 mês.\n\n"

        "**𝐈𝐈.  𝗠𝗨𝗧𝗘**\n"
        "▸ Remoção temporária dos privilégios de comunicação.\n"
        "╰─ A duração é determinada pela staff com base na __gravidade__ e no histórico anterior.\n\n"

        "**𝐈𝐈𝐈.  𝗕𝗔𝗡 𝗧𝗘𝗠𝗣𝗢𝗥𝗔𝗥𝗜𝗢 / 𝗕𝗟𝗔𝗖𝗞𝗟𝗜𝗦𝗧**\n"
        "▸ Remoção temporária do servidor.\n"
        "▸ Aplicado quando o mute foi __insuficiente__ ou a infração é de **gravidade considerável**.\n"
        "▸ Primeira blacklist → 1 mês de duração.\n"
        "▸ Cada nova blacklist aumenta até ser permanente.\n"
        "╰─ Pode ser aplicada sem avisos se a infração for grave.\n\n"

        "**𝐈𝐕.  𝗕𝗔𝗡 𝗣𝗘𝗥𝗠𝗔𝗡𝗘𝗡𝗧𝗘**\n"
        "▸ Remoção permanente do servidor sem __apelação__.\n"
        "╰─ Reservado para **violações graves** ou infrações repetidas após o esgotamento de todas as sanções.\n\n"

        "**— Violações estritas —**\n"
        "› Vazamentos / Compartilhamento de informações privadas\n"
        "› Doxxing / Exposição de dados pessoais sensíveis\n"
        "› Grooming / Manipulação de menores\n"
        "› Piadas sobre CP / Referências a abuso infantil\n"
        "› Ameaças / Assédio / Extorsão\n"
        "╰─ **Resultam em ação permanente imediata. Sem exceções.**\n\n"

        "-# ▸ Revise as regras para mais informações.\n"
        "-# ╰─ Celestials Dragons  ·  Punishments"
    ),
}

# ─────────────────────────────────────────────
#  L A N G   O P T I O N S
# ─────────────────────────────────────────────

LANG_OPTIONS = [
    {
        "label": "English",
        "value": "en",
        "emoji": {"id": "1499826848035766454", "name": "emoji_3"}
    },
    {
        "label": "Español",
        "value": "es",
        "emoji": {"id": "1499826873226629241", "name": "emoji_5"}
    },
    {
        "label": "Português",
        "value": "pt",
        "emoji": {"id": "1499826860794708069", "name": "emoji_4"}
    }
]

# ─────────────────────────────────────────────
#  P A Y L O A D S
# ─────────────────────────────────────────────

def build_accept_payload() -> dict:
    return {
        "flags": 1 << 15,
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 10,
                        "content": (
                            "▸ By accepting, you acknowledge that you have read and understood "
                            "the punishment system of **Celestials Dragons**.\n"
                            "╰─ Violations will result in the sanctions described — "
                            "ignorance is __not__ an excuse."
                        )
                    },
                    {"type": 14, "divider": True, "spacing": 1},
                    {
                        "type": 9,
                        "components": [
                            {
                                "type": 10,
                                "content": "-# ╰─ Tap to confirm you understand."
                            }
                        ],
                        "accessory": {
                            "type": 2,
                            "style": 3,
                            "label": "Accepted",
                            "custom_id": "accept_punishments",
                            "emoji": {"id": "1497991468584014025", "name": "emoji_2"}
                        }
                    }
                ]
            }
        ]
    }


def build_lang_select_payload() -> dict:
    return {
        "flags": 1 << 15,
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 10,
                        "content": (
                            "▸ Choose your language to view the punishment system.\n"
                            "╰─ The content will be shown below."
                        )
                    },
                    {"type": 14, "divider": True, "spacing": 1},
                    {
                        "type": 10,
                        "content": "-# ╰─ Select your language below."
                    }
                ]
            },
            {
                "type": 1,
                "components": [
                    {
                        "type": 3,
                        "custom_id": "punish_lang_select",
                        "placeholder": "Select your language...",
                        "options": LANG_OPTIONS
                    }
                ]
            }
        ]
    }


def build_punishment_payload(lang: str) -> dict:
    return {
        "flags": 1 << 15,
        "components": [
            {
                "type": 17,
                "components": [
                    {
                        "type": 10,
                        "content": PUNISHMENTS_CONTENT[lang]
                    }
                ]
            },
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 1,
                        "label": "Back",
                        "custom_id": "back_to_langs"
                    }
                ]
            }
        ]
    }

# ─────────────────────────────────────────────
#  A P I   H E L P E R S
# ─────────────────────────────────────────────

async def send_v2(channel_id: int, payload: dict):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                print(f"[ERROR send] {resp.status}: {text}")
                return f"{resp.status}: {text[:300]}"
            else:
                print("[OK] Mensaje enviado")
                return None


async def defer_update(interaction_id: str, token: str):
    url = f"https://discord.com/api/v10/interactions/{interaction_id}/{token}/callback"
    body = {"type": 6}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers={"Content-Type": "application/json"}) as resp:
            if resp.status not in (200, 201, 204):
                text = await resp.text()
                print(f"[ERROR defer] {resp.status}: {text}")


async def edit_original(token: str, payload: dict):
    url = f"https://discord.com/api/v10/webhooks/{APPLICATION_ID}/{token}/messages/@original"
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, json=payload, headers={"Content-Type": "application/json"}) as resp:
            if resp.status not in (200, 201, 204):
                text = await resp.text()
                print(f"[ERROR edit_original] {resp.status}: {text}")


async def send_followup_ephemeral(token: str, content: str):
    url = f"https://discord.com/api/v10/webhooks/{APPLICATION_ID}/{token}"
    payload = {"content": content, "flags": 64}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as resp:
            if resp.status not in (200, 201, 204):
                text = await resp.text()
                print(f"[ERROR followup] {resp.status}: {text}")


async def update_interaction(interaction_id: str, token: str, payload: dict):
    url = f"https://discord.com/api/v10/interactions/{interaction_id}/{token}/callback"
    body = {"type": 7, "data": payload}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers={"Content-Type": "application/json"}) as resp:
            if resp.status not in (200, 201, 204):
                text = await resp.text()
                print(f"[ERROR update] {resp.status}: {text}")

# ─────────────────────────────────────────────
#  B O T
# ─────────────────────────────────────────────

@client.event
async def on_ready():
    print(f"[ONLINE] {client.user} listo")


def has_permission(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(role.id in ALLOWED_ROLES for role in member.roles)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.content.strip() == ">setuppunishments":
        if not has_permission(message.author):
            err = await message.reply("❌ No tenés permisos para usar este comando.", delete_after=5)
            return
        try:
            await message.delete()
        except Exception as e:
            print(f"[WARN] No se pudo borrar el mensaje: {e}")

        error = await send_v2(CHANNEL_PUNISHMENTS, build_accept_payload())
        if error:
            err_msg = await message.channel.send(f"❌ **Error al enviar el mensaje:**\n```{error}```")
            await err_msg.delete(delay=15)


@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id", "")

    if custom_id == "accept_punishments":
        await defer_update(str(interaction.id), interaction.token)
        await asyncio.sleep(1)

        has_role = any(role.id == REQUIRED_ROLE_ID for role in interaction.user.roles)

        if has_role:
            await edit_original(interaction.token, build_lang_select_payload())
            await send_followup_ephemeral(
                interaction.token,
                "◈ **Punishments Accepted** — You have acknowledged the "
                "punishment system of **Celestials Dragons**."
            )
        else:
            await edit_original(interaction.token, build_accept_payload())
            await send_followup_ephemeral(
                interaction.token,
                "▸ **Rejected** — You do not have the required role "
                "to access the punishment system."
            )

    elif custom_id == "punish_lang_select":
        lang = interaction.data.get("values", ["en"])[0]
        await update_interaction(
            str(interaction.id),
            interaction.token,
            build_punishment_payload(lang)
        )

    elif custom_id == "back_to_langs":
        await update_interaction(
            str(interaction.id),
            interaction.token,
            build_lang_select_payload()
        )


client.run(TOKEN)
