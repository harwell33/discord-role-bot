# === bot.py ===
import discord
from discord.ext import commands, tasks
from database import (
    init_db, add_role, get_active_roles, remove_role, 
    get_users_with_role, get_expired_roles, role_exists, 
    prolong_role, get_log_channel, set_log_channel  # Додано імпорт get_log_channel
)
from datetime import datetime
import random
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# === Dropbox завантаження/збереження ===
import dropbox

def download_db():
    token = os.environ.get("DROPBOX_TOKEN")
    if not token:
        print("❌ DROPBOX_TOKEN not set")
        return

    dbx = dropbox.Dropbox(token)
    try:
        metadata, res = dbx.files_download("/roles.db")
        os.makedirs("data", exist_ok=True)
        with open("data/roles.db", "wb") as f:
            f.write(res.content)
        print("✅ roles.db завантажено з Dropbox")
    except dropbox.exceptions.ApiError as e:
        print("⚠️ Не вдалося завантажити roles.db з Dropbox:", e)

def upload_db():
    token = os.environ.get("DROPBOX_TOKEN")
    if not token:
        print("❌ DROPBOX_TOKEN not set")
        return

    dbx = dropbox.Dropbox(token)
    try:
        with open("data/roles.db", "rb") as f:
            dbx.files_upload(f.read(), "/roles.db", mode=dropbox.files.WriteMode.overwrite)
        print("✅ roles.db збережено у Dropbox")
    except Exception as e:
        print("⚠️ Не вдалося зберегти roles.db у Dropbox:", e)

# === Обробка помилок прав доступу ===
@bot.event
async def on_command_error(ctx, error):
    upload_db()
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ You need the 'Manage Roles' permission to use this command.")
    else:
        raise error

# === Автоматичне зняття прострочених ролей ===
@tasks.loop(hours=24)
async def check_expired_roles():
    expired = get_expired_roles()
    guild = discord.utils.get(bot.guilds)
    for user_id, role_id in expired:
        member = guild.get_member(user_id)
        role = guild.get_role(role_id)
        if member and role:
            await member.remove_roles(role)
            remove_role(user_id, role_id)
            log_channel_id = get_log_channel(guild.id)
            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(f"⏰ Auto-removed `{role.name}` from {member.mention} (expired)")
            print(f"[AUTO] Removed role '{role.name}' from '{member.display_name}' (expired)")

@bot.event
async def on_ready():
    download_db()
    os.makedirs("data", exist_ok=True)
    init_db()
    check_expired_roles.start()
    print(f'Bot {bot.user} is now running!')
    for guild in bot.guilds:
        print(f'Connected to server: {guild.name} (ID: {guild.id})')

# === Команда /assign — видати роль з терміном дії ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def assign(ctx, member: discord.Member, role: discord.Role, days: int = None):
    if role_exists(member.id, role.id):
        await ctx.send(f"⚠️ {member.display_name} already has the role `{role.name}` tracked by the bot.")
        return

    await member.add_roles(role)
    add_role(user_id=member.id, role_id=role.id, days=days, assigned_by=ctx.author.id)
    upload_db()
    log_channel_id = get_log_channel(ctx.guild.id)
    if log_channel_id:
        log_channel = ctx.guild.get_channel(log_channel_id)
        if log_channel:
            await log_channel.send(f"✅ {ctx.author.mention} assigned `{role.name}` to {member.mention}" + (f" for {days}d." if days else "."))
    await ctx.send(f"✅ Role `{role.name}` has been assigned to {member.display_name}" + (f" for {days} days." if days else "."))

# === Команда /remove — зняти роль ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def remove(ctx, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    remove_role(member.id, role.id)
    upload_db()
    log_channel_id = get_log_channel(ctx.guild.id)
    if log_channel_id:
        log_channel = ctx.guild.get_channel(log_channel_id)
        if log_channel:
            await log_channel.send(f"🗑️ {ctx.author.mention} removed `{role.name}` from {member.mention}")
    await ctx.send(f"🗑️ Role `{role.name}` has been removed from {member.display_name}.")

# === Команда /prolong — подовжити термін дії ролі ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def prolong(ctx, member: discord.Member, role: discord.Role, days: int):
    if not role_exists(member.id, role.id):
        await ctx.send(f"⚠️ Role `{role.name}` is not tracked for {member.display_name}.")
        return

    prolong_role(member.id, role.id, days)
    upload_db()  # Додано збереження в базу
    log_channel_id = get_log_channel(ctx.guild.id)
    if log_channel_id:
        log_channel = ctx.guild.get_channel(log_channel_id)
        if log_channel:
            await log_channel.send(f"🔁 {ctx.author.mention} prolonged `{role.name}` for {member.mention} by {days}d")
    await ctx.send(f"🔁 Role `{role.name}` for {member.display_name} has been extended by {days} days.")

