<?php
declare(strict_types=1);
namespace TestLogTests;
use PDO;
use TestLog\{Database, Migrator};

final class Fixture
{
    public static function run(): array
    {
        return ['sample' => 'Synthetic resistor A', 'notes' => 'Bench check', 'measurements' => [
            ['name' => 'Resistance', 'unit' => 'ohm', 'value' => '101.200001', 'lower_limit' => '95', 'upper_limit' => '105'],
        ]];
    }
    public static function database(): PDO
    {
        if (!str_ends_with(getenv('DB_NAME') ?: '', '_test')) {
            throw new \RuntimeException('Refusing to clear a database without a DB_NAME ending in _test.');
        }
        $db = Database::connect();
        Migrator::run($db);
        $db->exec('DELETE FROM measurements');
        $db->exec('DELETE FROM test_runs');
        return $db;
    }
}
