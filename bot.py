import os
import json
import threading
import discord
from discord import app_commands
from discord.ext import commands
import requests
from flask import Flask
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()

# --- سيرفر ويب خفيف للحفاظ على البوت 24/7 ---
web_app = Flask('')

@web_app.route('/')
def home():
    return "Valorant Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- إعدادات البوت وملف التخزين ---
DATA_FILE = "users.json"

def load_links():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_link(user_id: str, name: str, tag: str):
    data = load_links()
    data[str(user_id)] = {"name": name, "tag": tag}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# المفاتيح الخاصة بك
DISCORD_TOKEN = "MTU1NDUyODczMzA2MTMyNDgwMA.GqX5j4.1UY_krHVwpSW16d3oSjD4yqqgQRySoejXXkd1Y"
HENRIK_API_KEY = "HDEV-24e91560-b1ec-4735-85ea-1e790bda8f75"

def make_progress_bar(val: int, max_val: int = 100) -> str:
    total_blocks = 10
    filled = min(max(round((val / max_val) * total_blocks), 0), total_blocks)
    empty = total_blocks - filled
    return f"{'🟩' * filled}{'⬛' * empty} **{val}%**"

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"تمت مزامنة {len(synced)} أمر سلاش بنجاح!")
    except Exception as e:
        print(f"فشل مزامنة الأوامر: {e}")
    print(f"Logged in as {bot.user.name}")

# --- 1. أمر الربط: /link ---
@bot.tree.command(name="link", description="اربط حساب فالورانت بحساب الديسكورد بتاعك")
@app_commands.describe(player_id="اكتب اسمك والتاج مع بعض (مثال: Player#EU1)")
async def link_account(interaction: discord.Interaction, player_id: str):
    if "#" in player_id:
        parts = player_id.split("#")
        name = parts[0].strip()
        tag = parts[1].strip()
    elif " " in player_id:
        parts = player_id.split()
        name = parts[0].strip()
        tag = parts[1].strip()
    else:
        await interaction.response.send_message(
            "❌ لازم تكتب الاسم والتاج مع بعض مفصولين بـ `#`، مثال: `Player#EU1`", 
            ephemeral=True
        )
        return

    save_link(str(interaction.user.id), name, tag)
    await interaction.response.send_message(
        f"✅ تم ربط حسابك بنجاح بـ: **{name}#{tag}**!\nدلوقتي تقدر تكتب `/val` مباشرة أو حد يمنشنك وهيجيب إحصائياتك.", 
        ephemeral=True
    )

