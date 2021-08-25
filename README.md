# Tax Forms Scraper

Taking a list of tax form names (ex: "Form W-2", "Form 1095-C"), search the
website and returns the information about years range for each particular form,
or downloads forms in PDF-format.

## Tech

- Python v3.8.2
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

Returns a list of tax form names with years ranges:
- **search_forms** - returns json with the information:


```sh
scraper.search_forms(["Form 4563", "Form 8911", "Publ 1693"])
```

returns:

```sh
[
    {
        "form_number": "Form 4563",
        "form_title": "Exclusion of Income for Bona Fide Residents of American Samoa",
        "min_year": 1969,
        "max_year": 2019
    },
    {
        "form_number": "Form 8911",
        "form_title": "Alternative Fuel Vehicle Refueling Property Credit",
        "min_year": 2005,
        "max_year": 2021
    },
    {
        "form_number": "Publ 1693",
        "form_title": "SSA/IRS Reporter Newsletter",
        "min_year": 2003,
        "max_year": 2016
    }
]

```

- **save_json** - saves json with the information to the file "forms.json" to a directory under your script's
main directory:

```sh
scraper.save_json(["Form 4563", "Form 8911", "Publ 1693"])
```

Download particular form for a particular period of years to a specified subdirectory under your script's
main directory:
- **download_forms**:

```sh
scraper.download_forms('form name', 2018, 2021)
```
