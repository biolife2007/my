<?php

declare(strict_types=1);

if (isset($_SERVER['REQUEST_METHOD'])) {
    http_response_code(403);
    exit('CLI only');
}

const OUTPUT_NAME = 'price-box.xlsx';
const ID_VNID_NAME = 'id-vnid.xlsx';

$root = dirname(__DIR__, 2);
$scriptDir = __DIR__;
if (basename($scriptDir) === 'scripts') {
    $root = dirname(__DIR__);
    $scriptDir = $root . '/cli/box';
}

$idVnidPath = $scriptDir . '/' . ID_VNID_NAME;
$outputPath = $scriptDir . '/' . OUTPUT_NAME;
$adminUploadPath = $root . '/admin/uploads/' . OUTPUT_NAME;

require_once $root . '/config.php';

main($idVnidPath, $outputPath, $adminUploadPath);

function main(string $idVnidPath, string $outputPath, string $adminUploadPath): void
{
    if (!is_file($idVnidPath)) {
        throw new RuntimeException("File not found: {$idVnidPath}");
    }

    $idMap = readIdMap($idVnidPath);
    $products = fetchPublishedProducts();

    $rows = [];
    $missing = 0;
    foreach ($products as $product) {
        $sku = normalizeKey($product['sku']);
        $boxId = $idMap[$sku] ?? '';
        if ($boxId === '') {
            $missing++;
        }
        $rows[] = [$product['price'], $boxId, $product['sku']];
    }

    writeXlsx($outputPath, $rows);

    $adminDir = dirname($adminUploadPath);
    if (!is_dir($adminDir) && !mkdir($adminDir, 0755, true) && !is_dir($adminDir)) {
        throw new RuntimeException("Cannot create directory: {$adminDir}");
    }
    if (!copy($outputPath, $adminUploadPath)) {
        throw new RuntimeException("Cannot copy {$outputPath} to {$adminUploadPath}");
    }

    $matched = count($rows) - $missing;
    echo sprintf(
        "ok file=%s admin_copy=%s count=%d matched=%d missing=%d\n",
        $outputPath,
        $adminUploadPath,
        count($rows),
        $matched,
        $missing
    );
}

function fetchPublishedProducts(): array
{
    $host = defined('DB_HOSTNAME') ? DB_HOSTNAME : DB_HOST;
    $user = defined('DB_USERNAME') ? DB_USERNAME : '';
    $password = defined('DB_PASSWORD') ? DB_PASSWORD : '';
    $database = defined('DB_DATABASE') ? DB_DATABASE : '';
    $port = defined('DB_PORT') ? (int) DB_PORT : 3306;
    $prefix = defined('DB_PREFIX') ? DB_PREFIX : '';

    $mysqli = mysqli_init();
    if (!$mysqli) {
        throw new RuntimeException('Cannot initialize mysqli');
    }
    if (!$mysqli->real_connect($host, $user, $password, $database, $port)) {
        throw new RuntimeException('DB connection failed: ' . mysqli_connect_error());
    }
    $mysqli->set_charset('utf8');

    $productTable = dbName($prefix . 'product');
    $productToStoreTable = dbName($prefix . 'product_to_store');
    $sql = "
        SELECT p.price, TRIM(p.sku) AS sku
        FROM {$productTable} p
        WHERE p.status = 1
          AND (p.date_available = '0000-00-00' OR p.date_available <= CURDATE())
          AND EXISTS (
              SELECT 1
              FROM {$productToStoreTable} p2s
              WHERE p2s.product_id = p.product_id
          )
        ORDER BY p.product_id
    ";

    $result = $mysqli->query($sql);
    if (!$result) {
        throw new RuntimeException('DB query failed: ' . $mysqli->error);
    }

    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = [
            'price' => (string) $row['price'],
            'sku' => (string) $row['sku'],
        ];
    }
    $result->free();
    $mysqli->close();

    return $rows;
}

function dbName(string $name): string
{
    return '`' . str_replace('`', '``', $name) . '`';
}

function readIdMap(string $path): array
{
    $rows = readXlsxRows($path);
    if (!$rows) {
        return [];
    }

    $headers = array_map(static fn($value) => trim((string) $value), $rows[0]);
    $productIdIndex = array_search('id Продукта', $headers, true);
    $externalIdIndex = array_search('зовнішній id', $headers, true);
    if ($productIdIndex === false || $externalIdIndex === false) {
        throw new RuntimeException('Expected columns not found in id-vnid.xlsx');
    }

    $map = [];
    foreach (array_slice($rows, 1) as $row) {
        $externalId = normalizeKey($row[$externalIdIndex] ?? '');
        $productId = normalizeKey($row[$productIdIndex] ?? '');
        if ($externalId !== '' && $productId !== '') {
            $map[$externalId] = $productId;
        }
    }

    return $map;
}

