import argparse
import csv
import os
import shlex
import subprocess
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "exports" / "prolitech_prices_current.csv"


def load_env(path):
    env = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def sql_string(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def sql_decimal(value):
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.0001")))
    except (InvalidOperation, ValueError):
        raise ValueError(f"invalid decimal value: {value!r}")


def read_prices(path, only_sku=None):
    prices = {}
    invalid = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        required = {"sku", "price"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"CSV missing columns: {', '.join(sorted(missing))}")

        for line_no, row in enumerate(reader, start=2):
            sku = (row.get("sku") or "").strip()
            if only_sku and sku != only_sku:
                continue
            if not sku:
                invalid.append((line_no, sku, row.get("price"), "empty sku"))
                continue
            try:
                price = Decimal(str(row.get("price", "")).strip()).quantize(Decimal("0.0001"))
            except InvalidOperation:
                invalid.append((line_no, sku, row.get("price"), "invalid price"))
                continue
            if price < 0:
                invalid.append((line_no, sku, row.get("price"), "negative price"))
                continue
            prices[sku] = {
                "sku": sku,
                "price": price,
                "product_id": row.get("product_id", ""),
                "model": row.get("model", ""),
                "product_name": row.get("product_name", ""),
            }
    return list(prices.values()), invalid


def build_values_rows(rows):
    return ",\n".join(
        "("
        + ",".join(
            [
                sql_string(row["sku"]),
                sql_decimal(row["price"]),
                sql_string(row["product_id"]),
                sql_string(row["model"]),
                sql_string(row["product_name"]),
            ]
        )
        + ")"
        for row in rows
    )


def build_preview_sql(rows, max_change_percent):
    values = build_values_rows(rows)
    return f"""
DROP TEMPORARY TABLE IF EXISTS tmp_prolitech_price_sync;
CREATE TEMPORARY TABLE tmp_prolitech_price_sync (
  sku VARCHAR(255) NOT NULL PRIMARY KEY,
  price DECIMAL(15,4) NOT NULL,
  prolitech_product_id VARCHAR(64) NOT NULL,
  model VARCHAR(255) NOT NULL,
  product_name VARCHAR(255) NOT NULL
);
INSERT INTO tmp_prolitech_price_sync
  (sku, price, prolitech_product_id, model, product_name)
VALUES
{values};

SELECT
  tmp.sku,
  sp.id AS onebox_product_id,
  sp.name AS onebox_name,
  sp.price AS old_price,
  tmp.price AS new_price,
  ROUND(tmp.price - sp.price, 4) AS diff,
  CASE
    WHEN sp.id IS NULL THEN 'not_found'
    WHEN sp.price = tmp.price THEN 'same'
    WHEN sp.price > 0 AND ABS((tmp.price - sp.price) / sp.price * 100) > {max_change_percent} THEN 'large_change'
    ELSE 'will_update'
  END AS status
FROM tmp_prolitech_price_sync tmp
LEFT JOIN shopproduct sp
  ON sp.code1c = tmp.sku
ORDER BY status, tmp.sku;
"""


def build_apply_sql(rows, max_change_percent):
    values = build_values_rows(rows)
    return f"""
DROP TEMPORARY TABLE IF EXISTS tmp_prolitech_price_sync;
CREATE TEMPORARY TABLE tmp_prolitech_price_sync (
  sku VARCHAR(255) NOT NULL PRIMARY KEY,
  price DECIMAL(15,4) NOT NULL,
  prolitech_product_id VARCHAR(64) NOT NULL,
  model VARCHAR(255) NOT NULL,
  product_name VARCHAR(255) NOT NULL
);
INSERT INTO tmp_prolitech_price_sync
  (sku, price, prolitech_product_id, model, product_name)
VALUES
{values};

SELECT
  'BEFORE_UPDATE' AS marker,
  tmp.sku,
  sp.id AS onebox_product_id,
  sp.price AS old_price,
  tmp.price AS new_price
FROM tmp_prolitech_price_sync tmp
JOIN shopproduct sp
  ON sp.code1c = tmp.sku
WHERE sp.price <> tmp.price
  AND (
    sp.price = 0
    OR ABS((tmp.price - sp.price) / sp.price * 100) <= {max_change_percent}
  )
ORDER BY tmp.sku;

UPDATE shopproduct sp
JOIN tmp_prolitech_price_sync tmp
  ON tmp.sku = sp.code1c
SET
  sp.price = tmp.price,
  sp.pricesell = tmp.price,
  sp.udate = NOW()
WHERE sp.price <> tmp.price
  AND (
    sp.price = 0
    OR ABS((tmp.price - sp.price) / sp.price * 100) <= {max_change_percent}
  );

SELECT ROW_COUNT() AS updated_rows;
"""


def ssh_mysql(env, sql):
    ssh_host = env["ONEBOX_SSH_HOST"]
    ssh_user = env["ONEBOX_SSH_USER"]
    ssh_port = env.get("ONEBOX_SSH_PORT", "22")
    db_host = env.get("ONEBOX_DB_HOST", "localhost")
    db_port = env.get("ONEBOX_DB_PORT", "3306")
    db_name = env["ONEBOX_DB_DATABASE"]
    db_user = env["ONEBOX_DB_USERNAME"]
    db_password = env["ONEBOX_DB_PASSWORD"]

    remote = (
        f"MYSQL_PWD={shlex.quote(db_password)} "
        f"mysql -h {shlex.quote(db_host)} "
        f"-P {shlex.quote(db_port)} "
        f"-u {shlex.quote(db_user)} "
        f"--default-character-set=utf8 "
        f"-N -B {shlex.quote(db_name)}"
    )
    cmd = [
        "ssh",
        "-p",
        str(ssh_port),
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{ssh_user}@{ssh_host}",
        remote,
    ]
    return subprocess.run(
        cmd,
        input=sql,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_report(name, text):
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"{name}_{stamp}.tsv"
    path.write_text(text, encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Preview/apply Prolitech prices to OneBox.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to Prolitech prices CSV.")
    parser.add_argument("--env", default=str(ROOT / ".env_onebox"), help="Path to OneBox env file.")
    parser.add_argument("--sku", help="Limit run to one SKU. Required for the first apply test.")
    parser.add_argument("--apply", action="store_true", help="Actually update OneBox prices.")
    parser.add_argument("--max-updates", type=int, default=10000, help="Maximum allowed CSV rows in --apply mode.")
    parser.add_argument("--max-change-percent", type=Decimal, default=Decimal("70"), help="Skip larger price changes.")
    args = parser.parse_args()

    rows, invalid = read_prices(Path(args.csv), only_sku=args.sku)
    if not rows:
        raise RuntimeError("No valid rows found in CSV for the selected filter.")
    if args.apply and len(rows) > args.max_updates:
        raise RuntimeError(
            f"Refusing to apply {len(rows)} CSV rows; increase --max-updates intentionally."
        )

    env = load_env(Path(args.env))
    sql = build_apply_sql(rows, args.max_change_percent) if args.apply else build_preview_sql(rows, args.max_change_percent)
    result = ssh_mysql(env, sql)
    report = write_report("onebox_apply" if args.apply else "onebox_preview", result.stdout)

    if invalid:
        invalid_report = write_report(
            "onebox_invalid_csv_rows",
            "\n".join("\t".join(map(str, item)) for item in invalid) + "\n",
        )
        print(f"invalid_csv_rows={len(invalid)} invalid_report={invalid_report}")

    print(f"mode={'apply' if args.apply else 'preview'} csv_rows={len(rows)} report={report}")
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
