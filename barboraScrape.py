from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.chrome.options import Options
from psycopg2.pool import SimpleConnectionPool
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

def save_to_database(product_details):

    DB_POOL = SimpleConnectionPool(
        minconn=2,
        maxconn=5,
        dbname="postgres",
        user="",                #Provide details
        password="",
        host="localhost",
        port="5432"
    )

    conn = None
    cursor = None

    try:
        conn = DB_POOL.getconn()
        cursor = conn.cursor()
        #Check if the product already exists in the product table
        cursor.execute(
            "SELECT id FROM product WHERE url = %s FOR UPDATE", (product_details['url'],)
        )
        product_id = cursor.fetchone()

        if product_id:
            #Move existing data to product_history
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
                    CURRENT_TIMESTAMP, store_id, id, is_active
                FROM product
                WHERE id = %s
            """, (product_id,))
                
            #Update the product table with new details
            cursor.execute("""
                UPDATE product
                SET 
                    name = %s, product_code = %s, price = %s, price_measure = %s,
                    price_per = %s, price_per_measure = %s, discount_price = %s, 
                    discount_price_measure = %s, discount_price_per = %s,
                    discount_price_per_measure = %s, discount_percentage = %s,
                    discount_info = %s, deal_notice = %s, image = %s,
                    category = %s, category2 = %s, category3 = %s, is_active = %s
                WHERE id = %s
            """, (
                product_details['name'], product_details['product code'],
                product_details['price'], product_details['price measure'],
                product_details['price per'], product_details['price per measure'],
                product_details['discount price'], product_details['discount price measure'],
                product_details['discount price per'], product_details['discount price per measure'],
                product_details['discount percentage'], product_details['discount info'],
                product_details['deal notice'], product_details['image'], product_details['category'],
                product_details['category2'], product_details['category3'], product_details['is active'],
                product_id
            ))
        else:
            #Insert new product into the product table
            cursor.execute("""
                INSERT INTO product (
                    url, name, product_code, price, price_measure,
                    price_per, price_per_measure, discount_price, discount_price_measure, 
                    discount_price_per, discount_price_per_measure, discount_percentage, 
                    discount_info, deal_notice, image, category, category2, category3,
                    is_active, store_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                product_details['url'], product_details['name'], product_details['product code'],
                product_details['price'], product_details['price measure'],
                product_details['price per'], product_details['price per measure'],
                product_details['discount price'], product_details['discount price measure'],
                product_details['discount price per'], product_details['discount price per measure'],
                product_details['discount percentage'], product_details['discount info'],
                product_details['deal notice'], product_details['image'], 
                product_details['category'], product_details['category2'], 
                product_details['category3'], product_details['is active'], 2
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
def scrape_page(driver, page_url, processed_products):
    try:
        driver.get(page_url)

        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'desktop-menu--categories'))
        )

        product_elements = driver.find_elements(By.XPATH, "//div[starts-with(@id, 'fti-product-card-category-page-')]//div[1]/a")
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
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'b-products-allow-desktop-view'))
        )

        product_name = None
        try:
            product_name = driver.find_element(By.CLASS_NAME, "b-product-info--title").text
        except:
            pass

        prod_details = driver.find_element(By.CLASS_NAME, "b-products-allow-desktop-view")

        product_code = None
        try:
            id_element = driver.find_element(By.CSS_SELECTOR, 'div.tw-flex.tw-w-full')
            id_attribute = id_element.get_attribute('id')
            #Use regex to return numeric value after the last "_"
            result = re.search(r'_(\d+)$', id_attribute)
            if result:
                product_code = result.group(1)
        except:
            pass

        #Price in HTML structure is split between tags
        price, price_measure = None, None
        try:
            price_block_sub = prod_details.find_element(By.CLASS_NAME, "tw-border-neutral-200.tw-bg-white")
            price_integer = price_block_sub.find_element(By.CLASS_NAME, "tw-text-xl.tw-font-bold").text
            price_decimal = price_block_sub.find_element(By.CLASS_NAME, "tw-text-sm.tw-font-bold").text
            price = f"{price_integer}.{price_decimal}"

            price_measure = price_block_sub.find_element(By.XPATH, '//*[@id="fti-product-price--0"]/div[1]/div[1]/div[1]/span[4]').text
        except:
            pass

        price_per, price_per_measure = None, None
        try:
            price_per_block = price_block_sub.find_element(By.CLASS_NAME, "tw-leading-3").text
            price_per, price_per_measure = price_per_block.split("€/")
            price_per = price_per.replace(",", ".").strip()
            price_per_measure = f"€/{price_per_measure.strip()}"
        except:
            pass

        #Considering discount types
        discount_block, discount_info = None, None
        try:
            discount_block = prod_details.find_element(By.CLASS_NAME, "tw-bg-thanks-blue.tw-border-thanks-blue")
            discount_info = 'Paldies karte'
        except:
            try:
                discount_block = prod_details.find_element(By.CLASS_NAME, "tw-bg-red-500.tw-border-red-500")
                discount_info = 'Atlaide'
            except:
                pass
                    
        discount_price, discount_price_measure = None, None
        try:
            discount_price_integer = discount_block.find_element(By.CLASS_NAME, "tw-text-xl.tw-font-bold").text
            discount_price_decimal = discount_block.find_element(By.CLASS_NAME, "tw-text-sm.tw-font-bold").text
            discount_price = f"{discount_price_integer}.{discount_price_decimal}"
            discount_price_measure = discount_block.find_element(By.XPATH, '//*[@id="fti-product-price--0"]/div[1]/div[1]/div[1]/span[4]').text
        except:
            pass

        discount_price_per, discount_price_per_measure = None, None
        try:
            discount_price_per_block = discount_block.find_element(By.CLASS_NAME, "tw-leading-3").text
            discount_price_per, discount_price_per_measure = discount_price_per_block.split("€/")
            discount_price_per = discount_price_per.replace(",", ".").strip()
            discount_price_per_measure = f"€/{discount_price_per_measure.strip()}"
        except:
            pass  
            
        deal_notice = None
        try:
            deal_notice = prod_details.find_element(By.CLASS_NAME, "b-product-info--offer-valid-to").text
        except:
            pass
            
        discount_percentage = None
        try:
            discount_percentage = driver.find_element(By.XPATH, """//*[@id="product-details-promo-placeholder_000000000001348689"]/div/div/div/div[2]/div""").text
        except:
            pass

        image_url = None
        try:
            product_image = prod_details.find_element(By.CSS_SELECTOR, '.b-block-slider--slide img')
            image_url = product_image.get_attribute('src')
        except:
            pass

        #Scraping categories from a bradcrumb structure    
        category, category2, category3 = None, None, None
        try:
            breadcrumb_list = driver.find_element(By.CLASS_NAME, "breadcrumb")
                
            li_elements = breadcrumb_list.find_elements(By.TAG_NAME, "li")
                
            #Skip first because it is not applicable
            category_elements = li_elements[1:4]
            categories = [li.find_element(By.TAG_NAME, "span").text.strip() for li in category_elements]
                
            if len(categories) > 0:
                category = categories[0]
            if len(categories) > 1:
                category2 = categories[1]
            if len(categories) > 2:
                category3 = categories[2]
        except:
            pass
        
        is_active = True
        try:
          is_active = driver.find_element(By.CLASS_NAME, 'b-product-out-of-stock').text
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
            'price per': price_per,
            'price per measure': price_per_measure,
            'discount price': discount_price,
            'discount price measure': discount_price_measure,
            'discount price per': discount_price_per,
            'discount price per measure': discount_price_per_measure,
            'discount percentage': discount_percentage,
            'discount info': discount_info,
            'deal notice': deal_notice,
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
    page_links = []

    try:
        driver.set_window_size(1920, 1080)
        print(f"Category: {category_url}")
        driver.get(category_url)
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, 'category-page-results-placeholder'))
        )

        #Discover all pages by iterating through "next page" links
        current_url = category_url
        while True:
            page_links.append(current_url)

            try:
                next_page_link = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(text(), '»')]"))
                )
                next_page_href = next_page_link.get_attribute("href")

                #Stop if page has already been visited
                if next_page_href in page_links:
                    break

                driver.get(next_page_href)
                current_url = next_page_href
            except Exception:
                break

        #Iterate through pages and process products
        for page_link in page_links:
            print(f"Processing page: {page_link}")
            driver.get(page_link)
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
        driver.set_window_size(1920, 1080)

        url = 'https://www.barbora.lv/'
        driver.get(url)

        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'desktop-menu--categories'))
        )

        #Get categories
        category_divs = driver.find_elements(By.CLASS_NAME, 'category-item--title')
        category_links = []
        for category_div in category_divs:
            href = category_div.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = f"https://www.barbora.lv{href}"
                category_links.append(href)

        #selected_categories = [category_links[4]]      #Scrape one category if it had failed

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_category, category_url) for category_url in category_links]#selected_categories]
            for future in as_completed(futures):
                future.result()

    finally:
        driver.quit()

if __name__ == "__main__":
    main() 