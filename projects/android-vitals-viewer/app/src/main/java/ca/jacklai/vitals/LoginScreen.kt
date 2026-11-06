package ca.jacklai.vitals

import android.annotation.SuppressLint
import android.net.Uri
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView

/** The existing bridge binds SMART state to an HttpOnly browser cookie. This local-only
 * demonstration uses an isolated WebView; tokens stay on the server, never in Javascript. */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun LoginScreen(source: String, authorized: (String) -> Unit, cancel: () -> Unit) {
    var webView by remember { mutableStateOf<WebView?>(null) }
    var ready by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("Approve access to the fictional records in the bridge sign-in page.") }
    val cookies = remember { CookieManager.getInstance() }
    DisposableEffect(Unit) {
        cookies.removeAllCookies { ready = true }
        onDispose {
            webView?.apply { stopLoading(); clearHistory(); clearCache(true); destroy() }
            cookies.removeAllCookies(null)
        }
    }
    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        TextButton(onClick = cancel) { Text("Cancel sign-in") }
        Text(message, modifier = Modifier.padding(16.dp))
        if (ready) AndroidView(modifier = Modifier.fillMaxWidth().weight(1f), factory = { context ->
            WebView(context).apply {
                webView = this
                settings.javaScriptEnabled = true // OpenEMR consent forms; no JS interfaces are installed.
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                settings.domStorageEnabled = false
                cookies.setAcceptThirdPartyCookies(this, false)
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                        val uri = request.url
                        return uri.scheme !in setOf("http", "https") ||
                            (uri.scheme == "http" && uri.host !in setOf("localhost", "127.0.0.1"))
                    }
                    override fun onPageFinished(view: WebView, url: String) {
                        val uri = Uri.parse(url)
                        val expected = Uri.parse(source)
                        if (uri.scheme == expected.scheme && uri.host == expected.host && uri.port == expected.port &&
                            uri.path == "/auth/callback") {
                            if (!uri.getQueryParameter("error").isNullOrEmpty()) {
                                message = "Access denied. Cancel and sign in again."
                                return
                            }
                            val cookie = cookies.getCookie(source).orEmpty().split(';').map { it.trim() }
                                .firstOrNull { it.startsWith("bridge_session=") }.orEmpty()
                            if (cookie.isNotEmpty()) authorized(cookie) // Native GET validates completion; a callback alone grants no data.
                            else message = "Sign-in did not finish. Cancel and try again."
                        }
                    }
                }
                loadUrl("$source/auth/login")
            }
        })
    }
}
