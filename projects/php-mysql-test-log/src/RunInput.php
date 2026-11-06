<?php
declare(strict_types=1);
namespace TestLog;

final class RunInput
{
    private static function compareDecimal(string $a, string $b): int
    {
        $normalize = static function (string $v): string {
            [$whole, $fraction] = array_pad(explode('.', ltrim($v, '-')), 2, '');
            return str_pad($whole, 12, '0', STR_PAD_LEFT) . str_pad($fraction, 6, '0');
        };
        $aa = $normalize($a);
        $bb = $normalize($b);
        $negativeA = str_starts_with($a, '-') && trim($aa, '0') !== '';
        $negativeB = str_starts_with($b, '-') && trim($bb, '0') !== '';
        if ($negativeA !== $negativeB) { return $negativeA ? -1 : 1; }
        return strcmp($aa, $bb) * ($negativeA ? -1 : 1);
    }

    public static function validate(mixed $input): array
    {
        if (!is_array($input) || array_is_list($input)) {
            throw new ValidationException(['body' => 'Send a JSON object.']);
        }
        $errors = [];
        $text = static function (mixed $v, string $path, int $max, bool $required = true) use (&$errors): string {
            if (!is_string($v) || !mb_check_encoding($v, 'UTF-8')) {
                $errors[$path] = 'Use text.';
                return '';
            }
            $hasControl = preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', $v);
            $v = trim($v);
            if (($required && $v === '') || mb_strlen($v) > $max || $hasControl) {
                $errors[$path] = "Use " . ($required ? '1' : '0') . " to $max characters without control characters.";
            }
            return $v;
        };
        $sample = $text($input['sample'] ?? null, 'sample', 120);
        $notes = $text($input['notes'] ?? '', 'notes', 2000, false);
        $items = $input['measurements'] ?? null;
        if (!is_array($items) || !array_is_list($items) || count($items) < 1 || count($items) > 100) {
            $errors['measurements'] = 'Include 1 to 100 measurements.';
            $items = [];
        }
        $measurements = [];
        $names = [];
        foreach ($items as $i => $m) {
            $prefix = "measurements.$i";
            if (!is_array($m) || array_is_list($m)) { $errors[$prefix] = 'Use a measurement object.'; continue; }
            $name = $text($m['name'] ?? null, "$prefix.name", 80);
            // Reject duplicate names ignoring case before the database uniqueness check.
            $key = mb_strtolower($name);
            if (isset($names[$key])) { $errors["$prefix.name"] = 'Use a different measurement name in this run.'; }
            $names[$key] = true;
            $unit = $text($m['unit'] ?? null, "$prefix.unit", 24);
            $numbers = [];
            foreach (['value', 'lower_limit', 'upper_limit'] as $field) {
                $v = $m[$field] ?? null;
                // Decimal strings preserve instrument precision and reject coercions, exponents and NaN.
                if ((!is_string($v) && !is_int($v) && !is_float($v)) ||
                    !preg_match('/^-?\d{1,12}(?:\.\d{1,6})?$/D', (string)$v)) {
                    $errors["$prefix.$field"] = 'Use a decimal with at most 12 whole digits and 6 decimal places.';
                } else { $numbers[$field] = (string)$v; }
            }
            if (isset($numbers['lower_limit'], $numbers['upper_limit']) && self::compareDecimal($numbers['lower_limit'], $numbers['upper_limit']) > 0) {
                $errors["$prefix.upper_limit"] = 'The upper limit must be at least the lower limit.';
            }
            $measurements[] = ['name' => $name, 'unit' => $unit] + $numbers;
        }
        if ($errors) { throw new ValidationException($errors); }
        return compact('sample', 'notes', 'measurements');
    }
}
