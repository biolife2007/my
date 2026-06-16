# Prolitech

Scripts, SQL queries, exports, and notes for Prolitech.

## 38.xlsx price update

Daily cron script:

```bash
php /var/www/prolitech/scripts/fill_table_main_prices.php
```

The script reads `38.xlsx`, updates these columns from the regular OpenCart product price, and creates a backup before overwriting the file:

- `SKU колони` -> `Ціна колони`
- `SKU куба` -> `Ціна куба`

Manual check without changing the file:

```bash
php /var/www/prolitech/scripts/fill_table_main_prices.php --dry-run
```

Example cron run at 03:00 every day:

```cron
0 3 * * * /usr/bin/php /var/www/prolitech/scripts/fill_table_main_prices.php >> /var/www/prolitech/logs/fill_table_main_prices.log 2>&1
```

