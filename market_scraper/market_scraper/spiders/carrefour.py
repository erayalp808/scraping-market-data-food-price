import scrapy

from ..items import MarketItem
from datetime import date
import random


class CarrefourSpider(scrapy.Spider):
    name = "carrefour"
    current_date = date.today()
    home_url = "https://www.carrefoursa.com"

    user_agent_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 "
        "Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/14.0.3 Mobile/15E148 Safari/604.1",
        "Mozilla/4.0 (compatible; MSIE 9.0; Windows NT 6.1)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 "
        "Safari/537.36 Edg/87.0.664.75",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 "
        "Safari/537.36 Edge/18.18363",
    ]

    def start_requests(self):
        yield scrapy.Request(
            url=self.home_url,
            meta={
                "playwright": True,
                "playwright_include_page": True
            }
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]

        try:
            await page.wait_for_load_state("domcontentloaded")
            content = await page.content()
            await page.close()

            selector = scrapy.Selector(text=content)
            categories = selector.css("li.main-menu-item")

            for category in categories:
                main_category_name = category.css("a.main-menu-item-link  span:nth-child(2)::text").get().strip()

                sub_categories = category.css("li.main-menu-dropdown-item")

                for sub_category in sub_categories:
                    sub_category_name = sub_category.css("a.main-menu-dropdown-item-link::text").get().strip()
                    sub_category_url = sub_category.css("a.main-menu-dropdown-item-link::attr(href)").get()

                    lowest_categories = sub_category.css("a.main-menu-dropdown-item-sub-link")

                    if len(lowest_categories) >= 1:
                        for lowest_category in lowest_categories:
                            lowest_category_name = lowest_category.css("::text").get().strip()
                            lowest_category_url = lowest_category.attrib["href"]
                            info = {
                                "main_category": main_category_name,
                                "sub_category": sub_category_name,
                                "lowest_category": lowest_category_name
                            }

                            yield scrapy.Request(
                                url=self.home_url + lowest_category_url,
                                callback=self.parse_category_page,
                                meta={
                                    "playwright": True,
                                    "playwright_include_page": True,
                                    "info": info
                                },
                                headers={"User-Agent": random.choice(self.user_agent_list)}
                            )
                    else:
                        info = {
                            "main_category": main_category_name,
                            "sub_category": sub_category_name,
                            "lowest_category": None
                        }

                        yield scrapy.Request(
                            url=self.home_url + sub_category_url,
                            callback=self.parse_category_page,
                            meta={
                                "playwright": True,
                                "playwright_include_page": True,
                                "info": info
                            },
                            headers={"User-Agent": random.choice(self.user_agent_list)}
                        )

            await page.close()
        except Exception as exception:
            print(exception)
            yield scrapy.Request(
                url=response.url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                }
            )

    async def parse_category_page(self, response):
        page = response.meta["playwright_page"]

        try:
            await page.wait_for_load_state("domcontentloaded")
            content = await page.content()
            await page.close()

            selector = scrapy.Selector(text=content)
            product_cards = selector.css("li.product-listing-item .hover-box")

            for product_card in product_cards:
                is_out_of_stock = bool(product_card.css(".oos-cont").get())
                product_name = product_card.css(".item-name::text").get()
                product_price = float(product_card.css("span.item-price").attrib["content"])
                product_price_high = self.parse_price_high(product_card)
                product_link = self.home_url + product_card.css("a::attr(href)").get()

                product = MarketItem(
                    category2=response.meta["info"]["main_category"],
                    category1=response.meta["info"]["sub_category"],
                    category=response.meta["info"]["lowest_category"],
                    prod=product_name,
                    price=product_price,
                    high_price=product_price_high,
                    prod_link=product_link,
                    pages=response.url,
                    in_stock=not is_out_of_stock,
                    date=self.current_date
                )

                yield product

            next_page = self.get_next_page(selector)

            if next_page is not None:
                yield scrapy.Request(
                    url=self.home_url + next_page,
                    callback=self.parse_category_page,
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "info": response.meta["info"]
                    }
                )
        except Exception as exception:
            print(exception)
            yield scrapy.Request(
                url=response.url,
                callback=self.parse_category_page,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "info": response.meta["info"]
                }
            )

    def parse_price_high(self, product_card):
        whole_part = product_card.css("span.priceLineThrough::text").get()

        if whole_part is not None:
            whole_part = whole_part.strip().replace(',', '').replace('.', '')
            cents = product_card.css("span.formatted-price::text").get().strip()
            cents = cents.replace('TL', '').strip()
            price_high = float(whole_part + '.' + cents)

            return price_high
        else:
            return None

    def get_next_page(self, category_page):
        current_page = category_page.css(".pagination-item.active ::text").get()

        if current_page is not None:
            current_page = int(current_page)
            next_pages = category_page.css(".pagination-item ::attr(href)").getall()
            next_pages = next_pages[current_page - 1:]

            if len(next_pages) > 0:
                return next_pages[0]
            else:
                return None
        else:
            return None