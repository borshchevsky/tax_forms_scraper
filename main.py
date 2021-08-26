import asyncio
import click
from scraper import TaxFormsScraper

scraper = TaxFormsScraper()


def validate_form_names(ctx, param, value):
    for form in value:
        if len(form) < 4:
            raise click.BadParameter(f'Form name is too short: {form}')
    return value


def validate_int(ctx, param, value):
    try:
        value = int(value)
        if value < 1800:
            raise click.BadParameter('Years values must be more than 1800.')
    except ValueError:
        raise click.BadParameter('Years values must be integers.')
    return value


@click.group()
def main():
    pass


@main.command(help='Find year ranges for forms.')
@click.argument('forms', required=True, nargs=-1, callback=validate_form_names)
@click.option('-f', is_flag=True, help='Save json to file.')
def search(forms, f):
    if f:
        asyncio.run(scraper.save_json(forms))
    else:
        result = asyncio.run(scraper.search_forms(forms))
        if result:
            print(result)


@main.command(help="Download forms in PDF.")
@click.argument('form')
@click.argument('year_start', callback=validate_int)
@click.argument('year_end', callback=validate_int)
def download(form, year_start, year_end):
    asyncio.run(scraper.download_forms(form, year_start, year_end))


if __name__ == '__main__':
    main()
