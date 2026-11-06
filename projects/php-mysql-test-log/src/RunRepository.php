<?php
declare(strict_types=1);
namespace TestLog;
use PDO;
use Throwable;

final class RunRepository
{
    public function __construct(private readonly PDO $db) {}

    public function create(array $run): int
    {
        $this->db->beginTransaction();
        try {
            $this->db->prepare('INSERT INTO test_runs (sample, notes) VALUES (?, ?)')->execute([$run['sample'], $run['notes']]);
            $id = (int)$this->db->lastInsertId();
            $statement = $this->db->prepare('INSERT INTO measurements (run_id, name, unit, value, lower_limit, upper_limit) VALUES (?, ?, ?, ?, ?, ?)');
            foreach ($run['measurements'] as $m) {
                $statement->execute([$id, $m['name'], $m['unit'], $m['value'], $m['lower_limit'], $m['upper_limit']]);
            }
            $this->db->commit();
            return $id;
        } catch (Throwable $e) {
            $this->db->rollBack();
            throw $e;
        }
    }

    public function find(int $id): ?array
    {
        $statement = $this->db->prepare('SELECT id, sample, notes, created_at FROM test_runs WHERE id = ?');
        $statement->execute([$id]);
        $run = $statement->fetch();
        if (!$run) { return null; }
        $statement = $this->db->prepare('SELECT name, unit, value, lower_limit, upper_limit, (value BETWEEN lower_limit AND upper_limit) AS passed FROM measurements WHERE run_id = ? ORDER BY id');
        $statement->execute([$id]);
        $run['measurements'] = array_map(static function (array $m): array {
            $m['passed'] = (bool)$m['passed'];
            return $m;
        }, $statement->fetchAll());
        $run['passed'] = !in_array(false, array_column($run['measurements'], 'passed'), true);
        return $run;
    }

    public function recent(int $page = 1, string $status = 'all'): array
    {
        $where = match ($status) {
            'pass' => 'WHERE NOT EXISTS (SELECT 1 FROM measurements m WHERE m.run_id = r.id AND (m.value < m.lower_limit OR m.value > m.upper_limit))',
            'fail' => 'WHERE EXISTS (SELECT 1 FROM measurements m WHERE m.run_id = r.id AND (m.value < m.lower_limit OR m.value > m.upper_limit))',
            default => '',
        };
        $statement = $this->db->prepare("SELECT r.id, r.sample, r.created_at, COUNT(m.id) AS readings, MIN(m.value BETWEEN m.lower_limit AND m.upper_limit) AS passed FROM test_runs r JOIN measurements m ON m.run_id = r.id $where GROUP BY r.id ORDER BY r.id DESC LIMIT 21 OFFSET ?");
        $statement->bindValue(1, ($page - 1) * 20, PDO::PARAM_INT);
        $statement->execute();
        $rows = array_map(static function (array $row): array {
            $row['passed'] = (bool)$row['passed'];
            return $row;
        }, $statement->fetchAll());
        return ['runs' => array_slice($rows, 0, 20), 'has_more' => count($rows) > 20, 'page' => $page];
    }
}