# === Команда /myroles — показати активні ролі користувача ===
@bot.command()
async def myroles(ctx):
    user_roles = get_active_roles(ctx.author.id)
    if not user_roles:
        await ctx.send("📭 You have no active roles assigned by the bot.")
        return

    lines = []
    for role_id, expires_at in user_roles:
        role = ctx.guild.get_role(role_id)
        if not role:
            continue
        if expires_at:
            try:
                delta = datetime.fromisoformat(expires_at) - datetime.utcnow()
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                lines.append(f"• `{role.name}` — {days}d {hours}h {minutes}m {seconds}s left")
            except ValueError:
                lines.append(f"• `{role.name}` — error in date")
        else:
            lines.append(f"• `{role.name}` — permanent")

    await ctx.send("🧾 Your active roles:\n" + "\n".join(lines))

# === Команда /list — список користувачів з роллю ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def list(ctx, role: discord.Role):
    users = get_users_with_role(role.id)
    if not users:
        await ctx.send(f"📭 No users have the role `{role.name}`.")
        return

    lines = []
    for user_id, expires_at in users:
        member = ctx.guild.get_member(user_id)
        if not member:
            continue
        if expires_at:
            try:
                delta = datetime.fromisoformat(expires_at) - datetime.utcnow()
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                lines.append(f"• {member.display_name} — {days}d {hours}h {minutes}m {seconds}s left")
            except ValueError:
                lines.append(f"• {member.display_name} — error in date")
        else:
            lines.append(f"• {member.display_name} — permanent")

    await ctx.send(f"📋 Users with role `{role.name}`:\n" + "\n".join(lines))

# === Команда /randomrole — видати роль випадковим учасникам ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def randomrole(ctx, role: discord.Role, days: int, amount: int):
    eligible_members = [
        m for m in ctx.guild.members
        if not m.bot and not role_exists(m.id, role.id) and role not in m.roles
    ]

    if len(eligible_members) < amount:
        await ctx.send(f"⚠️ Not enough eligible members. Found only {len(eligible_members)}.")
        return

    selected = random.sample(eligible_members, amount)
    for member in selected:
        await member.add_roles(role)
        add_role(member.id, role.id, days=days, assigned_by=ctx.author.id)
    
    upload_db()  # Додано збереження в базу
    mentions = ", ".join(m.mention for m in selected)
    await ctx.send(f"🎲 Assigned role `{role.name}` for {days} days to: {mentions}")

# === Команда /logchannel — задати канал для логів ===
@bot.command()
@commands.has_permissions(manage_guild=True)
async def logchannel(ctx, channel: discord.TextChannel):
    set_log_channel(ctx.guild.id, channel.id)
    await ctx.send(f"📓 Log channel set to {channel.mention}")

# === Команда /expires — список ролей, що скоро завершаться ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def expires(ctx):
    all_data = []
    for member in ctx.guild.members:
        if member.bot:
            continue
        roles = get_active_roles(member.id)
        for role_id, expires_at in roles:
            if expires_at:
                try:
                    delta = datetime.fromisoformat(expires_at) - datetime.utcnow()
                    days = delta.days
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    if delta.total_seconds() > 0:
                        role = ctx.guild.get_role(role_id)
                        if role:
                            all_data.append(f"• {member.display_name} — `{role.name}` expires in {days}d {hours}h {minutes}m {seconds}s")
                except Exception:
                    continue
    if all_data:
        await ctx.send("⏳ Expiring roles:\n" + "\n".join(all_data))
    else:
        await ctx.send("✅ No expiring roles found.")

# === Команда /disablelog — прибрати лог-канал ===
@bot.command()
@commands.has_permissions(manage_guild=True)
async def disablelog(ctx):
    set_log_channel(ctx.guild.id, None)
    await ctx.send("📵 Log channel disabled.")

# === /help — короткий список доступних команд ===
@bot.command()
async def help(ctx):
    help_text = (
        "🛠 **Available Commands:**\n"
        "`!assign @user @role [days]` — assign a role optionally with duration\n"
        "`!remove @user @role` — remove a role\n"
        "`!prolong @user @role days` — extend role duration\n"
        "`!myroles` — show your active roles\n"
        "`!list @role` — list users with this role\n"
        "`!randomrole @role days count` — randomly assign a role to users\n"
        "`!logchannel #channel` — set log channel for role actions\n"
        "`!disablelog` — disable log channel\n"
        "`!expires` — list roles that are about to expire\n"
    )
    await ctx.send(help_text)

# === Запуск веб-сервера для Render ===
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

def run_web_server():
    port = int(os.environ.get("PORT", 3000))
    server = HTTPServer(("", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# === Запуск бота ===
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("❌ Discord token not found. Set the DISCORD_TOKEN environment variable.")
else:
    bot.run(TOKEN)
