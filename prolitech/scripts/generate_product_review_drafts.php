<?php

declare(strict_types=1);

const DEFAULT_ENV = __DIR__ . '/../.env_open';
const LEGACY_AUTO_DRAFT_MARKER = '[AUTO_DRAFT_V1]';
const DAILY_LIMIT = 3;
const SCHEDULE_HOURS = [10, 15, 20];
// PHP 7.4 on the hosting server ships an older tzdata alias set.
const TIMEZONE = 'Europe/Kiev';

function loadEnv(string $path): array
{
    if (!is_file($path)) {
        throw new RuntimeException("Environment file not found: {$path}");
    }

    $env = [];
    foreach (file($path, FILE_IGNORE_NEW_LINES) ?: [] as $line) {
        $line = trim($line);
        if ($line === '' || strpos($line, '#') === 0 || strpos($line, '=') === false) {
            continue;
        }
        [$key, $value] = explode('=', $line, 2);
        $env[trim($key)] = trim($value);
    }

    foreach (['DB_HOST', 'DB_DATABASE', 'DB_USERNAME', 'DB_PASSWORD'] as $key) {
        if (!array_key_exists($key, $env)) {
            throw new RuntimeException("Missing {$key} in {$path}");
        }
    }

    return $env;
}

function connect(array $env): PDO
{
    $dsn = sprintf(
        'mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
        $env['DB_HOST'],
        (int)($env['DB_PORT'] ?? 3306),
        $env['DB_DATABASE']
    );

    return new PDO($dsn, $env['DB_USERNAME'], $env['DB_PASSWORD'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
}

function quoteIdentifier(string $value): string
{
    if (!preg_match('/^[A-Za-z0-9_]+$/', $value)) {
        throw new RuntimeException("Unsafe SQL identifier: {$value}");
    }
    return '`' . $value . '`';
}

function dueCount(DateTimeImmutable $now): int
{
    $hour = (int)$now->format('G');
    $count = 0;
    foreach (SCHEDULE_HOURS as $scheduledHour) {
        if ($hour >= $scheduledHour) {
            ++$count;
        }
    }
    return min($count, DAILY_LIMIT);
}

function buildText(string $productName, int $lengthIndex): string
{
    $name = trim(preg_replace('/\s+/u', ' ', $productName) ?? $productName);
    $normalized = mb_strtolower($name, 'UTF-8');

    if (containsAny($normalized, ['дріждж'])) {
        $templates = [
            "У характеристиках «{$name}» особливо цікаві рекомендована температура бродіння та витрата на один літр сусла.",
            "У випадку з {$name} хотілося б бачити точні дані про допустиму температуру, тривалість бродіння й рекомендований тип сировини. Саме ці параметри найкраще показують, для якого рецепта вони підійдуть.",
            "{$name} варто оцінювати не лише за фасуванням, а й за температурним діапазоном, стійкістю до спирту та прогнозованим профілем аромату. Корисно було б додати таблицю дозування для різного об'єму сусла й зазначити, чи потрібна попередня регідратація. Така інформація значно спростила б вибір між кількома штамами.",
        ];
    } elseif (containsAny($normalized, ['квасн', 'концентрат квас'])) {
        $templates = [
            "Щодо «{$name}» головне питання — скільки готового напою виходить з однієї упаковки.",
            "{$name} виглядає зручним форматом для домашнього квасу. Було б корисно одразу вказати пропорцію розведення, рекомендовану кількість цукру та орієнтовний час бродіння.",
            "В описі {$name} найбільше цікавлять склад і точна схема приготування: пропорція води, кількість цукру, температура та час витримки. Також доречно зазначити, який смак виходить у готового напою — більш хлібний, солодовий чи з помітною кислинкою. Це допоможе підібрати концентрат під бажаний результат.",
        ];
    } elseif (containsAny($normalized, ['солод', 'солодовий екстракт'])) {
        $templates = [
            "В описі «{$name}» було б корисно вказати колірність EBC і рекомендовану частку в засипі.",
            "{$name} цікавий насамперед своїм впливом на колір, аромат і щільність напою. Хотілося б бачити дані про країну походження, колірність та рецепти, де він розкривається найкраще.",
            "Під час вибору {$name} важливі не лише вага й виробник, а й колірність EBC, екстрактивність та рекомендована частка в рецепті. Якщо це базовий солод, корисно знати його ферментативну активність; якщо спеціальний — які смакові відтінки він додає. Такий опис був би значно кориснішим для точного розрахунку засипу.",
        ];
    } elseif (containsAny($normalized, ['набір спецій', 'настоянк', 'спеці'])) {
        $templates = [
            "Для суміші «{$name}» цікаво знати повний склад і на який об'єм напою вона розрахована.",
            "{$name} може помітно спростити підбір спецій для рецепта. Не вистачає лише рекомендацій щодо об'єму основи, тривалості настоювання та бажаної міцності напою.",
            "Для {$name} хотілося б бачити не тільки перелік інгредієнтів, а й коротку схему настоювання: об'єм основи, рекомендовану міцність, час витримки та потребу у фільтрації. Цікаво також, які ноти мають переважати в готовому ароматі. Це дозволило б точніше зрозуміти характер суміші ще до приготування.",
        ];
    } elseif (containsAny($normalized, ['колона', 'самогонний апарат', 'сухопарник', 'дефлегматор', 'дистилятор', 'охолоджувач'])) {
        $templates = [
            "У характеристиках «{$name}» хотілося б уточнити робочу висоту конструкції та потрібну витрату води на охолодження.",
            "У {$name} важливі діаметр з'єднань, продуктивність охолоджувача та сумісність із різними кубами. Ці параметри дали б змогу швидко зрозуміти, чи підійде обладнання до вже наявної системи.",
            "{$name} має цікаву конфігурацію, але для обґрунтованого вибору потрібні точні технічні дані: загальна висота в зборі, діаметр і тип з'єднань, потужність нагріву, з якою справляється холодильник, та орієнтовна витрата води. Для моделей із сухопарниками або дефлегматором доречно також описати спосіб обслуговування й очищення. Саме такі подробиці дозволяють реально порівняти комплекти між собою.",
        ];
    } elseif (containsAny($normalized, ['мідн', 'мідь'])) {
        $templates = [
            "В описі «{$name}» цікаво дізнатися товщину міді та рекомендації щодо догляду за поверхнею.",
            "{$name} привертає увагу матеріалом і формою. Було б корисно уточнити товщину стінок, фактичний об'єм та чи має внутрішня поверхня захисне покриття.",
            "Під час вибору {$name} важливі товщина металу, якість швів і спосіб обробки внутрішньої поверхні. Окремо хотілося б бачити рекомендації з очищення міді, щоб вона довше зберігала вигляд. Якщо виріб контактує з напоями, доречно також зазначити корисний об'єм і допустимі умови використання.",
        ];
    } elseif (containsAny($normalized, ['обігрівач', 'нагрівач', 'тен ', 'терморегулятор'])) {
        $templates = [
            "Для моделі «{$name}» ключовими є реальна потужність, діапазон регулювання та захист від перегріву.",
            "{$name} варто порівнювати за потужністю, точністю підтримання температури й типом підключення. Також корисно знати розміри та рекомендовані умови встановлення.",
            "В описі {$name} хотілося б бачити робочий діапазон температур, точність регулювання, клас захисту та спосіб монтажу. Для нагрівального обладнання важливі також довжина кабелю й наявність захисту від перегріву. Ці деталі допомагають оцінити не лише продуктивність, а й зручність щоденного використання.",
        ];
    } else {
        $templates = [
            "В описі «{$name}» хотілося б бачити точні розміри, матеріал і повну комплектацію.",
            "Назва {$name} одразу пояснює призначення, але для порівняння бракує конкретики: розмірів, матеріалу, сумісності та переліку того, що входить до комплекту.",
            "Для {$name} корисно було б додати кілька практичних деталей: точні розміри, матеріал основних частин, комплектацію та обмеження щодо сумісності. Не менш цікаві рекомендації виробника з догляду й типові сценарії застосування. Такий опис допоміг би оцінити товар за конкретними параметрами, а не лише за назвою.",
        ];
    }

    return $templates[$lengthIndex % count($templates)];
}

function containsAny(string $text, array $needles): bool
{
    foreach ($needles as $needle) {
        if (mb_stripos($text, $needle, 0, 'UTF-8') !== false) {
            return true;
        }
    }
    return false;
}

function isQuestionText(string $text): bool
{
    return containsAny(mb_strtolower($text, 'UTF-8'), [
        '?', 'хотілося б', 'цікаво знати', 'цікаво дізнатися',
        'було б корисно', 'корисно було б', 'не вистачає',
        'головне питання', 'уточнити',
    ]);
}

function buildAuthor(int $daySeed, int $draftIndex): string
{
    // Twenty slots: 80% male, 20% female; 10% Latin and 10% patronymic forms.
    // The step of 7 is coprime with 20, so all slots are used evenly over time.
    $authors = [
        'Олексій', 'Андрій', 'Максим', 'Сергій', 'Дмитро',
        'Віталій', 'Ігор', 'Роман', 'Тарас', 'Богдан',
        'Юрій', 'Микола', 'Володимир', 'Наталія', 'Ірина',
        'Олена', 'Oleksii', 'Andrii', 'Дмитро Олександрович', 'Наталія Іванівна',
    ];
    return $authors[($daySeed + $draftIndex * 7) % count($authors)];
}

function buildRating(int $daySeed, int $draftIndex): int
{
    // Four of every five deterministic slots receive 5; one receives 4.
    return (($daySeed + $draftIndex * 3) % 5 === 0) ? 4 : 5;
}

function main(array $argv): int
{
    $apply = in_array('--apply', $argv, true) || getenv('REVIEW_DRAFTS_APPLY') === '1';
    $envPath = DEFAULT_ENV;
    foreach ($argv as $index => $arg) {
        if ($arg === '--env' && isset($argv[$index + 1])) {
            $envPath = $argv[$index + 1];
        }
    }

    date_default_timezone_set(TIMEZONE);
    $now = new DateTimeImmutable('now', new DateTimeZone(TIMEZONE));
    $hour = (int)$now->format('G');
    if ($apply && ($hour < 9 || $hour > 21)) {
        throw new RuntimeException('Apply mode is allowed only from 09:00 through 21:59 Europe/Kyiv.');
    }

    $env = loadEnv($envPath);
    $prefix = $env['DB_PREFIX'] ?? '';
    $productTable = quoteIdentifier($prefix . 'product');
    $descriptionTable = quoteIdentifier($prefix . 'product_description');
    $reviewTable = quoteIdentifier($prefix . 'review');
    $faqTable = quoteIdentifier($prefix . 'oct_faq');
    $trackingTable = quoteIdentifier($prefix . 'auto_review_draft');
    $faqTrackingTable = quoteIdentifier($prefix . 'auto_faq_draft');
    $pdo = connect($env);

    $pdo->exec("CREATE TABLE IF NOT EXISTS {$trackingTable} (
        review_id INT(11) NOT NULL,
        date_added DATETIME NOT NULL,
        PRIMARY KEY (review_id),
        KEY date_added (date_added)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS {$faqTrackingTable} (
        faq_id INT(11) NOT NULL,
        date_added DATETIME NOT NULL,
        PRIMARY KEY (faq_id),
        KEY date_added (date_added)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    // One-time migration from the former use of the administrator reply field.
    $migrateInsert = $pdo->prepare(
        "INSERT IGNORE INTO {$trackingTable} (review_id, date_added)
         SELECT review_id, date_added FROM {$reviewTable} WHERE reply = :legacy_marker"
    );
    $migrateInsert->execute(['legacy_marker' => LEGACY_AUTO_DRAFT_MARKER]);
    $migrateClear = $pdo->prepare(
        "UPDATE {$reviewTable} SET reply = '' WHERE reply = :legacy_marker"
    );
    $migrateClear->execute(['legacy_marker' => LEGACY_AUTO_DRAFT_MARKER]);
    if ($migrateClear->rowCount() > 0) {
        echo 'migrated_legacy_drafts=' . $migrateClear->rowCount() . " reply=empty\n";
    }

    $lockName = ($env['DB_DATABASE'] ?? 'db') . ':product-review-drafts';
    $lockStatement = $pdo->prepare('SELECT GET_LOCK(:lock_name, 5)');
    $lockStatement->execute(['lock_name' => $lockName]);
    if ((int)$lockStatement->fetchColumn() !== 1) {
        throw new RuntimeException('Could not acquire the review draft lock.');
    }

    try {
        if (getenv('REVIEW_DRAFTS_ROUTE_TODAY') === '1') {
            $routeSelect = $pdo->query(
                "SELECT r.review_id, r.product_id, r.customer_id, r.author, r.text,
                        r.status, r.date_added, r.date_modified
                 FROM {$reviewTable} r
                 JOIN {$trackingTable} t ON t.review_id = r.review_id
                 WHERE r.status = 0
                   AND r.date_added >= CURDATE()
                   AND r.date_added < CURDATE() + INTERVAL 1 DAY
                 ORDER BY r.review_id"
            );
            foreach ($routeSelect->fetchAll() as $draft) {
                if (!isQuestionText((string)$draft['text'])) {
                    continue;
                }
                $pdo->beginTransaction();
                try {
                    $moveToFaq = $pdo->prepare(
                        "INSERT INTO {$faqTable}
                            (product_id, customer_id, author, text, email, answer, status, date_added, date_modified)
                         VALUES
                            (:product_id, :customer_id, :author, :text, '', '', 0, :date_added, :date_modified)"
                    );
                    $moveToFaq->execute([
                        'product_id' => (int)$draft['product_id'],
                        'customer_id' => (int)$draft['customer_id'],
                        'author' => $draft['author'],
                        'text' => $draft['text'],
                        'date_added' => $draft['date_added'],
                        'date_modified' => $draft['date_modified'],
                    ]);
                    $faqId = (int)$pdo->lastInsertId();
                    $faqTrack = $pdo->prepare(
                        "INSERT INTO {$faqTrackingTable} (faq_id, date_added)
                         VALUES (:faq_id, :date_added)"
                    );
                    $faqTrack->execute(['faq_id' => $faqId, 'date_added' => $draft['date_added']]);
                    $deleteTrack = $pdo->prepare(
                        "DELETE FROM {$trackingTable} WHERE review_id = :review_id"
                    );
                    $deleteTrack->execute(['review_id' => (int)$draft['review_id']]);
                    $deleteReview = $pdo->prepare(
                        "DELETE FROM {$reviewTable} WHERE review_id = :review_id AND status = 0"
                    );
                    $deleteReview->execute(['review_id' => (int)$draft['review_id']]);
                    $pdo->commit();
                    echo sprintf(
                        "routed_review_id=%d to_faq_id=%d status=0 answer=empty\n",
                        (int)$draft['review_id'],
                        $faqId
                    );
                } catch (Throwable $routeError) {
                    $pdo->rollBack();
                    throw $routeError;
                }
            }
        }

        if (getenv('REVIEW_DRAFTS_REFRESH_TODAY') === '1') {
            $refreshSelectSql = "SELECT r.review_id, pd.name
                FROM {$reviewTable} r
                JOIN {$trackingTable} t ON t.review_id = r.review_id
                JOIN {$descriptionTable} pd
                  ON pd.product_id = r.product_id
                 AND pd.language_id = 1
                WHERE r.status = 0
                  AND r.date_added >= CURDATE()
                  AND r.date_added < CURDATE() + INTERVAL 1 DAY
                ORDER BY r.review_id";
            $refreshSelect = $pdo->prepare($refreshSelectSql);
            $refreshSelect->execute();
            $todayDrafts = $refreshSelect->fetchAll();
            $refreshUpdate = $pdo->prepare(
                "UPDATE {$reviewTable} SET text = :text, date_modified = NOW()
                 WHERE review_id = :review_id AND status = 0"
            );
            foreach ($todayDrafts as $draftIndex => $draft) {
                $newText = buildText((string)$draft['name'], $draftIndex % 3);
                $refreshUpdate->execute([
                    'text' => $newText,
                    'review_id' => (int)$draft['review_id'],
                ]);
                echo sprintf(
                    "refreshed_review_id=%d length=%d name=%s text=%s\n",
                    (int)$draft['review_id'],
                    mb_strlen($newText),
                    $draft['name'],
                    $newText
                );
            }
        }

        $countSql = "SELECT COUNT(*) FROM (
                SELECT r.date_added
                FROM {$reviewTable} r
                JOIN {$trackingTable} t ON t.review_id = r.review_id
                WHERE r.status = 0
                UNION ALL
                SELECT f.date_added
                FROM {$faqTable} f
                JOIN {$faqTrackingTable} t ON t.faq_id = f.faq_id
                WHERE f.status = 0
            ) generated
            WHERE date_added >= CURDATE()
              AND date_added < CURDATE() + INTERVAL 1 DAY";
        $countStatement = $pdo->prepare($countSql);
        $countStatement->execute();
        $existingToday = (int)$countStatement->fetchColumn();
        $targetToday = dueCount($now);
        $toCreate = max(0, min(DAILY_LIMIT - $existingToday, $targetToday - $existingToday));

        $productsSql = "SELECT p.product_id, p.viewed, pd.name
            FROM {$productTable} p
            JOIN {$descriptionTable} pd
              ON pd.product_id = p.product_id
             AND pd.language_id = 1
            WHERE p.status = 1
              AND p.viewed > 0
              AND NOT EXISTS (
                SELECT 1
                FROM {$reviewTable} r
                JOIN {$trackingTable} t ON t.review_id = r.review_id
                WHERE r.product_id = p.product_id
                  AND r.date_added >= CURDATE() - INTERVAL 30 DAY
              )
              AND NOT EXISTS (
                SELECT 1
                FROM {$faqTable} f
                JOIN {$faqTrackingTable} t ON t.faq_id = f.faq_id
                WHERE f.product_id = p.product_id
                  AND f.date_added >= CURDATE() - INTERVAL 30 DAY
              )
            ORDER BY p.viewed DESC, p.product_id DESC
            LIMIT 50";
        $productStatement = $pdo->prepare($productsSql);
        $productStatement->execute();
        $products = $productStatement->fetchAll();

        if ($toCreate > 0 && count($products) < $toCreate) {
            throw new RuntimeException('Not enough eligible viewed products to create drafts.');
        }

        $daySeed = (int)$now->format('Ymd');
        $offset = count($products) > 0 ? $daySeed % count($products) : 0;
        $selected = [];
        for ($i = 0; $i < $toCreate; ++$i) {
            $selected[] = $products[($offset + $existingToday + $i) % count($products)];
        }

        echo sprintf(
            "mode=%s date=%s existing=%d due=%d create=%d\n",
            $apply ? 'apply' : 'dry-run',
            $now->format('Y-m-d H:i:s T'),
            $existingToday,
            $targetToday,
            $toCreate
        );

        foreach ($selected as $index => $product) {
            $lengthIndex = ($existingToday + $index) % 3;
            $text = buildText((string)$product['name'], $lengthIndex);
            $author = buildAuthor($daySeed, $existingToday + $index);
            $rating = buildRating($daySeed, $existingToday + $index);
            $isQuestion = isQuestionText($text);
            echo sprintf(
                "type=%s product_id=%d viewed=%d author=%s rating=%s length=%d name=%s text=%s\n",
                $isQuestion ? 'question' : 'review',
                (int)$product['product_id'],
                (int)$product['viewed'],
                $author,
                $isQuestion ? '-' : (string)$rating,
                mb_strlen($text),
                $product['name'],
                $text
            );

            if (!$apply) {
                continue;
            }

            if ($isQuestion) {
                $faqInsert = $pdo->prepare(
                    "INSERT INTO {$faqTable}
                        (product_id, customer_id, author, text, email, answer, status, date_added, date_modified)
                     VALUES
                        (:product_id, 0, :author, :text, '', '', 0, NOW(), NOW())"
                );
                $faqInsert->execute([
                    'product_id' => (int)$product['product_id'],
                    'author' => $author,
                    'text' => $text,
                ]);
                $faqId = (int)$pdo->lastInsertId();
                $faqTrack = $pdo->prepare(
                    "INSERT INTO {$faqTrackingTable} (faq_id, date_added) VALUES (:faq_id, NOW())"
                );
                $faqTrack->execute(['faq_id' => $faqId]);
                echo 'inserted_faq_id=' . $faqId . " status=0 answer=empty\n";
                continue;
            }

            $insertSql = "INSERT INTO {$reviewTable}
                (product_id, customer_id, author, text, reply, rating, status, date_added, date_modified)
                VALUES
                (:product_id, 0, :author, :text, '', :rating, 0, NOW(), NOW())";
            $insertStatement = $pdo->prepare($insertSql);
            $insertStatement->execute([
                'product_id' => (int)$product['product_id'],
                'author' => $author,
                'text' => $text,
                'rating' => $rating,
            ]);
            $reviewId = (int)$pdo->lastInsertId();
            $trackStatement = $pdo->prepare(
                "INSERT INTO {$trackingTable} (review_id, date_added) VALUES (:review_id, NOW())"
            );
            $trackStatement->execute(['review_id' => $reviewId]);
            echo 'inserted_review_id=' . $reviewId . " status=0 reply=empty\n";
        }

        return 0;
    } finally {
        $releaseStatement = $pdo->prepare('SELECT RELEASE_LOCK(:lock_name)');
        $releaseStatement->execute(['lock_name' => $lockName]);
    }
}

try {
    exit(main(isset($_SERVER['argv']) && is_array($_SERVER['argv']) ? $_SERVER['argv'] : []));
} catch (Throwable $error) {
    file_put_contents('php://stderr', 'ERROR: ' . $error->getMessage() . PHP_EOL);
    exit(1);
}
