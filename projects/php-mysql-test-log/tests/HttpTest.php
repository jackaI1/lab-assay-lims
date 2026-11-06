<?php
declare(strict_types=1);
namespace TestLogTests;
require_once __DIR__ . '/Fixture.php';
use PHPUnit\Framework\TestCase;

final class HttpTest extends TestCase
{
    private static mixed $server = null;
    private static string $base;
    private static function stopServer(): void
    {
        if (is_resource(self::$server)) {
            proc_terminate(self::$server);
            proc_close(self::$server);
            self::$server = null;
        }
    }
    public static function setUpBeforeClass(): void
    {
        $socket = stream_socket_server('tcp://127.0.0.1:0', $errno, $error);
        if (!$socket) { throw new \RuntimeException($error); }
        $address = stream_socket_get_name($socket, false);
        fclose($socket);
        self::$base = 'http://' . $address;
        self::$server = proc_open([PHP_BINARY, '-S', $address, '-t', 'public', 'public/router.php'], [0=>['file','/dev/null','r'],1=>['file','/dev/null','w'],2=>['file','/dev/null','w']], $pipes, dirname(__DIR__));
        if (!is_resource(self::$server)) { throw new \RuntimeException('Could not start HTTP fixture.'); }
        register_shutdown_function(self::stopServer(...));
        $status = proc_get_status(self::$server);
        fwrite(STDERR, "HTTP fixture PID {$status['pid']}, address $address, started " . gmdate('c') . "; cleanup: proc_terminate/proc_close in tearDownAfterClass and shutdown.\n");
        for ($attempt=0; $attempt<100; $attempt++) {
            $probe = @stream_socket_client('tcp://' . $address, $errno, $error, .05);
            if ($probe) { fclose($probe); return; }
            usleep(50000);
        }
        self::stopServer();
        throw new \RuntimeException('HTTP fixture did not start.');
    }
    public static function tearDownAfterClass(): void { self::stopServer(); }
    protected function setUp(): void { Fixture::database(); }
    private function request(string $method, string $path, ?string $body = null, string $type = 'application/json'): array
    {
        $context = stream_context_create(['http'=>['method'=>$method,'header'=>"Content-Type: $type\r\n",'content'=>$body ?? '', 'ignore_errors'=>true, 'timeout'=>5]]);
        $response = file_get_contents(self::$base . $path, false, $context);
        $headers = http_get_last_response_headers();
        preg_match('/HTTP\/\S+ (\d+)/', $headers[0], $match);
        return [(int)$match[1], $response, implode("\n", $headers)];
    }
    public function testCreateGetListAndEscapedResultsPage(): void
    {
        $input = Fixture::run(); $input['sample'] = '<script>window.pwned=1</script>'; $input['notes'] = '<img src=x onerror=alert(1)>';
        [$status,$body,$headers] = $this->request('POST','/api/runs',json_encode($input));
        self::assertSame(201,$status); $run=json_decode($body,true);
        self::assertStringContainsString('Location: /api/runs/'.$run['id'],$headers);
        self::assertTrue($run['passed']);
        [$status,$body] = $this->request('GET','/api/runs/'.$run['id']);
        self::assertSame(200,$status); self::assertSame($run,json_decode($body,true));
        [$status,$body] = $this->request('GET','/api/runs');
        self::assertSame(200,$status); self::assertCount(1,json_decode($body,true)['runs']);
        [$status,$body,$headers] = $this->request('GET','/?run='.$run['id']);
        self::assertSame(200,$status); self::assertStringContainsString('&lt;script&gt;window.pwned=1&lt;/script&gt;',$body);
        self::assertStringNotContainsString($input['notes'],$body);
        self::assertStringContainsString('101.200001',$body);
        self::assertStringContainsString('Content-Security-Policy:',$headers);
    }
    public function testMalformedJsonWrongContentTypeAndOversizedBody(): void
    {
        self::assertSame(400,$this->request('POST','/api/runs','{broken')[0]);
        self::assertSame(415,$this->request('POST','/api/runs','{}','text/plain')[0]);
        self::assertSame(413,$this->request('POST','/api/runs',str_repeat(' ',262145))[0]);
    }
    public function testValidationErrorsNeverSavePartialData(): void
    {
        $input=Fixture::run(); $input['measurements'][0]['upper_limit']='1';
        [$status,$body]=$this->request('POST','/api/runs',json_encode($input));
        self::assertSame(422,$status); self::assertArrayHasKey('measurements.0.upper_limit',json_decode($body,true)['fields']);
        self::assertSame([],json_decode($this->request('GET','/api/runs')[1],true)['runs']);
    }
    public function testRoutesMethodsAndQueryValidation(): void
    {
        self::assertSame(404,$this->request('GET','/api/runs/999999999')[0]);
        self::assertSame(404,$this->request('GET','/?run=999999999')[0]);
        self::assertSame(404,$this->request('GET','/.env')[0]);
        self::assertSame(404,$this->request('GET','/vendor/autoload.php')[0]);
        [$status,,$headers]=$this->request('DELETE','/api/runs');
        self::assertSame(405,$status); self::assertStringContainsString('Allow: GET, POST',$headers);
        foreach (['?page=-1','?page[]=1','?status=maybe','?status[]=pass'] as $query) {
            self::assertSame(422,$this->request('GET','/api/runs'.$query)[0]);
        }
    }
    public function testUnavailableStorageReturnsUsefulErrorsWithoutSql(): void
    {
        $db = Fixture::database();
        $db->exec('RENAME TABLE test_runs TO temporarily_unavailable');
        try {
            [$status, $body] = $this->request('GET', '/api/runs');
            self::assertSame(503, $status);
            self::assertStringContainsString('Check the database connection', $body);
            self::assertStringNotContainsString('SQLSTATE', $body);
            [$status, $body] = $this->request('GET', '/');
            self::assertSame(503, $status);
            self::assertStringContainsString('run the migrations', $body);
        } finally {
            $db->exec('RENAME TABLE temporarily_unavailable TO test_runs');
        }
    }
    public function testStaticAssetsAndEmptyPage(): void
    {
        [$status,$body]=$this->request('GET','/'); self::assertSame(200,$status);
        self::assertStringContainsString('No runs in this view yet.',$body);
        self::assertSame(200,$this->request('GET','/app.js')[0]);
        self::assertSame(200,$this->request('GET','/style.css')[0]);
    }
}