# --- 2. أمر الإحصائيات: /val ---
@bot.tree.command(name="val", description="عرض إحصائيات فالورانت (لحسابك، أو لشخص تمنشنه، أو للاعب تبحث عنه)")
@app_commands.describe(
    user="منشن شخص رابط حسابه عشان تشوف إحصائياته (اختياري)",
    name="اسم اللاعب في اللعبة (اختياري)", 
    tag="تاج اللاعب (اختياري)"
)
async def val_stats(
    interaction: discord.Interaction, 
    user: discord.User = None, 
    name: str = None, 
    tag: str = None
):
    await interaction.response.defer()

    if name and tag:
        target_name = name
        target_tag = tag
    else:
        links = load_links()
        target_user = user if user else interaction.user
        user_info = links.get(str(target_user.id))

        if not user_info:
            if user:
                await interaction.followup.send(f"⚠️ المستخدم {user.mention} مش رابط حسابه بفالورانت لسه!")
            else:
                await interaction.followup.send(
                    "⚠️ أنت مش رابط حسابك لسه!\nاستخدم أمر `/link` أولاً، أو اكتب: `/val name:اسم tag:تاج`"
                )
            return

        target_name = user_info["name"]
        target_tag = user_info["tag"]

    headers = {"Authorization": HENRIK_API_KEY}
    account_url = f"https://api.henrikdev.xyz/valorant/v1/account/{target_name}/{target_tag}"

    try:
        acc_res = requests.get(account_url, headers=headers).json()

        if acc_res.get("status") != 200 or "data" not in acc_res:
            await interaction.followup.send(f"❌ تعذر العثور على اللاعب: `{target_name}#{target_tag}`، تأكد من صحة الاسم والتاج.")
            return

        acc_data = acc_res["data"]
        region = acc_data.get("region", "eu")
        account_level = acc_data.get("account_level", "N/A")
        card_image = acc_data.get("card", {}).get("small")
        banner_image = acc_data.get("card", {}).get("wide")

        # بيانات الرانك
        mmr_url = f"https://api.henrikdev.xyz/valorant/v2/mmr/{region}/{target_name}/{target_tag}"
        mmr_res = requests.get(mmr_url, headers=headers).json()

        current_data = mmr_res.get("data", {}).get("current_data", {})
        current_tier = current_data.get("currenttierpatched", "Unrated")
        ranking_in_tier = current_data.get("ranking_in_tier", 0)
        rank_image = current_data.get("images", {}).get("small")
        elo = current_data.get("elo", "N/A")

        # جلب تاريخ الماتشات المخزنة بالكامل لحساب التوتل الإجمالي
        stored_url = f"https://api.henrikdev.xyz/valorant/v1/stored-matches/{region}/{target_name}/{target_tag}"
        stored_res = requests.get(stored_url, headers=headers).json()

        # جلب آخر 5 ماتشات تفصيلية للعرض
        matches_url = f"https://api.henrikdev.xyz/valorant/v3/matches/{region}/{target_name}/{target_tag}?size=5"
        match_res = requests.get(matches_url, headers=headers).json()

        # إحصائيات التوتل (Lifetime / Stored)
        total_kills = 0
        total_deaths = 0
        total_assists = 0
        total_hs = 0
        total_shots = 0
        total_wins = 0
        total_matches_counted = 0
        agent_counts = {}
        top_agent_icon = None

        stored_data = stored_res.get("data", [])
        if stored_res.get("status") == 200 and stored_data:
            for item in stored_data:
                stats = item.get("stats", {})
                k = stats.get("kills", 0)
                d = stats.get("deaths", 0)
                a = stats.get("assists", 0)
                total_kills += k
                total_deaths += d
                total_assists += a

                hs = stats.get("headshots", 0)
                bs = stats.get("bodyshots", 0)
                ls = stats.get("legshots", 0)
                total_hs += hs
                total_shots += (hs + bs + ls)

                character = stats.get("character", {}).get("name", "Agent")
                agent_counts[character] = agent_counts.get(character, 0) + 1

                teams = item.get("teams", {})
                my_team = stats.get("team", "").lower()
                if teams.get(my_team) is True or item.get("results", {}).get("won") is True:
                    total_wins += 1

                total_matches_counted += 1

        # سجل آخر 5 ماتشات للعرض
        match_history_lines = []
        if match_res.get("status") == 200 and match_res.get("data"):
            matches = match_res["data"]
            for m in matches:
                metadata = m.get("metadata", {})
                map_name = metadata.get("map", "Map")
                p_team = None
                p_stats = None

                for p in m.get("players", {}).get("all_players", []):
                    if p.get("name", "").lower() == target_name.lower() and p.get("tag", "").lower() == target_tag.lower():
                        p_team = p.get("team", "").lower()
                        p_stats = p.get("stats", {})
                        p_agent = p.get("character", "Agent")
                        if not top_agent_icon:
                            top_agent_icon = p.get("assets", {}).get("agent", {}).get("small")
                        break

                if p_stats:
                    k = p_stats.get("kills", 0)
                    d = p_stats.get("deaths", 0)
                    a = p_stats.get("assists", 0)

                    if total_matches_counted == 0:
                        total_kills += k
                        total_deaths += d
                        total_assists += a
                        hs = p_stats.get("headshots", 0)
                        bs = p_stats.get("bodyshots", 0)
                        ls = p_stats.get("legshots", 0)
                        total_hs += hs
                        total_shots += (hs + bs + ls)

                    teams = m.get("teams", {})
                    my_score = 0
                    enemy_score = 0
                    won = False

                    if p_team in ["blue", "red"]:
                        enemy_team = "red" if p_team == "blue" else "blue"
                        my_score = teams.get(p_team, {}).get("rounds_won", 0)
                        enemy_score = teams.get(enemy_team, {}).get("rounds_won", 0)
                        won = teams.get(p_team, {}).get("has_won", False)

                    if won:
                        if total_matches_counted == 0: total_wins += 1
                        result_emoji = "🟢 **فوز **"
                    elif my_score == enemy_score and my_score > 0:
                        result_emoji = "🟡 **تعادل **"
                    else:
                        result_emoji = "🔴 **خسارة **"

                    match_history_lines.append(
                        f"{result_emoji} `[{my_score}-{enemy_score}]` ╎ 🗺️ **{map_name}** ╎ ⚔ `{k}/{d}/{a}` ╎ 🎭 `{p_agent}`"
                    )

            if total_matches_counted == 0:
                total_matches_counted = len(match_history_lines)

        safe_matches = max(total_matches_counted, 1)
        lifetime_kd = round(total_kills / total_deaths, 2) if total_deaths > 0 else total_kills
        lifetime_hs = round((total_hs / total_shots) * 100) if total_shots > 0 else 0
        lifetime_wr = round((total_wins / safe_matches) * 100) if total_matches_counted > 0 else 0
        most_played = max(agent_counts, key=agent_counts.get) if agent_counts else "N/A"

        embed = discord.Embed(
            title=f"📊 إحصائيات الحساب الشاملة | {target_name}#{target_tag}",
            description=f"🌐 **السيرفر:** `{region.upper()}` ╎ 🎖 **المستوى:** `LVL {account_level}` ╎ 🔢 **الـ ELO:** `{elo}`",
            color=0xFD4556
        )

        if rank_image:
            embed.set_thumbnail(url=rank_image)
        elif card_image:
            embed.set_thumbnail(url=card_image)

        if top_agent_icon:
            embed.set_author(name="Valorant Lifetime Tracker", icon_url=top_agent_icon)
        else:
            embed.set_author(name="Valorant Lifetime Tracker")

        rr_bar = make_progress_bar(ranking_in_tier)
        rank_desc = (
            f"**الرانك الحالي:** `{current_tier}`\n"
            f"**النقاط الحالية:** `{ranking_in_tier} / 100 RR`\n"
            f"**التقدم للرانك القادم:** {rr_bar}"
        )
        embed.add_field(name="🏆 تصنيف الرانك الحالي", value=rank_desc, inline=False)

        wr_bar = make_progress_bar(lifetime_wr)
        lifetime_summary = (
            f"🎯 **معدل الفوز الإجمالي (Win Rate):** {wr_bar} ({total_wins} فوز من {total_matches_counted} مباراة)\n"
            f"⚔️ **إجمالي الـ KD العام:** `{lifetime_kd}` ({total_kills} Kills / {total_deaths} Deaths)\n"
            f"🎯 **دقة الهيد شوت الكلية (HS%):** `{lifetime_hs}%`\n"
            f"🎭 **العميل الأكثر لعباً:** `{most_played}`"
        )
        embed.add_field(name="📈 إحصائيات الحساب الكلية (Career Stats)", value=lifetime_summary, inline=False)

        history_text = "\n".join(match_history_lines) if match_history_lines else "لا توجد مباريات مسجلة حديثاً."
        embed.add_field(name="📜 سجل آخر 5 مباريات (Match History)", value=history_text, inline=False)

        if banner_image:
            embed.set_image(url=banner_image)

        embed.set_footer(text="HenrikDev Valorant API • Lifetime Analytics")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send("⚠️ حدث خطأ أثناء جلب البيانات، تأكد من صحة الحساب وأن الملف الشخصي عام.")
        print(f"Error: {e}")

if not DISCORD_TOKEN:
    print("❌ خطأ: التوكن مش موجود في ملف .env!")
else:
    bot.run(DISCORD_TOKEN)