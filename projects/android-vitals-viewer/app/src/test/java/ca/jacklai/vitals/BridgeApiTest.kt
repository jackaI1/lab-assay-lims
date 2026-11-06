package ca.jacklai.vitals

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.*
import org.junit.Assert.*

class BridgeApiTest {
    private lateinit var server: MockWebServer
    @Before fun open() { server = MockWebServer(); server.start() }
    @After fun close() { server.shutdown() }
    @Test fun sendsCookieAndEncodedPatientRoute() = runTest {
        server.enqueue(MockResponse().setBody("{}"))
        BridgeApi().visits(server.url("/").toString(), "11111111-1111-4111-8111-111111111111", "bridge_session=opaque")
        val request = server.takeRequest()
        assertEquals("bridge_session=opaque", request.getHeader("Cookie"))
        assertEquals("/openemr/patients/11111111-1111-4111-8111-111111111111/visits", request.path)
    }
    @Test fun unauthorizedBecomesExpiredSession() = runTest {
        server.enqueue(MockResponse().setResponseCode(401))
        try { BridgeApi().visits(server.url("/").toString(), "11111111-1111-4111-8111-111111111111", "x"); fail() }
        catch (_: SessionExpired) { }
    }
    @Test fun upstreamErrorIsNotTreatedAsData() = runTest {
        server.enqueue(MockResponse().setResponseCode(502).setBody("private upstream detail"))
        try { BridgeApi().visits(server.url("/").toString(), "11111111-1111-4111-8111-111111111111", "x"); fail() }
        catch (e: BridgeFailure) { assertFalse(e.message!!.contains("private")); assertEquals(502, e.status) }
    }
    @Test(expected = IllegalArgumentException::class) fun refusesRemoteCleartext() { validateSource("http://example.com") }
    @Test(expected = IllegalArgumentException::class) fun refusesCredentialsInUrl() { validateSource("https://user:password@example.com") }
    @Test(expected = IllegalArgumentException::class) fun refusesPatientPathInjection() { validatePatient("../Patient") }
}
