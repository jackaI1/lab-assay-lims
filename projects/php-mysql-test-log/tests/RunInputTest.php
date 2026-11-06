<?php
declare(strict_types=1);
namespace TestLogTests;
require_once __DIR__ . '/Fixture.php';
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use TestLog\{RunInput, ValidationException};

final class RunInputTest extends TestCase
{
    public function testTrimsTextAndKeepsDecimalPrecision(): void
    {
        $data = Fixture::run();
        $data['sample'] = '  Sample α  ';
        $result = RunInput::validate($data);
        self::assertSame('Sample α', $result['sample']);
        self::assertSame('101.200001', $result['measurements'][0]['value']);
    }
    public function testAcceptsNegativeAndEqualLimitsAtFullPrecision(): void
    {
        $data = Fixture::run();
        $data['measurements'][0] = ['name' => 'Offset', 'unit' => 'V', 'value' => '-999999999999.999999', 'lower_limit' => '-999999999999.999999', 'upper_limit' => '-999999999999.999999'];
        self::assertSame($data, RunInput::validate($data));
    }
    #[DataProvider('invalidInputs')]
    public function testRejectsInvalidInputs(mixed $input, string $field): void
    {
        try { RunInput::validate($input); self::fail('Input should be rejected.'); }
        catch (ValidationException $e) { self::assertArrayHasKey($field, $e->errors); }
    }
    public static function invalidInputs(): iterable
    {
        yield 'null' => [null, 'body'];
        yield 'list' => [[], 'body'];
        foreach ([null, [], true, '', '  ', str_repeat('a', 121), "x\0"] as $i => $value) {
            $data = Fixture::run(); $data['sample'] = $value;
            yield "sample $i" => [$data, 'sample'];
        }
        $data = Fixture::run(); $data['notes'] = str_repeat('x', 2001);
        yield 'long notes' => [$data, 'notes'];
        foreach ([null, [], ['key' => []], array_fill(0, 101, [])] as $i => $items) {
            $data = Fixture::run(); $data['measurements'] = $items;
            yield "measurement list $i" => [$data, 'measurements'];
        }
        $data = Fixture::run(); $data['measurements'] = [42];
        yield 'not a measurement object' => [$data, 'measurements.0'];
        foreach (['value', 'lower_limit', 'upper_limit'] as $field) {
            foreach ([null, false, [], 'NaN', 'INF', '1e3', '1.0000001', '1000000000000', ' 10', '1 OR 1=1'] as $i => $value) {
                $data = Fixture::run(); $data['measurements'][0][$field] = $value;
                yield "$field $i" => [$data, "measurements.0.$field"];
            }
        }
        foreach ([['2','1'], ['999999999999.000002','999999999999.000001'], ['-999999999999.000001','-999999999999.000002'], ['0','-0.000001']] as $i => [$lower,$upper]) {
            $data = Fixture::run(); $data['measurements'][0]['lower_limit'] = $lower; $data['measurements'][0]['upper_limit'] = $upper;
            yield "reversed limits $i" => [$data, 'measurements.0.upper_limit'];
        }
        $data = Fixture::run(); $data['measurements'][] = $data['measurements'][0];
        $data['measurements'][1]['name'] = 'resistance';
        yield 'duplicate names' => [$data, 'measurements.1.name'];
        foreach (['name' => 81, 'unit' => 25] as $field => $length) {
            $data = Fixture::run(); $data['measurements'][0][$field] = str_repeat('x', $length);
            yield "long $field" => [$data, "measurements.0.$field"];
        }
    }
}
