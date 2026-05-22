import os

from csv_to_xlsx import write_xlsx
from export_open_no_brand_csv import load_env, query_mysql


SQL = """
SELECT
  m.manufacturer_id,
  m.name,
  m.sort_order,
  COUNT(p.product_id) AS product_count
FROM {prefix}manufacturer m
LEFT JOIN {prefix}product p
  ON p.manufacturer_id = m.manufacturer_id
GROUP BY m.manufacturer_id, m.name, m.sort_order
ORDER BY m.name
"""


def main():
    env = load_env(".env_open")
    rows = query_mysql(env, SQL)
    output = "open_brands.xlsx"
    write_xlsx(
        [["manufacturer_id", "назва бренду", "sort_order", "кількість товарів"], *rows],
        output,
    )
    print(f"ok file={os.path.abspath(output)} rows={len(rows)}")


if __name__ == "__main__":
    main()
