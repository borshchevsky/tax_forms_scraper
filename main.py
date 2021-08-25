import asyncio
import json
import os
import random
import sys
import time

import aiohttp
from bs4 import BeautifulSoup

SEARCH_URL = 'https://apps.irs.gov/app/picklist/list/priorFormPublication.html?indexOfFirstRow={}' \
             '&sortColumn=sortOrder&value={}&criteria=formNumber&resultsPerPage=200&isDescending=false'

DOWNLOAD_DIR = 'forms/'
AIOHTTP_CLIENT_TIMEOUT = 10


if sys.version_info[0] == 3 and sys.version_info[1] >= 8 and sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class TaxFormsScraper:
    def search_forms(self, forms: list) -> str:
        forms = set(forms)
        raw_data = asyncio.run(self.process(forms))
        data = self.get_data(raw_data)
        if data:
            return self.make_json(data)

    async def process(self, forms):
        searches = [self.get_search_results(form.lower()) for form in forms]
        tasks = []
        for completed in asyncio.as_completed(searches):
            form, search_results = await completed
            tasks.append(self.process_search_results(form, search_results))
        result = await asyncio.gather(*tasks)
        return None if None in result else result

    async def get_search_results(self, form):
        url = SEARCH_URL.format(0, form.replace(' ', '+'))
        return form, await self.get_content(url)

    async def process_search_results(self, form, search_results):
        parser = BeautifulSoup(search_results, 'html.parser')

        try:
            pages_count = int(parser.find('th', class_='ShowByColumn').text.split()[-2].replace(',', '')) // 200 + 1
        except AttributeError:
            return

        if pages_count == 1:
            return form, [search_results]
        return form, [search_results] + await self.get_rest_pages(form, pages_count)

    async def get_rest_pages(self, form, pages_count):
        pages = []
        for offset in range(200, pages_count * 200, 200):
            url = SEARCH_URL.format(offset, form)
            pages.append(await self.get_content(url))
        return pages

    # noinspection PyMethodMayBeStatic
    async def get_content(self, url):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)) as session:
            async with session.get(url) as response:
                return await response.read()

    def get_data(self, data: list, year_start: int = 0, year_end: int = 0):
        if not data:
            return
        data.sort()
        output = []
        for form, content in data:
            parsed_data = self.parse_data(form, content)
            if not parsed_data:
                return

            if year_start and year_end:
                years = list(filter(lambda x: year_start <= int(x['year']) <= year_end, parsed_data['years']))
                del parsed_data['years']
                parsed_data.update({'years': years})

            output.append({form: parsed_data})
        return output

    # noinspection PyMethodMayBeStatic
    def parse_data(self, form, content):
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

    # noinspection PyMethodMayBeStatic
    def make_json(self, data):
        json_dict = []
        for item in data:
            for form, content in item.items():
                years = set(map(lambda x: int(x['year']), content['years']))
                json_dict.append({
                    'form_number': form.capitalize(),
                    'form_title': content['title'],
                    'min_year': min(years),
                    'max_year': max(years)
                })
        return json.dumps(json_dict, indent=4)

    def download_forms(self, form: str, year_start: int, year_end: int):
        self.validate_years(year_start, year_end)
        raw_data = asyncio.run(self.process([form]))
        data = self.get_data(raw_data, year_start, year_end)
        if data:
            asyncio.run(self.get_forms(data[0]))

    # noinspection PyMethodMayBeStatic
    def validate_years(self, year_start, year_end):
        if not all([isinstance(year_start, int), isinstance(year_end, int)]):
            raise Exception('Year values must be integers.')
        if year_start < 1800 or year_end < 1800 or year_start > year_end:
            raise Exception('Invalid years values.')

    async def get_forms(self, data: dict):
        form, content = tuple(*data.items())
        tasks = [self.download_form(form, item['year'], item['download_link']) for item in content['years']]
        return await asyncio.gather(*tasks)

    async def download_form(self, form, year, url):
        filename = f'{form.capitalize()} - {year}.pdf'
        path = os.path.join(DOWNLOAD_DIR, filename)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        content = await self.get_content(url)
        with open(path, 'wb') as file:
            file.write(content)

    def save_json(self, forms):
        data = self.search_forms(forms)
        if data:
            with open('forms.json', 'w') as file:
                file.write(data)


