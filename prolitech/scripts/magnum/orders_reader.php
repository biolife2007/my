<?php
// Read-only order data for the Telegram notifier. Never callable over HTTP.
if (PHP_SAPI !== 'cli') { http_response_code(403); exit; }
$sites = ['prolitech' => '/home/rvbkkxiv/public_html', 'prolimax' => '/home/rvbkkxiv/prolimax.com.ua'];
$site = $argv[1] ?? '';
if (!isset($sites[$site])) { fwrite(STDERR, "Unknown site\n"); exit(1); }
require $sites[$site] . '/config.php';
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
try {
    $db = new mysqli(DB_HOSTNAME, DB_USERNAME, DB_PASSWORD, DB_DATABASE, defined('DB_PORT') ? (int)DB_PORT : 3306);
    $db->set_charset('utf8mb4');
    $prefix = DB_PREFIX;
    if (!preg_match('/^[a-zA-Z0-9_]*$/', $prefix)) { throw new Exception('Invalid prefix'); }
    $max = (int)$db->query("SELECT COALESCE(MAX(order_history_id),0) AS id FROM `{$prefix}order_history`")->fetch_assoc()['id'];
    $orders = [];
    if (isset($argv[2])) {
        $since = (int)$argv[2];
        // Only the first positive history entry denotes a newly placed order.
        // A draft created earlier but completed later is included correctly.
        $sql = "SELECT h.order_history_id, o.order_id, o.date_added, o.total, o.currency_code, o.currency_value
          FROM `{$prefix}order_history` h JOIN `{$prefix}order` o ON o.order_id=h.order_id
          WHERE h.order_history_id > {$since} AND h.order_history_id <= {$max} AND h.order_status_id > 0
          AND NOT EXISTS (SELECT 1 FROM `{$prefix}order_history` prev
            WHERE prev.order_id=h.order_id AND prev.order_status_id > 0 AND prev.order_history_id < h.order_history_id)
          ORDER BY h.order_history_id";
        $orders = $db->query($sql)->fetch_all(MYSQLI_ASSOC);
    }
    echo json_encode(['max_history_id' => $max, 'orders' => $orders], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
} catch (Throwable $e) {
    fwrite(STDERR, "Order database read failed for {$site}\n"); exit(1);
}
