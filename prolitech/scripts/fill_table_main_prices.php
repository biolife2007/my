<?php
declare(strict_types=1);

/**
 * Updates price columns in 38.xlsx from the Prolitech OpenCart database.
 *
 * Default pairs:
 *   SKU колони -> Ціна колони
 *   SKU куба   -> Ціна куба
 *
 * Usage:
 *   php fill_table_main_prices.php
 *   php fill_table_main_prices.php --file=/path/38.xlsx --output=/path/38.updated.xlsx
 *   php fill_table_main_prices.php --dry-run
 */

const DEFAULT_FILE = __DIR__ . '/../../38.xlsx';
const DEFAULT_ENV = __DIR__ . '/../.env_open';
const BACKUP_DIR = __DIR__ . '/../exports/price_update_backups';

$columnPairs = [
    'SKU колони' => 'Ціна колони',
    'SKU куба' => 'Ціна куба',
];

main($argv, $columnPairs);

function main(array $argv, array $columnPairs): void
{
    $options = parseOptions($argv);
    $inputFile = pathOption($options, 'file', DEFAULT_FILE);
    $outputFile = pathOption($options, 'output', $inputFile);
    $envFile = pathOption($options, 'env', DEFAULT_ENV);
    $dryRun = array_key_exists('dry-run', $options);

    assertReadableFile($inputFile, 'Excel file');
    assertReadableFile($envFile, 'Env file');

    $env = loadEnv($envFile);
    $prefix = $env['DB_PREFIX'] ?? '';

    $xlsx = readXlsx($inputFile);
    [$headers, $rows] = readSheetRows($xlsx);
    $columnIndexes = resolveColumnPairs($headers, $columnPairs);
    $skus = collectSkus($rows, $columnIndexes);

    if (!$skus) {
        logLine('No SKU values found.');
        return;
    }

    $prices = fetchPrices($env, $prefix, $skus);
    $stats = updatePriceCells($xlsx, $rows, $columnIndexes, $prices);

    logLine(sprintf(
        'Rows scanned=%d, unique SKU=%d, matched=%d, updated=%d, missing=%d',
        count($rows),
        count($skus),
        count($prices),
        $stats['updated'],
        $stats['missing']
    ));

    if ($dryRun) {
        logLine('Dry run: file was not changed.');
        return;
    }

    if (realpath($inputFile) === realpath($outputFile)) {
        ensureDir(BACKUP_DIR);
        $backup = BACKUP_DIR . '/38_price_update_backup_latest.xlsx';
        if (!copy($inputFile, $backup)) {
            throw new RuntimeException("Cannot create backup: {$backup}");
        }
        logLine("Backup: {$backup}");
    }

    writeXlsx($xlsx, $outputFile);
    logLine("Saved: {$outputFile}");
}

function parseOptions(array $argv): array
{
    $options = [];
    foreach (array_slice($argv, 1) as $arg) {
            if (startsWith($arg, '--')) {
                $arg = substr($arg, 2);
            if (contains($arg, '=')) {
                [$key, $value] = explode('=', $arg, 2);
                $options[$key] = $value;
            } else {
                $options[$arg] = true;
            }
        }
    }
    return $options;
}

function pathOption(array $options, string $key, string $default): string
{
    return isset($options[$key]) ? (string)$options[$key] : $default;
}

function assertReadableFile(string $path, string $label): void
{
    if (!is_file($path) || !is_readable($path)) {
        throw new RuntimeException("{$label} is not readable: {$path}");
    }
}

function ensureDir(string $path): void
{
    if (!is_dir($path) && !mkdir($path, 0775, true) && !is_dir($path)) {
        throw new RuntimeException("Cannot create directory: {$path}");
    }
}

function logLine(string $message): void
{
    fwrite(STDOUT, '[' . date('Y-m-d H:i:s') . '] ' . $message . PHP_EOL);
}

function loadEnv(string $path): array
{
    $env = [];
    foreach (file($path, FILE_IGNORE_NEW_LINES) ?: [] as $line) {
        $line = trim($line);
        if ($line === '' || startsWith($line, '#') || !contains($line, '=')) {
            continue;
        }
        [$key, $value] = explode('=', $line, 2);
        $env[trim($key)] = trim($value);
    }
    return $env;
}

