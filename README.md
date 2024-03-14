# Business Listing Scraper

### Currently Supported sites are: [Brownbook](https://www.brownbook.net/) <br>

This repo is about scraping data from different business listing websites using **Python**  and **scrapy framework**.
<br><br> This includes below-mentioned features.
* Take keyword and location as input and scrape all the data based on the criteria.
* The scraped data includes columns such as business id, category, name, email, business email, phone, mobile, websites, address, city, zip, claimed status, claim verified, country and social media urls.
* This scraper also supports multiple keywords scraping. You can separate multiple keywords by using seperator as ,,

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Support](#support)
- [Contributing](#contributing)

## Installation

* Make sure python is installed and accessable through terminal/cmd by typing ```python --version``` or ```python3 --version```
* (Optional step) Create virtual environment by following tutorial on [How to install virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
* Clone the repo locally using ```git clone https://github.com/CraftyPythonDeveloper/business-listing-scraper```
* ```cd business_listing_scraper```
* Install requirements ```pip install -r requirements.txt```

## Usage

To run the script follow the below-mentioned steps:

- ```cd business_scrapers```
- Then run the below command to scrape the data. change the keyword and location. If you want to scrape multiple keywords, pass ,, as a seperator. E.g to scrape two keywords art gallery and wall art use keywords="art gallery,, wall art" and location="new york,,new york"
- ``scrapy crawl brownbook -O data.csv -a keywords="art gallery" -a location="new york"``
## Support

- If you face any issue or bug, you can create an issue describing the error message and steps to reproduce the same error, with log file attached.

Please [open an issue](https://github.com/CraftyPythonDeveloper/business-listing-scraper/issues/new) for support.

## Contributing

Please contribute by create a branch, add commits, and [open a pull request](https://github.com/CraftyPythonDeveloper/business-listing-scraper/pulls).
