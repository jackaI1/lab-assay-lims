<?php
declare(strict_types=1);
namespace TestLogTests;
require_once __DIR__ . '/Fixture.php';
use PDO;
use PDOException;
use PHPUnit\Framework\TestCase;
use TestLog\{Migrator, RunInput, RunRepository};

final class MySqlTest extends TestCase
{
    private PDO $db;
    private RunRepository $repo;
    protected function setUp(): void { $this->db = Fixture::database(); $this->repo = new RunRepository($this->db); }
    public function testMigrationsAreRepeatableOnMySql(): void
    {
        Migrator::run($this->db); Migrator::run($this->db);
        self::assertSame('1', (string)$this->db->query('SELECT COUNT(*) FROM schema_migrations')->fetchColumn());
        self::assertStringContainsString('8.4', $this->db->query('SELECT VERSION()')->fetchColumn());
        self::assertFalse($this->db->getAttribute(PDO::ATTR_EMULATE_PREPARES));
    }
    public function testStoresExactDecimalsAndSqlInjectionAsText(): void
    {
        $input = Fixture::run(); $input['sample'] = "A'); DROP TABLE test_runs; --";
        $input['notes'] = '<script>alert(1)</script>';
        $run = $this->repo->find($this->repo->create(RunInput::validate($input)));
        self::assertSame($input['sample'], $run['sample']);
        self::assertSame($input['notes'], $run['notes']);
        self::assertSame('101.200001', $run['measurements'][0]['value']);
        self::assertTrue($run['passed']);
    }
    public function testInclusiveLimitsAndOneFailedReadingFailTheRun(): void
    {
        $input = Fixture::run();
        $input['measurements'] = [
            ['name'=>'Lower', 'unit'=>'V', 'value'=>'-1', 'lower_limit'=>'-1','upper_limit'=>'1'],
            ['name'=>'Upper', 'unit'=>'V', 'value'=>'1', 'lower_limit'=>'-1','upper_limit'=>'1'],
            ['name'=>'Outside', 'unit'=>'V', 'value'=>'1.000001', 'lower_limit'=>'-1','upper_limit'=>'1'],
        ];
        $run = $this->repo->find($this->repo->create(RunInput::validate($input)));
        self::assertSame([true,true,false], array_column($run['measurements'], 'passed'));
        self::assertFalse($run['passed']);
    }
    public function testFullPrecisionLimitsAreComparedByMySql(): void
    {
        $input = Fixture::run();
        $input['measurements'][0]['value'] = '999999999999.000002';
        $input['measurements'][0]['lower_limit'] = '999999999999.000001';
        $input['measurements'][0]['upper_limit'] = '999999999999.000001';
        $run = $this->repo->find($this->repo->create(RunInput::validate($input)));
        self::assertFalse($run['passed']);
        self::assertSame('999999999999.000002', $run['measurements'][0]['value']);
    }
    public function testFailedMeasurementInsertRollsBackWholeRun(): void
    {
        $input = Fixture::run(); $input['measurements'][] = $input['measurements'][0];
        try { $this->repo->create($input); self::fail('Duplicate reading should fail.'); }
        catch (PDOException) {
            self::assertSame(0, (int)$this->db->query('SELECT COUNT(*) FROM test_runs')->fetchColumn());
            self::assertSame(0, (int)$this->db->query('SELECT COUNT(*) FROM measurements')->fetchColumn());
        }
    }
    public function testStatusFilterAndStablePagination(): void
    {
        for ($i=0; $i<22; $i++) { $this->repo->create(RunInput::validate(Fixture::run())); }
        $input = Fixture::run(); $input['measurements'][0]['value']='200';
        $failedId = $this->repo->create(RunInput::validate($input));
        $first = $this->repo->recent(); $second = $this->repo->recent(2);
        self::assertCount(20, $first['runs']); self::assertTrue($first['has_more']);
        self::assertCount(3, $second['runs']); self::assertFalse($second['has_more']);
        self::assertSame([], array_intersect(array_column($first['runs'], 'id'), array_column($second['runs'], 'id')));
        self::assertSame([$failedId], array_column($this->repo->recent(1, 'fail')['runs'], 'id'));
        self::assertCount(20, $this->repo->recent(1, 'pass')['runs']);
        self::assertNull($this->repo->find(999999999));
    }
}
