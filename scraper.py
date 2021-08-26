import asyncio
import json
import logging
import os
import sys

import aiohttp
from bs4 import BeautifulSoup

SEARCH_URL = 'https://apps.irs.gov/app/picklist/list/priorFormPublication.html?indexOfFirstRow={}' \
             '&sortColumn=sortOrder&value={}&criteria=formNumber&resultsPerPage=200&isDescending=false'

DOWNLOAD_DIR = 'forms/'
AIOHTTP_CLIENT_TIMEOUT = 10

if sys.version_info[0] == 3 and sys.version_info[1] >= 8 and sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('IRS scraper')


class TaxFormsScraper:
    async def search_forms(self, forms: list) -> str:
        forms = set(forms)
        raw_data = await self.process(forms)
        data = await self.get_data(raw_data)
        if data:
            return await self.make_json(data)
        logger.info(' Nothing found.')

    async def process(self, forms):
        searches = [self.get_search_results(form.lower()) for form in forms]
        tasks = []
        for completed in asyncio.as_completed(searches):
            form, search_results = await completed
            tasks.append(self.process_search_results(form, search_results))
        return await asyncio.gather(*tasks)

    async def get_search_results(self, form):
        url = SEARCH_URL.format(0, form.replace(' ', '+'))
        return form, await self.get_content(url)

    async def process_search_results(self, form, search_results):
        parser = BeautifulSoup(search_results, 'html.parser')

        try:
            pages_count = int(parser.find('th', class_='ShowByColumn').text.split()[-2].replace(',', '')) // 200 + 1
        except AttributeError:
            return form, None

        if pages_count == 1:
            return form, [search_results]
        return form, [search_results] + await self.get_rest_pages(form, pages_count)

    async def get_rest_pages(self, form, pages_count):
        pages = []
        for offset in range(200, pages_count * 200, 200):
            url = SEARCH_URL.format(offset, form)
            pages.append(await self.get_content(url))
        return pages

    @staticmethod
    async def get_content(url):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)) as session:
            async with session.get(url) as response:
                return await response.read()

    async def get_data(self, data, year_start: int = 0, year_end: int = 0):
        if not data:
            return
        output = []
        for form, content in sorted(data):
            parsed_data = await self.parse_data(form, content)

            if year_start and year_end and parsed_data:
                years = list(filter(lambda x: year_start <= int(x['year']) <= year_end, parsed_data['years']))
                del parsed_data['years']
                parsed_data.update({'years': years})

            output.append({form: parsed_data})
        return output

    @staticmethod
    async def parse_data(form, content):
        if not content:
            return None
        years = []
        title = None
        for item in content:
            parser = BeautifulSoup(item, 'html.parser')
            rows = parser.find_all(['tr'], class_=['even', 'odd'])
            for row in rows:
                a_tag = row.find('a')
                form_name = a_tag.text
                if form_name.lower() != form:
                    continue
                download_link = a_tag['href']
                title = row.find('td', class_='MiddleCellSpacer').text.strip()
                year = row.find('td', class_='EndCellSpacer').text.strip()
                years.append({
                    'year': year,
                    'download_link': download_link
                })
        return {'title': title, 'years': years} if title else None

    @staticmethod
    async def make_json(data):
        json_dict = []
        for item in data:
            for form, content in item.items():
                if not content:
                    item = {form.capitalize(): 'not found'}
                else:
                    years = set(map(lambda x: int(x['year']), content['years']))
                    item = {
                        'form_number': form.capitalize(),
                        'form_title': content['title'],
                        'min_year': min(years),
                        'max_year': max(years)
                    }
                json_dict.append(item)
        return json.dumps(json_dict, indent=4)

    async def download_forms(self, form: str, year_start: int, year_end: int):
        year_start, year_end = await self.validate_years(year_start, year_end)
        raw_data = await self.process([form])
        data = await self.get_data(raw_data, year_start, year_end)
        if data:
            _, downloaded = await self.get_forms(data[0])
            logger.info(f' {downloaded} forms were downloaded.')

    @staticmethod
    async def validate_years(year_start, year_end):
        try:
            year_start, year_end = int(year_start), int(year_end)
        except ValueError:
            raise Exception('Start and end years must be integers.')

        if year_start < 1800 or year_end < 1800 or year_start > year_end:
            raise Exception('Invalid years values.')
        return year_start, year_end

    async def get_forms(self, data: dict):
        form, content = tuple(*data.items())

        if not content:
            return None, 0

        tasks = [self.download_form(form, item['year'], item['download_link']) for item in content['years']]
        return await asyncio.gather(*tasks), len(tasks)

    async def download_form(self, form, year, url):
        filename = f'{form.capitalize()} - {year}.pdf'
        path = os.path.join(DOWNLOAD_DIR, filename)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        content = await self.get_content(url)
        with open(path, 'wb') as file:
            file.write(content)

    async def save_json(self, forms):
        data = await self.search_forms(forms)
        if data:
            with open('forms.json', 'w') as file:
                file.write(data)
                logger.info(' Saved to "forms.json"')
