# bot.py
import asyncio
import datetime
import logging
import os
import random
import time

import requests
from discord import Embed, HTTPException, Intents, Client
from discord.ext import commands, tasks
from discord.utils import find
from dotenv import load_dotenv

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

time.sleep(15)
load_dotenv()
logger = logging.getLogger('discord')
logger.setLevel(os.getenv('LOGGING_LEVEL'))
handler = logging.FileHandler(filename='err.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

token = os.getenv('DISCORD_TOKEN')

command_list = ['help', 'add_phrase', 'remove_phrase', 'show_phrases', 'phrase_count', 'word_count', 'update_prefix', 'show_pfp', 'bot_name', 'bot_pfp',
                'message_count', 'love', 'add_love_phrase', 'remove_love_phrase', 'show_love_phrases', 'diary', 'dear_diary', 'show_diary']
prefixes = {}

if MongoClient is not None:
    client = MongoClient(os.getenv('MONGODB_URL'))
    db = client.mandybot
    prefixes = db.guildstats.find_one({'_name': '_mandybot_prefixes'}).get('_mandybot_prefixes')


def find_prefix(bot, message):
    if not prefixes:
        return '*'
    server_id = str(message.guild.id)
    return prefixes.get(server_id, '*')


class MandyBot(commands.Bot):
    async def setup_hook(self):
        scheduled_reminder_med_1.start()
        scheduled_reminder_med_2.start()


bot = MandyBot(command_prefix=find_prefix, intents=Intents().all())


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


@bot.event
async def on_guild_join(guild):
    general = find(lambda x: x.position == 0, guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        await general.send('MandyBot is a bot written for my girlfriend Mandy for valentines day 2020\n'
                           'This bot is for sending love to everyone and tracking user usage statistics such as the amount users have said a '
                           'phrase, and their word counts!\n'
                           'You can add and remove love phrases to the love pool, add and remove phrases to be tracked, see phrases being tracked and see '
                           'love phrases, as well as see users word counts and phrase counts.')


@bot.event
async def on_message(message):
    # Cant track if no mongodb connection
    if db is None:
        return

    # Dont track the bots messages or let the bot issue commands
    if message.author == bot.user:
        return

    # Dont track words/phrases used during a command
    for command in command_list:
        if message.content.startswith(find_prefix(None, message) + command):
            await bot.process_commands(message)
            return
    # Process messages if not a command or said by the bot
    user_stats = db.userstats.find_one({'_discord_user_id': message.author.id})
    if user_stats:
        process_message(user_stats, message)
    else:
        process_message({'_discord_user_id': message.author.id}, message, True)


@bot.command(name='add_phrase', help='Add a phrase to be tracked by the bot - Usage *add_phrase "add this whole thing"')
async def add_phrase(ctx, phrase_to_add):
    # Cant track if no mongodb connection
    if db is None:
        return

    phrase_to_add = phrase_to_add.lower()
    guild_phrases = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if guild_phrases:
        if guild_phrases.get(''):
            if phrase_to_add not in guild_phrases.get('_tracked_phrases'):
                db.guildstats.update_one({'_discord_guild_id': ctx.guild.id}, {'$push': {'_tracked_phrases': phrase_to_add}})
            else:
                await ctx.send("The phrase \"{}\" is already being tracked!".format(phrase_to_add))
                return
        else:
            db.guildstats.update_one({'_discord_guild_id': ctx.guild.id}, {'$push': {'_tracked_phrases': phrase_to_add}})
    else:
        db.guildstats.insert_one({'_discord_guild_id': ctx.guild.id, '_tracked_phrases': [phrase_to_add]})
    await ctx.send("Added: \"{}\" to the server's tracked phrases!".format(phrase_to_add))


@bot.command(name='remove_phrase', help='Remove a phrase tracked by the bot - Usage *remove_phrase "remove this whole thing"')
async def remove_phrase(ctx, phrase_to_remove):
    # Cant track if no mongodb connection
    if db is None:
        return
    phrase_to_remove = phrase_to_remove.lower()
    guild_phrases = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if guild_phrases and guild_phrases.get('_tracked_phrases') and phrase_to_remove not in guild_phrases.get('_tracked_phrases'):
        db.guildstats.update_one({'_discord_guild_id': ctx.guild.id}, {'$pull': {'_tracked_phrases': phrase_to_remove}})
        await ctx.send("Removed: \"{}\" from the server's tracked phrases!".format(phrase_to_remove))
    else:
        await ctx.send("This server has no phrase \"{}\" to remove!".format(phrase_to_remove))


@bot.command(name='show_phrases', help='Show this server\'s tracked phrases')
async def show_phrases(ctx):
    # Cant track if no mongodb connection
    if db is None:
        return
    guild_phrases = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if guild_phrases and guild_phrases.get('_tracked_phrases'):
        string_list = format_list_to_printable_lists(guild_phrases.get('_tracked_phrases'))
        for item in string_list:
            await ctx.send(item)
    else:
        await ctx.send("This server has no tracked phrases!")


@bot.command(name='phrase_count', help='Show users phrase usage, both arguments are optional - Usage *phrase_count @user "phrase to show"')
async def phrase_count(ctx, user_to_show=None, phrase_to_show=None):
    # Cant track if no mongodb connection
    if db is None:
        return
    guild_id = str(ctx.message.guild.id)
    if user_to_show:
        try:
            user_id = strip_user_id(user_to_show)
        except:
            await ctx.send("Please tag a proper person for the first argument to show their phrase count.")
            return
    else:
        user_id = ctx.message.author.id
    user_stats = db.userstats.find_one({'_discord_user_id': user_id})
    if user_stats and user_stats.get(guild_id):
        await ctx.send('{} has said:'.format(ctx.guild.get_member(user_id).name))
        phrases = user_stats.get(guild_id).get('_phrase_count')
        if phrase_to_show and phrases:
            await ctx.send(phrase_to_show + ': ' + str(phrases.get(phrase_to_show, 0)))
        else:
            for string_item in format_dict_to_string(phrases):
                await ctx.send(string_item)
    else:
        await ctx.send('This user has yet to say anything in this server')


@bot.command(name='word_count', help='Show users word usage, both arguments are optional - Usage *phrase_count @user "phrase to show"')
async def word_count(ctx, user_to_show=None, word_to_show=None):
    # Cant track if no mongodb connection
    if db is None:
        return
    guild_id = str(ctx.message.guild.id)
    if user_to_show:
        try:
            user_id = strip_user_id(user_to_show)
        except:
            await ctx.send("Please tag a proper person for the first argument to show their word count.")
            return
    else:
        user_id = ctx.message.author.id
    user_stats = db.userstats.find_one({'_discord_user_id': user_id})
    if user_stats and user_stats.get(guild_id):
        await ctx.send('{} has said:'.format(ctx.guild.get_member(user_id).name))
        words = user_stats.get(guild_id).get('_word_count')
        if not words:
            return
        if word_to_show:
            await ctx.send(word_to_show + ': ' + str(words.get(word_to_show, 0)))
        else:
            for string_item in format_dict_to_string(words):
                await ctx.send(string_item)
    else:
        await ctx.send('This user has yet to say anything in this server')


@bot.command(name='update_prefix', help='Change the prefix of the bot')
async def update_prefix(ctx, new_prefix):
    # Cant track if no mongodb connection
    if db is None:
        return
    db.guildstats.update_one({'_name': '_mandybot_prefixes'}, {'$set': {'_mandybot_prefixes.' + str(ctx.guild.id): new_prefix}})
    prefixes[str(ctx.guild.id)] = new_prefix
    await ctx.send("Prefix updated to {}".format(new_prefix))


@bot.command(name='show_pfp', help='Show the users pfp')
async def show_pfp(ctx, user_to_show=None):
    if user_to_show:
        try:
            user_id = strip_user_id(user_to_show)
        except:
            await ctx.send("Please tag a proper person to show their profile picture.")
            return
    else:
        user_id = ctx.message.author.id
    user = ctx.message.guild.get_member(user_id)
    if not user:
        return  # Can't find the user, then quit
    pfp = user.avatar_url
    embed = Embed(title="Profile Picture", description='{}\'s profile picture!'.format(user.mention), color=0xecce8b)
    embed.set_image(url=pfp)
    await ctx.send(embed=embed)


@bot.command(name='bot_name', help='Set the nickname of the bot')
async def bot_name(ctx, new_name):
    await ctx.message.guild.me.edit(nick=new_name)


@bot.command(name='bot_pfp', help='Set the avatar of the bot')
async def bot_pfp(ctx, image_url):
    response = requests.get(image_url)
    image_bytes = response.content
    await bot.user.edit(avatar=image_bytes)


@bot.command(name='message_count', help='Shows the total number of messages sent for a user')
async def message_count(ctx, user_to_show=None):
    # Cant track if no mongodb connection
    if db is None:
        return
    guild_id = str(ctx.message.guild.id)
    if user_to_show:
        try:
            user_id = strip_user_id(user_to_show)
        except:
            await ctx.send("Please tag a proper person for the first argument to show their word count.")
            return
    else:
        user_id = ctx.message.author.id
    user_stats = db.userstats.find_one({'_discord_user_id': user_id})
    if user_stats:
        messages = user_stats.get(guild_id).get('_message_count')
        await ctx.send('{} has sent {} messages in this server!'.format(ctx.guild.get_member(user_id).name, messages))
    else:
        await ctx.send('This user has sent 0 messages in this server')


@bot.command(name='love', help='Show a user some love')
async def love(ctx, user_to_show):
    # Cant track if no mongodb connection
    if db is None:
        return
    if user_to_show:
        try:
            user_id = strip_user_id(user_to_show)
        except:
            await ctx.send("You love yourself <3")
            return
    else:
        await ctx.send("You love yourself <3")
    guild_phrases = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if guild_phrases and guild_phrases.get('_love_phrases'):
        love_phrase = random.choice(guild_phrases.get('_love_phrases'))
        await ctx.send('<@!{}> loves <@!{}> {}'.format(ctx.message.author.id, user_id, love_phrase))
    else:
        await ctx.send('<@!{}> loves <@!{}> so fucking much! <3 <3'.format(ctx.message.author.id, user_id))


@bot.command(name='add_love_phrase', help='Add a phrase to the love pool - Usage *add_love_phrase "add this whole thing"')
async def add_love_phrase(ctx, phrase_to_add):
    # Cant track if no mongodb connection
    if db is None:
        return
    phrase_to_add = phrase_to_add.lower()
    guild_phrases = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if guild_phrases:
        if guild_phrases.get('_love_phrases'):
            if phrase_to_add not in guild_phrases.get('_love_phrases'):
                db.guildstats.update_one({'_discord_guild_id': ctx.guild.id}, {'$push': {'_love_phrases': phrase_to_add}})
            else:
                await ctx.send("The phrase \"{}\" is already in the love phrases!".format(phrase_to_add))
                return
        else:
            db.guildstats.update_one({'_discord_guild_id': ctx.guild.id}, {'$push': {'_love_phrases': phrase_to_add}})
    else:
        db.guildstats.insert_one({'_discord_guild_id': ctx.guild.id, '_love_phrases': [phrase_to_add]})
    await ctx.send("Added: \"{}\" to the server's love phrases!".format(phrase_to_add))


@bot.command(name='remove_love_phrase', help='Remove a phrase from the love pool - Usage *remove_love_phrase "remove this whole thing"')
async def remove_love_phrase(ctx, phrase_to_remove):
    # Cant track if no mongodb connection
    if db is None:
        return
    phrase_to_remove = phrase_to_remove.lower()
    guild_phrases = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if guild_phrases and guild_phrases.get('_love_phrases') and phrase_to_remove not in guild_phrases.get('_love_phrases'):
        db.guildstats.update_one({'_discord_guild_id': ctx.guild.id}, {'$pull': {'_love_phrases': phrase_to_remove}})
        await ctx.send("Removed: \"{}\" from the server's love phrases!".format(phrase_to_remove))
    else:
        await ctx.send("This server has no love phrase \"{}\" to remove!".format(phrase_to_remove))


@bot.command(name='show_love_phrases', help='Show this server\'s love phrases')
async def show_love_phrases(ctx):
    # Cant track if no mongodb connection
    if db is None:
        return
    guild_phrases = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if guild_phrases and guild_phrases.get('_love_phrases'):
        string_list = format_list_to_printable_lists(guild_phrases.get('_love_phrases'))
        for item in string_list:
            await ctx.send(item)
    else:
        await ctx.send("This server has no love phrases!")


@bot.command(name='diary', help='Shows a random diary entry')
async def diary(ctx):
    # Cant track if no mongodb connection
    if db is None:
        return
    diary_entries = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if diary_entries and diary_entries.get('_diary_entries'):
        diary_entry = random.choice(diary_entries.get('_diary_entries'))
        await ctx.send(diary_entry)
    else:
        await ctx.send('No diary entries!')


@bot.command(name='dear_diary', help='Add an entry to the diary')
async def dear_diary(ctx, entry_to_add):
    # Cant track if no mongodb connection
    if db is None:
        return
    diary_entries = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    diary_start = '\nEntry Number {}, \n{}\nDear Diary,\n{}'
    if diary_entries:
        diary_entry = diary_start.format(len(diary_entries.get('_diary_entries', [])) + 1, datetime.datetime.today().strftime('%m-%d-%Y'), entry_to_add)
        db.guildstats.update_one({'_discord_guild_id': diary_entries.get('_discord_guild_id')}, {'$push': {'_diary_entries': diary_entry}})
    else:
        diary_entry = diary_start.format(1, datetime.datetime.today().strftime('%m-%d-%Y'), entry_to_add)
        db.guildstats.insert_one({'_discord_guild_id': ctx.guild.id, '_diary_entries': [diary_entry]})
    await ctx.send('The following was added to the diary:{}'.format(diary_entry))


@bot.command(name='show_diary', help='Show all diary entries')
async def show_diary(ctx):
    # Cant track if no mongodb connection
    if db is None:
        return
    diary_entries = db.guildstats.find_one({'_discord_guild_id': ctx.guild.id})
    if diary_entries and diary_entries.get('_diary_entries'):
        string_list = format_list_to_printable_lists(diary_entries.get('_diary_entries'))
        for item in string_list:
            await ctx.send(item)
    else:
        await ctx.send('There are no diary entries yet!')


# Reminder message for medicine
@tasks.loop(seconds=10)
async def scheduled_reminder_med_1():
    message_channel = bot.get_channel(863916120855674921)
    await message_channel.send("<@991864524758061156> take your medicine princess!")


# @scheduled_reminder_med_1.before_loop
# async def before_scheduled_reminder_1():
#     for _ in range(60 * 24):  # loop the whole day
#         if datetime.datetime.now().hour == 9:  # 24 hour format
#             return
#         await asyncio.sleep(60)


# Reminder message for medicine
@tasks.loop(hours=168)
async def scheduled_reminder_med_2():
    message_channel = bot.get_channel(863916120855674921)
    await message_channel.send("<@991864524758061156> take your vitamin D medicine princess!")


@scheduled_reminder_med_2.before_loop
async def before_scheduled_reminder_2():
    for _ in range(60 * 24 * 7):  # loop the whole week waiting for sunday
        cur_date_time = datetime.datetime.now()
        if cur_date_time.hour == 9 and cur_date_time.weekday() == 6:  # 24 hour format
            return
        await asyncio.sleep(60)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    elif isinstance(error, HTTPException):
        ctx.send('You are changing the profile picture too quickly, please wait and try again!')
    else:
        await ctx.send('An error occurred! Please try again')
        print(error)
        logger.error('{}: MESSAGE: {}'.format(error, ctx.message.content))


def process_message(user_stats, message, insert=False):
    # Cant track if no mongodb connection
    if db is None:
        return
    if not message.content:
        return
    content = message.content.lower()
    message_items = content.split()
    guild_id = str(message.guild.id)
    count_dict = {guild_id + '._message_count': 1}
    for item in message_items:
        # Check for words that start with special mongodb characters and remove them
        item = strip_special_chars(item)
        if item:
            if count_dict.get(item):
                count_dict[guild_id + '._word_count.' + item] = int(count_dict.get(guild_id + '._word_count.' + item)) + 1
            else:
                count_dict[guild_id + '._word_count.' + item] = 1

    guild_phrases = db.guildstats.find_one({'_discord_guild_id': message.guild.id})
    if guild_phrases:
        phrases = guild_phrases.get('_tracked_phrases')
        if not phrases:
            phrases = []
    else:
        phrases = []

    for phrase in phrases:
        if phrase == '_discord_guild_id':
            continue
        phrases_count = content.count(phrase)
        count_dict[guild_id + '._phrase_count.' + phrase] = phrases_count

    if insert:
        db.userstats.insert_one({'_discord_user_id': user_stats.get('_discord_user_id')})
        return
    db.userstats.update_one({'_discord_user_id': user_stats.get('_discord_user_id')}, {'$inc': count_dict})


def strip_special_chars(str_item):
    return ''.join(e for e in str_item if e.isalnum())


def format_dict_to_string(dict_to_format):
    formatted_strings = []
    for key in dict_to_format.keys():
        formatted_strings.append(key + ': ' + str(dict_to_format.get(key)) + '\n')
    return format_list_to_printable_lists(formatted_strings, '', '')


def format_list_to_printable_lists(list_to_format, spacing=' ', separator=','):
    # Discord only allows messages to be 2000 chars or less, organize list of items into 2000 char or less chunks
    string_list = []
    current_string = ""
    for item in list_to_format:
        if len(current_string) == 0:
            current_string += item + separator
        elif len(spacing + item + separator) + len(current_string) <= 2000:
            current_string += spacing + item + separator
        else:
            string_list.append(current_string)
            current_string = item + separator
    # Strip the trailing separator
    if separator:
        current_string = current_string[:-1]
    string_list.append(current_string)
    return string_list


def strip_user_id(mention_string):
    return int(mention_string[3:-1])


bot.run(token)
