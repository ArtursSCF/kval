from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import re
import time

driver_path = Service("C:\chromedriver-win64\chromedriver-win64\chromedriver.exe")
driver = webdriver.Chrome(service=driver_path)

try:
    url = 'https://www.rimi.lv/e-veikals'
    driver.get(url)

    # Gaida lai 'category-menu' būtu ielādējies
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'category-menu'))
    )

    # Atrod visus "div", kam ir 'category-menu', lai rasmotu produktu kategoriju "href"
    category_divs = driver.find_elements(By.CLASS_NAME, 'category-menu')

    category_links = []
    for category_div in category_divs:
        buttons = category_div.find_elements(By.XPATH, './/button[@role="menuitem"]')

        for button in buttons:
            href = button.get_attribute('href')
            if href:
                full_url = f"https://www.rimi.lv{href}"
                category_links.append(full_url)

    # Seko līdzi apstrādātiem URL, lai izvairītos no dublikātiem
    processed_products = set()

    def scrape_page(page_url):
        try:
            driver.get(page_url)
            time.sleep(2)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'product-grid'))
            )

            # Rasmo produktu "href" linku daļas
            product_elements = driver.find_elements(By.CSS_SELECTOR, '.card__url.js-gtm-eec-product-click')
            page_products = []
            for product in product_elements:
                product_href = product.get_attribute('href')
                if product_href and product_href not in processed_products:
                    processed_products.add(product_href)
                    page_products.append(product_href)
            return page_products
        except Exception as e:
            print(f"Error processing page {page_url}: {str(e)}")
            return []

    def scrape_product_details(product_url):
        """Scrapes details from a product page."""
        try:
            driver.get(product_url)
            time.sleep(2)

            # Gaida, lai produktu detaļu elementi ielādētos
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'product__main'))
            )

            product_name = driver.find_element(By.CSS_SELECTOR, 'h1.name').text

            product_container = driver.find_element(By.CLASS_NAME, 'product__main')
            product_code = product_container.get_attribute('data-product-code')

            # Cena ir sadalīta atsevišķos HTML tagos, tāpēc atlasa visus un veic konkatenāciju
            price = None
            try:
                price_whole = driver.find_element(By.CSS_SELECTOR, '.price-wrapper .price span').text
                price_fraction = driver.find_element(By.CSS_SELECTOR, '.price-wrapper .price div sup').text
                price_unit = driver.find_element(By.CSS_SELECTOR, '.price-wrapper .price div sub').text.strip()
                price = f"{price_whole}.{price_fraction} {price_unit}"
            except:
                pass

            deal_notice = None
            try:
                deal_notice = driver.find_element(By.CLASS_NAME, 'notice').text
            except:
                pass

            old_price = None
            try:
                old_price = driver.find_element(By.CLASS_NAME, 'price__old-price').text
            except:
                pass

            price_per = None
            try:
                price_per = driver.find_element(By.CLASS_NAME, 'price-per').text
            except:
                pass

            discount_info = None
            try:
                # Gadījumi, kad ir atlaide pērkot > 1
                discount_info = driver.find_element(By.CLASS_NAME, 'price-label__text').text
            except:
                try:
                    # Gadījumi, kad ir atlaide izmantojot rimi karti
                    card_deal = driver.find_element(By.CSS_SELECTOR, '.price-label__body img')
                    discount_info = 'Rimi karte'  # Set this as the value if the 'rimi_card' exists
                except:
                    # Pārējie gadījumi
                    pass

            discount_percentage = None
            try:
                discount_percentage = driver.find_element(By.CLASS_NAME, 'price-label__header').text
            except:
                pass
            
            # Atlaižu cena ir sadalīta atsevišķos HTML tagos, tāpēc atlasa visus un veic konkatenāciju
            discount_price = None
            try:
                major = driver.find_element(By.CLASS_NAME, 'major').text
                minor_container = driver.find_element(By.CLASS_NAME, 'minor')
                cents = minor_container.find_element(By.CLASS_NAME, 'cents').text
                currency = minor_container.find_element(By.CLASS_NAME, 'currency').text

                discount_price = f"{major}.{cents} {currency}"
            except:
                pass

            discount_price_per = None
            try:
                discount_price_per = driver.find_element(By.CLASS_NAME, 'price-per-unit').text
            except:
                pass

            # Produkti kam ir "Iespējams zemākā cena!" zīme
            lowest_price = None
            try:
                badge = driver.find_element(By.CSS_SELECTOR, '.type-badge.-position-top-right')
                lowest_price_image = badge.find_element(By.CSS_SELECTOR, 'picture img')
                lowest_price = lowest_price_image.get_attribute('src')
            except:
                pass

            image_url = None
            try:
                product_image = driver.find_element(By.CSS_SELECTOR, '.product__main-image img')
                image_url = product_image.get_attribute('src')
            except:
                pass
            
            # Atrod visus <a> tagus iekš 'section-header__container' klases un nolasa teksta daļu
            category_container = driver.find_element(By.CLASS_NAME, 'section-header__container')
            categories = category_container.find_elements(By.TAG_NAME, 'a')
            category_texts = [category.text.strip() for category in categories]

            # Piešķir kategoriju tekstu attiecīgiem mainīgajiem, rēķinoties uz trīs
            category = category_texts[0] if len(category_texts) > 0 else None
            category2 = category_texts[1] if len(category_texts) > 1 else None
            category3 = category_texts[2] if len(category_texts) > 2 else None

            return {
                'url': product_url,
                'name': product_name,
                'product code': product_code,
                'price': price,
                'deal notice': deal_notice,
                'old price': old_price,
                'price per': price_per,
                'discount info': discount_info,
                'discount percentage': discount_percentage,
                'discount price': discount_price,
                'discount price per': discount_price_per,
                'lowest price': lowest_price,
                'image': image_url,
                'category': category,
                'category2': category2,
                'category3': category3,
            }
        except Exception as e:
            print(f"Error processing product {product_url}: {str(e)}")
            return None

    # Visit each category page and extract product links
    for category_url in category_links:
        try:
            print(f"Category: {category_url}")

            driver.get(category_url)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'product-grid'))
            )

            # Atrod kategorijas produktu lapu skaita elementus un nosaka maksimālo skaitu
            pagination_items = driver.find_elements(By.CLASS_NAME, 'pagination__item')
            max_page = 1
            if pagination_items:
                page_numbers = [int(item.text) for item in pagination_items if item.text.isdigit()]
                max_page = max(page_numbers) if page_numbers else 1

            # Atrod skaitli izmantojot regex URL konsturkcijai
            sh_number_match = re.search(r'SH-(\d+)', category_url)
            sh_number = sh_number_match.group(1) if sh_number_match else None

            # Ģenerē lapu URL balstoties uz lapas numura
            page_links = [
                f'{category_url}?currentPage={page_num}&pageSize=20&query=%3Arelevance%3AallCategories%3ASH-{sh_number}%3AassortmentStatus%3AinAssortment'
                for page_num in range(1, max_page + 1)
            ]

            # Apstrādā katru kataloga lapu sekvenciāli, lai caglabātu secību
            for page_num, page_link in enumerate(page_links, start=1):
                print(f"Page {page_num}: {page_link}")
                products = scrape_page(page_link)
                if products:
                    print(f"All the products from Page {page_num}:")
                    for product in products:
                        print(f"Product: {product}")
                        product_details = scrape_product_details(product)
                        if product_details:
                            print("Product details:")
                            print(f"    url: {product_details['url']}")
                            print(f"    name: {product_details['name']}")
                            print(f"    product code: {product_details['product code']}")
                            print(f"    price: {product_details['price']}")
                            print(f"    deal notice: {product_details['deal notice']}")
                            print(f"    old price: {product_details['old price']}")
                            print(f"    discount info: {product_details['discount info']}")
                            print(f"    discount percentage: {product_details['discount percentage']}")
                            print(f"    discount price: {product_details['discount price']}")
                            print(f"    discount price per: {product_details['discount price per']}")
                            print(f"    lowest price: {product_details['lowest price']}")
                            print(f"    image: {product_details['image']}")
                            print(f"    category: {product_details['category']}")
                            print(f"    category2: {product_details['category2']}")
                            print(f"    category3: {product_details['category3']}")
                else:
                    print(f"No products found on Page {page_num}.")

        except Exception as e:
            print(f"Error processing category {category_url}: {str(e)}")
            continue

finally:
    driver.quit()
