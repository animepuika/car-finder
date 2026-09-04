import discord
from asgiref.sync import sync_to_async
from discord import app_commands

from listings.queries import cars_for_discord, listing_stats, tracked_search_summary

MAKE_CHOICES = ['volkswagen', 'skoda', 'audi', 'honda']
PERIOD_CHOICES = ['today', 'week', 'month']
SORT_CHOICES = ['newest', 'cheapest', 'lowest_mileage']
ACCENT_COLOR = 0xB3502B


def listing_to_embed(listing):
    embed = discord.Embed(
        title=f'{listing.make} {listing.model} ({listing.year or "?"})',
        url=listing.listing_url,
        description=f'€{listing.price_eur}' if listing.price_eur is not None else 'Price on request',
        color=ACCENT_COLOR,
    )
    if listing.primary_photo_url:
        embed.set_thumbnail(url=listing.primary_photo_url)

    specs = [s for s in [
        f'{listing.mileage_km} km' if listing.mileage_km else None,
        listing.engine,
        listing.transmission,
        listing.body_type,
        listing.color,
    ] if s]
    if specs:
        embed.add_field(name='Specs', value=' · '.join(specs), inline=False)

    if listing.ta_valid_until:
        ta_label = 'TA valid until' if listing.has_valid_ta else 'TA expired'
        embed.add_field(name=ta_label, value=listing.ta_valid_until.strftime('%d.%m.%Y'), inline=True)

    if listing.probably_sold:
        embed.set_footer(text='Probably sold - not refreshed in 14+ days')

    return embed


def build_client():
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    @tree.command(name='cars', description='Show tracked car listings')
    @app_commands.describe(period='How recent', make='Which make', sort='Sort order')
    @app_commands.choices(
        period=[app_commands.Choice(name=p, value=p) for p in PERIOD_CHOICES],
        make=[app_commands.Choice(name=m, value=m) for m in MAKE_CHOICES],
        sort=[app_commands.Choice(name=s.replace('_', ' '), value=s) for s in SORT_CHOICES],
    )
    async def cars(
        interaction: discord.Interaction,
        period: app_commands.Choice[str] = None,
        make: app_commands.Choice[str] = None,
        sort: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer()

        shown, remaining = await sync_to_async(cars_for_discord)(
            make=make.value if make else None,
            period=period.value if period else None,
            sort=sort.value if sort else 'newest',
        )

        if not shown:
            await interaction.followup.send('No matching listings found.')
            return

        content = f'+{remaining} more - see the website for all of them.' if remaining else None
        await interaction.followup.send(content=content, embeds=[listing_to_embed(c) for c in shown])

    @tree.command(name='stats', description='Overview of everything currently tracked')
    async def stats(interaction: discord.Interaction):
        await interaction.response.defer()
        data = await sync_to_async(listing_stats)()

        embed = discord.Embed(title='Car Finder stats', color=ACCENT_COLOR)
        embed.add_field(name='Total for-sale listings', value=str(data['total']), inline=False)

        if data['by_make']:
            by_make_lines = '\n'.join(f'{row["make"]}: {row["count"]}' for row in data['by_make'])
            embed.add_field(name='By make', value=by_make_lines, inline=True)

        if data['min_price'] is not None:
            price_lines = f'Min: €{data["min_price"]}\nMax: €{data["max_price"]}\nAvg: €{data["avg_price"]}'
            embed.add_field(name='Price range', value=price_lines, inline=True)

        await interaction.followup.send(embed=embed)

    @tree.command(name='tracked', description='Show what makes/models are currently being tracked')
    async def tracked(interaction: discord.Interaction):
        await interaction.response.defer()
        searches = await sync_to_async(tracked_search_summary)()

        if not searches:
            await interaction.followup.send('Nothing is being tracked right now.')
            return

        lines = []
        for ts in searches:
            label = f'{ts.make} {ts.model}'.strip() if ts.model else f'{ts.make} (all models)'
            extras = []
            if ts.max_price_eur is not None:
                extras.append(f'≤€{ts.max_price_eur}')
            if ts.require_ta:
                extras.append('TA required')
            if extras:
                label += f' - {", ".join(extras)}'
            lines.append(label)

        embed = discord.Embed(title='Currently tracked', description='\n'.join(lines), color=ACCENT_COLOR)
        await interaction.followup.send(embed=embed)

    @client.event
    async def on_ready():
        await tree.sync()
        print(f'Logged in as {client.user}')

    return client
