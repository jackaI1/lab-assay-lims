<?php
declare(strict_types=1);
// Only explicit static assets are served directly. Never expose source or dotfiles.
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if (in_array($path, ['/style.css', '/app.js'], true)) { return false; }
require __DIR__ . '/index.php';
