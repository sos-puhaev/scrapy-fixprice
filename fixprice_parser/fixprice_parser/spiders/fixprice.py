import scrapy
import time
import random
from urllib.parse import urljoin
from fixprice_parser.items import ProductItem
from scrapy_playwright.page import PageMethod

class ProductsSpider(scrapy.Spider):
    name = 'products'
    allowed_domains = ['fix-price.com']
    custom_settings = {
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 180000,
        'DOWNLOAD_DELAY': random.uniform(3, 7),
        'CONCURRENT_REQUESTS': 1,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 180000,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-extensions',
                '--disable-popup-blocking',
                '--disable-notifications',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                f'--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(100, 115)}.0.0.0 Safari/537.36'
            ],
        },
        'PLAYWRIGHT_CONTEXTS': {
            'default': {
                'viewport': {'width': 1920, 'height': 1080},
                'ignore_https_errors': True,
                'java_script_enabled': True,
                'locale': 'ru-RU',
                'timezone_id': 'Europe/Moscow',
            }
        }
    }

    def start_requests(self):
        urls = [
            'https://fix-price.com/catalog/kosmetika-i-gigiena/ukhod-za-polostyu-rta',
        ]
        for url in urls:
            yield scrapy.Request(
                url,
                cookies={'selectedCity': 'Екатеринбург'},
                callback=self.parse_category,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle', timeout=180000),
                        PageMethod('evaluate', '''() => {
                            window.scrollBy(0, 500);
                            return true;
                        }'''),
                        PageMethod('wait_for_timeout', random.randint(2000, 5000)),
                    ],
                    'playwright_context': 'default',
                }
            )

    async def parse_category(self, response):
        page = response.meta['playwright_page']
        
        try:
            product_data = await page.evaluate('''() => {
                const items = [];
                document.querySelectorAll('div.product-card').forEach(card => {
                    const link = card.querySelector('a.product-card__link');
                    if (link) {
                        items.push({
                            url: link.href,
                            title: card.querySelector('.product-card__title')?.innerText,
                            price: card.querySelector('.product-card__price')?.innerText
                        });
                    }
                });
                return items;
            }''')

            if not product_data:
                self.logger.warning(f"No products found at {response.url}")
                await page.screenshot(path='debug_no_products.png', full_page=True)
                return

            for product in product_data:
                item = ProductItem()
                item['url'] = urljoin(response.url, product['url'])
                item['title'] = product['title'].strip() if product['title'] else ''
                item['price_data'] = {
                    'current': float(product['price'].replace(' ', '')) if product['price'] else 0.0,
                    'original': 0.0,
                    'sale_tag': ''
                }
                yield item

                await page.wait_for_timeout(random.randint(1000, 3000))

            has_next_page = await page.evaluate('''() => {
                const nextBtn = document.querySelector('a.pagination__item--arrow_right');
                if (nextBtn) {
                    nextBtn.scrollIntoView();
                    return true;
                }
                return false;
            }''')
            
            if has_next_page:
                next_page_url = await page.evaluate('''() => {
                    return document.querySelector('a.pagination__item--arrow_right').href;
                }''')
                
                if next_page_url:
                    yield scrapy.Request(
                        urljoin(response.url, next_page_url),
                        callback=self.parse_category,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_methods': [
                                PageMethod('wait_for_load_state', 'networkidle', timeout=180000),
                            ],
                        }
                    )
        except Exception as e:
            self.logger.error(f"Error parsing category: {str(e)}")
            await page.screenshot(path='error_screenshot.png', full_page=True)
        finally:
            await page.close()

    async def parse_product(self, response):
        pass