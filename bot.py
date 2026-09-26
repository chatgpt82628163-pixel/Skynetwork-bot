"""
SkyNetwork Discord bot: verification through SkyNetwork Connect.

A member presses the button, signs in on the SkyNetwork website with their CID and password, and comes back:
the bot then knows their real CID and name, sets the nickname "First Last - CID" and gives the verified role.
The password never reaches the bot. One CID belongs to one Discord account.

Settings come from the environment (see .env.example; on the server /etc/skynetwork-bot.env):
  DISCORD_TOKEN          bot token from the Discord Developer Portal
  CONNECT_CLIENT_ID      client of SkyNetwork Connect (website: Staff → Connect)
  CONNECT_CLIENT_SECRET  its secret
  SKYNET_URL             the website, e.g. https://sky.network.npzy2.us
  PUBLIC_URL             where this bot is reached from outside, e.g. https://sky.network.npzy2.us/discord
                         (the redirect address of the client is PUBLIC_URL + /callback)
  BOT_WEB_PORT           local port of the bot's web page (default 8090; nginx forwards PUBLIC_URL here)
  VERIFIED_ROLE_ID       optional: role given to verified members
  BOT_DB                 optional: file of the CID ↔ Discord links (default links.db next to this file)
"""
import base64
import hashlib
import html
import os
import secrets
import sqlite3
import time

import aiohttp
import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands

BOT_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CLIENT_ID = os.environ.get("CONNECT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CONNECT_CLIENT_SECRET", "")
SKYNET_URL = os.environ.get("SKYNET_URL", "https://sky.network.npzy2.us").rstrip("/")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
WEB_PORT = int(os.environ.get("BOT_WEB_PORT", "8090"))
VERIFIED_ROLE_ID = int(os.environ.get("VERIFIED_ROLE_ID") or 0)
DB_PATH = os.environ.get("BOT_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "links.db")

REDIRECT_URI = f"{PUBLIC_URL}/callback"
LINK_LIFETIME = 10 * 60  # seconds a sign-in link stays valid

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# Sign-ins in progress: state -> (Discord user id, guild id, PKCE verifier, expiry, the interaction to update).
pending: dict[str, tuple[int, int, str, float, discord.Interaction]] = {}


# ---- CID ↔ Discord links -----------------------------------------------------------------------

def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS links (guild_id INTEGER, cid INTEGER, discord_id INTEGER, name TEXT, linked_at INTEGER,"
              " PRIMARY KEY (guild_id, cid))")
    return c


def link(guild_id: int, cid: int, discord_id: int, name: str) -> int | None:
    """Stores the link; returns the Discord account that had this CID before, if another one."""
    with db() as c:
        row = c.execute("SELECT discord_id FROM links WHERE guild_id = ? AND cid = ?", (guild_id, cid)).fetchone()
        # A Discord account has one CID: an earlier link of this account to another CID goes.
        c.execute("DELETE FROM links WHERE guild_id = ? AND discord_id = ?", (guild_id, discord_id))
        c.execute("INSERT OR REPLACE INTO links VALUES (?, ?, ?, ?, ?)", (guild_id, cid, discord_id, name, int(time.time())))
    return row[0] if row and row[0] != discord_id else None


# ---- helpers --------------------------------------------------------------------------------------

def make_nickname(name: str, cid: int | str) -> str:
    """'First Last - CID', at most 32 characters (Discord's limit); the name is shortened, never the CID."""
    suffix = f" - {cid}"
    name = name.strip() or f"User {cid}"
    room = 32 - len(suffix)
    return (name[:room].rstrip() if len(name) > room else name) + suffix


def authorize_url(state: str, verifier: str) -> str:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = {
        "response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "scope": "profile",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    }
    from urllib.parse import urlencode
    return f"{SKYNET_URL}/oauth/authorize?{urlencode(query)}"


async def fetch_profile(code: str, verifier: str) -> dict:
    """Exchanges the code for a token and reads the member (cid, name, rating...). Raises on failure."""
    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"User-Agent": "SkyNetworkBot/2.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
        form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code_verifier": verifier}
        async with s.post(f"{SKYNET_URL}/oauth/token", data=form) as r:
            token = await r.json(content_type=None)
            if r.status != 200:
                raise RuntimeError(token.get("error_description") or token.get("error") or f"status {r.status}")
        async with s.get(f"{SKYNET_URL}/oauth/userinfo", headers={"Authorization": f"Bearer {token['access_token']}"}) as r:
            profile = await r.json(content_type=None)
            if r.status != 200:
                raise RuntimeError(profile.get("error_description") or f"status {r.status}")
    return profile


async def apply_to_member(guild: discord.Guild, discord_id: int, profile: dict) -> str:
    """Nickname and role for the verified member; returns the message for them."""
    cid, name = int(profile["cid"]), str(profile.get("name", ""))
    nickname = make_nickname(name, cid)
    member = await guild.fetch_member(discord_id)
    role = guild.get_role(VERIFIED_ROLE_ID) if VERIFIED_ROLE_ID else None

    previous = link(guild.id, cid, discord_id, name)
    if previous:
        # The CID moved to this account: the old one loses the nickname and the role.
        try:
            old = await guild.fetch_member(previous)
            await old.edit(nick=None)
            if role:
                await old.remove_roles(role, reason=f"CID {cid} verified by another account")
        except discord.HTTPException:
            pass

    notes = []
    try:
        if role:
            await member.add_roles(role, reason=f"SkyNetwork CID {cid}")
    except discord.Forbidden:
        notes.append("не удалось выдать роль: роль бота должна быть выше неё")
    if member.id == guild.owner_id:
        notes.append("вы владелец сервера — Discord не даёт боту менять ваш ник")
    else:
        try:
            await member.edit(nick=nickname, reason=f"SkyNetwork CID {cid}")
        except discord.Forbidden:
            notes.append("не удалось сменить ник: роль бота должна стоять выше вашей роли")
    text = f"✅ Верификация пройдена: **{nickname}**"
    return text + ("\n⚠️ " + "; ".join(notes) if notes else "")


# ---- Discord ----------------------------------------------------------------------------------------

class VerifyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Пройти верификацию", style=discord.ButtonStyle.success, emoji="✈️",
                       custom_id="verify_cid_persistent")
    async def click_verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = time.time()
        for s in [s for s, p in pending.items() if p[3] < now]:
            pending.pop(s, None)
        state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        pending[state] = (interaction.user.id, interaction.guild_id, verifier, now + LINK_LIFETIME, interaction)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Войти через SkyNetwork", url=authorize_url(state, verifier), emoji="🔐"))
        await interaction.response.send_message(
            "Нажмите кнопку и войдите на сайте SkyNetwork своим CID и паролем. Ссылка личная и действует 10 минут.",
            view=view, ephemeral=True)


@bot.tree.command(name="setup_verify", description="Отправить сообщение с кнопкой верификации в этот канал")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌐 Верификация SkyNetwork",
        description="Нажмите на кнопку и войдите на сайте SkyNetwork: бот поставит ник «Имя Фамилия - CID».",
        color=discord.Color.from_rgb(46, 134, 222),
    )
    await interaction.channel.send(embed=embed, view=VerifyButtonView())
    await interaction.response.send_message("Кнопка размещена!", ephemeral=True)


