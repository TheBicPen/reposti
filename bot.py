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
    "scan": "reposti scan",
    # "scan_all": "reposti !scanall",
    "disable": "reposti disable",
    "enable": "reposti enable",
    "exclude": "reposti exclude",
    "include": "reposti include",
    "hello": "hi reposti",
    "hash": "reposti hash",
    "hashdiff": "reposti diff",
    "diff": "reposti diff",
    "repost_found": "General reposti"

}



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

async def scan_channel(channel, data, history_args):
    print(f"Scanning '#{channel.name}', {'all' if history_args.get('limit') is None else history_args['limit']} posts")
    await channel.send("Scanning posts...")
    scanned_posts = 0
    images_found = 0
    image_errors = 0
    hashes={}
    async with channel.typing():
        async for m in channel.history(**history_args):
            if scanned_posts % 100 == 0:
                print(f"Scanned {scanned_posts} posts in '#{channel.name}'") #, m.jump_url)
            embeds = image_hash_from_message(m)
            for h in embeds["hashes"]:
                if h in hashes:
                    hashes[h].append((channel.id, m.id))
                else:
                    hashes[h] = [(channel.id, m.id)]
            
            images_found += len(embeds["hashes"]) + embeds["errors"]
            image_errors += embeds["errors"]
            scanned_posts += 1
    add_hash_data(data, channel.guild, hashes)
    print(f"Done. Scanned {scanned_posts} posts, found {len(hashes)} unique images, {image_errors} errors.")
    await channel.send(f"Done. Scanned {scanned_posts} posts, found {len(hashes)} unique images, {image_errors} errors.")

def save_guild_data(data, guild):
    guild_name, server_file = unique_guild_data(guild)
    with open(server_file, "w") as f:
        json.dump(data[guild_name], f)

def get_guild_data(data, guild, k, default=None):
    guild_name, _ = unique_guild_data(guild)
    return data[guild_name].get(k, default)

def set_guild_data(data, guild, k, v):
    guild_name, _ = unique_guild_data(guild)
    data[guild_name][k] = v
    save_guild_data(data, guild)

def add_hash_data(data, guild, hashes: dict):
    """
    Adds hashes to data.
    hashes should be a dict that maps the hash strings to a list (typically of tuples containing channel and message IDs).
    Only unique list elements are added.
    """
    guild_name, _ = unique_guild_data(guild)
    if not get_guild_data(data, guild, "hashes"):
        set_guild_data(data, guild, "hashes", {})
    for h,posts in hashes.items():
        if h in get_guild_data(data, guild, "hashes", []):
            for p in posts:
                matching_posts = get_guild_data(data, guild, "hashes")[h]
                if p in matching_posts:
                    matching_posts.append(p)
        else:
            get_guild_data(data, guild, "hashes", [])[h] = posts
    save_guild_data(data, guild)

    

async def load_data(client) -> dict:
    data={}
    async for guild in client.fetch_guilds():
        unique_guild, server_file = unique_guild_data(guild)
        if not data.get(unique_guild):
            data[unique_guild] = {}
        with open(server_file, "a+") as f:
            f.seek(0)
            try:
                if path.getsize(server_file) == 0:
                    print("Created new file for", unique_guild)
                    json.dump({}, f)
                    data[unique_guild] = {}
                else:
                    data[unique_guild] = json.load(f)
            except json.JSONDecodeError as e:
                f.seek(0)
                contents = f.read()
                print(e, server_file, "contents:", contents)
                data[unique_guild] = {}
                with open(server_file + ".bak", "w") as backup:
                    backup.write(contents)
                f.seek(0)
                json.dump({}, f)
    return data



def unique_guild_data(guild):
    unique_name = "".join([x for x in guild.name if x.isalnum()]) + "_" + str(guild.id)
    file_name = path.join("data", unique_name + ".json")
    return (unique_name, file_name)

def check_message(data, message, max_diff=0):
    embeds = image_hash_from_message(message)
    guild_name, _ = unique_guild_data(message.guild)
    for h in embeds["hashes"]:
        if max_diff == 0:
            if h in get_guild_data(data, message.guild, "hashes", default=[]):
                print("Found matching hash", h)
                return get_guild_data(data, message.guild, "hashes")[h]
        else:
            for hash2 in get_guild_data(data, message.guild, "hashes", default=[]):
                diff = hash_diff(h, hash2)
                if diff < max_diff:
                    print("Found matching hash", h, hash2, diff)
                    return get_guild_data(data, message.guild, "hashes")[h]
    return None

