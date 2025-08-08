import discord, asyncio, sqlite3, os, zipfile, time, threading, schedule
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from openai import OpenAI  # ✅ New import

TOKEN = ""

client_ai = OpenAI(api_key="YOUR_OPENAI_API_KEY")  # ✅ Replace with your API Key

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

db_file = "Cafe ☕️.db"
backup_dir = os.path.expanduser("~/Cafe ☕️bot_backups")

if not os.path.exists(db_file):
    if os.path.exists(backup_dir):
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".zip")])
        if backups:
            with zipfile.ZipFile(os.path.join(backup_dir, backups[-1]), 'r') as zip_ref:
                zip_ref.extractall(".")

conn = sqlite3.connect(db_file)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS money (user_id INTEGER PRIMARY KEY, balance INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS invites (inviter_id INTEGER, invited_id INTEGER UNIQUE)")
c.execute("CREATE TABLE IF NOT EXISTS afk (user_id INTEGER PRIMARY KEY, reason TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS prefixes (guild_id INTEGER PRIMARY KEY, prefix TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS commands (prefix TEXT, cmd TEXT, msg TEXT, type TEXT)")
conn.commit()

@bot.event
async def on_guild_join(guild):
    c.execute("INSERT OR IGNORE INTO prefixes (guild_id, prefix) VALUES (?, '!')", (guild.id,))
    conn.commit()

def get_prefix(bot, message):
    try:
        c.execute("SELECT prefix FROM prefixes WHERE guild_id = ?", (message.guild.id,))
        result = c.fetchone()
        return result[0] if result else "!"
    except:
        return "!"

bot.command_prefix = get_prefix

@tree.command(name="setprefix")
@app_commands.checks.has_permissions(administrator=True)
async def setprefix(interaction: discord.Interaction, prefix: str):
    c.execute("INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)", (interaction.guild.id, prefix))
    conn.commit()
    embed = discord.Embed(description=f"✅ Prefix set to `{prefix}`.", color=0x00ffff)
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await tree.sync()
    except Exception as e:
        print("❌ Sync failed:", e)
    await cache_invites()

def backup_task():
    while True:
        try:
            if os.path.exists(db_file):
                filename = f"Cafe ☕️bot_backup_{datetime.now().strftime('%Y-%m-%d--%H-%M-%S')}.zip"
                with zipfile.ZipFile(os.path.join(backup_dir, filename), 'w') as z:
                    z.write(db_file)
                print(" Backup saved.")
        except Exception as e:
            print("❌ Backup failed:", e)
        time.sleep(600)

threading.Thread(target=backup_task, daemon=True).start()

guild_invites = {}
async def cache_invites():
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            guild_invites[guild.id] = invites
        except: pass

@bot.event
async def on_member_join(member):
    await asyncio.sleep(2)
    try:
        new_invites = await member.guild.invites()
        old_invites = guild_invites.get(member.guild.id, [])
        inviter = None
        for invite in new_invites:
            for old in old_invites:
                if invite.code == old.code and invite.uses > old.uses:
                    inviter = invite.inviter
                    break
        if inviter:
            c.execute("INSERT OR IGNORE INTO invites (inviter_id, invited_id) VALUES (?, ?)", (inviter.id, member.id))
            c.execute("INSERT OR IGNORE INTO money (user_id, balance) VALUES (?, 0)", (inviter.id,))
            c.execute("UPDATE money SET balance = balance + 10 WHERE user_id = ?", (inviter.id,))
            conn.commit()
        guild_invites[member.guild.id] = new_invites
    except: pass

@tree.command(name="afk")
async def afk(interaction: discord.Interaction, reason: str = "AFK"):
    c.execute("INSERT OR REPLACE INTO afk (user_id, reason) VALUES (?, ?)", (interaction.user.id, reason))
    conn.commit()
    embed = discord.Embed(description=f" {interaction.user.mention} is now AFK: {reason}", color=0x00ffff)
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    c.execute("SELECT reason FROM afk WHERE user_id = ?", (message.author.id,))
    if c.fetchone():
        c.execute("DELETE FROM afk WHERE user_id = ?", (message.author.id,))
        conn.commit()

    for user in message.mentions:
        c.execute("SELECT reason FROM afk WHERE user_id = ?", (user.id,))
        result = c.fetchone()
        if result:
            await message.channel.send(f" {user.mention} is AFK: {result[0]}")

    c.execute("SELECT * FROM commands")
    for prefix, cmd, msg, typ in c.fetchall():
        if message.content.strip() == prefix + cmd:
            if typ == "send here":
                await message.channel.send(msg)
            elif typ == "dm":
                await message.author.send(msg)

    await bot.process_commands(message)

# 💡 AI Image Generator Command (fixed for OpenAI v1+)
@tree.command(name="imagine", description="Generate an AI image from a prompt.")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        response = client_ai.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="512x512"
        )
        image_url = response.data[0].url
        embed = discord.Embed(title="🧠 AI Image Generator", description=f"Prompt: `{prompt}`", color=0x00ffff)
        embed.set_image(url=image_url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error generating image: {e}")

# Cafe ☕️Money commands
@tree.command(name="money")
async def money(interaction: discord.Interaction, user: discord.User = None):
    user = user or interaction.user
    c.execute("SELECT balance FROM money WHERE user_id = ?", (user.id,))
    result = c.fetchone()
    bal = result[0] if result else 0
    embed = discord.Embed(title=" Cafe ☕️Money Balance", description=f"**{user.mention} has `{bal}` Cafe ☕️Money.**", color=0x00ffff)
    await interaction.response.send_message(embed=embed)

@tree.command(name="givemoney")
async def givemoney(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id == user.id:
        embed = discord.Embed(description="❌ You can't give yourself money.", color=0xff0000)
        await interaction.response.send_message(embed=embed)
        return
    c.execute("SELECT balance FROM money WHERE user_id = ?", (interaction.user.id,))
    bal = c.fetchone()
    if not bal or bal[0] < amount:
        embed = discord.Embed(description="❌ Not enough money.", color=0xff0000)
        await interaction.response.send_message(embed=embed)
        return
    c.execute("INSERT OR IGNORE INTO money (user_id, balance) VALUES (?, 0)", (user.id,))
    c.execute("UPDATE money SET balance = balance - ? WHERE user_id = ?", (amount, interaction.user.id))
    c.execute("UPDATE money SET balance = balance + ? WHERE user_id = ?", (amount, user.id))
    conn.commit()
    embed = discord.Embed(description=f"✅ Gave `{amount}` Cafe ☕️Money to {user.mention}", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@tree.command(name="topmoney")
async def topmoney(interaction: discord.Interaction):
    c.execute("SELECT user_id, balance FROM money ORDER BY balance DESC LIMIT 10")
    rows = c.fetchall()
    embed = discord.Embed(title=" Top Cafe ☕️Money Users", color=0x00ffff)
    for i, (uid, bal) in enumerate(rows, 1):
        try:
            user = await bot.fetch_user(uid)
            embed.add_field(name=f"{i}. {user.name}", value=f"`{bal}` ", inline=False)
        except:
            continue
    await interaction.response.send_message(embed=embed)

@tree.command(name="clearmoney")
@app_commands.checks.has_permissions(administrator=True)
async def clearmoney(interaction: discord.Interaction):
    c.execute("DELETE FROM money")
    conn.commit()
    embed = discord.Embed(description="🧹 All money cleared.", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@tree.command(name="clearinvites")
@app_commands.checks.has_permissions(administrator=True)
async def clearinvites(interaction: discord.Interaction):
    c.execute("DELETE FROM invites")
    conn.commit()
    embed = discord.Embed(description="🧹 All invites cleared.", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@tree.command(name="invites")
async def invites(interaction: discord.Interaction, user: discord.User = None):
    user = user or interaction.user
    c.execute("SELECT COUNT(*) FROM invites WHERE inviter_id = ?", (user.id,))
    count = c.fetchone()[0]
    embed = discord.Embed(title=" Invite Log", description=f">> {user.mention} has `{count}` invites", color=0x00ffff)
    await interaction.response.send_message(embed=embed)

@tree.command(name="create")
@app_commands.checks.has_permissions(administrator=True)
async def create(interaction: discord.Interaction, prefix: str, cmd: str, msg: str, type: str):
    c.execute("INSERT INTO commands VALUES (?, ?, ?, ?)", (prefix, cmd, msg, type.lower()))
    conn.commit()
    embed = discord.Embed(description="✅ Custom command created.", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@tree.command(name="dm")
@app_commands.checks.has_permissions(administrator=True)
async def dm(interaction: discord.Interaction, user: discord.User, msg: str):
    try:
        await user.send(msg)
        embed = discord.Embed(description=f" Sent DM to {user.mention}", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except:
        embed = discord.Embed(description="❌ Couldn't DM user.", color=0xff0000)
        await interaction.response.send_message(embed=embed)

# Moderation commands
@tree.command(name="kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    embed = discord.Embed(description=f" {member.mention} kicked.", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@tree.command(name="ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)
    embed = discord.Embed(description=f"⛔ {member.mention} banned.", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@tree.command(name="timeout")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int):
    until = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(until)
    embed = discord.Embed(description=f"⏱️ {member.mention} timed out for `{minutes}` minutes.", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