# ---- web page the website sends the member back to -----------------------------------------------------

def page(title: str, text: str, ok: bool) -> web.Response:
    color = "#2e86de" if ok else "#d64545"
    body = (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            f"<title>{html.escape(title)}</title><body style='font-family:system-ui;background:#10161c;color:#e6ebf2;"
            f"display:grid;place-items:center;min-height:100vh;margin:0'><div style='max-width:420px;padding:24px;"
            f"border-top:4px solid {color}'><h2>{html.escape(title)}</h2><p>{text}</p></div>")
    return web.Response(text=body, content_type="text/html")


async def callback(request: web.Request) -> web.Response:
    state = request.query.get("state", "")
    entry = pending.pop(state, None)
    if not entry or entry[3] < time.time():
        return page("Ссылка устарела", "Нажмите кнопку верификации в Discord ещё раз.", False)
    discord_id, guild_id, verifier, _, interaction = entry
    if "error" in request.query:
        return page("Вход отменён", "Верификация не пройдена. Можно попробовать ещё раз из Discord.", False)
    try:
        profile = await fetch_profile(request.query.get("code", ""), verifier)
        guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
        message = await apply_to_member(guild, discord_id, profile)
    except Exception as e:
        print(f"Verification failed: {e}")
        return page("Не получилось", "Не удалось проверить вход. Попробуйте ещё раз или напишите администрации.", False)
    try:
        await interaction.edit_original_response(content=message, view=None)
    except discord.HTTPException:
        pass
    plain = html.escape(message.replace("**", "").replace("✅ ", ""))
    return page("Готово", f"{plain}<br><br>Можно вернуться в Discord.", True)


async def start_web():
    app = web.Application()
    app.router.add_get("/callback", callback)
    app.router.add_get("/health", lambda _: web.Response(text="ok"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", WEB_PORT).start()
    print(f"Web page on 127.0.0.1:{WEB_PORT}, redirect address {REDIRECT_URI}")


@bot.event
async def setup_hook():
    bot.add_view(VerifyButtonView())  # the button keeps working after a restart
    await start_web()
    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")
    except Exception as e:
        print(f"Could not sync slash commands: {e}")


@bot.event
async def on_ready():
    print(f"Bot started as {bot.user}")


if __name__ == "__main__":
    missing = [n for n, v in (("DISCORD_TOKEN", BOT_TOKEN), ("CONNECT_CLIENT_ID", CLIENT_ID),
                               ("CONNECT_CLIENT_SECRET", CLIENT_SECRET), ("PUBLIC_URL", PUBLIC_URL)) if not v]
    if missing:
        raise SystemExit("Not set: " + ", ".join(missing))
    bot.run(BOT_TOKEN)
