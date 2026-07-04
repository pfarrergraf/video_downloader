import SwiftUI
import WebKit

struct DownloadWebView: UIViewRepresentable {
    @ObservedObject var bridge: DownloadBridge

    func makeCoordinator() -> Coordinator {
        Coordinator(bridge: bridge)
    }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        let userContentController = WKUserContentController()
        userContentController.add(context.coordinator, name: "downloadThat")
        configuration.userContentController = userContentController
        configuration.allowsInlineMediaPlayback = true

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        bridge.attach(webView: webView)
        webView.loadBootstrapPage()
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        private let bridge: DownloadBridge

        init(bridge: DownloadBridge) {
            self.bridge = bridge
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "downloadThat" else { return }
            bridge.handle(message: message.body)
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            bridge.notifyReady()
        }
    }
}

private extension WKWebView {
    func loadBootstrapPage() {
        if let url = Bundle.main.url(forResource: "iphone_bootstrap", withExtension: "html", subdirectory: nil) {
            loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
            return
        }

        let fallback = """
        <!doctype html><html><body style='font-family:-apple-system;padding:24px'>
        <h1>DownloadThat iOS</h1>
        <p>Missing iphone_bootstrap.html resource.</p>
        </body></html>
        """
        loadHTMLString(fallback, baseURL: nil)
    }
}
