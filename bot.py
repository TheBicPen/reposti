import discord
import imagehash
import requests
import json
# from textdistance import hamming
from PIL import Image, UnidentifiedImageError
from os import environ, path
from io import BytesIO

SAME_DIFF = 20
HASH_SIZE = 16

default_strings = {
    "scan": "reposti scan",
    "clear": "reposti scanclear",
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
    out = {"hashes": [], "errors": 0, "unhashables": 0}
    urls = []
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
            out["hashes"].append(
                str(imagehash.whash(img, hash_size=HASH_SIZE)))
        except UnidentifiedImageError as e:
            out["errors"] += 1
            print(e, url)
    return out


def num_in_ranges(ranges, num: int):
    """
    Returns whether a number is in a list of sorted ranges.
    """
    if len(ranges) > 1:
        if num < ranges[len(ranges) // 2][0]:
            return num_in_ranges(ranges[:len(ranges) // 2], num)
        else:
            return num_in_ranges(ranges[len(ranges) // 2:], num)
    elif len(ranges) == 1:
        return num >= ranges[0][0] and num <= ranges[0][1]
    else:
        return False


def add_range(ranges, new_range: tuple):
    """
    Adds a range to a list of ranges
    """
    min_i = None
    max_i = None
    # extend a range to the union of the new range and the nearest overlap
    for i, r in enumerate(ranges):
        if r[0] <= new_range[0] and new_range[0] <= r[1] or new_range[0] <= r[0] and r[0] <= new_range[1] and min_i is None:
            r[0] = min(r[0], new_range[0])
            min_i = i
        if r[0] <= new_range[1] and new_range[1] <= r[1] or new_range[0] <= r[1] and r[1] <= new_range[1]:
            ranges[min_i][1] = max(r[1], new_range[1])
            max_i = i
    # if there is no overlap, insert the new range
    if min_i is None and max_i is None:
        for i, r in enumerate(ranges):
            if new_range[1] < r[0]:
                ranges.insert(i, list(new_range))
                break
        else:
            ranges.append(list(new_range))
    else:
        # pop all ranges between the min and max of the new range
        for i in range(min_i + 1, max_i + 1):
            ranges.pop(min_i + 1)


async def scan_channel(channel, data, history_args, until_message=None, force_rescan=False):
    print(
        f"Scanning '#{channel.name}', {'all' if history_args.get('limit') is None else history_args['limit']} posts")
    posts_skipped = 0
    posts_scanned = 0
    images_found = 0
    image_errors = 0
    hashes = {}
    first_message = None
    last_message = None
    scanned_ranges = get_guild_data(
        data, channel.guild, "scanned_ranges", default={}).get(str(channel.id), [])  # keys are stored as strings
    async for m in channel.history(**history_args):
        if until_message and m.id == until_message:
            break
        if (posts_scanned + posts_skipped) % 100 == 0:
            if posts_scanned + posts_skipped == 0:
                first_message = m.id
            else:
                print(
                    f"Scanned {posts_scanned}/{posts_scanned + posts_skipped} posts in '#{channel.name}'", m.jump_url)
        last_message = m.id
        if not force_rescan and num_in_ranges(scanned_ranges, m.id):
            posts_skipped += 1
            continue
        embeds = image_hash_from_message(m)
        for h in embeds["hashes"]:
            if h in hashes:
                hashes[h].append((channel.id, m.id))
            else:
                hashes[h] = [(channel.id, m.id)]

        images_found += len(embeds["hashes"]) + embeds["errors"]
        image_errors += embeds["errors"]
        posts_scanned += 1
    add_hash_data(data, channel.guild, hashes)
    if last_message:
        add_scanned_range(data, channel, (first_message, last_message))
    return posts_scanned, posts_skipped, len(hashes), image_errors


def add_scanned_range(data, channel, message_range: tuple):
    message_range = (min(message_range), max(message_range))
    channels = get_guild_data(
        data, channel.guild, "scanned_ranges", default={})
    channel_id = str(channel.id)  # since JSON can only use strings as keys
    if str(channel_id) not in channels:
        channels[channel_id] = []
    add_range(channels[channel_id], message_range)
    set_guild_data(data, channel.guild, "scanned_ranges", channels)


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


def del_guild_data(data, guild, k, raise_error=True):
    guild_name, _ = unique_guild_data(guild)
    try:
        del data[guild_name][k]
    except KeyError as e:
        if raise_error:
            raise e
    save_guild_data(data, guild)


def add_hash_data(data, guild, hashes: dict):
    """
    Adds hashes to data.
    hashes should be a dict that maps the hash strings to a list (typically of tuples containing channel and message IDs).
    Only unique list elements are added.
    """
    if not get_guild_data(data, guild, "hashes"):
        set_guild_data(data, guild, "hashes", {})
    for h, posts in hashes.items():
        if h in get_guild_data(data, guild, "hashes", []):
            for p in posts:
                matching_posts = get_guild_data(data, guild, "hashes")[h]
                if p in matching_posts:
                    matching_posts.append(p)
        else:
            get_guild_data(data, guild, "hashes", [])[h] = posts
    save_guild_data(data, guild)


async def load_data(client) -> dict:
    data = {}
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
    unique_name = "".join(
        [x for x in guild.name if x.isalnum()]) + "_" + str(guild.id)
    file_name = path.join("data", unique_name + ".json")
    return (unique_name, file_name)


def check_message(data, message, max_diff=0):
    embeds = image_hash_from_message(message)
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

    def __init__(self):
        super().__init__()
        self.command_strings = default_strings.copy()

    def check_command(self, message, command):
        return message.content.startswith(self.command_strings[command])

    def get_args(self, message, command):
        return message.content[len(self.command_strings[command]):].split()

    async def on_ready(self):
        print('We have logged in as {0.user}'.format(self))
        self.data = await load_data(self)

    async def on_guild_join(self, guild):
        self.data = await load_data(self)

    async def on_message(self, message):
        if message.author == client.user:
            return

        # if message.author == message.guild.owner: #intents or some other junk broke this
        if message.author.id == message.guild.owner_id:
            if self.check_command(message, "hello"):
                print("Hello there")
                await message.reply('Hello there')

            elif self.check_command(message, "clear"):
                if args := self.get_args(message, "clear"):
                    if args[0] == "all":
                        channels = message.guild.channels
                    else:
                        channels = message.channel_mentions
                else:
                    channels = [message.channel]
                scanned_channels = get_guild_data(
                    self.data, message.guild, "scanned_ranges")
                for channel in channels:
                    try:
                        del scanned_channels[str(channel.id)]
                    except KeyError:
                        pass
                save_guild_data(self.data, message.channel.guild)
                await message.reply("Removed scan cache for: " + ", ".join([c.name for c in channels]))

            elif self.check_command(message, "scan"):
                history_args = {
                    "limit": None,
                    # "oldest_first": True
                }
                channels = [message.channel]
                force_rescan = False
                for w in self.get_args(message, "scan"):
                    if w.isdecimal():
                        history_args["limit"] = int(w)
                    elif w == "now":
                        history_args["before"] = message
                        # history_args["oldest_first"] = None
                    elif w == "all":
                        channels = message.guild.channels
                    elif w == "rescan":
                        force_rescan = True
                if mentions := message.channel_mentions:
                    channels = mentions
                async with message.channel.typing():
                    await message.channel.send("Scanning posts...")
                    for channel in channels:
                        scan_info = await scan_channel(channel, self.data, history_args, force_rescan=force_rescan)
                        info_str = f"Done. Scanned {scan_info[0]}/{scan_info[0] + scan_info[1]} posts in #{channel.name}, found {scan_info[2]} unique images, {scan_info[3]} errors."
                        print(info_str)
                        await message.channel.send(info_str)

            elif self.check_command(message, "hash"):
                if message.reference:
                    m = message.reference.resolved
                    if isinstance(m, discord.DeletedReferencedMessage):
                        await message.reply("The message was deleted.")
                        print("The message was deleted.")
                    if m is None:
                        await message.reply("Discord refused to find the message this one references.")
                        print(
                            "Discord refused to find the message this one references.")
                    elif isinstance(m, discord.Message):
                        await message.reply(str(image_hash_from_message(m)))
                else:
                    await message.reply("Reply to a message to trigger this command.")

            elif self.check_command(message, "hashdiff"):
                words = self.get_args(message, "hashdiff")
                if len(words) != 2:
                    await message.reply("This command needs 2 hashes.")
                else:
                    await message.reply(str(hash_diff(*words)))

            elif self.check_command(message, "diff"):
                words = self.get_args(message, "diff")
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
                channels = get_guild_data(
                    self.data, message.guild, "included_channels")
                if args and args[0] == "all":
                    channels = [c.id for c in message.guild.channels]
                elif args and args[0] == "none":
                    channels = []
                else:
                    channels.append([c.id for c in message.channel_mentions])
                set_guild_data(self.data, message.guild,
                               "included_channels", channels)
                await message.reply("Checking the following channels for reposts:" + ", ".join([str(message.guild.get_channel(c)) for c in channels]))

            elif self.check_command(message, "exclude"):
                args = self.get_args(message, "exclude")
                channels = get_guild_data(
                    self.data, message.guild, "included_channels")
                if args and args[0] == "all":
                    channels = []
                elif args and args[0] == "none":
                    channels = [c.id for c in message.guild.channels]
                else:
                    try:
                        channels.remove(
                            [c.id for c in message.channel_mentions])
                    except ValueError:
                        await message.reply("A mentioned channel was not in the list. List not updated.")

                set_guild_data(self.data, message.guild,
                               "included_channels", channels)
                await message.reply("Checking the following channels for reposts:" + ", ".join([str(message.guild.get_channel(c)) for c in channels]))

        if message.channel.id in get_guild_data(self.data, message.guild, "included_channels", []) and (match := check_message(self.data, message, SAME_DIFF)):
            jump = None
            try:
                channel = message.guild.get_channel(match[0][0])
                jump = await channel.fetch_message(match[0][1])
                jump = " " + jump.jump_url
            finally:
                await message.reply(self.command_strings["repost_found"] + (jump if jump else ""))


if __name__ == '__main__':
    client = Client()

    token = environ.get("REPOSTI_DISCORD_TOKEN")
    if token:
        client.run(token)
    else:
        print("No Discord token found. Run the image with the correct environment variable set.")
        exit("")
