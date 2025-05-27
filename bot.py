# bot.py
import discord
from discord.ext import commands, tasks
from database import init_db, add_role, get_active_roles, remove_role, get_users_with_role, get_expired_roles, role_exists, prolong_role
from datetime import datetime
import random

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ADMIN_ROLE_NAME більше не використовується, бо перевірка йде через Discord permissions

@bot.event
async def on_command_error(ctx, error):
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
            print(f"[AUTO] Removed role '{role.name}' from '{member.display_name}' (expired)")

@bot.event
async def on_ready():
    os.makedirs("data", exist_ok=True)  # <-- створюється папка
    init_db()
    check_expired_roles.start()
    print(f'Bot {bot.user} is now running!')

# === /assign — призначення ролі користувачу ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def assign(ctx, member: discord.Member, role: discord.Role, days: int = None):
    if not has_admin_role(ctx):
        await ctx.send("⛔ You don't have permission to use this command.")
        return

    if role_exists(member.id, role.id):
        await ctx.send(f"⚠️ {member.display_name} already has the role `{role.name}` tracked by the bot.")
        return

    await member.add_roles(role)
    add_role(user_id=member.id, role_id=role.id, days=days, assigned_by=ctx.author.id)
    await ctx.send(f"✅ Role `{role.name}` has been assigned to {member.display_name}" + (f" for {days} days." if days else "."))

# === /prolong — продовження терміну дії ролі ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def prolong(ctx, member: discord.Member, role: discord.Role, days: int):
    if not has_admin_role(ctx):
        await ctx.send("⛔ You don't have permission to use this command.")
        return

    if not role_exists(member.id, role.id):
        await ctx.send(f"⚠️ Role `{role.name}` is not tracked for {member.display_name}.")
        return

    prolong_role(member.id, role.id, days)
    await ctx.send(f"🔁 Role `{role.name}` for {member.display_name} has been extended by {days} days.")

# === /myroles — показати свої ролі та залишок днів ===
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
                dt_expire = datetime.fromisoformat(expires_at)
                delta = dt_expire - datetime.utcnow()
                days, seconds = delta.days, delta.seconds
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                lines.append(
                    f"• `{role.name}` — {days}d {hours}h {minutes}m {seconds}s left "
                    f"(until {dt_expire.strftime('%Y-%m-%d %H:%M:%S UTC')})"
                )
            except ValueError:
                lines.append(f"• `{role.name}` — error in date")
        else:
            lines.append(f"• `{role.name}` — permanent")

    await ctx.send("🧾 Your active roles:\n" + "\n".join(lines))

# === /remove — видалити роль вручну ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def remove(ctx, member: discord.Member, role: discord.Role):
    if not has_admin_role(ctx):
        await ctx.send("⛔ You don't have permission to use this command.")
        return

    await member.remove_roles(role)
    remove_role(member.id, role.id)
    await ctx.send(f"🗑️ Role `{role.name}` has been removed from {member.display_name}.")

# === /list — список користувачів з роллю ===
@bot.command()
async def list(ctx, role: discord.Role):
    members = get_users_with_role(role.id)
    if not members:
        await ctx.send(f"📭 No users found with role `{role.name}`.")
        return

    lines = []
    for user_id, expires_at in members:
        member = ctx.guild.get_member(user_id)
        if not member:
            continue
        if expires_at:
            try:
                dt_expire = datetime.fromisoformat(expires_at)
                delta = dt_expire - datetime.utcnow()
                days, seconds = delta.days, delta.seconds
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                lines.append(
                    f"• {member.display_name} — {days}d {hours}h {minutes}m {seconds}s left "
                    f"(until {dt_expire.strftime('%Y-%m-%d %H:%M:%S UTC')})"
                )
            except ValueError:
                lines.append(f"• {member.display_name} — error in date")
        else:
            lines.append(f"• {member.display_name} — permanent")

    await ctx.send(f"🧾 Members with role `{role.name}`:\n" + "\n".join(lines))

# === /randomrole — випадкова видача ролі N учасникам на X днів ===
@bot.command()
@commands.has_permissions(manage_roles=True)
async def randomrole(ctx, role: discord.Role, days: int, amount: int):
    if not has_admin_role(ctx):
        await ctx.send("⛔ You don't have permission to use this command.")
        return

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

    mentions = ", ".join(m.mention for m in selected)
    await ctx.send(f"🎲 Assigned role `{role.name}` for {days} days to: {mentions}")
    
# === Запуск бота як веб-сервісу ===
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = os.environ.get("DISCORD_TOKEN")

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

if not TOKEN:
    print("❌ Discord token not found. Set the DISCORD_TOKEN environment variable.")
else:
    bot.run(TOKEN)
