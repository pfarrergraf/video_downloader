import SwiftUI

struct ContentView: View {
    @StateObject private var bridge = DownloadBridge(
        licenseClient: LicenseClient(),
        deviceIdentity: DeviceIdentity()
    )

    var body: some View {
        DownloadWebView(bridge: bridge)
            .ignoresSafeArea(edges: .bottom)
            .navigationTitle("DownloadThat")
    }
}

#Preview {
    ContentView()
}
