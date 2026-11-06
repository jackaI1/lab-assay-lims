<?php
declare(strict_types=1);
require __DIR__ . '/../vendor/autoload.php';
use TestLog\{Database, RunInput, RunRepository, ValidationException};

header('X-Content-Type-Options: nosniff');
header("Content-Security-Policy: default-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
header('Cache-Control: no-store');
function jsonResponse(int $status, array $body): never {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($body, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
    exit;
}
function positiveId(mixed $value, string $field): int {
    if (!is_string($value) || !preg_match('/^[1-9][0-9]{0,8}$/D', $value)) {
        throw new ValidationException([$field => 'Use a positive integer with at most 9 digits.']);
    }
    return (int)$value;
}
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$method = $_SERVER['REQUEST_METHOD'];
$isApi = str_starts_with($path, '/api/');
try {
    $detailRoute = preg_match('#^/api/runs/([1-9][0-9]{0,8})$#D', $path, $match);
    if (!in_array($path, ['/', '/api/runs'], true) && !$detailRoute) { jsonResponse(404, ['error' => 'Not found.']); }
    $allowed = $path === '/api/runs' ? ['GET', 'POST'] : ['GET'];
    if (!in_array($method, $allowed, true)) {
        header('Allow: ' . implode(', ', $allowed));
        jsonResponse(405, ['error' => 'Method not allowed.']);
    }
    if ($path === '/api/runs' && $method === 'POST') {
        if (strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') {
            jsonResponse(415, ['error' => 'Send Content-Type: application/json.']);
        }
        $body = file_get_contents('php://input', false, null, 0, 262145);
        if (strlen($body) > 262144) { jsonResponse(413, ['error' => 'Keep the request under 256 KiB.']); }
        try { $input = json_decode($body, true, 32, JSON_THROW_ON_ERROR); }
        catch (JsonException) { jsonResponse(400, ['error' => 'Send valid JSON.']); }
        $run = RunInput::validate($input);
        $repo = new RunRepository(Database::connect());
        $id = $repo->create($run);
        header('Location: /api/runs/' . $id);
        jsonResponse(201, $repo->find($id));
    }
    $page = positiveId($_GET['page'] ?? '1', 'page');
    $status = $_GET['status'] ?? 'all';
    if (!is_string($status) || !in_array($status, ['all', 'pass', 'fail'], true)) {
        throw new ValidationException(['status' => 'Choose all, pass or fail.']);
    }
    $repo = new RunRepository(Database::connect());
    if ($detailRoute) {
        $run = $repo->find((int)$match[1]);
        if (!$run) { jsonResponse(404, ['error' => 'Run not found.']); }
        jsonResponse(200, $run);
    }
    if ($isApi) { jsonResponse(200, $repo->recent($page, $status)); }
    $selected = isset($_GET['run']) ? $repo->find(positiveId($_GET['run'], 'run')) : null;
    if (isset($_GET['run']) && !$selected) { http_response_code(404); }
    $listing = $repo->recent($page, $status);
    header('Content-Type: text/html; charset=utf-8');
    require __DIR__ . '/../src/page.php';
} catch (ValidationException $e) {
    jsonResponse(422, ['error' => $e->getMessage(), 'fields' => $e->errors]);
} catch (Throwable $e) {
    error_log('Test log request failed: ' . get_class($e));
    if ($isApi) { jsonResponse(503, ['error' => 'The log is unavailable. Check the database connection and migrations.']); }
    http_response_code(503);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="en"><meta charset="utf-8"><title>Test log unavailable</title><h1>The log is unavailable</h1><p>Check the database connection and run the migrations, then reload.</p></html>';
}
