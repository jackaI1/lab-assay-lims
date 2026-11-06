<?php
declare(strict_types=1);
namespace TestLog;
final class ValidationException extends \RuntimeException
{
    public function __construct(public readonly array $errors)
    {
        parent::__construct('Check the listed fields.');
    }
}