class Client(discord.Client):

    def check_command(self, message, command):
        return message.content.startswith(self.command_strings[command])
            
    def get_args(self, message, command):
        return message.content[len(self.command_strings[command]):].split()

    async def on_ready(self):
        print('We have logged in as {0.user}'.format(client))
        self.command_strings = default_strings.copy()
        self.data = await load_data(client)
                

    async def on_message(self, message):
        if message.author == client.user:
            return

        # if message.author == message.guild.owner: #intents or some other junk broke this
        if message.author.id == message.guild.owner_id:
            if self.check_command(message, "hello"):
                print("Hello there")
                await message.reply('Hello there')
            elif self.check_command(message, "scan"):
                history_args = {
                    "limit": None
                }
                channels = [message.channel]
                for w in self.get_args(message, "scan"):
                    if w.isdecimal():
                        history_args["limit"] = int(w)
                    elif w == "here":
                        history_args["before"] = message
                    elif w == "all":
                        channels = message.guild.channels
                for channel in channels:
                    await scan_channel(channel, self.data, history_args)

            elif self.check_command(message, "hash"):
                if message.reference:
                    m = message.reference.resolved
                    if isinstance(m, discord.DeletedReferencedMessage):
                        await message.reply("The message was deleted.")
                        print("The message was deleted.")
                    if m is None:
                        await message.reply("Discord refused to find the message this one references.")
                        print("Discord refused to find the message this one references.")
                    elif isinstance(m, discord.Message):
                        await message.reply(str(image_hash_from_message(m)))
                else:
                    await message.reply("Reply to a message to trigger this command.")

            elif self.check_command(message, "hashdiff"):
                words = get_args(message, "hashdiff")
                if len(words) != 2:
                    await message.reply("This command needs 2 hashes.")
                else:
                    await message.reply(str(hash_diff(*words)))

            elif self.check_command(message, "diff"):
                words = get_args(message, "diff")
                if len(words) != 2:
                    await message.reply("This command needs 2 message IDs.")
                else:
                    try:
                        m1 = await message.channel.fetch_message(words[0])
                        m2 = await message.channel.fetch_message(words[1])
                        h1 = image_hash_from_message(m1)
                        h2 = image_hash_from_message(m2)
                        if not h1["hashes"]:
                            await message.reply("1st message had no hashable images.")
                        elif not h2["hashes"]:
                            await message.reply("2nd message had no hashable images.")
                        else:
                            await message.reply(str(hash_diff(h1["hashes"][0], h2["hashes"][0])))

                    except:
                        await message.reply("An error occurred. Are the message IDs valid?")
            elif self.check_command(message, "enable"):
                set_guild_data(self.data, message.guild, "enabled", True)
                await message.reply(f"Enabled repost checking on this server. Note that some channels may still be excluded. Run `{self.command_strings['include']} all` to include all channels.")
            elif self.check_command(message, "disable"):
                set_guild_data(self.data, message.guild, "enabled", False)
                await message.reply("Disabled repost checking on this server.")

            elif self.check_command(message, "include"):
                args = self.get_args(message, "include")
                channels = get_guild_data(self.data, message.guild, "included_channels")
                if args and args[0] == "all":
                    channels = [c.id for c in message.guild.channels]
                elif args and args[0] == "none":
                    channels = []
                else:
                    channels.append([c.id for c in message.channel_mentions])
                set_guild_data(self.data, message.guild, "included_channels", channels)
                await message.reply("Checking the following channels for reposts:" + ", ".join([str(message.guild.get_channel(c)) for c in channels]))
                
            elif self.check_command(message, "exclude"):
                args = self.get_args(message, "exclude")
                channels = get_guild_data(self.data, message.guild, "included_channels")
                if args and args[0] == "all":
                    channels = []
                elif args and args[0] == "none":
                    channels = [c.id for c in message.guild.channels]
                else:
                    try:
                        channels.remove([c.id for c in message.channel_mentions])
                    except ValueError:
                        await message.reply("A mentioned channel was not in the list. List not updated.")

                set_guild_data(self.data, message.guild, "included_channels", channels)
                await message.reply("Checking the following channels for reposts:" + ", ".join([str(message.guild.get_channel(c)) for c in channels]))

            
        if message.channel.id in get_guild_data(self.data, message.guild, "included_channels") and (match := check_message(self.data, message, SAME_DIFF)):
            jump = None
            try:
                channel = message.guild.get_channel(match[0][0])
                jump = await channel.fetch_message(match[0][1])
                jump =  " " + jump.jump_url
            finally:
                await message.reply(self.command_strings["repost_found"] + (jump if jump else ""))
    
client = Client()

token = environ.get("REPOSTI_DISCORD_TOKEN")
if token:
    client.run(token)
else:
    print("No Discord token found. Run the image with the correct environment variable set.")
    exit("")



