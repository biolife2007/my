from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


CATEGORY_UK = "https://prolimax.com.ua/obigrivaci/keramychni-obihrivachi/"
OUT_FILE = Path("prolimax_keramichni_obigrivachi_names.xlsx")


@dataclass
class Product:
    url_uk: str
    url_ru: str | None
    sku: str
    name_uk: str
    name_ru: str
    shade_uk: str
    shade_ru: str
    power_uk: str
    power_ru: str


def clean(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def category_pages(session: requests.Session) -> list[str]:
    soup = get_soup(session, CATEGORY_UK)
    pages = {CATEGORY_UK}
    for link in soup.select("a[href]"):
        href = link["href"]
        if href.startswith(CATEGORY_UK + "?page="):
            pages.add(href)
    return sorted(pages, key=lambda url: int(re.search(r"page=(\d+)", url).group(1)) if "page=" in url else 1)


def product_urls(session: requests.Session) -> list[str]:
    urls: dict[str, None] = {}
    for page_url in category_pages(session):
        soup = get_soup(session, page_url)
        for title_link in soup.select(".us-module-title a[href]"):
            href = urljoin(page_url, title_link["href"])
            if href.startswith("https://prolimax.com.ua/") and "/ru/" not in href:
                urls[href] = None
    return list(urls.keys())


def alternate_ru_url(soup: BeautifulSoup) -> str | None:
    link = soup.select_one('link[rel="alternate"][hreflang="ru-ua"][href]')
    return link["href"] if link else None


def title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    return clean(h1.get_text(" ")) if h1 else ""


def sku(soup: BeautifulSoup) -> str:
    code = soup.select_one(".us-product-info-code")
    if code:
        return clean(code.get_text(" "))
    text = soup.get_text(" ")
    match = re.search(r"(?:Код товару|Код товара):\s*([^\s]+)", text)
    return clean(match.group(1)) if match else ""


def attrs(soup: BeautifulSoup) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in soup.select(".us-product-attr-item, #us-product-attributes tr"):
        parts = [clean(part.get_text(" ")) for part in item.find_all(["span", "td", "th"], recursive=True)]
        parts = [part.rstrip(":") for part in parts if part]
        if len(parts) >= 2:
            result[parts[0]] = parts[1]
    return result


def find_attr(attributes: dict[str, str], needles: tuple[str, ...]) -> str:
    for key, value in attributes.items():
        key_l = key.lower()
        if any(needle.lower() in key_l for needle in needles):
            return value
    return ""


def append_details(name: str, shade: str, power: str, power_label: str) -> str:
    details = []
    if shade and shade.lower() not in name.lower():
        details.append(shade)
    if power:
        power_text = power if re.search(r"\b(вт|w)\b", power, re.IGNORECASE) else f"{power} {power_label}"
        if power not in name:
            details.append(power_text)
    return f"{name} ({', '.join(details)})" if details else name


def parse_product(session: requests.Session, url: str) -> Product:
    soup_uk = get_soup(session, url)
    uk_attrs = attrs(soup_uk)
    ru_url = alternate_ru_url(soup_uk)
    soup_ru = get_soup(session, ru_url) if ru_url else None
    ru_attrs = attrs(soup_ru) if soup_ru else {}

    shade_uk = find_attr(uk_attrs, ("Відтінки", "Відтінок"))
    power_uk = find_attr(uk_attrs, ("Номінальна споживча потужність", "Потужність"))
    shade_ru = find_attr(ru_attrs, ("Оттенки", "Оттенок")) or shade_uk
    power_ru = find_attr(ru_attrs, ("Номинальная потребляемая мощность", "Мощность")) or power_uk

    name_uk = append_details(title(soup_uk), shade_uk, power_uk, "Вт")
    name_ru_base = title(soup_ru) if soup_ru else title(soup_uk)
    name_ru = append_details(name_ru_base, shade_ru, power_ru, "Вт")

    return Product(
        url_uk=url,
        url_ru=ru_url,
        sku=sku(soup_uk),
        name_uk=name_uk,
        name_ru=name_ru,
        shade_uk=shade_uk,
        shade_ru=shade_ru,
        power_uk=power_uk,
        power_ru=power_ru,
    )


def write_workbook(products: list[Product]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ceramic heaters"
    sheet.append(["SKU", "Назва укр", "назва рос"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for product in products:
        sheet.append([product.sku, product.name_uk, product.name_ru])

    widths = {"A": 18, "B": 90, "C": 90}
    for col, width in widths.items():
        sheet.column_dimensions[col].width = width
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = cell.alignment.copy(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"
    workbook.save(OUT_FILE)


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        }
    )

    urls = product_urls(session)
    products: list[Product] = []
    for index, url in enumerate(urls, start=1):
        products.append(parse_product(session, url))
        percent = index / len(urls) * 100 if urls else 100
        print(f"{percent:5.1f}% ({index}/{len(urls)}) {products[-1].sku} {products[-1].name_uk}", flush=True)

    products.sort(key=lambda item: (item.sku, item.name_uk))
    write_workbook(products)
    print(f"Saved {len(products)} products to {OUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
