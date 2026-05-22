SELECT
  COALESCE(NULLIF(p.sku, ''), p.model) AS sku,
  pd.name AS `назва товару укр`,
  COALESCE(GROUP_CONCAT(DISTINCT cd.name ORDER BY cd.name SEPARATOR ' | '), '') AS `назва категорії`
FROM open_product p
JOIN open_product_description pd
  ON pd.product_id = p.product_id
 AND pd.language_id = 1
LEFT JOIN open_manufacturer m
  ON m.manufacturer_id = p.manufacturer_id
LEFT JOIN open_product_to_category p2c
  ON p2c.product_id = p.product_id
LEFT JOIN open_category_description cd
  ON cd.category_id = p2c.category_id
 AND cd.language_id = 1
WHERE p.manufacturer_id = 0
   OR m.manufacturer_id IS NULL
GROUP BY p.product_id, sku, pd.name
ORDER BY pd.name;
