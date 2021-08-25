# Tax Forms Scraper

Scraps www.irs.gov for information about years range for particular form,
or downloads forms in PDF-format.

## Tech

- Python v3.8
- BeautifulSoup 4
- asyncio
- aiohttp

## Installation

Install the dependencies.
```sh
pip3 install -r requirements.txt
```

## Usage

Create an object:

```sh
scraper = TaxFormScraper()
```

Take a list of tax form names with years ranges:
- **search_forms** - returns json with the information:


```sh
scraper.search_forms(list_of_form_names)
```

- **save_json** - saves json with the information to the file "forms.json" to a directory under your script's
main directory:

```sh
scraper.save_json(list_of_form_names)
```

Download particular form for a particular period of years to a specified subdirectory under your script's
main directory:
- **download_forms**

```sh
scraper.download_forms('form name', 2018, 2021)
```
