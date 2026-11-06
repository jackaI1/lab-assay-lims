<?php
declare(strict_types=1);
namespace TestLog;
use PDO;
use RuntimeException;

final class Migrator
{
    public static function run(PDO $db): void
    {
        if (!$db->query("SELECT GET_LOCK('testlog_migrations', 15)")->fetchColumn()) {
            throw new RuntimeException('Could not lock migrations.');
        }
        try {
            $db->exec('CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)');
            foreach (glob(__DIR__ . '/../migrations/*.sql') as $file) {
                $version = basename($file);
                $check = $db->prepare('SELECT 1 FROM schema_migrations WHERE version = ?');
                $check->execute([$version]);
                if ($check->fetchColumn()) { continue; }
                // MySQL DDL commits implicitly. Each file must be safe to retry after interruption.
                foreach (explode(';', file_get_contents($file)) as $sql) {
                    if (trim($sql) !== '') { $db->exec($sql); }
                }
                $db->prepare('INSERT INTO schema_migrations (version) VALUES (?)')->execute([$version]);
            }
        } finally {
            $db->query("SELECT RELEASE_LOCK('testlog_migrations')");
        }
    }
}
