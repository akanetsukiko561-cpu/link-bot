import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import difflib

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log',encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

main_server_ID = 1437940275803590731
forum_channel_ID = 1439508350277517364

@bot.event
async def on_ready():
    print("We are ready to go in, {bot.user.name}")

# Wait for a reply from the user
async def ask(ctx, question):
    await ctx.send(question)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    msg = await bot.wait_for("message", check=check)
    return msg.content

def fuzzy_match(user_ops, thread_title):
    thread_title_lower = thread_title.lower()
    for op in user_ops:
        matches = difflib.get_close_matches(op, thread_title_lower.split(), n=1, cutoff=0.6)
        if matches:
            return True
    return False

@bot.command()
async def strats(ctx):
    guild = bot.get_guild(MAIN_SERVER_ID)
    forum = guild.get_channel(FORUM_CHANNEL_ID)

    if not isinstance(forum, discord.ForumChannel):
        return await ctx.send("Forum channel not found!")

    # Step 1 — ask for map
    map_name = await ask(ctx, "🗺️ What **map** are you looking for strats on?")

    # Step 2 — ask for site
    site_name = await ask(ctx, "📍 What **site**?")

    # Step 3 — ask for preferred operators
    preferred_operators = await ask(ctx, "👥 Which **preferred operators**? (comma-separated)")
    preferred_ops = [op.strip().lower() for op in preferred_operators.split(",")]

    # Step 4 — ask for operators they want to counter
    counter_operators = await ask(ctx, "⚔️ Which **operators do you want to counter**? (comma-separated)")
    counter_ops = [op.strip().lower() for op in counter_operators.split(",")]

    # Step 5 — collect matching threads
    matching_threads = []

    for thread in forum.threads:
        title = thread.name.lower()
        if map_name.lower() in title and site_name.lower() in title:
            matching_threads.append(thread)

    if not matching_threads:
        return await ctx.send("No matching strats found in the forum.")

    # Step 6 — prioritize threads
    def strat_priority(thread):
        title = thread.name.lower()
        score = 0
        # Counter operators get highest weight
        for op in counter_ops:
            if difflib.get_close_matches(op, title.split(), n=1, cutoff=0.6):
                score += 10
        # Preferred operators get medium weight
        for op in preferred_ops:
            if difflib.get_close_matches(op, title.split(), n=1, cutoff=0.6):
                score += 5
        return -score  # higher score = first

    matching_threads.sort(key=strat_priority)

    # Step 7 — separate threads into preferred & others for display
    preferred_threads = []
    nonpreferred_threads = []
    for thread in matching_threads:
        if fuzzy_match(preferred_ops, thread.name):
            preferred_threads.append(thread)
        else:
            nonpreferred_threads.append(thread)

    # Step 8 — display threads
    response = "**Strats with your preferred operators:**\n"
    if preferred_threads:
        for i, thread in enumerate(preferred_threads, start=1):
            response += f"{i}. {thread.name}\n"
    else:
        response += "_None match your preferred operators._\n"

    response += "\n**Other strats for this map/site (no preferred operators):**\n"
    if nonpreferred_threads:
        for i, thread in enumerate(nonpreferred_threads, start=1):
            index = len(preferred_threads) + i
            response += f"{index}. {thread.name}\n"
    else:
        response += "_None._"

    await ctx.send(response)

    # Step 9 — user selects a strat
    choice = await ask(ctx, "Which strat number would you like?")
    try:
        choice_index = int(choice) - 1
    except ValueError:
        return await ctx.send("Invalid choice.")

    final_list = preferred_threads + nonpreferred_threads
    try:
        thread = final_list[choice_index]
    except IndexError:
        return await ctx.send("Choice out of range.")

    # Step 10 — read first message for Google Slides and counter info
    messages = [m async for m in thread.history(limit=1)]
    if not messages:
        return await ctx.send("This strat has no content.")

    first_message = messages[0].content
    slides_link = None
    counter_info = None

    for word in first_message.split():
        if "docs.google.com/presentation" in word:
            slides_link = word
            break

    # Check for "best used to counter" if thread is not default
    if "default" not in thread.name.lower():
        lines = first_message.splitlines()
        for line in lines:
            if "best used to counter" in line.lower():
                counter_info = line.strip()
                break

    if not slides_link:
        return await ctx.send("No Google Slides link found in that strat.")

    response_msg = f"📊 **Here is your strat:**\n{slides_link}"
    if counter_info:
        response_msg += f"\n⚔️ {counter_info}"

    await ctx.send(response_msg)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)