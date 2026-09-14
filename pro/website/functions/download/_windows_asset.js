const INSTALLER_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest-Setup.exe";
const INSTALLER_SHA256_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest-Setup.exe.sha256";
const PORTABLE_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest.exe";
const PORTABLE_SHA256_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest.exe.sha256";

export async function fetchWindowsAsset(method = "GET") {
  const installer = await fetch(INSTALLER_URL, { method, redirect: "follow" });
  if (installer.ok) {
    return { upstream: installer, filename: "DownloadThat-Setup.exe", installer: true };
  }

  const portable = await fetch(PORTABLE_URL, { method, redirect: "follow" });
  if (portable.ok) {
    return { upstream: portable, filename: "DownloadThat.exe", installer: false };
  }
  return { upstream: portable, filename: "DownloadThat.exe", installer: false };
}

export async function fetchWindowsChecksum(method = "GET") {
  const installer = await fetch(INSTALLER_SHA256_URL, { method, redirect: "follow" });
  if (installer.ok) {
    return { upstream: installer, filename: "DownloadThat-Setup.exe", installer: true };
  }

  const portable = await fetch(PORTABLE_SHA256_URL, { method, redirect: "follow" });
  return { upstream: portable, filename: "DownloadThat.exe", installer: false };
}
