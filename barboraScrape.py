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
    driver.set_window_size(1920, 1080)

    url = 'https://www.barbora.lv/'
    driver.get(url)

    # Gaida lai 'desktop-menu--categories' būtu ielādējies
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'desktop-menu--categories'))
    )

    # Atrod visus "div", kam ir 'desktop-menu--categories', lai rasmotu produktu kategoriju "href"
    category_divs = driver.find_elements(By.CLASS_NAME, 'category-item--title')

    #Rasmo "href" un apstrādā linkus, ja tie ir relatīvi 
    category_links = []
    for category_div in category_divs:
        href = category_div.get_attribute("href")
        if href:
            if not href.startswith("http"):
                href = f"https://www.barbora.lv{href}"
            category_links.append(href)

    # Seko līdzi apstrādātiem URL, lai izvairītos no dublikātiem
    processed_products = set()

    def scrape_page(page_url):
        try:
            driver.get(page_url)
            time.sleep(2)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'desktop-menu--categories'))
            )

            # Rasmo produktu "href" linku daļas
            product_elements = driver.find_elements(By.XPATH, "//div[starts-with(@id, 'fti-product-card-category-page-')]//div[1]/a")
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
        
        try:
            driver.get(product_url)
            time.sleep(2)

            product_name = None
            try:
                product_name = driver.find_element(By.CLASS_NAME, "b-product-info--title").text
            except:
                pass

            prod_details = driver.find_element(By.CLASS_NAME, "b-products-allow-desktop-view")

            # Cena ir sadalīta atsevišķos HTML tagos, tāpēc atlasa visus un veic konkatenāciju
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

            #Atlaižu sadalījums ar paldies karti vai vienkārša atlaide
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
            
            category, category2, category3 = None, None, None
            try:
                #Atrod "breadcrumb" <ol> elementu
                breadcrumb_list = driver.find_element(By.CLASS_NAME, "breadcrumb")
                
                li_elements = breadcrumb_list.find_elements(By.TAG_NAME, "li")
                
                #Izlaiž pirmo <li> un ņem vērā nākamos trīs, ja pieejami
                category_elements = li_elements[1:4]
                categories = [li.find_element(By.TAG_NAME, "span").text.strip() for li in category_elements]
                
                #Piešķir kategorijām mainīgos
                if len(categories) > 0:
                    category = categories[0]
                if len(categories) > 1:
                    category2 = categories[1]
                if len(categories) > 2:
                    category3 = categories[2]
            except:
                pass
                

            return {
                'url': product_url,
                'name': product_name,
                'price': price,
                'price_measure': price_measure,
                'price_per': price_per,
                'price_per_measure': price_per_measure,
                'discount_price': discount_price,
                'discount_price_measure': discount_price_measure,
                'discount_price_per': discount_price_per,
                'discount_price_per_measure': discount_price_per_measure,
                'discount_percentage': discount_percentage,
                'discount_info': discount_info,
                'deal_notice': deal_notice,
                'image_url': image_url,
                'category': category,
                'category2': category2,
                'category3': category3,
            }
        
        except Exception as e:
            print(f"Error processing product {product_url}: {str(e)}")
            return None

    ##Cikls caur kategoriju URL    
    for category_url in category_links:
        try:
            print(f"Category: {category_url}")

            category_href = category_url
            while category_href:
                try:
                    driver.get(category_href)
                    time.sleep(2)

                    #Rasmo produktu URL un produktu informāciju
                    products = scrape_page(category_href)
                    for product in products:
                        product_details = scrape_product_details(product)
                        if product_details:
                            print("Product details:")
                            print(f"    url: {product_details['url']}")
                            print(f"    name: {product_details['name']}")
                            print(f"    price: {product_details['price']}")
                            print(f"    price_measure: {product_details['price_measure']}")
                            print(f"    price_per: {product_details['price_per']}")
                            print(f"    price_per_measure: {product_details['price_per_measure']}")
                            print(f"    discount_price: {product_details['discount_price']}")
                            print(f"    discount_price_measure: {product_details['discount_price_measure']}")
                            print(f"    discount_price_per: {product_details['discount_price_per']}")
                            print(f"    discount_price_per_measure: {product_details['discount_price_per_measure']}")
                            print(f"    discount_percentage: {product_details['discount_percentage']}")
                            print(f"    discount_info: {product_details['discount_info']}")
                            print(f"    deal_notice: {product_details['deal_notice']}")
                            print(f"    image_url: {product_details['image_url']}")
                            print(f"    category: {product_details['category']}")
                            print(f"    category2: {product_details['category2']}")
                            print(f"    category3: {product_details['category3']}")

                    #Produktu kataloga lapu pāršķiršanas apstrāde
                    try:
                        pagination = driver.find_element(By.CLASS_NAME, "b-pagination-wrapper--desktop-top")
                        next_page_link = pagination.find_elements(By.XPATH, ".//a[contains(text(), '»')]")
                        
                        if next_page_link:
                            next_page_href = next_page_link[0].get_attribute("href")
                            
                            #Pārbaude vai nākamā lapa ir ekvivalenta tagadējai lapai
                            if next_page_href == category_href:
                                break
                            
                            #Atjauno category_href uz nākamās lapas URL
                            category_href = next_page_href
                            print(f"Page: {category_href}")
                            time.sleep(3)
                        else:
                            break

                    except Exception as e:
                        print(f"Error finding pagination: {e}")
                        break
                  
                except Exception as e:
                    print(f"Error processing category {category_url}: {str(e)}")
                    continue
                
        except Exception as e:
          print(f"Error processing category {category_url}: {str(e)}")
          continue

finally:
    driver.quit()