function readXlsxRows(string $path): array
{
    $zip = new ZipArchive();
    if ($zip->open($path) !== true) {
        throw new RuntimeException("Cannot open xlsx: {$path}");
    }

    $sharedStrings = [];
    $sharedXml = $zip->getFromName('xl/sharedStrings.xml');
    if ($sharedXml !== false) {
        $shared = simplexml_load_string($sharedXml);
        foreach ($shared->si as $item) {
            $sharedStrings[] = collectText($item);
        }
    }

    $sheetXml = $zip->getFromName('xl/worksheets/sheet1.xml');
    $zip->close();
    if ($sheetXml === false) {
        throw new RuntimeException('Cannot read xl/worksheets/sheet1.xml');
    }

    $sheet = simplexml_load_string($sheetXml);
    $rows = [];
    foreach ($sheet->sheetData->row as $row) {
        $cells = [];
        foreach ($row->c as $cell) {
            $ref = (string) $cell['r'];
            $index = columnIndex($ref);
            $cells[$index] = cellValue($cell, $sharedStrings);
        }
        if ($cells) {
            ksort($cells);
            $max = max(array_keys($cells));
            $line = [];
            for ($i = 0; $i <= $max; $i++) {
                $line[] = $cells[$i] ?? '';
            }
            $rows[] = $line;
        }
    }

    return $rows;
}

function collectText(SimpleXMLElement $node): string
{
    $text = '';
    foreach ($node->xpath('.//text()') as $part) {
        $text .= (string) $part;
    }
    return $text;
}

function cellValue(SimpleXMLElement $cell, array $sharedStrings): string
{
    $type = (string) $cell['t'];
    if ($type === 'inlineStr') {
        return collectText($cell->is);
    }

    $value = isset($cell->v) ? (string) $cell->v : '';
    if ($type === 's') {
        return $sharedStrings[(int) $value] ?? '';
    }

    return $value;
}

function columnIndex(string $cellRef): int
{
    preg_match('/^[A-Z]+/', strtoupper($cellRef), $matches);
    $letters = $matches[0] ?? 'A';
    $index = 0;
    foreach (str_split($letters) as $letter) {
        $index = $index * 26 + (ord($letter) - 64);
    }
    return $index - 1;
}

function normalizeKey($value): string
{
    $text = trim((string) $value);
    if (preg_match('/^\d+\.0$/', $text)) {
        $text = substr($text, 0, -2);
    }
    return $text;
}

function writeXlsx(string $path, array $rows): void
{
    $dir = dirname($path);
    if (!is_dir($dir) && !mkdir($dir, 0755, true) && !is_dir($dir)) {
        throw new RuntimeException("Cannot create directory: {$dir}");
    }

    $zip = new ZipArchive();
    if ($zip->open($path, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
        throw new RuntimeException("Cannot write xlsx: {$path}");
    }

    $zip->addFromString('[Content_Types].xml', contentTypesXml());
    $zip->addFromString('_rels/.rels', rootRelsXml());
    $zip->addFromString('xl/workbook.xml', workbookXml());
    $zip->addFromString('xl/_rels/workbook.xml.rels', workbookRelsXml());
    $zip->addFromString('xl/styles.xml', stylesXml());
    $zip->addFromString('xl/worksheets/sheet1.xml', sheetXml($rows));
    $zip->close();
}

function sheetXml(array $rows): string
{
    $maxRow = max(1, count($rows) + 1);
    $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
    $xml .= '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">';
    $xml .= '<dimension ref="A1:C' . $maxRow . '"/>';
    $xml .= '<sheetViews><sheetView workbookViewId="0"/></sheetViews>';
    $xml .= '<sheetFormatPr defaultRowHeight="15"/>';
    $xml .= '<cols><col min="1" max="1" width="14" customWidth="1"/><col min="2" max="2" width="12" customWidth="1"/><col min="3" max="3" width="24" customWidth="1"/></cols>';
    $xml .= '<sheetData>';
    $xml .= rowXml(1, ['Ціна', 'id-box', 'sku']);
    foreach ($rows as $i => $row) {
        $xml .= rowXml($i + 2, $row, [true, true, false]);
    }
    $xml .= '</sheetData></worksheet>';
    return $xml;
}

function rowXml(int $rowNumber, array $values, array $numeric = [false, false, false]): string
{
    $xml = '<row r="' . $rowNumber . '">';
    foreach ($values as $i => $value) {
        $xml .= cellXml($rowNumber, $i + 1, (string) $value, $numeric[$i] ?? false);
    }
    return $xml . '</row>';
}

function cellXml(int $rowNumber, int $columnIndex, string $value, bool $numeric): string
{
    $ref = columnName($columnIndex) . $rowNumber;
    if ($numeric && is_numeric($value)) {
        return '<c r="' . $ref . '"><v>' . htmlspecialchars($value, ENT_XML1) . '</v></c>';
    }
    return '<c r="' . $ref . '" t="inlineStr"><is><t>' . htmlspecialchars($value, ENT_XML1) . '</t></is></c>';
}

function columnName(int $index): string
{
    $name = '';
    while ($index > 0) {
        $index--;
        $name = chr(65 + ($index % 26)) . $name;
        $index = intdiv($index, 26);
    }
    return $name;
}

function contentTypesXml(): string
{
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>';
}

function rootRelsXml(): string
{
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';
}

function workbookXml(): string
{
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="price-box" sheetId="1" r:id="rId1"/></sheets></workbook>';
}

function workbookRelsXml(): string
{
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>';
}

function stylesXml(): string
{
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>';
}
