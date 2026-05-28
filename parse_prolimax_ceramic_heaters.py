from __future__ import annotations

import re
from copy import copy
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font


CATEGORY_UK = "https://prolimax.com.ua/obigrivaci/keramychni-obihrivachi/"
OUT_FILE = Path("prolimax_keramichni_obigrivachi_names_914.xlsx")
PAGE_COUNT = 39


@dataclass
class Card:
    page: int
    url: str


@dataclass
class Product:
    sku: str
    name_uk: str
    name_ru: str


def clean(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def page_url(page: int) -> str:
    return CATEGORY_UK if page == 1 else f"{CATEGORY_UK}?page={page}"


def product_cards(session: requests.Session) -> list[Card]:
    cards: list[Card] = []
    for page in range(1, PAGE_COUNT + 1):
        soup = get_soup(session, page_url(page))
        links = soup.select(".us-module-title a[href]")
        for link in links:
            href = urljoin(CATEGORY_UK, link["href"])
            if href.startswith("https://prolimax.com.ua/") and "/ru/" not in href:
                cards.append(Card(page=page, url=href))
        print(f"category page {page}/{PAGE_COUNT}: {len(links)} cards", flush=True)
    return cards


def title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    return clean(h1.get_text(" ")) if h1 else ""


def sku(soup: BeautifulSoup) -> str:
    code = soup.select_one(".us-product-info-code")
    return clean(code.get_text(" ")) if code else ""


def alternate_ru_url(soup: BeautifulSoup) -> str | None:
    link = soup.select_one('link[rel="alternate"][hreflang="ru-ua"][href]')
    return link["href"] if link else None


def attrs(soup: BeautifulSoup) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for item in soup.select(".us-product-attr-item"):
        parts = [clean(part.get_text(" ")).rstrip(":") for part in item.find_all("span")]
        if len(parts) >= 2:
            result.append((parts[0], parts[1]))
    return result


def find_attr(attributes: list[tuple[str, str]], needles: tuple[str, ...]) -> str:
    for key, value in attributes:
        key_l = key.lower()
        if any(needle in key_l for needle in needles):
            return value
    return ""


def with_unit_watts(value: str) -> str:
    if not value:
        return ""
    if re.search(r"\b(вт|w)\b", value, re.IGNORECASE):
        return value
    return f"{value} Вт"


def build_name(base_name: str, shade: str, power: str) -> str:
    parts = [base_name]
    if shade:
        parts.append(shade)
    if power:
        parts.append(with_unit_watts(power))
    return " ".join(parts)


def parse_product(session: requests.Session, card: Card) -> Product:
    soup_uk = get_soup(session, card.url)
    uk_attrs = attrs(soup_uk)
    ru_url = alternate_ru_url(soup_uk)
    soup_ru = get_soup(session, ru_url) if ru_url else None
    ru_attrs = attrs(soup_ru) if soup_ru else []

    shade_uk = find_attr(uk_attrs, ("відтін",))
    power_uk = find_attr(uk_attrs, ("номінал", "потуж"))
    shade_ru = find_attr(ru_attrs, ("оттен",)) or shade_uk
    power_ru = find_attr(ru_attrs, ("номинал", "мощн")) or power_uk

    return Product(
        sku=sku(soup_uk),
        name_uk=build_name(title(soup_uk), shade_uk, power_uk),
        name_ru=build_name(title(soup_ru) if soup_ru else title(soup_uk), shade_ru, power_ru),
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

    for column, width in {"A": 18, "B": 100, "C": 100}.items():
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = copy(cell.alignment)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"
    workbook.save(OUT_FILE)


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        }
    )

    cards = product_cards(session)
    products: list[Product] = []
    for index, card in enumerate(cards, start=1):
        product = parse_product(session, card)
        products.append(product)
        percent = index / len(cards) * 100 if cards else 100
        print(f"{percent:5.1f}% ({index}/{len(cards)}) page={card.page} {product.sku} {product.name_uk}", flush=True)

    write_workbook(products)
    print(f"Saved {len(products)} products to {OUT_FILE.resolve()}", flush=True)


if __name__ == "__main__":
    main()
