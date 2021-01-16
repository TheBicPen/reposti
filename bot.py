import discord
import imagehash
import requests
import json
# from textdistance import hamming
from PIL import Image, UnidentifiedImageError
from os import environ, path
from io import BytesIO

SAME_DIFF=20
HASH_SIZE=16

default_strings = {
    "scan": "reposti !scan",
    # "scan_all": "reposti !scanall",
    "disable": "reposti !disable",
    "enable": "reposti !enable",
    "hello": "hi reposti",
    "hash": "reposti !hash",
    "hashdiff": "hashdiff",
    "repost_found": "General reposti"
}
command_strings = default_strings.copy()

data={}

def hash_diff(h1, h2):
    """
    ImageHash difference is computed by finding the Hamming distance between the binary arrays.
    We only store the hash.
    """
    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)


def image_hash_from_message(message):
    """
    Returns list of hashes(str) of images in message. Embeds with no images are None, embeds with errors are 0.
    """
    # if len(message.embeds) == 0:
    #     return False
    # print("Has embed:", m.jump_url)
    out={"hashes": [], "errors": 0, "unhashables": 0}
    urls=[]
    for embed in message.embeds:
        if embed.thumbnail.url is not discord.Embed.Empty:
            urls.append(embed.thumbnail.url)
        elif embed.image.url is not discord.Embed.Empty:
            urls.append(embed.image.url)
        elif embed.url is not discord.Embed.Empty and embed.type == 'image':
            urls.append(embed.url)
        else:
            out["unhashables"] += 1
    for attachment in message.attachments:
        urls.append(attachment.url)
    for url in urls:
        # print(url)
        try:
            img_data = requests.get(url).content
            img = Image.open(BytesIO(img_data))
            out["hashes"].append(str(imagehash.whash(img, hash_size=HASH_SIZE)))
        except UnidentifiedImageError as e:
            out["errors"] += 1
            print(e, url)
    return out

async def scan_channel(channel, history_args):
    print(f"Scanning '#{channel.name}', {'all' if history_args.get('limit') is None else history_args['limit']} posts")
    await channel.send("Scanning posts...")
    scanned_posts = 0
    images_found = 0
    image_errors = 0
    hashes=[]
    async with channel.typing():
        async for m in channel.history(**history_args):
            if scanned_posts % 100 == 0:
                print(f"Scanned {scanned_posts} posts in '#{channel.name}'") #, m.jump_url)
            embeds = image_hash_from_message(m)
            hashes.extend(embeds["hashes"])
            images_found += len(embeds["hashes"]) + embeds["errors"]
            image_errors += embeds["errors"]
            scanned_posts += 1
    hashes=list(set(hashes)) # switch to using sets and implement a JSON codec
    guild_name, server_file = unique_guild_data(channel.guild)
    if not data[guild_name].get("hashes"):
        data[guild_name]["hashes"] = []
    data[guild_name]["hashes"].extend(hashes)
    data[guild_name]["hashes"] = list(set(data[guild_name]["hashes"]))
    with open(server_file, "w") as f:
        json.dump(data[guild_name], f)
    print(f"Done. Scanned {scanned_posts} posts, found {images_found} images, {len(hashes)} unique images, {image_errors} errors.")
    await channel.send(f"Done. Scanned {scanned_posts} posts, found {images_found} images, {len(hashes)} unique images, {image_errors} errors.")

client = discord.Client()

def unique_guild_data(guild):
    unique_name = "".join([x for x in guild.name if x.isalnum()]) + "_" + str(guild.id)
    file_name = path.join("data", unique_name + ".json")
    return (unique_name, file_name)

def check_message(message, max_diff=0):
    embeds = image_hash_from_message(message)
    guild_name, _ = unique_guild_data(message.guild)
    for h in embeds["hashes"]:
        if max_diff == 0:
            if h in data[guild_name]["hashes"]:
                print("Found matching hash", h)
                return True
        else:
            for hash2 in data[guild_name]["hashes"]:
                diff = hash_diff(h, hash2)
                if diff < max_diff:
                    print("Found matching hash", h, hash2, diff)
                    return True
    return False


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    async for guild in client.fetch_guilds():
        unique_guild, server_file = unique_guild_data(guild)
        if not data.get(unique_guild):
            data[unique_guild] = {}
        with open(server_file, "a+") as f:
            f.seek(0)
            try:
                data[unique_guild] = json.load(f)
            except json.JSONDecodeError as e:
                print(e, server_file, "contents:")
                f.seek(0)
                print(f.read())
                data[unique_guild] = {}
            

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(command_strings["hello"]):
        print("Hello there")
        await message.channel.send('Hello!')
    elif message.content.startswith(command_strings["scan"]):
        history_args = {
            "limit": None
        }
        channels = [message.channel]
        for w in message.content[len(command_strings["scan"]):].split():
            if w.isdecimal():
                history_args["limit"] = int(w)
            elif w == "here":
                history_args["before"] = message
            elif w == "all":
                channels = message.guild.channels
        for channel in channels:
            await scan_channel(channel, history_args)

    elif message.content.startswith(command_strings["hash"]):
        if message.reference:
            m = message.reference.resolved
            if isinstance(m, discord.DeletedReferencedMessage):
                await message.channel.send("The message was deleted.")
                print("The message was deleted.")
            if m is None:
                await message.channel.send("Discord refused to find the message this one references.")
                print("Discord refused to find the message this one references.")
            elif isinstance(m, discord.Message):
                await message.channel.send(str(image_hash_from_message(m)))
        else:
            await message.channel.send("Reply to a message to trigger this command.")

    elif message.content.startswith(command_strings["hashdiff"]):
        words = message.content[len(command_strings["hashdiff"]):].split()
        if len(words) != 2:
            await message.channel.send("This command needs 2 hashes.")
        else:
            await message.channel.send(str(hash_diff(*words)))

        
    if check_message(message, SAME_DIFF):
        await message.reply(command_strings["repost_found"])
    

token = environ.get("REPOSTI_DISCORD_TOKEN")
if token:
    client.run(token)
else:
    print("No Discord token found. Run the image with the correct environment variable set.")
    exit("")



