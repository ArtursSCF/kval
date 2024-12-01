from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

#Funkcija kategoriju URL rasmošanai
def scrape_categories(driver):
    
    categories_container = driver.find_element(By.CLASS_NAME, "desktop-menu--categories")

    category_links = categories_container.find_elements(By.CLASS_NAME, "category-item--title")

    all_category_links = []
    for link in category_links:
        category_href = link.get_attribute("href")
        all_category_links.append((category_href))

    return all_category_links

#Funkcija produktu URL rasmošanai
def scrape_products(driver, category_href):
    
    print(f"Scraping products from: {category_href}")
    
    all_product_links = []

    #Cikls cauri produktu katalogu lapām
    while True:
        #Atver specifiskās kategorijas 1. lapu
        driver.get(category_href)
        time.sleep(5)

        #Rasmo pirmās lapas produktu URL
        try:
            product_elements = driver.find_elements(By.XPATH, "//div[starts-with(@id, 'fti-product-card-category-page-')]//div[1]/a")
            for product in product_elements:
                product_link = product.get_attribute("href")
                if product_link not in all_product_links:  #Izvairīšanās no dublikātiem
                    all_product_links.append(product_link)
                    print(f"  Product link: {product_link}")
        except Exception as e:
            print(f"Error while scraping products from {category_href}: {e}")
        
        #Pārbauda nākamo lapu, ja eksistē turpina uz to, ja ekvivalenta tagadējai tad pārtrauc
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
        #Kļūdu apstrāde lapu atrašanai
        except Exception as e:
            print(f"Error finding pagination: {e}")
            break

    return all_product_links

if __name__ == "__main__":
    
    service = Service("C:\chromedriver-win64\chromedriver-win64\chromedriver.exe")
    driver = webdriver.Chrome(service=service)

    try:
        #Iestata, lai kad lapa tiek renderēta tā netiek nokluisēti atgriezta pēc izmēriem, kas atbilst telefona lapas struktūrai
        driver.set_window_size(1920, 1080)

        driver.get("https://www.barbora.lv/")
        time.sleep(5)

        #Rasmo visus kategoriju URL
        all_category_links = scrape_categories(driver)

        all_product_links = []

        #Cikls caur katrai kategorijai, lai rasmotu produktu URL
        for category_href in all_category_links:
            category_product_links = scrape_products(driver, category_href)
            all_product_links.extend(category_product_links)

    finally:
        driver.quit()