test_list = ["Form 8915-B", "Form 5713", "Inst 1040 (Schedule J)", "Form 1120", "Form 5305-EA", "Inst 1098-E and 1098-T", "Inst 990 or 990-EZ (Sch C)", "Form 2290", "Form 944-SS", "Form W-2", "Form 1099-H", "Publ 538", "Inst 8939", "Form 4563", "Form 8911", "Publ 1693", "Form 1065 (Schedule K-1)", "Form 2290 (SP)", "Inst 1120 (Schedule O)", "Form 8966-C", "Form 712", "Form 1120-DISC (Schedule K)", "Form 5500-C", "Form 8966", "Form 1120-W", "Form W-14", "Inst 5330", "Form 8950", "Publ 597", "Form 990 (Schedule M)", "Form 8946", "Form 1125-A", "Inst 8979", "Inst 8821 (SP)", "Form 8879-PE", "Inst 990 or 990-EZ (Sch L)", "Notc 1392", "Inst 8910", "Inst 940 (PR)", "Form 7200 (sp)", "Form 5305-SIMPLE", "Form 1120-S (Schedule M-3)", "Form 6781", "Form 5500 (Schedule SSA)", "Inst 720-TO", "Form 3115", "Inst 8801", "Publ 901", "Form 8975", "Form 5306-A", "Form 8281", "Form 940-EZ", "Form 8947", "Publ 976 (SP)", "Form 1041 (Schedule I)", "Form 8810", "Form 990-W", "Inst 8915-D", "Form 1120-X", "Inst 990 or 990-EZ (Sch A)", "Form 8302", "Inst 1040-EZ", "Form 5884-C", "Form 1040-EZ-T", "Form 2848 (SP)", "Inst 6198", "Form 8288-A", "Inst 990-PF", "Inst 1120-REIT", "Form 8809", "Inst 1118 (Schedule J)", "Publ 1167", "Inst W-3C (PR)", "Form 1065 (Schedule D-SUPP)", "Form 7200 (SP)", "Form 8836", "Form 8958", "Form 13614-C (KR)", "Form 9465 (SP)", "Inst 843", "Publ 4895", "Form 8942", "Publ 16", "Inst 8918", "Inst W-3SS", "Form 6197", "Form 8985", "Publ 6186", "Form 5500 (Schedule P)", "Form 1065 (Schedule C)", "Inst CT-1X", "Form 8828", "Form 6745", "Form 5712", "Form 8858", "Publ 504", "Publ 850 (EN-CN-T)", "Form 8835", "Form FinCEN109A", "Form 8875", "Inst 1066", "Form 1094-C", "Form 990-BL", "Form 8885", "Publ 1458", "Form 8804", "Form 2290 (FR)", "Inst 4797", "Form 2439", "Inst W-14", "Form FinCEN102A", "Form 8820", "Form 2210", "Inst 3903-F", "Form 1120 (Schedule PH)", "Form W-4 (SP)", "Form 1125-E", "Form 5884-B", "Form 990-T", "Inst 8609", "Form 1023-Interactive", "Inst 1040 (General Inst.)", "Form 1040-NR-EZ", "Publ 1660 (SP)", "Form 4626", "Form 1095-B", "Form 965 (Schedule H)", "Inst 1099 General Instructions", "Form 1040 (Schedule 1) (SP)", "Form 1098-F", "Publ 4164", "Form 8978 (Schedule A)", "Form FinCEN110", "Form 1120-REIT", "Publ 5392", "Form 1120-L (Schedule M-3)", "Inst 1120-S (Schedule D)", "Inst 8854", "Inst 706", "Publ 911", "Form 8902", "Inst 990 (Schedule K)", "Form 5305", "Inst 944-X (PR)", "Inst 7200 (SP)", "Publ 179", "Form 941", "Form 8804-W", "Form 8995-A (Schedule B)", "Form 8508-I", "Inst 4506-A", "Publ 6292-A", "Publ 17 (ZH-S)", "Form 720-CS", "Form 990-W (FY)", "Form 8879-EMP", "Form 1118", "Inst 8734", "Inst 941", "Form 1040 (Schedule A)", "Publ 575", "Publ 1660", "Inst 8864", "Form 1118 (Schedule K)", "Form 8606", "Inst 8928", "Publ 1693 (SP)", "Form 1120 (Schedule B)", "Inst 1120-PC (Schedule M-3)", "Publ 5 (SP)", "Inst 720", "Publ 915", "Inst 8975", "Publ 908", "Publ 501", "Form 1065 (Schedule M-3)", "Form 990 or 990-EZ (Sch A)", "Form 5495", "Notc 931", "Form 8853", "Publ 4163", "Form W-3 (PR)", "Inst 8883", "Form 941-C (PR)", "Publ 946", "Form 1040 (Schedule J)", "Publ 1212", "Form 5712-A", "Publ 542", "Form 1023", "Form 8861", "Inst 1041 (Schedule D)", "Form 5213", "Publ 1 (ZH-T)", "Publ 596", "Form 720-X", "Inst 1041 (Schedule K-1)", "Form 8842", "Publ 530", "Form 13614-C", "Inst 941 (Schedule B)", "Form 8935-T", "Form 1096 (Schedule A)", "Form 8874-A", "Inst 941 (Schedule R)", "Form 944-X", "Form 8974", "Form 8881", "Form 8275-R", "Form 1042-S", "Inst 6478", "Form W-2AS", "Form 8945", "Form 1042-T", "Form 1065-B", "Publ 213", "Inst 1099-INT and 1099-OID", "Inst 990-EZ", "Form 8948", "Form 8453-FE", "Inst 5471", "Form 1096", "Inst 1065", "Form 730", "Inst 8828", "Inst 1040 (Tax Tables)", "Form 940 (PR)", "Form 1099-LS", "Publ 1516", "Inst 5713", "Publ 519", "Inst 1120-S (Schedule K-1)", "Form 1040-T", "Form 8859", "Form 8957", "Publ 5035", "Form 4952", "Form 1040-ES", "Inst 8873", "Publ 1459", "Inst 943-X", "Form 8621", "Inst 5498-ESA", "Inst 2555-EZ", "Publ 3415", "Form 8858 (Schedule M)", "Form 8995-A (Schedule D)", "Form 1099-R", "Publ 4425", "Publ 15-B", "Form 8804 (Schedule A)", "Form 1120-FSC", "Publ 850 (EN-RU)", "Form 1040 (Schedule 8812)", "Form 990 (Schedule D)", "Form 8971", "Inst 944 (PR)", "Form 8874", "Form 1120 (Schedule H)", "Form 8824", "Inst 1040 (Schedule R & RP)", "Publ 584", "Inst 965-B", "Form 8818", "Form 637", "Form 8582", "Form 4461-B", "Form 8872", "Form 8865 (Schedule K-1)", "Form 1095-A", "Form 1120-S", "Form 8876", "Inst 8942", "Inst 5472", "Form 5305-SEP", "Inst 1040-A", "Form 1099-QA", "Form 8941", "Form 1099-B", "Form 13614-C (VN)", "Form 9465", "Form 8907", "Form 8717", "Form 1120-POL", "Publ 589", "Inst 8863", "Publ 51", "Form 1098-E", "Form 1099-A", "Form 1120 (Schedule C)", "Publ 17 (SP)", "Form 3520", "Form 5578", "Inst 1099-S", "Form 1120 (Schedule N)", "Form 8752", "Form 8995-A (Schedule A)", "Form 1120-IC-DISC (Schedule P)", "Inst 5405", "Inst 8609-A", "Form 8959", "Form 8716", "Inst 2220", "Inst 990", "Form 5713 (Schedule A)", "Publ 561", "Form 4506-T", "Inst 8804-W", "Form 990 or 990-EZ (Sch E)", "Publ 936", "Form 1099-OID", "Form 8288", "Publ 1 (SP)", "Publ 950", "Publ 5186", "Inst 1099-MISC", "Form 8379", "Form 1040 (PR) (Anejo H-PR)", "Form 2758", "Form 5500-EZ", "Form 1040 (Schedule C)", "Form 2438", "Inst 990-BL", "Form 1120-RIC", "Form 8927", "Form 1040 (Schedule EIC) (SP)", "Form 4868 (SP)", "Form 1120 (Schedule PH) (FY)", "Form 8996", "Form 8986", "Publ 1 (VIE)", "Form 8275", "Form 8938", "Inst 1041", "Form 6251", "Inst 8027", "Form 5305-B", "Publ 537", "Publ 1141", "Inst 8615", "Publ 393", "Inst 8978", "Form 1098", "Form 4361", "Form 5498-ESA", "Form 1040 (Schedule L)", "Form 8838", "Form 4852", "Form 1040 (Schedule D)", "Form 1040-SR(SP)", "Publ 4162", "Form 5500 (Schedule R)", "Inst 1120 (Schedule UTP)", "Form 1139", "Publ 5216", "Inst 8275", "Form 8609 (Schedule A)", "Form 8038-TC", "Form 8899", "Publ 536-SUPP", "Form 4868", "Form 56-F", "Form 1042 (Schedule Q)", "Inst 941-X (PR)", "Form 8893", "Inst 8038-G", "Publ 1 (TL)", "Form 1127-A", "Form 5884-D", "Form 8975 (Schedule A)", "Form 944 (SP)", "Form 1040-ES (E)", "Publ 15-A", "Inst 945-X", "Form 8233", "Form FinCEN104", "Form W-10", "Publ 4", "Publ 4681", "Publ 5164", "Form 4506T-EZ", "Inst SS-4 (PR)", "Inst 5695", "Publ 4450", "Inst 1028", "Form 1099-NEC (EY)", "Inst 8023", "Form 945-X", "Form 8937", "Publ 596 (SP)", "Inst 706-GS(D)", "Form 1120-S (Schedule B-1)", "Form 13614-C (HT)", "Form 941-X", "Form 2032", "Inst 8895", "Form 8921", "Publ 503", "Inst 8957", "Inst 1040 (PR) (Anejo H-PR)", "Form 8839", "Form 8916-A", "Inst 8606", "Form 3903", "Inst 990 (Schedule J)", "Inst 9465-FS", "Inst 944-X (SP)", "Inst 4972", "Inst 8949", "Inst 990 (Schedule H)", "Form 2119", "Inst 8850", "Form 5558", "Form 4461", "Form 3491", "Form 706-NA", "Form 8849 (Schedule 8)", "Publ 1 (RU)", "Form 1098-Q", "Form 8860", "Form 9041", "Form 2240", "Publ 556", "Form 8834", "Form 1041 (Schedule J)", "Form 1040 (PR)", "Form 4255", "Form 8282", "Form 1120-S (Schedule K-3)", "Form 1040 (Schedule SE)", "Form 8930", "Inst 5884-A", "Inst 1125-E", "Publ 559", "Form 4875", "Form 8922", "Form 8863", "Inst 8915-B", "Inst 8849 (Schedule 6)", "Form 1040 (Schedule R)", "Publ 1436", "Form 8836 (SP)", "Form 8992", "Form 973", "Inst 1040-SS", "Form 8962", "Form 1040 (PR) (Schedule H)", "Form 5500 (Schedule C)", "Form 709", "Form 1120-DISC (Schedule N)", "Inst 720-CS", "Form 943 (Schedule R)", "Publ 945", "Form W-13", "Form 8900", "Form 3468", "Publ 541", "Form 8919", "Inst 1065-X", "Inst 8283", "Form 4726", "Publ 533", "Publ 2194", "Publ 974", "Inst 1040 (Schedule H)", "Inst 1098-F", "Publ 1136", "Form 8915-E", "Form 1120-FSC (Schedule P)", "Publ 947", "Inst 1065 (Schedule C)", "Form T (Timber)", "Form 8586", "Form 972", "Publ 6149", "Form 1040-NR (Schedule NEC)", "Inst SS-8", "Form 1103", "Form 8453-PE", "Form 990-EZ", "Publ 971", "Inst 1040 (Schedule C)", "Form 8928", "Notc 797", "Publ 3920", "Inst 8915-A", "Inst 1120 and 1120-A", "Form 8613", "Publ 1 (HT)", "Form 4562", "Form 941-C", "Form 4137", "Inst 1094-B and 1095-B", "Form 8453-E", "Form 990-PF", "Form 8935", "Publ 4801", "Form 3920", "Form W-3SS", "Form 5310-A", "Inst 1095-A", "Form 8831", "Publ 968", "Inst 1120 (Schedule M-3)", "Form 4469", "Inst 5227", "Form 4506", "Form 990 or 990-EZ (Sch G)", "Form W-11", "Inst 8804 (Schedule A)", "Form 1094", "Inst 8621-A", "Form 1099-NEC", "Form 1045", "Form 1040 (Schedule 3) (SP)", "Inst 1040-NR", "Form 4970", "Form 8879-EO", "Inst 8930", "Form 2553", "Form 8936", "Inst 2119", "Form 1040 (Schedule H)", "Form 1065 (Schedule B-1)", "Publ 939", "Publ 524", "Inst 1099-LTC", "Form 8396", "Inst 8038-TC", "Form 6765", "Form 943", "Inst 940-EZ", "Form 4506-A", "Form 8913", "Inst 461", "Form 1040-NB-A", "Form 8960", "Publ 1 (PA)", "Form 8802", "Inst 8594", "Publ 510", "Inst 1120-F (Schedule V)", "Form 8882", "Form 8717-A", "Publ 502", "Form 8878-A", "Inst 8824", "Publ 523", "Form 8848", "Form 8865 (Schedule H)", "Inst 8940", "Form 8849 (Schedule 1)", "Form 8689", "Inst 8926", "Publ 505", "Form 706-GS(D)", "Inst 8991", "Inst 990 or 990-EZ (Sch G)", "Inst 1099", "Inst 8941", "Inst 8582", "Inst 943", "Form 8453", "Publ 555", "Publ 938", "Publ 967", "Form 1040 (Schedule LEP) (SP)", "Notc 703", "Inst 1120-S (Schedule M-3)", "Form 8718", "Publ 600-A", "Form 941-SS", "Form 5330", "Form 8995-A (Schedule C)", "Form 1120-S (Schedule K-1)", "Form 990 (SF)", "Inst 706-GS(T)", "Publ 595", "Form 5500 (Schedule H)", "Form 8038-R", "Form 706-CE", "Inst 8858", "Form 4720", "Form 1028", "Publ 4684", "Publ 850 (EN-VN)", "Form 8453-OL", "Publ 850 (EN-CN-S)", "Inst 6252", "Form 8288-B", "Form 1040 (Schedule E)", "Form 706-QDT", "Inst 1120 (Schedule PH) (FY)", "Publ 5078", "Form 8838-P", "Form 5471 (Schedule P)", "Publ 5165", "Form 1065 (Schedule K-3)", "Form 706-GS(D-1)", "Inst 8913", "Inst 1120-S", "Form 940 (Schedule A)", "Form 1099-SA", "Form 8582-CR", "Publ 571", "Inst 990-T", "Form 8939", "Inst 9465-FS (SP)", "Publ 970", "Publ 5329", "Form 5695", "Form 5471 (Schedule J)", "Form 8819", "Form 2678", "Inst 1120-F (Schedule S)", "Form 2350 (SP)", "Form 8655", "Inst 1097-BTC", "Publ 5292", "Form 5316", "Inst 8915-E", "Form 5500", "Form 8952", "Form 5304-SIMPLE", "Inst 8867", "Inst 5500", "Form 8453-EO", "Form 4782", "Inst 706-D", "Publ 5420", "Form 8851", "Inst 2555", "Form 5405-FY", "Form 1095-C", "Publ 1542", "Inst 8288", "Inst 990 and 990-EZ", "Form 8908", "Form 1120-PC", "Form 3921", "Form 6497", "Inst 7200", "Form W-2 P", "Form 4797", "Form 1040-SR", "Inst 7202 (SP)", "Publ 1187", "Form 940 (PR) (Schedule A)", "Publ 1544", "Form 5309", "Publ 4829", "Form 8879-I", "Form 8933", "Form 9465-FS", "Form 8830", "Publ 17 (ZH-T)", "Form 5471 (Schedule H)", "Form 8850", "Form 5471 (Schedule M)", "Form W-3C", "Inst 8839", "Inst 940", "Inst 8872", "Form 966", "Form 5305-RA", "Form 8271", "Inst 1040-EZ & A", "Inst 1099-DIV", "Form 8050", "Form 8300", "Form 8909", "Form 1120-IC-DISC (Schedule K)", "Form 5735", "Inst 7200 (sp)", "Notc 940 (SP)", "Form 8656", "Inst 941-X", "Form 8995", "Inst 5500 (Schedule B)", "Form 8329", "Form 990-AR", "Publ 4210", "Form 990 (Schedule I-1)", "Inst 706-A", "Form 13614-C (CN-S)", "Publ 4492 (SP)", "Form 1040 (Schedule 1)", "Form 8963", "Form 1040-C", "Form 1099-F", "Inst 1120-F (Schedule P)", "Inst 3800", "Publ 5296", "Form 8453-I", "Form 4848", "Form 1099-MISC", "Inst 1040-A (Schedule 2)", "Form 8955-SSA", "Publ 3", "Publ 4594", "Form 8813", "Form 2440", "Form 943-A", "Form 8903", "Form 5500 (Schedule A)", "Publ 1 (PL)", "Form 1040-A (Schedule 2)", "Form 1115", "Inst 943 (PR)", "Form 965-B", "Inst 8962", "Inst 944-X", "Inst 8960", "Form 4136", "Publ 1345", "Form 8283-V", "Inst 1099-PATR", "Inst 5884", "Form 1041-S", "Form 1041-T", "Form 13614-C (TL)", "Inst 8038-T", "Inst 990 (Schedule A)", "Inst W-2", "Publ 1544 (SP)", "Form FinCEN101A", "Inst 941 (PR) (Schedule B)", "Form 5305-A-SEP", "Form 8880", "Form 940 (Schedule R)", "Form 1040 (Schedule F)", "Inst 2441", "Inst 8902", "Publ 526", "Inst 1120 (Schedule PH)", "Form 1120-PC (Schedule M-3)", "Form 8833", "Form 5300", "Notc 1437", "Inst 8845", "Form 8308", "Form 8825", "Inst 941 (PR)", "Form 990 or 990-EZ (Sch L)", "Form 1040 (Schedule 2) (SP)", "Form 1041-N", "Publ 536", "Publ 590", "Form 8879", "Form FinCEN109", "Form 5227", "Notc 1382", "Form 1138", "Form 1122", "Form 9452", "Form 8849 (Schedule 6)", "Form 7202 (SP)", "Form 1040 (Schedule 5)", "Publ 1 (AR)", "Form 8915-D", "Form 1120-F (Schedule S)", "Inst 1120-SF", "Inst 1042", "Inst 6765", "Inst 5500 (Schedule P)", "Form 8912", "Inst 8959", "Form FinCEN103", "Form 8849", "Form 1120-F", "Inst 3921 & 3922", "Form 1065-X", "Form 1040-F", "Form 1310", "Inst 8886-T", "Form 1120-F Schedules M-1, M-2", "Form 4466", "Publ 17 (VIE)", "Inst 5310", "Publ 587", "Inst T (Timber)", "Form 8453-B", "Form 5452", "Inst 1116", "Form 4219", "Inst SS-4", "Inst 8810", "Inst 1040 (Schedule LEP)", "Inst 1098", "Inst 8937", "Inst 1099-Q", "Form 3922", "Form 461", "Form 6627", "Publ 1 (GUJ)", "Inst 1139", "Inst 3921 and 3922", "Publ 54", "Form 8879-F", "Form 1040-ES (SP)", "Form 1126", "Form 1120 (Schedule G)", "Form 1363", "Form 6069", "Inst 8966", "Inst 56", "Form 8734", "Form 940", "Form 8865 (Schedule K-2)", "Form 8816", "Inst 8995", "Inst 8809-I", "Inst 8802", "Form 8884", "Inst 5735", "Form 8811", "Inst 8903", "Inst 1099-K", "Form 5498-MSA", "Form 8453-R", "Publ 1", "Form 8453-OL (SP)", "Form 1040-NR (Schedule A)", "Publ 590-B", "Form 2106-EZ", "Inst 8938", "Inst 1120-RIC", "Inst 3115", "Inst 990 (Schedule F)", "Publ 463-SUPP", "Form 8868", "Publ 550", "Form 990 or 990-EZ (Sch N-1)", "Inst 1040 (Schedule 8812) (SP)", "Form 1040 (Schedule EIC)", "Form 1040 (Schedule C-EZ)", "Form 706-D", "Publ 1 (PT)", "Inst 1040 (Schedule A)", "Form 8865 (Schedule P)", "Form 5499", "Form 5500 (Schedule MB)", "Form 1097-BTC", "Form 5471 (Schedule N)", "Form 8809-I", "Form 8866", "Form 8940", "Form 990 (Schedule J-1)", "Form 706-GS(T)", "Inst 990 (Schedule D)", "Form 1040 (Schedule LEP)", "Form 1120-IC-DISC (Schedule Q)", "Form 4876-A", "Inst 8908", "Form 5471", "Inst 1040 (Schedule A&B)", "Form 965 (Schedule E)", "Form 5884-A", "Publ 17", "Form 990 (Schedule R-1)", "Form 8951", "Inst 1120-H", "Form W-4S", "Form 13614-C (CN-T)", "Inst 944", "Publ 1304", "Form W-2C", "Publ 6961-A", "Form SS-4", "Form 928", "Inst 2210-F", "Form 1098-C", "Inst 8038", "Inst 1040 (Schedule B)", "Inst 8881", "Form 990 (Schedule F-1)", "Inst 1023-EZ", "Form 4790", "Inst 8935", "Form 8857 (SP)", "Form 8038-T", "Inst 8900", "Form 990 (Schedule I)", "Form 1041-QFT", "Publ 15", "Inst 8911", "Form 5713 (Schedule C)", "Form 1040-B (FY)", "Publ 590-A", "Publ 1 (KO)", "Form 945", "Form 8904", "Form 970", "Form 8990", "Form 8801", "Form 8596", "Notc 1015", "Form 8864", "Form 4972", "Form 6252", "Inst 8390", "Form 1128", "Inst 8971", "Form 1099-SB", "Publ 4505", "Form 4070-A", "Form 1040-A (Schedule 3)", "Form 1120-L (SChedule D)", "Form 990-T (Schedule M)", "Inst 8993", "Publ 907", "Inst 926", "Form 990 or 990-EZ (Sch C)", "Form 5500 (Schedule E)", "Form W-11 (SP)", "Notc 1373", "Inst 1099-MSA and 5498MSA", "Form 1040 (Schedule 2)", "Inst 1040", "Inst 8936", "Form 8944", "Inst 7004", "Inst 1040 (PR) (Anexo H-PR)", "Publ 4810", "Form 965 (Schedule B)", "Form 5754", "Form W-4P", "Publ 584 (SP)", "Publ 850 (EN-SP)", "Inst 1120-IC-DISC", "Inst 1099-INT and 1099OID", "Publ 55-B", "Inst 1098-Q", "Form 2441", "Form 1120 (Schedule D)", "Form 8926", "Form 1041-A", "Form 1120-F (Schedule M-3)", "Notc 1036", "Inst 1120-F (Schedule H)", "Publ 4492-B", "Form W-2VI", "Inst 1098-C", "Form 5310", "Form 8453-S", "Form 8865 (Schedule O)", "Form 990 (Schedule H)", "Publ 579 (SP)", "Form 5307", "Form 8508", "Publ 972", "Publ 534", "Form 943-A (PR)", "Form 1041 (Schedule D)", "Form 5500 (Schedule I)", "Form SS-8 (PR)", "Inst 4684", "Form 8931", "Form 1116", "Form W-3", "Form 8854", "Inst 8853", "Form 8453-P", "Form 1120-S (Schedule D)", "Form 1098-T", "Inst 1099-SA and 5498-SA", "Inst 8841", "Form 8973", "Publ 925", "Form 5305-S", "Inst 1099-G", "Publ 917", "Inst 8857 (SP)", "Form 1065 (Schedule K-2)", "Form 5500-C/R", "Form W-2G", "Form 5305-E", "Inst 4562-FY", "Inst 1099-A and 1099C", "Form 1041-V", "Form 3903-F", "Form 1040 (Schedule 3)", "Form W-2GU", "Form 1094-B", "Form 6198", "Publ 5530", "Form 8910", "Form 8453-F", "Form 8611", "Form 851", "Form 2555-EZ", "Publ 535", "Inst 1120-W", "Form 8822", "Form 1042-F", "Form 5471 (Schedule O)", "Inst 2848", "Form 7202", "Inst 8912", "Inst 8955-SSA", "Form 1040 (SP)", "Form 5305-SA", "Form 8862", "Form 1120-F (Schedule V)", "Form 1120-C", "Form 2220", "Inst 8275-R", "Inst 8909", "Inst 8233", "Form 8915-C", "Form 2120", "Form 8865 (Schedule K-3)", "Inst 8921", "Publ 1223", "Form 1040 (PR) (Anexo H-PR)", "Form 11-C", "Inst 706-NA", "Form 990 (Schedule O)", "Form 8879-EX", "Form 1040-NR", "Publ 527", "Form 1066", "Form 2688", "Form 941 (PR)", "Form 1040 (Schedule A&B)", "Form 8870", "Form 8840", "Form 8995-A", "Inst 1024", "Form 7200", "Form 1118 (Schedule J)", "Form 1099-CAP", "Form 1099-DIV", "Form 965-D", "Inst 1120-F (Schedule I)", "Form 9325", "Inst W-2G and 5754", "Form 8027", "Publ 4205", "Inst 8950", "Form 1120 (Schedule O)", "Inst 8898", "Form 1065", "Publ 1045", "Inst 1120-F (Schedule M-3)", "Form 1120-H-FY", "Publ 3744", "Form 1040-EZ-I", "Inst 4562", "Inst 8857", "Publ 5223", "Form 1040 (Schedule M)", "Form 8949", "Form 943 (PR)", "Form 1042", "Publ 954", "Inst 1099-A and 1099-C", "Publ 5316", "Form 13614-C (PL)", "Form 1120 (Schedule UTP)", "Inst 8804, 8805 and 8813", "Form 8693", "Form 8888", "Inst 1040-B", "Form 5500-R", "Form 944 (PR)", "Form 8869", "Form SS-4 (PR)", "Form 8873", "Form 8027-T", "Form 8879-C", "Inst 1065 (Schedule B-2)", "Publ 509", "Inst 8996", "Form 8879-B", "Form 982", "Form 706 (Schedule R-1)", "Form 941 (Schedule D)", "Form 5498", "Publ 1 (JA)", "Form 1066 (Schedule Q)", "Form 1065 (Schedule D)", "Form 8453-EMP", "Form 8812", "Form 8878 (SP)", "Form 1000", "Form 976", "Form 8932", "Form 4029", "Form 8965", "Form 2848", "Form 1040 (Schedule 4)", "Inst 1045", "Form 2063", "Form 8832", "Publ 600", "Form 1120-IC-DISC", "Form 1120-F (Schedule I)", "Form 943-X", "Inst 1120-FSC (Schedule P)", "Publ 5108", "Inst SS-8 (PR)", "Form 4684", "Inst 8038-B", "Form 1024-A", "Form 8849 (Schedule 5)", "Form 990 (Schedule F)", "Publ 6186-A", "Form 843", "Form 1120-W (FY)", "Publ 1239", "Form 965 (Schedule F)", "Form 8887", "Form 5305-C", "Inst 5884-D", "Form 1040-ES (PR)", "Form 941 (PR) (Schedule B)", "Form 8805", "Form 1118 (Schedule I)", "Form 8082", "Form 5498-QA", "Form 2106", "Form 1041 (Schedule D-1)", "Form 5500 (Schedule F)", "Publ 1 (BN)", "Form 5308", "Form 8453-NR", "Form 965 (Schedule G)", "Publ 969", "Inst 990 (Schedule R)", "Publ 508", "Form 4070", "Publ 1244", "Form 8609-A", "Form 965 (Schedule D)", "Form 5306", "Publ 560", "Inst 1065 (Schedule M-3)", "Publ 5258", "Form W-3C (PR)", "Inst 706-GS(D-1)", "Form 1040 (Schedule D-1)", "Form 4768", "Form CT-2", "Form 8865 (Schedule G)", "Publ 5136", "Form 990 (Schedule R)", "Form 8915-A", "Publ 5337", "Form 6088", "Form 1099-ASC", "Inst 990-C", "Inst 1120-L", "Form 5405", "Form 8846", "Inst 8973", "Inst 1041-N", "Form 8883", "Publ 919", "Inst 1040 (Schedule C/C-EZ)", "Form 1065-B (Schedule K-1)", "Form 8916", "Form 8894", "Inst 1040 (Schedule E)", "Inst 965-A", "Inst 8849", "Publ 5354", "Inst 8379", "Publ 531", "Inst 709", "Publ 584-B", "Publ 4344", "Inst 8915-C", "Inst 4255", "Inst 8844", "Inst 1040 (Schedule R)", "Form 8845", "Publ 529", "Inst 8952", "Form 8997", "Publ 554", "Form 8703", "Form 1099-K", "Form 943-X (PR)", "Publ 547", "Form 8817", "Inst 8889", "Form 8889", "Inst 1065-B", "Inst 1042-S", "Inst 2106", "Form 965 (Schedule A)", "Form 965", "Form 941 (Schedule R)", "Inst 8697", "Form 990 or 990-EZ (Sch N)", "Form 990 (Schedule J-2)", "Inst 8965", "Form 8857", "Form 8915", "Form 2220 (Schedule W)", "Inst 8974", "Form 8841", "Form 4461-A", "Form 1120-L", "Publ 4492", "Inst 1120-ND", "Publ 583", "Form 1040 (Schedule 6)", "Form 1098-MA", "Form 1120-A", "Inst 1128", "Form 8823", "Inst 1040-A (Schedule 3)", "Form 8809-EX", "Inst 8963", "Form 8328", "Form 1040 (Schedule 8812) (SP)", "Form 8879-S", "Inst 5500-EZ", "Inst 3520-A", "Form 1065 (Schedule B-2)", "Form 4831", "Publ 5384", "Publ 1457", "Inst 1118", "Inst 2290 (FR)", "Inst 3468", "Inst 1040 (PR) (Sch H-PR)", "Form 944", "Form 8871", "Form 1099-BCD", "Inst W-12", "Form 8895", "Inst 2553", "Form 5884", "Inst CT-1", "Form 965-E", "Form 1024", "Inst 1099-MISC and 1099-NEC", "Inst 5500-C/R", "Form 5768", "Publ 593", "Inst 1040 (Schedule SE)", "Form FinCEN107", "Form 8993", "Form 8609", "Form 706-A", "Inst 5310-A", "Form 8917", "Inst 965", "Publ 3991", "Form 8898", "Inst 8915", "Form 5329", "Form 720-TO", "Publ 957", "Form 8404", "Publ 1 (KM)", "Form 1120-H", "Form 1120 (Schedule EP) FY", "Publ 1 (UR)", "Form 1040 (Schedule B)", "Inst 8907", "Form 8274", "Form 8905", "Form 1041-ES", "Publ 225", "Form 990 (Schedule A)", "Inst 8985", "Form 990-A (SF)", "Publ 520", "Publ 850 (EN-KR)", "Form 990-P (Schedule A)", "Form SS-8", "Form 952", "Publ 515", "Inst 8986", "Form CT-1", "Form 1120-SF", "Form 942", "Inst 941-SS", "Inst 8862", "Inst 941 (Schedule D)", "Form 1127", "Form SS-16", "Inst 1040 (PR)", "Publ 4436", "Form 8849 (Schedule 3)", "Form 1099-G", "Publ 5313", "Form 8160-T", "Inst 8038-CP", "Form 4625", "Publ 1 (IT)", "Form 941-X (PR)", "Inst 2848 (SP)", "Form 1040", "Publ 6292", "Form 1120-ND", "Publ 4492-A", "Form 5471 (Schedule I-1)", "Inst 3903", "Form 8615", "Form 8827", "Form 1041 (Schedule K-1)", "Inst 1120-FSC", "Form 5305-R", "Inst 1120 (Schedule D)", "Inst 4768", "Form 8844", "Form 8923", "Form 8878", "Inst 1120-L (Schedule M-3)", "Notc 609", "Inst 1120-C", "Form 8300 (SP)", "Form 990-C", "Form 8806", "Inst 1120 (Schedule EP)", "Form 8879 (SP)", "Inst 8804-C", "Publ 926", "Inst 943-A (PR)", "Form 1120-F (Schedule H)", "Inst 4626", "Inst 1099-H", "Inst 1040 (Schedule F)", "Publ 1500", "Inst 7202", "Publ 516", "Publ 6961", "Form 9465-FS (SP)", "Inst 8904", "Inst 8656", "Form 965 (Schedule C)", "Form 1040-NR (Schedule OI)", "Inst 9465 (SP)", "Form CT-1X", "Form 990-T (Schedule A)", "Form 8886-T", "Inst 1040-C", "Form 1099-PATR", "Inst 5307", "Inst 1040 (Schedule 8812)", "Form 8892", "Form 8038", "Form 944-X (SP)", "Inst 4868", "Inst 2290 (SP)", "Notc 609 (SP)", "Form 8264", "Form 1040-A (Schedule 1)", "Form 1041", "Form 5500 (Schedule G)", "Form 8023", "Form W-12", "Form 1040-EZ", "Publ 1179", "Inst 1099-QA and 5498-QA", "Form 8594", "Inst 8821", "Form 1040 (Schedule D Supp.)", "Publ 15-T", "Form 4835", "Form 8994", "Form 5498-SA", "Inst 9465", "Form 8621-A", "Form 8979", "Publ 557", "Form 1040-SS", "Inst 1099-R and 5498", "Publ 721", "Form 5074", "Form 8038-GC", "Publ 929", "Form 1099-Q", "Form 941 (Schedule B)", "Inst 1094-C and 1095-C", "Inst 944 (SP)", "Form 990 (Schedule J)", "Form W-4", "Form 990 or 990-EZ (Sch A)", "Inst 1065 (Schedule D)", "Publ 1 (CN-T)", "Publ 1220", "Form FinCEN105", "Form 1099-C", "Inst 1065 (Schedule K-1)", "Form 8918", "Inst 5300", "Form 4810", "Form 8991", "Inst 2290", "Inst 1040-X", "Inst 8829", "Form 8815", "Form 706", "Form TD F 90-22.1", "Publ 517", "Publ 976", "Form 5505", "Publ 1 (FA)", "Publ 5338", "Form 8330", "Publ 4961", "Form 13614-C (PT)", "Form 1040-A", "Form 8332", "Inst 8862 (SP)", "Form 6744", "Inst 1040 (SP)", "Form 1099-INT", "Publ 5084", "Publ 6187-A", "Form 8855", "Form 8038-CP", "Publ 1 (FR)", "Form 8596-A", "Form 990", "Form 8886", "Form 926", "Publ 4012", "Form 8901", "Publ 564", "Inst 706-QDT", "Form 6118", "Form 8925", "Form 8390", "Inst 8264", "Form 720", "Inst W-3 (PR)", "Inst 1120-PC", "Publ 17 (KO)", "Publ 334", "Form 3520-A", "Publ 544", "Form 1065 (Schedule D-1)", "Inst 6251", "Form 1120-S (Schedule K-2)", "Publ 547 (SP)", "Inst 8990", "Form 8862 (SP)", "Form 8914", "Form 4562-FY", "Form 5735 (Schedule P)", "Form 673", "Form 1120-F (Schedule P)", "Inst 4720", "Form 5500 (Schedule D)", "Inst 1118 (Schedule K)", "Inst 8933", "Publ 918", "Inst 943-X (PR)", "Form 8803", "Inst 1099-SB", "Publ 4473", "Inst 8835", "Inst 1024-A", "Form 8038-G", "Inst 1120-F", "Form 8865", "Publ 17 (RU)", "Inst 1040 (Schedule M)", "Form 5471 (Schedule E)", "Form 8453-X", "Form 5713 (Schedule B)", "Publ 570", "Inst 1099-LS", "Form 1099-LTC", "Form 8822-B", "Inst 1041 (Schedule I)", "Inst 8995-A", "Form 13614-C (AR)", "Form 8038-B", "Inst 4952", "Publ 6187", "Inst 2210", "Inst 1099-CAP", "Form 8697", "Inst 8871", "Inst 982", "Form 2350", "Inst 8582-CR", "Form 1099-MSA", "Form 8906", "Form 1101", "Form 1040-X", "Form 8896", "Publ TD CIR 230", "Inst 4136", "Publ 514", "Publ 598", "Form 1040-V", "Inst 8886", "Inst 1099-B", "Form 945-A", "Publ 1546", "Form 8453-C", "Publ 5241", "Form 8847", "Form 1120 (Schedule M-3)", "Form 13614-C (SP)", "Form 8612", "Publ 3402", "Inst 8082", "Inst 8866", "Form 1040-ES (NR)", "Publ 521", "Inst 8994", "Form 8610 (Schedule A)", "Form 8891", "Inst 8865", "Form 1023-EZ", "Form 5500 (Schedule SB)", "Inst 1120", "Form 8814", "Inst W-2C and W-3C", "Form 4506T-EZ (SP)", "Form 4849", "Form 5500 (Schedule B)", "Form 990, 990EZ, 990-PF (Sch B)", "Inst 8992", "Form 5305-A", "Form 5472", "Inst 1040-NR-EZ", "Form 5500 (Schedule T)", "Form 8453 (SP)", "Inst 8885", "Form 3800", "Inst 945", "Publ 80", "Inst 1040 (Schedule D)", "Form 8804-C", "Form 8924", "Form 944-X (PR)", "Form 2555", "Form 1120 (Schedule EP)", "Form 8843", "Inst 1023", "Form 2210-F", "Publ 463", "Publ 5500", "Form 990 (Schedule K)", "Form 8867", "Form 1099-S", "Form 8849 (Schedule 2)", "Form 7004", "Inst 3520", "Form 1120 (Schedule PS)", "Form 8283", "Form 8821 (SP)", "Form 8826", "Inst 944-SS", "Inst W-2 and W-3", "Form 965-A", "Form 56", "Inst 1065-B (Schedule K-1)", "Publ 946-SUPP", "Publ 551", "Form 8821", "Form 5305-RB", "Inst 8621", "Form 8725", "Form 1120 (Schedule FY)", "Form 1120-F (Schedule Q)", "Form 8829", "Form 8610", "Publ 1494", "Inst 5329", "Publ 525", "Form 8874-B", "Form 6478", "Publ 972 (sp)", "Publ 553", "Form 707", "Form 8453-EX"]

test_list = random.choices(test_list, k=10)

if __name__ == '__main__':
    print(len(test_list))

    scraper = TaxFormsScraper()

    start = time.perf_counter()
    print(scraper.search_forms(['form w-2']))
    # scraper.save_json(test_list)
    # scraper.download_forms('form w-3', 1800, 1800)
    print(time.perf_counter() - start)
