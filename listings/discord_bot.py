import discord
from asgiref.sync import sync_to_async
from discord import app_commands

from listings.queries import cars_for_discord

MAKE_CHOICES = ['volkswagen', 'skoda', 'audi', 'honda']
PERIOD_CHOICES = ['today', 'week', 'month']
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
    ] if s]
    if specs:
        embed.add_field(name='Specs', value=' · '.join(specs), inline=False)

    return embed


def build_client():
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    @tree.command(name='cars', description='Show tracked car listings')
    @app_commands.describe(period='How recent', make='Which make')
    @app_commands.choices(
        period=[app_commands.Choice(name=p, value=p) for p in PERIOD_CHOICES],
        make=[app_commands.Choice(name=m, value=m) for m in MAKE_CHOICES],
    )
    async def cars(
        interaction: discord.Interaction,
        period: app_commands.Choice[str] = None,
        make: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer()

        shown, remaining = await sync_to_async(cars_for_discord)(
            make=make.value if make else None,
            period=period.value if period else None,
        )

        if not shown:
            await interaction.followup.send('No matching listings found.')
            return

        content = f'+{remaining} more - see the website for all of them.' if remaining else None
        await interaction.followup.send(content=content, embeds=[listing_to_embed(c) for c in shown])

    @client.event
    async def on_ready():
        await tree.sync()
        print(f'Logged in as {client.user}')

    return client
