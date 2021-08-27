# Tax Forms Scraper

Taking a list of tax form names (ex: "Form W-2", "Form 1095-C"), search the www.irs.gov
website and returns the information about years range for each particular form,
or downloads forms in PDF format.

## Tech

- Python v3.8.2
- BeautifulSoup 4
- asyncio
- aiohttp

## Installation

Create a virtual environment:

```sh
python3 -m venv venv
```

Run the virtual environment:

```sh
source venv/bin/activate
```

Install the dependencies.
```sh
pip install -r requirements.txt
```

## Usage

### Under you script's directory type:
- to return a list of tax form names with years ranges (form names must be enclosed in quotes and divided by spaces):

```sh
python main.py search "form 4563" "form 8911" "publ 1693"
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

- to save the information to the file "forms.json" to the directory under your script's
main directory add -f option:

```sh
python main.py search "form 4563" "form 8911" "publ 1693" -f
```

- to download a particular form for a 2001-2015 years period to "forms/" subdirectory:


```sh
python main.py download "form w-2" 2001 2015
```