function fetchPrices(array $env, string $prefix, array $skus): array
{
    foreach (['DB_HOST', 'DB_PORT', 'DB_DATABASE', 'DB_USERNAME', 'DB_PASSWORD'] as $key) {
        if (!isset($env[$key])) {
            throw new RuntimeException("Missing {$key} in env file.");
        }
    }

    $dsn = sprintf(
        'mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
        $env['DB_HOST'],
        (int)$env['DB_PORT'],
        $env['DB_DATABASE']
    );
    $pdo = new PDO($dsn, $env['DB_USERNAME'], $env['DB_PASSWORD'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);

    $prices = [];
    foreach (array_chunk(array_values($skus), 500) as $chunk) {
        $placeholders = implode(',', array_fill(0, count($chunk), '?'));
        $sql = "
            SELECT sku, model, price
            FROM {$prefix}product
            WHERE sku IN ({$placeholders})
               OR model IN ({$placeholders})
        ";
        $stmt = $pdo->prepare($sql);
        $stmt->execute(array_merge($chunk, $chunk));

        foreach ($stmt as $row) {
            $price = normalizePrice((string)$row['price']);
            foreach (['sku', 'model'] as $field) {
                $key = normalizeSku((string)($row[$field] ?? ''));
                if ($key !== '') {
                    $prices[$key] = $price;
                }
            }
        }
    }

    return $prices;
}

function normalizeSku(string $value): string
{
    return strtoupper(trim($value));
}

function normalizePrice(string $value): string
{
    $number = (float)$value;
    if (abs($number - round($number)) < 0.000001) {
        return (string)(int)round($number);
    }
    return rtrim(rtrim(number_format($number, 4, '.', ''), '0'), '.');
}

function readXlsx(string $path): array
{
    $zip = new ZipArchive();
    if ($zip->open($path) !== true) {
        throw new RuntimeException("Cannot open xlsx: {$path}");
    }

    $files = [];
    for ($i = 0; $i < $zip->numFiles; $i++) {
        $name = $zip->getNameIndex($i);
        $files[$name] = $zip->getFromIndex($i);
    }
    $zip->close();

    $sharedStrings = [];
    if (isset($files['xl/sharedStrings.xml'])) {
        $sharedStrings = parseSharedStrings($files['xl/sharedStrings.xml']);
    }

    $sheetPath = detectFirstSheetPath($files);
    if (!isset($files[$sheetPath])) {
        throw new RuntimeException("Worksheet XML was not found: {$sheetPath}");
    }

    $sheet = new DOMDocument();
    $sheet->preserveWhiteSpace = false;
    $sheet->formatOutput = false;
    $sheet->loadXML($files[$sheetPath]);

    return [
        'path' => $path,
        'files' => $files,
        'sharedStrings' => $sharedStrings,
        'sheetPath' => $sheetPath,
        'sheet' => $sheet,
    ];
}

function detectFirstSheetPath(array $files): string
{
    if (isset($files['xl/workbook.xml'], $files['xl/_rels/workbook.xml.rels'])) {
        $workbook = simplexml_load_string($files['xl/workbook.xml']);
        $workbook->registerXPathNamespace('main', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main');
        $workbook->registerXPathNamespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships');
        $sheets = $workbook->xpath('//main:sheet');
        if ($sheets) {
            $rid = (string)$sheets[0]->attributes('r', true)->id;
            $rels = simplexml_load_string($files['xl/_rels/workbook.xml.rels']);
            foreach ($rels->Relationship as $rel) {
                if ((string)$rel['Id'] === $rid) {
                    $target = ltrim((string)$rel['Target'], '/');
                    return startsWith($target, 'xl/') ? $target : 'xl/' . $target;
                }
            }
        }
    }

    return 'xl/worksheets/sheet1.xml';
}

function parseSharedStrings(string $xml): array
{
    $doc = simplexml_load_string($xml);
    $strings = [];
    foreach ($doc->si as $si) {
        if (isset($si->t)) {
            $strings[] = (string)$si->t;
            continue;
        }

        $text = '';
        foreach ($si->r as $run) {
            $text .= (string)$run->t;
        }
        $strings[] = $text;
    }
    return $strings;
}

function readSheetRows(array $xlsx): array
{
    $xpath = new DOMXPath($xlsx['sheet']);
    $xpath->registerNamespace('x', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main');

    $rows = [];
    $headers = [];
    foreach ($xpath->query('//x:sheetData/x:row') as $rowNode) {
        $rowNumber = (int)$rowNode->getAttribute('r');
        $cells = [];
        foreach ($xpath->query('x:c', $rowNode) as $cellNode) {
            $ref = $cellNode->getAttribute('r');
            $col = columnNameToIndex(preg_replace('/\d+/', '', $ref));
            $cells[$col] = readCellValue($cellNode, $xlsx['sharedStrings']);
        }

        if ($rowNumber === 1) {
            $headers = $cells;
        } else {
            $rows[$rowNumber] = $cells;
        }
    }

    return [$headers, $rows];
}

function readCellValue(DOMElement $cellNode, array $sharedStrings): string
{
    $type = $cellNode->getAttribute('t');

    if ($type === 'inlineStr') {
        $text = '';
        foreach ($cellNode->getElementsByTagName('t') as $textNode) {
            $text .= $textNode->textContent;
        }
        return trim($text);
    }

    $valueNode = null;
    foreach ($cellNode->childNodes as $child) {
        if ($child instanceof DOMElement && $child->localName === 'v') {
            $valueNode = $child;
            break;
        }
    }

    if (!$valueNode) {
        return '';
    }

    $value = $valueNode->textContent;
    if ($type === 's') {
        return trim((string)($sharedStrings[(int)$value] ?? ''));
    }

    return trim($value);
}

function resolveColumnPairs(array $headers, array $columnPairs): array
{
    $byName = [];
    foreach ($headers as $col => $header) {
        $byName[trim((string)$header)] = $col;
    }

    $resolved = [];
    foreach ($columnPairs as $skuHeader => $priceHeader) {
        if (!isset($byName[$skuHeader])) {
            throw new RuntimeException("Column was not found: {$skuHeader}");
        }
        if (!isset($byName[$priceHeader])) {
            throw new RuntimeException("Column was not found: {$priceHeader}");
        }
        $resolved[] = [
            'skuHeader' => $skuHeader,
            'skuCol' => $byName[$skuHeader],
            'priceHeader' => $priceHeader,
            'priceCol' => $byName[$priceHeader],
        ];
    }
    return $resolved;
}

function collectSkus(array $rows, array $columnIndexes): array
{
    $skus = [];
    foreach ($rows as $cells) {
        foreach ($columnIndexes as $pair) {
            $sku = normalizeSku((string)($cells[$pair['skuCol']] ?? ''));
            if ($sku !== '') {
                $skus[$sku] = $sku;
            }
        }
    }
    return $skus;
}

function updatePriceCells(array $xlsx, array $rows, array $columnIndexes, array $prices): array
{
    $stats = ['updated' => 0, 'missing' => 0];

    foreach ($rows as $rowNumber => $cells) {
        foreach ($columnIndexes as $pair) {
            $sku = normalizeSku((string)($cells[$pair['skuCol']] ?? ''));
            if ($sku === '') {
                continue;
            }
            if (!array_key_exists($sku, $prices)) {
                $stats['missing']++;
                continue;
            }

            setNumericCell($xlsx['sheet'], $rowNumber, $pair['priceCol'], $prices[$sku]);
            $stats['updated']++;
        }
    }

    return $stats;
}

function setNumericCell(DOMDocument $sheet, int $rowNumber, int $columnIndex, string $value): void
{
    $xpath = new DOMXPath($sheet);
    $xpath->registerNamespace('x', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main');

    $sheetData = $xpath->query('//x:sheetData')->item(0);
    if (!$sheetData) {
        throw new RuntimeException('sheetData node was not found.');
    }

    $row = $xpath->query(sprintf('//x:sheetData/x:row[@r="%d"]', $rowNumber))->item(0);
    if (!$row) {
        $row = $sheet->createElementNS('http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'row');
        $row->setAttribute('r', (string)$rowNumber);
        appendRowSorted($sheetData, $row, $rowNumber);
    }

    $cellRef = columnIndexToName($columnIndex) . $rowNumber;
    $cell = $xpath->query(sprintf('x:c[@r="%s"]', $cellRef), $row)->item(0);
    if (!$cell) {
        $cell = $sheet->createElementNS('http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'c');
        $cell->setAttribute('r', $cellRef);
        appendCellSorted($row, $cell, $columnIndex);
    }

    while ($cell->firstChild) {
        $cell->removeChild($cell->firstChild);
    }
    $cell->removeAttribute('t');

    $v = $sheet->createElementNS('http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'v');
    $v->appendChild($sheet->createTextNode($value));
    $cell->appendChild($v);
}

function appendRowSorted(DOMElement $sheetData, DOMElement $newRow, int $newRowNumber): void
{
    foreach ($sheetData->childNodes as $child) {
        if ($child instanceof DOMElement && $child->localName === 'row' && (int)$child->getAttribute('r') > $newRowNumber) {
            $sheetData->insertBefore($newRow, $child);
            return;
        }
    }
    $sheetData->appendChild($newRow);
}

function appendCellSorted(DOMElement $row, DOMElement $newCell, int $newColumnIndex): void
{
    foreach ($row->childNodes as $child) {
        if (!$child instanceof DOMElement || $child->localName !== 'c') {
            continue;
        }
        $ref = $child->getAttribute('r');
        $col = columnNameToIndex(preg_replace('/\d+/', '', $ref));
        if ($col > $newColumnIndex) {
            $row->insertBefore($newCell, $child);
            return;
        }
    }
    $row->appendChild($newCell);
}

function writeXlsx(array $xlsx, string $outputFile): void
{
    $files = $xlsx['files'];
    $files[$xlsx['sheetPath']] = $xlsx['sheet']->saveXML();

    $zip = new ZipArchive();
    if ($zip->open($outputFile, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
        throw new RuntimeException("Cannot write xlsx: {$outputFile}");
    }

    foreach ($files as $name => $content) {
        $zip->addFromString($name, $content);
    }
    $zip->close();
}

function columnNameToIndex(string $name): int
{
    $name = strtoupper($name);
    $index = 0;
    for ($i = 0, $len = strlen($name); $i < $len; $i++) {
        $index = $index * 26 + (ord($name[$i]) - 64);
    }
    return $index;
}

function columnIndexToName(int $index): string
{
    $name = '';
    while ($index > 0) {
        $index--;
        $name = chr(65 + ($index % 26)) . $name;
        $index = intdiv($index, 26);
    }
    return $name;
}

function startsWith(string $value, string $prefix): bool
{
    return substr($value, 0, strlen($prefix)) === $prefix;
}

function contains(string $value, string $needle): bool
{
    return $needle === '' || strpos($value, $needle) !== false;
}
