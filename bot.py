import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import re
from datetime import datetime

# ========================================================
#                    KONFIGURACJA BOTA
# ========================================================
# TUTAJ WKLEJ SWÓJ AKTUALNY TOKEN Z DISCORD DEVELOPER PORTAL:
TOKEN = "MTU2MzU1MzcxNjIwMjYzNTM3NA.G2JU3G.uT_0FfNf-oeKVz_IhM8QYS9pCJBX81Dtt-Wwes"

# Twój nick na Discordzie do powiadomień AntiNuke na PV
OWNER_NAME = "padowiec2137"

# Dokładna nazwa roli gracza
ROLE_GRACZ_NAME = "GRACZ |  PIACHMC.PL"

# Ranga administracji do ticketów
TICKET_ROLE_NAME = "adm role."

LOBBY_CHANNEL_NAME = "lobby"
PROPOZYCJE_CHANNEL_NAME = "propozycje"
TICKETS_CATEGORY_NAME = "TICKETY"

EMBED_COLOR = 0x0099FF  # Odcień błękitu ze SkyHub

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

def has_ticket_permission(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    for role in member.roles:
        if role.name.strip().lower() == TICKET_ROLE_NAME.strip().lower():
            return True
    return False

def find_gracz_role(guild: discord.Guild):
    for role in guild.roles:
        clean = " ".join(role.name.split()).lower()
        if clean == "gracz | piachmc.pl" or role.name == ROLE_GRACZ_NAME:
            return role
    for role in guild.roles:
        if role.name.strip().lower() == "gracz":
            return role
    return None

async def get_owner(guild: discord.Guild):
    for m in guild.members:
        if m.name.lower() == OWNER_NAME.lower():
            return m
    return guild.owner


# ========================================================
#             ANTINUKE: PANEL POTWIERDZENIA NA PV
# ========================================================
class AntiNukeConfirmView(discord.ui.View):
    def __init__(self, action_type: str, executor: discord.Member, target_info: str):
        super().__init__(timeout=120)
        self.action_type = action_type
        self.executor = executor
        self.target_info = target_info

    @discord.ui.button(label="Akceptuj", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"✅ **Zaakceptowano:** `{self.action_type}` od użytkownika **{self.executor}**.",
            view=self
        )

    @discord.ui.button(label="Odrzuć (Zablokuj)", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            danger_roles = [r for r in self.executor.roles if r.permissions.administrator or r.permissions.manage_guild or r.permissions.ban_members]
            if danger_roles:
                await self.executor.remove_roles(*danger_roles, reason="AntiNuke: Odrzucono próbę przez Właściciela")
        except Exception:
            pass

        await interaction.response.edit_message(
            content=f"🚨 **Odrzucono akcję!** Zablokowano próbę `{self.action_type}` i odebrano uprawnienia użytkownikowi **{self.executor}**.",
            view=self
        )


async def send_antinuke_alert(guild: discord.Guild, action_type: str, executor: discord.Member, target_info: str):
    if not executor or executor.id == bot.user.id or executor.name.lower() == OWNER_NAME.lower():
        return

    owner = await get_owner(guild)
    if not owner:
        return

    embed = discord.Embed(
        title="🛡️ ANTY-NUKE: WYKRYTO PODEJRZANĄ AKCJĘ!",
        description=(
            f"Ktoś wykonuje wrażliwą czynność na serwerze **{guild.name}**!\n\n"
            f"👤 **Wykonawca:** {executor.mention} (`{executor.name}` | ID: `{executor.id}`)\n"
            f"⚡ **Akcja:** `{action_type}`\n"
            f"🎯 **Cel:** `{target_info}`\n"
            f"⏰ **Czas:** `{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`\n\n"
            f"Wybierz czy chcesz **zaakceptować** czy **zablokować i odebrać uprawnienia** wykonawcy!"
        ),
        color=0xED4245
    )
    embed.set_footer(text="PIACHMC.PL • System Ochrony AntiNuke")

    try:
        view = AntiNukeConfirmView(action_type, executor, target_info)
        await owner.send(embed=embed, view=view)
    except Exception as e:
        print(f"Błąd wysyłania alertu AntiNuke: {e}")


# ========================================================
#            1. WERYFIKACJA (1:1 ZE SKYHUB)
# ========================================================
class MathVerifyModal(discord.ui.Modal):
    def __init__(self, num1: int, num2: int):
        self.num1 = num1
        self.num2 = num2
        self.expected = num1 + num2
        super().__init__(title="PIACHMC.PL ▸ Weryfikacja")
        
        self.answer_input = discord.ui.TextInput(
            label=f"Rozwiąż działanie: {num1} + {num2} = ?",
            placeholder="Wpisz poprawny wynik...",
            required=True,
            max_length=5
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_val = self.answer_input.value.strip()
        try:
            val_int = int(user_val)
        except ValueError:
            await interaction.response.send_message("❌ **Błąd:** Musisz podać liczbę!", ephemeral=True)
            return

        if val_int == self.expected:
            guild = interaction.guild
            member = interaction.user
            role = find_gracz_role(guild)

            if not role:
                try:
                    role = await guild.create_role(name=ROLE_GRACZ_NAME)
                except Exception:
                    pass

            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "⚠️ **Wynik poprawny!** Upewnij się, że rola bota na liście ról Discord jest WYŻEJ niż ranga gracza.",
                        ephemeral=True
                    )
                    return
                except Exception as e:
                    print(f"Błąd nadawania rangi: {e}")

            await interaction.response.send_message(
                f"✅ **Pomyślnie zweryfikowano!** Otrzymałeś rangę **{role.name if role else ROLE_GRACZ_NAME}** na serwerze **PIACHMC.PL**.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ **Napisałeś złe działanie!** Spróbuj ponownie.", ephemeral=True)

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kliknij, aby przejść weryfikacje", style=discord.ButtonStyle.secondary, custom_id="verify_btn")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        await interaction.response.send_modal(MathVerifyModal(num1, num2))


# ========================================================
#             2. TICKETY (1:1 ZE SKYHUB)
# ========================================================
TICKET_CATEGORIES = [
    {"label": "Backup", "desc": "Pomoc w sprawach backupu konta/itemów", "emoji": "💾", "code": "backup"},
    {"label": "Odwołanie od bana", "desc": "Złóż odwołanie od blokady", "emoji": "⚖️", "code": "odwolanie"},
    {"label": "Zgłoś cheatera", "desc": "Zgłoś nieuczciwego gracza", "emoji": "🚨", "code": "cheater"},
    {"label": "Odebranie nagrody", "desc": "Odbiór nagrody z konkursu/eventu", "emoji": "🎁", "code": "nagroda"},
    {"label": "Media", "desc": "Współpraca YT / TikTok / Social", "emoji": "🎬", "code": "media"}
]

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zamknij ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        member = interaction.user
        is_creator = f"ID: {member.id}" in (channel.topic or "")

        if not (is_creator or has_ticket_permission(member)):
            await interaction.response.send_message(f"❌ Tylko autor lub ranga **{TICKET_ROLE_NAME}** może zamknąć to zgłoszenie!", ephemeral=True)
            return

        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        embed = discord.Embed(
            title="🔒 Zamykanie zgłoszenia",
            description="Ticket zostanie usunięty za **5 sekund**...\nDziękujemy za kontakt z serwerem **PIACHMC.PL**!",
            color=0xED4245
        )
        await interaction.followup.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Zamknięty przez {member.name}")
        except Exception:
            pass

class TicketDetailsModal(discord.ui.Modal):
    def __init__(self, cat_code: str, cat_label: str):
        self.cat_code = cat_code
        self.cat_label = cat_label
        super().__init__(title=f"Zgłoszenie: {cat_label}")

        self.help_needed = discord.ui.TextInput(
            label="Jakiej pomocy potrzebujesz?",
            placeholder="Opisz dokładnie swój problem...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.extra_info = discord.ui.TextInput(
            label="Dodatkowe informacje (nick, dowody)",
            placeholder="Podaj swój nick z gry, linki itp...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.add_item(self.help_needed)
        self.add_item(self.extra_info)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user

        for ch in guild.text_channels:
            if ch.topic and f"ID: {member.id}" in ch.topic:
                await interaction.followup.send(f"❌ Pamiętaj, że możesz mieć tylko **jeden otwarty ticket**! Twój ticket: {ch.mention}", ephemeral=True)
                return

        category = discord.utils.get(guild.categories, name=TICKETS_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKETS_CATEGORY_NAME)

        channel_name = f"ticket-{self.cat_code}-{member.name.lower()[:10]}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        ticket_role = discord.utils.get(guild.roles, name=TICKET_ROLE_NAME)
        if ticket_role:
            overwrites[ticket_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Kategoria: {self.cat_label} | ID: {member.id}"
        )

        embed = discord.Embed(
            description=(
                f"```PIACHMC.PL x Zgłoszenie: {self.cat_label}```\n"
                f"> Witaj {member.mention}! Dziękujemy za kontakt z administracją.\n"
                f"> Prosimy o cierpliwość, ranga **{TICKET_ROLE_NAME}** wkrótce odpowie.\n\n"
                f"**❓ Jakiej pomocy potrzebujesz?**\n"
                f"```{self.help_needed.value}```\n"
                f"**📝 Dodatkowe informacje:**\n"
                f"```{self.extra_info.value.strip() if self.extra_info.value else 'Brak'}```"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text="PIACHMC.PL • Twoje małe wielkie imperium!")

        view = CloseTicketView()
        role_ping = ticket_role.mention if ticket_role else f"@{TICKET_ROLE_NAME}"
        await ticket_channel.send(content=f"{member.mention} | {role_ping}", embed=embed, view=view)
        await interaction.followup.send(f"✅ Twój ticket został utworzony: {ticket_channel.mention}", ephemeral=True)

class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=cat["label"], description=cat["desc"], emoji=cat["emoji"], value=cat["code"])
            for cat in TICKET_CATEGORIES
        ]
        super().__init__(
            placeholder="Aktualnie nie masz zadnej zaznaczonej kategorii!",
            min_values=1,
            max_values=1,
            custom_id="ticket_category_select",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_code = self.values[0]
        selected_cat = next((c for c in TICKET_CATEGORIES if c["code"] == selected_code), None)
        cat_label = selected_cat["label"] if selected_cat else "Pomoc"
        await interaction.response.send_modal(TicketDetailsModal(selected_code, cat_label))

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


# ========================================================
#                    SAYDM MODAL
# ========================================================
class SayDMModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Wysyłanie DM do Wszystkich")

        self.dm_title = discord.ui.TextInput(
            label="Tytuł Wiadomości",
            placeholder="np. Nowa edycja piachmc.pl!",
            required=True,
            max_length=100
        )
        self.dm_content = discord.ui.TextInput(
            label="Treść Wiadomości",
            placeholder="Wpisz treść wiadomości do graczy...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.dm_title)
        self.add_item(self.dm_content)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        members = [m for m in guild.members if not m.bot]

        embed = discord.Embed(
            title=f"📢 {self.dm_title.value}",
            description=self.dm_content.value,
            color=0xFEE75C,
            timestamp=datetime.now()
        )
        embed.set_author(name="PIACHMC.PL", icon_url=guild.icon.url if guild.icon else None)
        embed.set_footer(text="PIACHMC.PL • Twoje małe wielkie imperium!")

        success_count = 0
        blocked_members = []
        await interaction.followup.send(f"⏳ Wysyłanie DM do {len(members)} graczy...", ephemeral=True)

        for member in members:
            try:
                await member.send(embed=embed)
                success_count += 1
                await asyncio.sleep(0.3)
            except Exception:
                blocked_members.append(f"• {member.name} ({member.id})")

        blocked_text = "\n".join(blocked_members[:20]) if blocked_members else "Brak"
        if len(blocked_members) > 20:
            blocked_text += f"\n... i {len(blocked_members) - 20} więcej."

        result_embed = discord.Embed(
            title="📊 RAPORT WYSYŁANIA SAYDM",
            color=0x57F287 if len(blocked_members) == 0 else 0xED4245
        )
        result_embed.add_field(name="✅ Wysłano", value=f"**{success_count}**", inline=True)
        result_embed.add_field(name="❌ Zablokowane", value=f"**{len(blocked_members)}**", inline=True)
        result_embed.add_field(name="🚫 Kto zablokował DM", value=f"```{blocked_text}```", inline=False)
        result_embed.set_footer(text="PIACHMC.PL • Twoje małe wielkie imperium!")

        await interaction.followup.send(embed=result_embed, ephemeral=True)


# ========================================================
#                    EVENTY BOTA & ANTILINK / ANTIPING
# ========================================================
@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🤖 Bot zalogowany jako: {bot.user.name}")
    print(f"👑 Właściciel do autoryzacji AntiNuke: {OWNER_NAME}")
    print(f"🎖️ Rola gracza: {ROLE_GRACZ_NAME}")
    print(f"🛡️ Rola administracji: {TICKET_ROLE_NAME}")
    print("=" * 50)

    bot.add_view(VerificationView())
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView())

    try:
        synced = await bot.tree.sync()
        print(f"⚡ Zsynchronizowano {len(synced)} komend slash.")
    except Exception as e:
        print(f"Błąd synchronizacji: {e}")
        
    await bot.change_presence(activity=discord.Game(name="piachmc.pl 🏜️"))


# ----------------- ANTINUKE LISTENERY -----------------
@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    guild = channel.guild
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            executor = entry.user
            if executor and executor.id != bot.user.id and executor.name.lower() != OWNER_NAME.lower():
                await send_antinuke_alert(guild, "Usunięcie kanału", executor, f"Kanał #{channel.name}")
    except Exception:
        pass

@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    guild = channel.guild
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            executor = entry.user
            if executor and executor.id != bot.user.id and executor.name.lower() != OWNER_NAME.lower():
                if not channel.name.startswith("ticket-"):
                    await send_antinuke_alert(guild, "Stworzenie nowego kanału", executor, f"Kanał #{channel.name}")
    except Exception:
        pass

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            executor = entry.user
            if executor and executor.id != bot.user.id and executor.name.lower() != OWNER_NAME.lower():
                await send_antinuke_alert(guild, "Zbanowanie gracza", executor, f"Gracz {user.name} ({user.id})")
    except Exception:
        pass

@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                executor = entry.user
                if executor and executor.id != bot.user.id and executor.name.lower() != OWNER_NAME.lower():
                    await send_antinuke_alert(guild, "Wyrzucenie gracza (Kick)", executor, f"Gracz {member.name} ({member.id})")
                break
    except Exception:
        pass


# ----------------- 4. LOBBY (1:1 ZE SKYHUB) -----------------
@bot.event
async def on_member_join(member: discord.Member):
    channel = discord.utils.get(member.guild.text_channels, name=LOBBY_CHANNEL_NAME)
    if not channel:
        for ch in member.guild.text_channels:
            if "lobby" in ch.name.lower() or "powitania" in ch.name.lower():
                channel = ch
                break

    if not channel:
        return

    now_str = datetime.now().strftime("%H:%M")
    embed = discord.Embed(
        description=(
            f"Witaj {member.mention} na oficjalnym Discordzie serwera **PIACHMC.PL**! Mamy nadzieję, że z nami zostaniesz!\n"
            f"Jesteś naszym **{member.guild.member_count}** członkiem! 🎉"
        ),
        color=EMBED_COLOR
    )
    embed.set_author(name="💚 PIACHMC.PL ▸ Lobby", icon_url=member.guild.icon.url if member.guild.icon else None)
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    embed.set_thumbnail(url=avatar_url)
    embed.set_footer(text=f"PIACHMC.PL • Twoje małe wielkie imperium! • Dziś o {now_str}")

    await channel.send(content=member.mention, embed=embed)


# ----------------- 5. PROPOZYCJE, ANTILINK & ANTIPING -----------------
LINK_REGEX = re.compile(r"(https?://\S+|discord\.(gg|io|me|li)/\S+|discord\.com/invite/\S+)", re.IGNORECASE)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 1. ANTIPING
    if ("@everyone" in message.content or "@here" in message.content) and not message.author.guild_permissions.mention_everyone:
        try:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention}, nie masz uprawnień do oznaczania wszystkich!", delete_after=5)
            return
        except Exception:
            pass

    # 2. ANTILINK
    if not message.author.guild_permissions.administrator and LINK_REGEX.search(message.content):
        try:
            await message.delete()
            await message.channel.send(f"🚫 {message.author.mention}, wysyłanie linków i zaproszeń jest zabronione na serwerze **PIACHMC.PL**!", delete_after=5)
            return
        except Exception:
            pass

    # 3. KANAŁ PROPOZYCJI
    if message.channel.name.lower() == PROPOZYCJE_CHANNEL_NAME.lower():
        content = message.content.strip()
        if content:
            try:
                await message.delete()
            except Exception:
                pass

            author = message.author
            avatar_url = author.avatar.url if author.avatar else author.default_avatar.url
            now_str = datetime.now().strftime("%H:%M")

            embed = discord.Embed(
                description=(
                    f"**🟪 Autor propozycji**\n"
                    f"• **Użytkownik:** {author.mention}\n"
                    f"• **Nick:** `{author.name}`\n"
                    f"• **ID:** `{author.id}`\n\n"
                    f"**📜 Treść propozycji**\n"
                    f"> {content}\n\n"
                    f"**❗ Głosowanie społeczności**\n"
                    f"Wyraź swoją opinię klikając w przycisk poniżej:\n"
                    f"• ✅ **Popieram** tę propozycję\n"
                    f"• ❌ **Nie popieram** tej propozycji"
                ),
                color=EMBED_COLOR
            )
            embed.set_author(name=f"{author.name} ({author.name})", icon_url=avatar_url)
            embed.title = "📢 PIACHMC.PL ▸ Nowa Propozycja"
            embed.set_thumbnail(url=avatar_url)
            embed.set_footer(text=f"PIACHMC.PL • Twoje małe wielkie imperium! • Dziś o {now_str}")

            sent_msg = await message.channel.send(embed=embed)
            await sent_msg.add_reaction("✅")
            await sent_msg.add_reaction("❌")
            return

    await bot.process_commands(message)


# ========================================================
#                    KOMENDY SLASH
# ========================================================
@bot.tree.command(name="setup_weryfikacja", description="Wyślij panel weryfikacji")
@app_commands.default_permissions(administrator=True)
async def setup_weryfikacja(interaction: discord.Interaction):
    now_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    embed = discord.Embed(
        description=(
            "| :white_check_mark: **Witaj!** Aby uzyskać dostęp do serwera, musisz się **zweryfikować**.\n\n"
            "• :x: Naciśnięcie przycisku oznacza **akceptację regulaminu** serwera Discord."
        ),
        color=EMBED_COLOR
    )
    embed.set_author(name="PIACHMC.PL ▸ Weryfikacja", icon_url="https://images.emojiterra.com/google/noto-color-emoji/v2.038/512px/1f50e.png")
    embed.set_footer(text=f"PIACHMC.PL • Twoje małe wielkie imperium! • {now_date}")
    
    await interaction.channel.send(embed=embed, view=VerificationView())
    await interaction.response.send_message("✅ Wysłano panel weryfikacji!", ephemeral=True)


@bot.tree.command(name="setup_tickety", description="Wyślij panel ticketów")
@app_commands.default_permissions(administrator=True)
async def setup_tickety(interaction: discord.Interaction):
    embed = discord.Embed(
        description=(
            "```PIACHMC.PL x Stworz Ticket```\n"
            "| Aby stworzyc **Ticket**, kliknij menu znajdujace sie ponizej z **wybrana kategoria**.\n"
            "| Pamietaj, ze mozesz miec tylko **jeden** otwarty ticket!\n\n"
            "🕒 **Prosimy cierpliwie czekac. Czas na odpowiedz to 24h!**\n"
            "📄 **Nie oznaczaj zarzadu (Wlascicieli). Tylko administracja moze oznaczac zarzad!**\n\n"
            "__**Wybierz kategorie, ktora cie interesuje!**__"
        ),
        color=EMBED_COLOR
    )
    embed.set_footer(text="PIACHMC.PL • Twoje male wielkie imperium!")
    await interaction.channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ Wysłano panel ticketów!", ephemeral=True)


@bot.tree.command(name="setup_lobby", description="Ustaw obecny kanał jako Lobby")
@app_commands.default_permissions(administrator=True)
async def setup_lobby(interaction: discord.Interaction):
    global LOBBY_CHANNEL_NAME
    LOBBY_CHANNEL_NAME = interaction.channel.name
    embed = discord.Embed(
        title="💚 KANAŁ LOBBY SKONFIGUROWANY",
        description=f"Pomyślnie ustawiono {interaction.channel.mention} jako kanał powitań!",
        color=EMBED_COLOR
    )
    embed.set_footer(text="PIACHMC.PL • Twoje małe wielkie imperium!")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Kanał {interaction.channel.mention} to teraz Lobby!", ephemeral=True)


@bot.tree.command(name="setup_propozycje", description="Ustaw obecny kanał jako Propozycje")
@app_commands.default_permissions(administrator=True)
async def setup_propozycje(interaction: discord.Interaction):
    global PROPOZYCJE_CHANNEL_NAME
    PROPOZYCJE_CHANNEL_NAME = interaction.channel.name
    embed = discord.Embed(
        title="💡 KANAŁ PROPOZYCJI - PIACHMC.PL",
        description="Napisz swoją propozycję na tym kanale — automatycznie zamieni się w ramkę do głosowania!",
        color=EMBED_COLOR
    )
    embed.set_footer(text="PIACHMC.PL • Twoje małe wielkie imperium!")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Kanał {interaction.channel.mention} to teraz Propozycje!", ephemeral=True)


@bot.tree.command(name="saydm", description="Wyślij wiadomość prywatną (DM) do wszystkich")
@app_commands.default_permissions(administrator=True)
async def saydm(interaction: discord.Interaction):
    if not (interaction.user.guild_permissions.administrator or has_ticket_permission(interaction.user)):
        await interaction.response.send_message("❌ Brak uprawnień!", ephemeral=True)
        return
    await interaction.response.send_modal(SayDMModal())


if __name__ == "__main__":
    bot.run(TOKEN)
