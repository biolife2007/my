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

## Unpublished product review drafts

Preview without database changes:

```bash
/opt/alt/php74/usr/bin/php /home/rvbkkxiv/automation/prolitech/scripts/generate_product_review_drafts.php
```

The production cron checks hourly from 09:00 through 21:00 (Europe/Kyiv). It
creates at most three unpublished (`status = 0`) Ukrainian drafts per day across
reviews and product questions,
scheduled for 10:00, 15:00, and 20:00, with catch-up after a missed run:

```cron
0 9-21 * * * REVIEW_DRAFTS_APPLY=1 /opt/alt/php74/usr/bin/php /home/rvbkkxiv/automation/prolitech/scripts/generate_product_review_drafts.php >> /home/rvbkkxiv/automation/prolitech/logs/generate_product_review_drafts.log 2>&1
```

Drafts use varied Ukrainian author names with an approximately 80/20 male/female
distribution. About 10% use Latin letters, another 10% use an `ім'я + по батькові`
form, and the remaining 80% are simple Cyrillic first names. Draft ratings follow
an approximately 80% rating-5 and 20% rating-4 distribution and use only products
ranked by the OpenCart `viewed` counter. The administrator `reply` field always
remains empty. Automated provenance is stored separately in the internal
`{DB_PREFIX}auto_review_draft` tracking table while `status = 0`. A product is
not selected again by this automation for 30 days.

Question-like text is stored in `{DB_PREFIX}oct_faq`, with empty `email` and
`answer` fields. Review-like text is stored in `{DB_PREFIX}review`, with an empty
administrator `reply`. Both types count toward the same daily limit.

