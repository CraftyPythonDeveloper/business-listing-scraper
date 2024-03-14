import scrapy
from urllib.parse import quote, urlparse, parse_qs, unquote
import json
from business_scrapers.utils import get_random_headers


class BrownbookSpider(scrapy.Spider):
    name = 'brownbook'
    allowed_domains = ['brownbook.net']

    def __init__(self, keywords: str, location: str, *args, **kwargs) -> None:
        super(BrownbookSpider, self).__init__(*args, **kwargs)
        self.keywords = [quote(keyword.strip()) for keyword in keywords.strip().split(",,")]
        self.locations = [quote(loc.strip()) for loc in location.strip().split(",,")]
        self.base_url = "https://www.brownbook.net/search/worldwide/{location}/{keyword}/?page={page}"
        self.api = "https://api.brownbook.net/app/api/v1/business/{business_id}/fetch"

    def start_requests(self, *args, **kwargs) -> None:
        # https://www.brownbook.net/search/worldwide/New%20York/art%20gallery/?page=1
        for keyword, location in zip(self.keywords, self.locations):
            url = self.base_url.format(location=location, keyword=keyword, page=1)
            yield scrapy.Request(url, callback=self.parse, meta={'keyword': keyword, 'location': location},
                                 headers=get_random_headers())

    @staticmethod
    def convert_bool(num):
        if str(num) == "1":
            return "Yes"
        elif str(num) == "0":
            return "No"
        else:
            return ""

    def parse(self, response, *args, **kwargs):
        keyword = response.meta.get("keyword")
        location = response.meta.get("location")
        for url in response.xpath("//a[@aria-label='business-link']/@href").getall():
            try:
                business_id = url.split("/")[2]
                yield scrapy.Request(self.api.format(business_id=business_id), callback=self.parse_business_data,
                                     meta={"business_url": url, "response_url": response.url, "keyword": keyword,
                                           "location": location}, headers=get_random_headers())
            except IndexError:
                print("No business id found..")
                continue

        next_page_url = response.css('#nav-right-arrow').get()
        if next_page_url:
            parsed_url = urlparse(response.url)
            query_params = parse_qs(parsed_url.query)
            page_number = query_params.get('page', [None])[0]
            if page_number:
                url = self.base_url.format(location=location, keyword=keyword,
                                           page=int(page_number) + 1)
                yield scrapy.Request(url, callback=self.parse, meta={'keyword': keyword, 'location': location},
                                     headers=get_random_headers())

    def parse_business_data(self, response, *args, **kwargs):
        business_data = json.loads(response.text)
        if business_data["message"] != "Business has been retrieved":
            return
        business_data = business_data["data"]["metadata"]
        data = dict()
        data["Business Id"] = business_data.get("id")
        data["Business Category"] = unquote(response.meta.get("keyword", ""))
        data["Business Name"] = business_data.get("name")
        data["Contact Name"] = business_data["user"].get("name")
        data["Contact Email"] = business_data["user"].get("email")
        data["Business Email"] = business_data.get("email")
        data["Phone"] = business_data.get("phone", "")
        data["Mobile"] = business_data.get("mobile", "")
        data["Website"] = business_data.get("website", "")
        data["Address"] = business_data.get("address", "")
        data["City"] = business_data.get("city", "")
        data["Zip Code"] = business_data.get("zipcode", "")
        data["Claimed"] = self.convert_bool(business_data.get("claimed", ""))
        data["Claim Verified"] = self.convert_bool(business_data.get("claim_verified", ""))
        data["Country"] = business_data.get("country_code", "")
        data["Facebook"] = business_data.get("facebook", "")
        data["Instagram"] = business_data.get("instagram", "")
        data["Linkedin"] = business_data.get("linkedin", "")
        data["Tiktok"] = business_data.get("tiktok", "")
        data["Twitter"] = business_data.get("twitter", "")
        data["URL"] = response.meta.get("business_url", "")
        yield data
