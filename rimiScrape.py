from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.chrome.options import Options
from psycopg2.pool import SimpleConnectionPool
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import time
import re

#Logic of saving the scraped data to the database
def save_to_database(product_details):
    #Database pooling for efficient connection for concurrency
    DB_POOL = SimpleConnectionPool(
        minconn=2,
        maxconn=5,
        dbname="postgres",
        user="",            #Provide details
        password="",
        host="localhost",
        port="5432"
    )

    conn = None
    cursor = None

    try:
        conn = DB_POOL.getconn()
        cursor = conn.cursor()

        #Check if scraped product already exists in the database
        cursor.execute(
            "SELECT id, write_date FROM product WHERE url = %s FOR UPDATE", (product_details['url'],)
        )
        result = cursor.fetchone()

        if result:
            product_id = result[0]

            #Moveing existing/previously scraped data to product_history table
            cursor.execute("""
                INSERT INTO product_history (
                    price, price_measure, old_price, old_price_measure,
                    price_per, price_per_measure, discount_price,
                    discount_price_measure, discount_price_per,
                    discount_price_per_measure, discount_percentage,
                    write_date, store_id, product_id, is_active
                )
                SELECT 
                    price, price_measure, old_price, old_price_measure,
                    price_per, price_per_measure, discount_price,
                    discount_price_measure, discount_price_per,
                    discount_price_per_measure, discount_percentage,
                    write_date, store_id, id, is_active
                FROM product
                WHERE id = %s
            """, (product_id,))

            #Update the existing porducts table with new details
            cursor.execute("""
                UPDATE product
                SET 
                    name = %s, product_code = %s, price = %s, price_measure = %s,
                    old_price = %s, old_price_measure = %s, price_per = %s,
                    price_per_measure = %s, discount_price = %s, 
                    discount_price_measure = %s, discount_price_per = %s,
                    discount_price_per_measure = %s, discount_percentage = %s,
                    discount_info = %s, deal_notice = %s, lowest_price = %s,
                    image = %s, category = %s, category2 = %s, category3 = %s, is_active = %s,
                    write_date = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                product_details['name'], product_details['product code'],
                product_details['price'], product_details['price measure'],
                product_details['old price'], product_details['old price measure'],
                product_details['price per'], product_details['price per measure'],
                product_details['discount price'], product_details['discount price measure'],
                product_details['discount price per'], product_details['discount price per measure'],
                product_details['discount percentage'], product_details['discount info'],
                product_details['deal notice'], product_details['lowest price'],
                product_details['image'], product_details['category'], product_details['category2'],
                product_details['category3'], product_details['is active'], product_id
            ))
        else:
            #Insert the new products that had no match into the product table
            cursor.execute("""
                INSERT INTO product (
                    url, name, product_code, price, price_measure,
                    old_price, old_price_measure, price_per, price_per_measure,
                    discount_price, discount_price_measure, discount_price_per,
                    discount_price_per_measure, discount_percentage, discount_info,
                    deal_notice, lowest_price, image, category, category2, category3,
                    is_active, store_id, write_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                product_details['url'], product_details['name'], product_details['product code'],
                product_details['price'], product_details['price measure'],
                product_details['old price'], product_details['old price measure'],
                product_details['price per'], product_details['price per measure'],
                product_details['discount price'], product_details['discount price measure'],
                product_details['discount price per'], product_details['discount price per measure'],
                product_details['discount percentage'], product_details['discount info'],
                product_details['deal notice'], product_details['lowest price'],
                product_details['image'], product_details['category'], product_details['category2'],
                product_details['category3'], product_details['is active'], 1
            ))
        conn.commit()
    except Exception as e:
        print(f"Error saving product to database for URL {product_details['url']}: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            DB_POOL.putconn(conn)

#Chrome settings for faster execution
def create_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service("C:\chromedriver-win64\chromedriver-win64\chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver

#Scrapes product links from a category page (singular page of many pages in a certain category)
#and keepts track of them.
#Returns a list of products found on the page
def scrape_page(driver, page_url, processed_products):
    try:
        driver.get(page_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-grid'))
        )
        product_elements = driver.find_elements(By.CSS_SELECTOR, '.card__url.js-gtm-eec-product-click')
        page_products = []
        for product in product_elements:
            product_href = product.get_attribute('href')
            if product_href and product_href not in processed_products:
                processed_products.add(product_href)
                page_products.append(product_href)
        return page_products
    except TimeoutException:
        print(f"Timeout while loading page: {page_url}")
        return []
    except Exception as e:
        print(f"Error processing page {page_url}: {str(e)}")
        return []

def scrape_product_details(driver, product_url):
    try:
        driver.get(product_url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product__main'))
        )

        product_name = driver.find_element(By.CSS_SELECTOR, 'h1.name').text

        product_container = driver.find_element(By.CLASS_NAME, 'product__main')
        product_code = product_container.get_attribute('data-product-code')

        #Price in HTML structure is split between tags, so we scrape them all
        price, price_measure = None, None
        try:
            price_whole = driver.find_element(By.CSS_SELECTOR, '.price-wrapper .price span').text
            price_fraction = driver.find_element(By.CSS_SELECTOR, '.price-wrapper .price div sup').text
            price_measure = driver.find_element(By.CSS_SELECTOR, '.price-wrapper .price div sub').text.strip()
            price = f"{price_whole}.{price_fraction}"
        except:
            pass

        deal_notice = None
        try:
            deal_notice = driver.find_element(By.CLASS_NAME, 'notice').text
        except:
            pass

        old_price, old_price_measure = None, None
        try:
            old_price_text = driver.find_element(By.CLASS_NAME, 'price__old-price').text
            
            #Use regex to divide price from mesasure
            match = re.search(r'(\d+[.,]?\d*)\s*([^\d\s]+)', old_price_text)
            if match:
                old_price = float(match.group(1).replace(',', '.'))
                old_price_measure = match.group(2)
        except:
            pass

        price_per, price_per_measure = None, None
        try:
            price_per_text = driver.find_element(By.CLASS_NAME, 'price-per').text

            match = re.search(r'(\d+[.,]?\d*)\s*([^\d\s]+)', price_per_text)
            if match:
                price_per = float(match.group(1).replace(',', '.'))
                price_per_measure = match.group(2)
        except:
            pass

        #Handle different discount display types
        discount_info = None
        try:                    #Discount for multiple units
            discount_info = driver.find_element(By.CLASS_NAME, 'price-label__text').text
        except:
            try:
                card_deal = driver.find_element(By.CSS_SELECTOR, '.price-label__body img')
                discount_info = 'Rimi karte'
            except:
                try:
                    card_deal = driver.find_element(By.CSS_SELECTOR, '.price-label__header img')
                    discount_info = 'Rimi karte'
                except:
                    pass

        discount_percentage = None
        try:
            discount_percentage = driver.find_element(By.CSS_SELECTOR, '.price-label__header.-yellow').text
        except:
            pass
            
        discount_price, discount_price_measure = None, None
        try:
            major = driver.find_element(By.CLASS_NAME, 'major').text
            minor_container = driver.find_element(By.CLASS_NAME, 'minor')
            cents = minor_container.find_element(By.CLASS_NAME, 'cents').text
            discount_price_measure = minor_container.find_element(By.CLASS_NAME, 'currency').text

            discount_price = f"{major}.{cents}"
        except:
            pass

        discount_price_per, discount_price_per_measure = None, None
        try:
            discount_price_per_text = driver.find_element(By.CLASS_NAME, 'price-per').text

            match = re.search(r'(\d+[.,]?\d*)\s*([^\d\s]+)', discount_price_per_text)
            if match:
                discount_price_per = float(match.group(1).replace(',', '.'))
                discount_price_per_measure = match.group(2)
        except:
            pass

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
            
        #Funda all <a> tags within the class and read the text
        category_container = driver.find_element(By.CLASS_NAME, 'section-header__container')
        categories = category_container.find_elements(By.TAG_NAME, 'a')
        category_texts = [category.text.strip() for category in categories]

        #Apply each text part to relevant variable
        category = category_texts[0] if len(category_texts) > 0 else None
        category2 = category_texts[1] if len(category_texts) > 1 else None
        category3 = category_texts[2] if len(category_texts) > 2 else None

        is_active = True
        try:
            is_active = product_container.find_element(By.CLASS_NAME, 'info').text
            if is_active:
              is_active = False
        except:
            pass

        return {
            'url': product_url,
            'name': product_name,
            'product code': product_code,
            'price': price,
            'price measure': price_measure,
            'old price': old_price,
            'old price measure': old_price_measure,
            'price per': price_per,
            'price per measure': price_per_measure,
            'discount price': discount_price,
            'discount price measure': discount_price_measure,
            'discount price per': discount_price_per,
            'discount price per measure': discount_price_per_measure,
            'discount percentage': discount_percentage,
            'discount info': discount_info,
            'deal notice': deal_notice,
            'lowest price': lowest_price,
            'image': image_url,
            'category': category,
            'category2': category2,
            'category3': category3,
            'is active': is_active
        }
    except Exception as e:
        print(f"Error processing product {product_url}: {str(e)}")
        return None

def process_category(category_url):
    driver = create_webdriver()
    processed_products = set()
    try:
        print(f"Category: {category_url}")
        driver.get(category_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-grid'))
        )
        #Pagination breakdown and building category links
        pagination_items = driver.find_elements(By.CLASS_NAME, 'pagination__item')
        max_page = max([int(item.text) for item in pagination_items if item.text.isdigit()] or [1])
        sh_number_match = re.search(r'SH-([\d\-]+)', category_url)
        sh_number = sh_number_match.group(1) if sh_number_match else None
        page_links = [
            f'{category_url}?currentPage={page_num}&pageSize=20&query='
            f'%3Arelevance%3AallCategories%3ASH-{sh_number}'
            f'%3AassortmentStatus%3AinAssortment'
            for page_num in range(1, max_page + 1)
        ]
        for page_link in page_links:
            products = scrape_page(driver, page_link, processed_products)
            for product_url in products:
                product_details = scrape_product_details(driver, product_url)
                if product_details:
                    save_to_database(product_details)
    except Exception as e:
        print(f"Error processing category {category_url}: {str(e)}")
    finally:
        driver.quit()

def main():
    driver = create_webdriver()
    try:
        url = 'https://www.rimi.lv/e-veikals'
        try:
          driver.get(url)
          WebDriverWait(driver, 10).until(
              EC.presence_of_element_located((By.CLASS_NAME, 'category-menu'))
          )
        except Exception as e:
            print(f"Error: Failed to access {url}: {str(e)}")
            return
        
        #Extract category links from home page
        category_divs = driver.find_elements(By.CLASS_NAME, 'category-menu')
        category_links = []
        for category_div in category_divs:
            buttons = category_div.find_elements(By.XPATH, './/button[@role="menuitem"]')
            for button in buttons:
                href = button.get_attribute('href')
                if href:
                    full_url = f"https://www.rimi.lv{href}"
                    category_links.append(full_url)

        #selected_categories = category_links[17:19]      #Code used if scraping fails to scrape remaining data 

        #Runs category scraping concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_category, category_url) for category_url in category_links]  #selected_categories]
            for future in as_completed(futures):
                future.result()
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
