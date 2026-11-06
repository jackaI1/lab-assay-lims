package ca.jacklai.vitals

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.UUID
import java.util.concurrent.TimeUnit

class SessionExpired : IOException("Session expired. Sign in again.")
class BridgeFailure(val status: Int) : IOException("Bridge request failed ($status). Try again or sign in again.")

fun validateSource(value: String): String {
    val url = value.trim().toHttpUrl()
    require(url.username.isEmpty() && url.password.isEmpty() && url.query == null && url.fragment == null && url.encodedPath == "/") {
        "Use a bridge origin without a path, password or query"
    }
    require(url.isHttps || url.host in setOf("localhost", "127.0.0.1")) { "Use HTTPS or a local bridge" }
    return url.toString().trimEnd('/')
}
fun validatePatient(value: String): String = UUID.fromString(value.trim()).toString()

open class BridgeApi {
    private val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS).callTimeout(40, TimeUnit.SECONDS)
        .followRedirects(false).followSslRedirects(false).build()
    open suspend fun visits(source: String, patient: String, session: String): String = withContext(Dispatchers.IO) {
        val url = validateSource(source).toHttpUrl().newBuilder().addPathSegment("openemr")
            .addPathSegment("patients").addPathSegment(validatePatient(patient)).addPathSegment("visits").build()
        val request = Request.Builder().url(url).header("Cookie", session).build()
        execute(request)
    }
    suspend fun logout(source: String, session: String) = withContext(Dispatchers.IO) {
        execute(Request.Builder().url("${validateSource(source)}/auth/logout")
            .header("Cookie", session).post(ByteArray(0).toRequestBody()).build())
    }
    private fun execute(request: Request): String = client.newCall(request).execute().use { response ->
        if (response.code in setOf(401, 403)) throw SessionExpired()
        if (!response.isSuccessful) throw BridgeFailure(response.code)
        val body = response.body ?: throw IOException("Empty bridge response")
        // Bound memory use, including chunked responses without Content-Length.
        val stream = body.source()
        if (stream.request(2_000_001)) throw IOException("Visit report is too large")
        val bytes = stream.readByteArray()
        bytes.toString(Charsets.UTF_8)
    }
}
