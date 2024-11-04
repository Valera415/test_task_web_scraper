import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from progress.bar import IncrementalBar
from datetime import datetime


URL = "https://yacht-parts.ru/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36"
}


def error_log(item_url):
    """Записывает ошибку получения данных. Иногда через время страница становится доступна."""

    with open("error_log.txt", "a+", encoding="UTF-8") as log:
        log.writelines(f"{datetime.now()}: Не удалось получить данные по адрессу {URL + item_url}\n")


def get_page_soup(url):
    """Возвращает объект BeautifulSoup"""

    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Ошибка загрузки страницы {url}: {response.status_code}")
        return None
    return BeautifulSoup(response.content, "html.parser")


def get_data_from_item(item_url, logging=True):
    """Получает данные о товаре по его URL.
    Получает разными способами, так как теги и классы меняются от страницы к странице"""

    item_data = {}
    max_attempts = 3
    attempt = 0

    while attempt <= max_attempts:
        try:
            item_soup = get_page_soup(URL + item_url)
            item_data['name'] = item_soup.find("h1", id="pagetitle").text.strip()
            description = item_soup.find("div", class_="preview_text")

            if description:
                item_data['description'] = description.text.strip()
            else:
                try:
                    item_data['description'] = item_soup.find("div", class_="detail_text").find_all("p")[1].text.strip()
                except:
                    data = item_soup.find("div", class_="detail_text")
                    item_data['description'] = data.text.strip() if data else "Без описания"

            image = item_soup.find("img", {"alt": item_data['name']})

            if image:
                item_data['image'] = image["src"]
            else:
                try:
                    item_data['image'] = item_soup.find("img", {"alt": item_data['name'] + " "})["src"]
                except:
                    item_data['image'] = "Без картинки"

            price = item_soup.find("div", class_="price")
            item_data['price'] = price.text.strip() if price else "Под заказ"
            item_data['art'] = item_soup.find("span", class_="value").text.strip()
            item_data['category'] = item_soup.find("a", id="bx_breadcrumb_2").text.strip()

            item_brand = item_soup.find("a", class_="brand_picture")
            item_data['brand'] = item_brand.find("img")["title"] if item_brand else "Не указан"
            break

        except Exception as e:
            attempt += 1
            print(f"Попытка {attempt} не удалась для {item_url}: {e}")
            if attempt == max_attempts:
                print(f"Не удалось получить данные из {item_url} после {max_attempts+1} попыток.")
                item_data = {}
    else:
        if logging:
            error_log(item_url)
    return item_data


def get_data_from_error_log():
    """Повторно получает данные из файла ошибок и сохраняет их в таблицу"""

    if not os.path.exists("error_log.txt"):
        return
    else:
        data_from_error_log = []
        with open("error_log.txt", "r", encoding="UTF-8") as log:
            error_urls = log.readlines()
            for item in error_urls:
                data_from_item = get_data_from_item(item.split()[8][24:], logging=False)
                if data_from_item:
                    data_from_error_log.append(data_from_item)
        save_to_excel(data_from_error_log)


def get_data_from_page(subcategory_link, page):
    """Получает данные товаров с одной страницы подкатегории"""

    item_list = []
    page_url = f"{subcategory_link}?PAGEN_1={page}"
    print(f"\nGetting data from page {page}...", end="\r")
    page_soup = get_page_soup(page_url)
    if not page_soup:
        print(f"Не удалось получить содержимое страницы: {page_url}")
        error_log(page_url)
        return item_list
    items = page_soup.find_all("div", class_="item-title")

    if not items:
        items = page_soup.find_all("td", class_="item-name-cell")

    for item in items:
        data = get_data_from_item(item.find("a")['href'])

        if data:
            item_list.append(data)
    return item_list


def get_subcategory_data(subcategory_link):
    """Получает данные товаров со всех страниц подкатегории"""

    subcategory_soup = get_page_soup(subcategory_link)
    pagination = subcategory_soup.find("span", class_="nums")
    max_page = int(pagination.find_all("a")[-1].text) if pagination else 1
    print("Pages:", max_page)
    subcategory_data = []

    for page in range(1, max_page + 1):
        subcategory_data.extend(get_data_from_page(subcategory_link, page))

    return subcategory_data


def save_to_excel(data, filename="data7.xlsx"):
    """Сохраняет данные в таблицу"""

    df = pd.DataFrame(data)
    if not os.path.exists(filename):
        df.to_excel(filename, index=False)
    else:
        with pd.ExcelWriter(filename, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            df.to_excel(writer, index=False, header=False, startrow=writer.sheets['Sheet1'].max_row)


def main():
    """Главная функция программы"""

    main_page_soup = get_page_soup(URL + "catalog/")
    categories = main_page_soup.find_all("li", class_="name")

    total_bar = IncrementalBar('Total progress:', max=len(categories))
    total_bar.start()
    print()

    for category in categories:
        print(category.text)

        category_url = URL + category.find("a", href=True)['href']
        category_soup = get_page_soup(category_url)

        subcategories = category_soup.find_all("div", class_="item-title")
        sub_bar = IncrementalBar('Category progress:', max=len(subcategories))

        sub_bar.start()
        print()
        for subcategory in subcategories:
            subcategory_link = URL + subcategory.find("a", href=True)['href']
            subcategory_data = get_subcategory_data(subcategory_link)
            save_to_excel(subcategory_data)
            sub_bar.next()

        sub_bar.finish()
        total_bar.next()

    total_bar.finish()
    print("Данные сохранены!")


if __name__ == "__main__":
    main()
