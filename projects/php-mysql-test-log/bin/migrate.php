<?php
declare(strict_types=1);
require __DIR__ . '/../vendor/autoload.php';
TestLog\Migrator::run(TestLog\Database::connect());
echo "Database is up to date.\n";
