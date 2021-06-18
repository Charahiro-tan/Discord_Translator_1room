import asyncio
import re
import os

from async_google_trans_new import AsyncTranslator, constant
import aiohttp
import discord
import ujson

client = discord.Client()
g = AsyncTranslator(url_suffix='co.jp')

DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
CHANNEL_ID    = int(os.environ['CHANNEL_ID'])
CHANNEL_URL   = os.environ['CHANNEL_URL']

HOME_LANG     = os.environ['HOME_LANG']
HOME_TO_LANG  = os.environ['HOME_TO_LANG']

try:
    GAS_URL = os.environ['GAS_URL']
except:
    GAS_URL = ''

try:
    IGNORE_ID = os.environ['IGNORE_ID']
    l = IGNORE_ID.split(':')
    if len(l) >= 1:
        ignore_ids = [int(id) for id in l]
    else:
        ignore_ids = []
except:
    ignore_ids = []


del_word = [r"<a?:\w+?:\d+?>",r"<@! \d+>",r"^(.)\1+$",r"https?://[\w!\?/\+\-_~=;\.,\*&@#\$%\(\)'\[\]]+",
    r"^草$",r"^!.*",r"^w$",r"^ｗ$",r"ww+",r"ｗｗ+",r"^\s+"]

langlist = list(constant.LANGUAGES.keys())
del_word_compiled = [re.compile(w) for w in del_word]

async def gas_translate(msg, lang_tgt, lang_src):
    gas_use = False
    params = {
        'text' : msg,
        'target' : lang_tgt,
        'source' : lang_src
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(GAS_URL, params=params) as r:
            if r.status == 200:
                js = await r.json()
                if js['code'] == 200:
                    translated_text = js.get('text')
                    gas_use = True
            return translated_text, gas_use


async def web_hook(message, msg, author, thumbnail):
    headers = {'Content-Type': 'application/json'}
    data = {
        "username"   : author,
        "content"    : msg,
        "avatar_url" : thumbnail
    }
    async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
        async with session.post(CHANNEL_URL, headers=headers, json=data) as res:
            if res.status != 204:
                await message.channel.send('Webhookの送信に失敗しました')

@client.event
async def on_message(message):
    if message.author.bot:
        return
    
    if message.channel.id != CHANNEL_ID:
        return
    
    if message.author.id in ignore_ids:
        print('無視ユーザーです')
        return
    
    msg = message.content
    display_name = message.author.display_name
    author_thumbnail = message.author.avatar_url.BASE + message.author.avatar_url._url

    for r in del_word_compiled:
        msg = r.sub('', msg)
    
    if len(msg) <= 1:
        return
    
    #################################
    
    lang_src = None
    lang_tgt = None
    
    split_msg = msg.split(':')
    if len(split_msg) >= 2:
        if split_msg[0].lower() in langlist:
            lang_tgt = split_msg[0]
            msg = ':'.join(split_msg[1:])
            detect_task = asyncio.create_task(g.detect(msg))
            lang_src = await detect_task
            lang_src = lang_src[0]
        else:
            msg = ':'.join(split_msg[0:])
    else:
        msg = ':'.join(split_msg[0:])
    
    if lang_tgt is None:
        detect_task = asyncio.create_task(g.detect(msg))
        lang_src = await detect_task
        lang_src = lang_src[0]
        
        if lang_src == HOME_LANG:
            lang_tgt = HOME_TO_LANG
        else:
            lang_tgt = HOME_LANG
    
    ############################################
    
    translated = ''
    gas_use = False
    
    if GAS_URL:
        translated, gas_use = await gas_translate(msg, lang_tgt, lang_src)
    if not translated:
        trans_task = asyncio.create_task(g.translate(msg, lang_tgt,lang_src))
        translated = await trans_task
    
    if not translated:
        return
    
    p = f'({display_name}){message.content}({lang_src}):{translated}({lang_tgt})'
    if gas_use:
        p = p + '(GAS)'
    else:
        p = p + '(No GAS)'
    print(p)
    
    display_name = display_name + f'({lang_src} > {lang_tgt})'
    await web_hook(message, translated, display_name, author_thumbnail)

client.run(DISCORD_TOKEN)