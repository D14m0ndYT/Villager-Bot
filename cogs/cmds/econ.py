from discord.ext import commands
import discord
import asyncio
import math
import random
import aiohttp


class Econ(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.d = self.bot.d

        self.db = self.bot.get_cog("Database")

        self.ses = aiohttp.ClientSession(loop=self.bot.loop)

    """
    async def mine_captcha(ctx):
        self.d.miners[ctx.author.id] = self.d.miners.get(ctx.author.id, 0) + 1

        jj = await (await self.ses.get('http://betterapi.net/gen/captcha')).json()

        pass
    """

    async def math_problem(ctx, source_multi=1):
        mine_commands = self.d.miners.get(ctx.author.id, 0)
        self.d.miners[ctx.author.id] = mine_commands + 1

        if mine_commands >= 100*source_multi:
            self.d.miners[ctx.author.id] = 0

            prob = f'{random.randint(0, 45)}{random.choice(("+", "-",))}{random.randint(0, 25)}'
            prob = (prob, str(eval(prob)),)

            await self.bot.send(ctx, 'Please solve this problem to continue: `{prob[0]}`')

            def author_check(m):
                return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

            try:
                m = await self.bot.wait_for('message', check=author_check, timeout=10)
            except asyncio.TimeoutError:
                await self.bot.send(ctx, 'You ran out of time, what a slowpoke...')
                return False

            if m.content == prob[1]:
                await self.bot.send(ctx, 'Correct answer!')
                return True

            await self.bot.send(ctx, 'Incorrect answer!')
            return False

    @commands.command(name='bal', aliases=['balance'])
    async def bal(self, ctx, user: discord.User = None):
        """Shows the balance of a user or the message sender"""

        if user is None:
            user = ctx.author

        db_user = await self.db.fetch_user(user.id)

        u_items = await self.db.fetch_items(user.id)
        total_wealth = db_user['emeralds'] + db_user['vault_bal'] * 9 + sum([u_it['sell_price'] + u_it['item_amount'] for u_it in u_items])

        embed = discord.Embed(color=self.d.cc)
        embed.set_author(name=f'{user.display_name}\'s emeralds', icon_url=user.avatar_url_as())

        embed.description = f'Total Wealth: {total_wealth}{self.d.emojis.emerald}'

        embed.add_field(name='Pocket', value=f'{db_user["emeralds"]}{self.d.emojis.emerald}')
        embed.add_field(name='Vault', value=f'{db_user["vault_bal"]}{self.d.emojis.emerald_block}/{db_user["vault_max"]}')

        await ctx.send(embed=embed)

    @commands.command(name='inv', aliases=['inventory', 'pocket'])
    async def inventory(self, ctx, user: discord.User = None):
        """Shows the inventory of a user or the message sender"""

        if user is None:
            user = ctx.author

        u_items = await self.db.fetch_items(user.id)
        items_sorted = sorted(u_items, key=lambda item: item['sell_price'], reverse=True)  # sort items by sell price
        items_chunks = [items_sorted[i:i + 16] for i in range(0, len(items_sorted), 16)]  # split items into chunks of 16 [[16..], [16..], [16..]]

        page = 0
        page_max = len(items_chunks)

        msg = None

        while True:
            body = ''  # text for that page
            for item in items_chunks[page]:
                it_am_txt = f'{item["item_amount"]}'
                it_am_txt += ' \uFEFF' * (len(it_am_txt - 5))
                body += f'`{it_am_txt}x` **{item["item_name"]}** ({item["sell_price"]}{self.d.emojis.emerald})\n'

            embed = discord.Embed(color=self.d.cc, description=body)
            embed.set_author(name=f'{user.display_name}\'s inventory', icon_url=user.avatar_url_as())
            embed.set_footer(text=f'Page {page+1}/{page_max+1}')

            if msg is None:
                msg = await ctx.send(embed=embed)
            else:
                await msg.edit(embed=embed)

            await msg.add_reaction('➡️')
            await asyncio.sleep(.1)
            await msg.add_reaction('⬅️')
            await asyncio.sleep(.1)

            try:
                def author_check(react, r_user):
                    return r_user == ctx.author and ctx.channel == react.message.channel and msg.id == react.message.id

                react, r_user = await self.bot.wait_for('reaction_add', check=author_check, timeout=180)  # wait for reaction from message author (3min)
            except asyncio.TimeoutError:
                return

            if react.emoji == '⬅️': page -= 1
            if react.emoji == '➡️': page += 1
            await asyncio.sleep(.1)

    @commands.command(name='deposit', aliases=['dep'])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def vault_deposit(self, ctx, emerald_blocks: str):
        """Deposits the given amount of emerald blocks into the vault"""

        db_user = await self.db.fetch_user(ctx.author.id)

        c_v_bal = db_user['vault_bal']
        c_v_max = db_user['vault_max']
        c_bal = db_user['emeralds']

        if c_bal < 9:
            await self.bot.send(ctx, 'You don\'t have enough emeralds to deposit.')
            return

        if amount.lower() in ('all', 'max',):
            amount = c_v_max - c_v_bal

            if amount * 9 > c_bal:
                amount = math.floor(c_bal / 9)
        else:
            try:
                amount = int(emerald_blocks)
            except ValueError:
                await self.bot.send(ctx, 'You have to use a number.')
                return

        if amount < 1:
            await self.bot.send(ctx, 'You can\'t deposit less than one emerald block.')
            return

        if amount > c_v_max - c_v_bal:
            await self.bot.send(ctx, 'You don\'t have enough space for that.')
            return

        await self.db.balance_sub(ctx.author.id, amount * 9)
        await self.db.set_vault(ctx.author.id, c_v_bal + amount, c_v_max)

        await self.bot.send(ctx, f'Deposited {amount}{self.d.emojis.emerald_block}'
        f'({amount * 9}{self.d.emojis.emerald}) into your vault.')

    @commands.command(name='withdraw', aliases=['with'])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def vault_withdraw(self, ctx, emerald_blocks: str):
        """Withdraws a certain amount of emerald blocks from the vault"""

        db_user = await self.db.fetch_user(ctx.author.id)

        c_v_bal = db_user['vault_bal']
        c_v_max = db_user['vault_max']

        c_bal = db_user['emeralds']

        if c_v_bal < 1:
            await self.bot.send(ctx, 'You don\'t have enough emerald blocks to withdraw.')
            return

        if amount.lower() in ('all', 'max',):
            amount = c_v_bal
        else:
            try:
                amount = int(emerald_blocks)
            except ValueError:
                await self.bot.send(ctx, 'You have to use a number.')
                return

        if amount < 1:
            await self.bot.send(ctx, 'You can\'t withdraw less than one emerald block.')
            return

        if amount > c_v_bal:
            await self.bot.send(ctx, 'You can\'t withdraw more than you have.')
            return

        await self.db.balance_add(ctx.author.id, amount * 9)
        await self.db.set_vault(ctx.author.id, c_v_bal - amount, c_v_max)

        await self.bot.send(ctx, f'Withdrew {amount}{self.d.emojis.emerald_block}'
        f'({amount * 9}{self.d.emojis.emerald}) from your vault.')

    async def format_required(self, item, amount=1):
        if item[3][0] == 'Netherite Pickaxe':
            return f' {item[1] * amount}{self.d.emojis.emerald} + {4 * amount}{self.d.emojis.netherite}'

        if item[3][0] == 'Netherite Sword':
            return f' {item[1] * amount}{self.d.emojis.emerald} + {6 * amount}{self.d.emojis.netherite}'

        return f' {item[1] * amount}{self.d.emojis.emerald}'

    @commands.group(name='shop')
    async def shop(self, ctx):
        """Shows the available options in the Villager Shop"""

        if ctx.invoked_subcommand is None:
            embed = discord.Embed(color=self.d.cc)
            embed.set_author(name='Villager Shop', icon_url=self.d.splash_logo)

            embed.add_field(name='__**Tools**__', value=f'`{ctx.prefix}shop tools`')
            embed.add_field(name='__**Magic**__', value=f'`{ctx.prefix}shop magic`')
            embed.add_field(name='__**Other**__', value=f'`{ctx.prefix}shop other`')

            embed.set_footer(text=f'Use {ctx.prefix}inventory to see what you have!')

            await ctx.send(embed=embed)

    @shop.command(name='tools')
    async def shop_tools(self, ctx):
        """Allows you to shop for tools"""

        tool_items = []

        for item in [self.d.shop_items[key] for key in list(self.d.shop_items)]:  # filter out non-tool items
            if item[0] == 'tools':
                tool_items.append(item)

        tool_items_sorted = sorted(tool_items, key=lambda item: item[1])  # sort by buy price
        tool_items_chunked = [tool_items_sorted[i:i + 3] for i in range(0, len(tool_items_sorted), 3)]  # split items into chunks of 3

        page = 0
        page_max = len(tool_items_chunked)

        msg = None

        while True:
            embed = discord.Embed(color=self.d.cc)
            embed.set_author(name='Villager Shop [Tools]', icon_url=self.d.splash_logo)

            for item in tool_items_chunked[page]:
                embed.add_field(name=f'{item[3][0]} ({await self.format_required(item)})', value=f'`{ctx.prefix}buy {item[3][0].lower()}`', inline=False)

            embed.set_footer(text=f'Page {page+1}/{page_max}')

            if msg is None:
                msg = await ctx.send(embed=embed)
            else:
                if not msg.embeds[0] == embed:
                    await msg.edit(embed=embed)

            await asyncio.sleep(.1)
            await msg.add_reaction('⬅️')
            await asyncio.sleep(.1)
            await msg.add_reaction('➡️')

            try:
                def author_check(react, r_user):
                    return r_user == ctx.author and ctx.channel == react.message.channel and msg.id == react.message.id

                react, r_user = await self.bot.wait_for('reaction_add', check=author_check, timeout=180)  # wait for reaction from message author (3min)
            except asyncio.TimeoutError:
                return

            await react.remove(ctx.author)

            if react.emoji == '⬅️': page -= 1
            if react.emoji == '➡️': page += 1

            if page > page_max - 1: page = page_max - 1
            if page < 0: page = 0
            await asyncio.sleep(.1)

    @shop.command(name='magic')
    async def shop_magic(self, ctx):
        """Allows you to shop for magic items"""

        magic_items = []

        for item in [self.d.shop_items[key] for key in list(self.d.shop_items)]:  # filter out non-tool items
            if item[0] == 'magic':
                magic_items.append(item)

        magic_items_sorted = sorted(magic_items, key=lambda item: item[1])  # sort by buy price
        magic_items_chunked = [magic_items_sorted[i:i + 3] for i in range(0, len(magic_items_sorted), 3)]  # split items into chunks of 3

        page = 0
        page_max = len(magic_items_chunked)

        msg = None

        while True:
            embed = discord.Embed(color=self.d.cc)
            embed.set_author(name='Villager Shop [Magic]', icon_url=self.d.splash_logo)

            for item in magic_items_chunked[page]:
                embed.add_field(name=f'{item[3][0]} ({await self.format_required(item)})', value=f'`{ctx.prefix}buy {item[3][0].lower()}`', inline=False)

            embed.set_footer(text=f'Page {page+1}/{page_max}')

            if msg is None:
                msg = await ctx.send(embed=embed)
            else:
                if not msg.embeds[0] == embed:
                    await msg.edit(embed=embed)

            await asyncio.sleep(.1)
            await msg.add_reaction('⬅️')
            await asyncio.sleep(.1)
            await msg.add_reaction('➡️')

            try:
                def author_check(react, r_user):
                    return r_user == ctx.author and ctx.channel == react.message.channel and msg.id == react.message.id

                react, r_user = await self.bot.wait_for('reaction_add', check=author_check, timeout=180)  # wait for reaction from message author (3min)
            except asyncio.TimeoutError:
                return

            await react.remove(ctx.author)

            if react.emoji == '⬅️': page -= 1
            if react.emoji == '➡️': page += 1

            if page > page_max - 1: page = page_max - 1
            if page < 0: page = 0
            await asyncio.sleep(.1)

    @shop.command(name='other')
    async def shop_other(self, ctx):
        """Allows you to shop for other/miscellaneous items"""

        other_items = []

        for item in [self.d.shop_items[key] for key in list(self.d.shop_items)]:  # filter out non-tool items
            if item[0] == 'other':
                other_items.append(item)

        other_items_sorted = sorted(other_items, key=lambda item: item[1])  # sort by buy price
        other_items_chunked = [other_items_sorted[i:i + 3] for i in range(0, len(other_items_sorted), 3)]  # split items into chunks of 3

        page = 0
        page_max = len(other_items_chunked)

        msg = None

        while True:
            embed = discord.Embed(color=self.d.cc)
            embed.set_author(name='Villager Shop [Other]', icon_url=self.d.splash_logo)

            for item in other_items_chunked[page]:
                embed.add_field(name=f'{item[3][0]} ({await self.format_required(item)})', value=f'`{ctx.prefix}buy {item[3][0].lower()}`', inline=False)

            embed.set_footer(text=f'Page {page+1}/{page_max}')

            if msg is None:
                msg = await ctx.send(embed=embed)
            else:
                if not msg.embeds[0] == embed:
                    await msg.edit(embed=embed)

            await asyncio.sleep(.1)
            await msg.add_reaction('⬅️')
            await asyncio.sleep(.1)
            await msg.add_reaction('➡️')

            try:
                def author_check(react, r_user):
                    return r_user == ctx.author and ctx.channel == react.message.channel and msg.id == react.message.id

                react, r_user = await self.bot.wait_for('reaction_add', check=author_check, timeout=180)  # wait for reaction from message author (3min)
            except asyncio.TimeoutError:
                return

            await react.remove(ctx.author)

            if react.emoji == '⬅️': page -= 1
            if react.emoji == '➡️': page += 1

            if page > page_max - 1: page = page_max - 1
            if page < 0: page = 0
            await asyncio.sleep(.1)

    @commands.command(name='buy')
    async def buy(self, ctx, *, amount_item):
        """Allows you to buy items"""

        amount_item = amount_item.lower()

        db_user = await self.db.fetch_user(ctx.author.id)

        if amount_item.startswith('max ') or item.startswith('all '):
            item = amount_item[4:]
            amount = math.floor(db_user['emeralds'] / self.d.shop_items[item])

            if amount < 1:
                await self.bot.send(ctx, 'You don\'t have enough emeralds to buy any of this item.')
                return
        else:
            split = amount_item.split(' ')

            try:
                amount = int(split.pop(0))
            except ValueError:
                amount = 1

            item = ' '.join(split)

        if amount < 1:
            await self.bot.send(ctx, 'You can\'t buy less than one of an item.')
            return

        shop_item = self.d.shop_items.get(item)

        if shop_item is None:
            await self.bot.send(ctx, f'`{item}` is invalid or isn\'t in the Villager Shop.')
            return

        db_item = await self.db.fetch_item(ctx.author.id, shop_item[3][0])

        if shop_item[2] == "db_item_count < 1":
            amount = 1

        if shop_item[1] * amount < db_user['emeralds']:
            if db_item is not None:
                db_item_count = db_item['item_amount']
            else:
                db_item_count = 0

        if eval(shop_item[2]):
            if shop_item[3][0].startswith('Netherite'):
                db_scrap = await self.db.fetch_item(ctx.author.id, 'Netherite Scrap')

                if 'Sword' in shop_item[3][0]:
                    required = 6

                if 'Pickaxe' in shop_item[3][0]:
                    required = 3

                if scrap is not None and db_scrap['item_amount'] >= required:
                    await self.db.remove_item(ctx.author.id, 'Netherite Scrap', required)
                else:
                    await self.bot.send(ctx, f'You need a total of {required}{self.bot.cusom_emojis["netherite"]} '
                                             f'(Netherite Scrap) to buy this item.')
                    return

            await self.db.balance_sub(ctx.author.id, shop_item[1] * amount)
            await self.db.add_item(ctx.author.id, shop_item[3][0], shop_item[3][1], amount)

            await self.bot.send(ctx, f'You have bought {amount}x **{shop_item[3][0]}**!'
            f'for {await self.db.format_required(shop_item, amount)} (You have {amount + db_item["item_amount"]} total)')

            if shop_item[3][0] == 'Rich Person Trophy':
                await self.db.rich_trophy_wipe(ctx.author.id)

    @commands.command(name='sell')
    async def sell(self, ctx, *, amount_item):
        """Allows you to sell items"""

        amount_item = amount_item.lower()

        db_user = await self.db.fetch_user(ctx.author.id)

        if amount_item.startswith('max ') or item.startswith('all '):
            item = amount_item[4:]
            db_item = await self.db.fetch_item(item)

            amount = db_item['item_amount']
        else:
            split = amount_item.split(' ')

            try:
                amount = int(split.pop(0))
            except ValueError:
                amount = 1

            item = ' '.join(split)
            db_item = await self.db.fetch_item(item)

        if db_item is None:
            await self.bot.send(ctx, 'Either that item is invalid or you don\'t have it.')
            return

        if amount > db_item['item_amount']:
            await self.bot.send(ctx, 'You can\'t sell more than you have of that item.')
            return

        if amount < 1:
            await self.bot.send(ctx, 'You can\'t sell less than one of an item.')
            return

        await self.db.balance_add(ctx.author.id, amount * db_item['item_amount'])
        await self.db.remove_item(ctx.author.id, db_item['item_name'], amount)

        await self.send(ctx, f'You have sold {amount}x **{db_item["item_name"]}** for '
                             f'a total of {amount*db_item["sell_price"]}{self.d.emojis.emerald}')

    @commands.command(name='give')
    async def give(self, ctx, user: discord.User, *, amount_item):
        """Give an item or emeralds to another person"""

        if ctx.author.id == user.id:
            await self.bot.send(ctx, 'You can\'t give stuff to yourself!')
            return

        amount_item = amount_item.lower()

        try:
            # to be given is emeralds
            amount = int(amount_item)
            item = 'emerald'
        except Exception:
            split = amount_item.split(' ')

            try:
                amount = int(split.pop(0))
            except Exception:
                amount = 1

            item = ' '.join(split)

        if amount < 1:
            await self.bot.send(ctx, 'You can\'t give someone less than one of an item.')
            return

        db_user = await self.db.fetch_user(ctx.author.id)

        if item in ('emerald', 'emeralds', ':emerald:',):
            if amount > db_user["emeralds"]:
                await self.bot.send(ctx, 'You can\'t give someone more emeralds than you have.')
                return

            await self.db.balance_sub(ctx.author.id, amount)
            await self.db.balance_add(user.id, amount)

            await self.bot.send(ctx, f'{ctx.author.mention} gave {amount}{self.d.emojis.emerald} to {user.mention}!')
        else:
            db_item = await self.db.fetch_item(ctx.author.id, item)

            if db_item is None:
                await self.bot.send(ctx, 'You can\'t give an item you don\'t even have.')
                return

            if amount > db_item['item_amount']:
                await self.bot.send(ctx, 'You can\'t give more of an item than you have.')
                return

            if amount < 1:
                await self.bot.send(ctx, 'You can\'t give less than one of an item.')
                return

            await self.db.remove_item(ctx.author.id, item, amount)
            await self.db.add_item(user, item, amount)

            await self.bot.send(ctx, f'{ctx.author.mention} gave {amount}x **{db_item["item_name"]}** to {user.mention}')

    @commands.command(name='gamble')
    async def gamble(self, ctx, amount):
        """Gamble for emeralds with Villager Bot"""

        db_user = await self.db.fetch_user(ctx.author.id)

        if amount.lower() in ('all', 'max',):
            amount = db_user['emeralds']
        else:
            try:
                amount = int(amount)
            except ValueError:
                await self.bot.send(ctx, 'You have to use a number.')
                return

        if amount > db_user['emeralds']:
            await self.bot.send(ctx, 'You can\'t gamble more emeralds than you have.')
            return

        if amount < 10:
            await self.bot.send(ctx, 'You have to gamble 10 or more emeralds at a time.')
            return

        u_roll = random.randint(1, 6) + random.randint(1, 6)
        b_roll = random.randint(1, 6) + random.randint(1, 6)

        await self.bot.send(ctx, f'Your roll: `{u_roll}` **|** Bot roll: `{b_roll}`')

        if u_roll > b_roll:
            multi = 100 + randint(5, 30) + (await self.db.fetch_item(ctx.author.id, 'Bane Of Pillagers Amulet') is not None) * 75
            multi += (await self.db.fetch_item(ctx.author.id, 'Rich Person Trophy') is not None) * 20
            multi /= 100

            await self.db.balance_add(ctx.author.id, multi * amount)
            await self.bot.send(ctx, f'You won! Villager Bot {randomm.choice(self.d.gamble_sayings)} {multi * amount}{self.d.emojis.emerald}')
        elif u_roll < b_roll:
            await self.db.balance_sub(ctx.author.id, amount)
            await self.bot.send(ctx, f'You lost {amount} to Villager Bot...')
        else:
            await self.bot.send(ctx, 'Tie! Maybe Villager Bot will steal your emeralds anyways...')

    @commands.command(name='beg')
    async def beg(self, ctx):
        """Beg for emeralds"""

        db_user = await self.db.fetch_user(ctx.author.id)

        if random.choice([True, True, True, True, True, False]):
            amount = 10 + math.ceil(math.log(db_user['emeralds'], 1.5))
            amount = random.randint(1, 4) if amount < 1 else amount

            await self.bot.send(ctx, random.choice(self.d.begging_sayings['positive']).format(amount))
        else:
            amount = 10 + math.ceil(math.log(db_user['emeralds'], 1.3))
            amount = random.randint(1, 4) if amount < 1 else amount

            await self.bot.send(ctx, random.choice(self.d.begging_sayings['negative']).format(amount))

    @commands.command(name='mine', aliases=['mein'])
    async def mine(self, ctx):
        if not self.math_problem(ctx): return

        db_user = await self.db.fetch_user(ctx.author.id)
        pickaxe = await self.db.fetch_pickaxe(ctx.author.id)

        # only works cause num of pickaxes is 6 and levels of fake finds is 3
        fake_finds = self.d.mining.finds[math.floor(self.d.mining.pickaxes.index(pickaxe)/2)]

        yield_ = self.d.mining.yields_pickaxes[pickaxe] # [chance, out of]
        yield_chance_list = ([True]*yield_[0]).extend([False]*yield_[1])
        found = random.choice(yield_chance_list)

        for item in list(self.d.mining.yields_enchant_items):
            if await self.db.fetch_item(ctx.author.id, item) is not None:
                found +=  self.d.mining.yields_enchant_items[item] if found else 0
                break

        if not found:
            for item in self.d.findables:  # try to see if user gets an item
                if random.randint(0, item[2]) == 1:
                    await self.db.add_item(ctx.author.id, item[0], item[2], 1)

                    a = 'a'
                    if item[0][0] in self.d.vowels:
                        a = 'an'

                    await self.bot.send(ctx,
                        f'You {random.choice(self.d.item_finds_text.actions)} '
                        f'{a} {c[0]} (Worth {c[1]}{self.d.emojis.emerald}) '
                        f'{random.choice(self.d.item_finds_text.places)}'
                    )

                    return

            await self.bot.send(f'You {random.choice(self.d.mining.useless)} {random.randint(1, 6)} {random.choice(fake_finds)}')
        else:
            if await self.db.fetch_item(ctx.author.id, 'Rich Person Trophy') is not None:
                found *= 2

            await self.db.balance_add(ctx.author.id, found)

            await self.bot.send(f'You {random.choice(self.d.mining.actions)} {found}{self.d.emojis.emerald}!')

    @commands.command(name='pillage')
    async def pillage(self, ctx, victim: discord.User):
        if victim.bot:
            if victim.id == self.bot.user.id:
                await self.bot.send(ctx, 'You imbecile, Villager Bot cannot be defeated, Villager Bot is immortal and all powerful.')
            else:
                await self.bot.send(ctx, 'You can\'t pillage bots as they don\'t have rights and therefore can\'t have emeralds.')
            return

        if ctx.guild.get_member(victim.id) is None:
            await self.bot.send(ctx, 'You can\'t pillage people from other servers...')
            return

        db_user = await self.db.fetch_user(ctx.author.id)

        if db_user['emeralds'] < 64:
            await self.bot.send(ctx, f'You can only pillage people if you have more than 64{self.d.emojis.emerald}')
            return

        db_victim = await self.db.fetch_user(victim.id)

        if db_user['emeralds'] < 64:
            await self.bot.send(ctx, f'You can only pillage a person if they have more than 64{self.d.emojis.emerald}')
            return

        pillage_commands = self.d.pillagers.get(ctx.author.id, 0)
        self.d.pillagers[ctx.author.id] = pillage_commands + 1

        user_bees = await self.db.fetch_item(ctx.author.id, 'Jar Of Bees')
        user_bees = 0 if user_bees is None else user_bees['item_amount']

        victim_bees = await self.db.fetch_item(victim.id, 'Jar Of Bees')
        victim_bees = 0 if victim_bees is None else victim_bees['item_amount']

        if pillage_commands > 7:
            chances = [False]*20 + [True]
        elif await self.db.fetch_item(victim.id, 'Bane Of Pillagers Amulet'):
            chances = [False]*5 + [True]
        elif user_bees > victim_bees:
            chances = [False]*3 + [True]*5
        elif user_bees < victim_bees:
            chances = [False]*5 + [True]*3
        else:
            chances = [True, False]

        success = random.choice(chances)

        if success:
            stolen = math.ceil(db_victim['emeralds'] * (random.randint(10, 40) / 100))
            adjusted = math.ceil(stole * .92)

            await self.db.balance_sub(victim.id, stolen)
            await self.db.balance_add(ctx.author.id, adjusted)  # 8% tax

            await self.send(ctx, random.choice(self.d.pillaging.u_win.user).format(adjusted, self.d.emojis.emerald))
            await self.send(victim, random.choice(self.d.pillaging.u_win.victim).format(ctx.author, stolen, self.d.emojis.emerald))

            await self.db.update_lb(ctx.author.id, 'pillages', 1, 'add')
            await self.db.update_lb(ctx.author.id, 'pillages_amount', adjusted, 'add')
        else:
            penalty = 32

            await self.db.balance_sub(ctx.author.id, penalty)
            await self.db.balance_add(victim.id, penalty)

            await self.send(ctx, random.choice(self.d.pillaging.u_lose.user).format(penalty, self.d.emojis.emerald))
            await self.send(victim, random.choice(self.d.pillaging.u_lose.victim).format(ctx.author))

    @commands.command(name='chug')
    async def chug(self, ctx, *, _pot):
        pot = _pot.lower()

        if pot in self.d.potions.get(ctx.author.id):
            await self.bot.send(ctx, 'You can\'t use more than one of each type of potion at once.')
            return

        db_item = await self.db.fetch_item(ctx.author.id, pot)

        if db_item is None:
            await self.bot.send(ctx, 'You can\'t use an item you don\'t even have.')
            return

        if pot == 'haste i potion':
            await self.db.remove_item(ctx.author.id, pot, 1)

            self.d.potions[ctx.author.id] = self.d.potions.get(ctx.author.id, [])
            self.d.potions[ctx.author.id].append(pot)

            await self.bot.send(ctx, self.d.potions.chug.format('Haste I Potion', 6))

            await asyncio.sleep(60 * 6)

            await self.bot.send(ctx.author, self.d.potions.done.format('Haste I Potion'))

            self.d.potions[ctx.author.id].pop(self.d.potions[ctx.author.id].index(pot))  # pop pot from active potion fx
            return

        if pot == 'haste ii potion':
            await self.db.remove_item(ctx.author.id, pot, 1)

            self.d.potions[ctx.author.id] = self.d.potions.get(ctx.author.id, [])
            self.d.potions[ctx.author.id].append(pot)

            await self.bot.send(ctx, self.d.potions.chug.format('Haste II Potion', 4.5))

            await asyncio.sleep(60 * 6)

            await self.bot.send(ctx.author, self.d.potions.done.format('Haste II Potion'))

            self.d.potions[ctx.author.id].pop(self.d.potions[ctx.author.id].index(pot))  # pop pot from active potion fx
            return

        if pot == 'vault potion':
            db_user = await self.db.fetch_user(ctx.author.id)

            if db_user['vault_max'] > 1999:
                await self.bot.send(ctx, 'You cannot expand your vault further via this method.')
                return

            add = randint(9, 15)

            if db_user['vault_max'] + add > 2000:
                add = 2000 - db_user['vault_max']

            await self.db.remove_item(ctx.author.id, 'Vault Potion', 1)
            await self.db.set_vault(ctx.author.id, db_user['vault_bal'], db_user['vault_max'] + add)

            await self.send(ctx, f'You\'ve chugged a **Vault Potion**. Your vault space has increased by {add} spaces.')
            return

        await self.bot.send(ctx, 'Either that isn\'t a potion, or it doesn\'t exist.')

    @commands.command(name='harvesthoney', aliases=['honey'])
    async def harvest_honey(self, ctx):
        bees = await self.db.fetch_item(ctx.author.id, 'Jar Of Bees')
        if bees is not None:
            bees = bees['item_amount']
        else:
            bees = 0

        if bees > 1024: bees = 1024

        if bees < 100:
            await self.bot.send(ctx, random.choice(self.d.honey.not_viable))
            ctx.command.reset_cooldown(ctx)
            return

        jars = bees - random.randint(math.ceil(bees / 6), math.ceil(bees / 2))
        await self.db.add_item(ctx.author.id, 'Honey Jar', 1, jars)
        await self.bot.send(ctx, random.choice(self.d.honey.honey))

        if random.choice([False]*3 + [True]):
            bees_lost = random.randint(math.ceil(bees / 75), math.ceil(bees / 50))


def setup(bot):
    bot.add_cog(Econ(bot))
