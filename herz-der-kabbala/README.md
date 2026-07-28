# Herz der Kabbala – Dev-Staging

Dieses Verzeichnis ist vollständig vom Video-Downloader getrennt und dient nur als vorübergehender Staging-Ort für die zweisprachige Website „Herz der Kabbala – Jüdische Weisheit für heute“.

## Deployment

- Branch: `herz-der-kabbala-dev`
- Cloudflare Pages project: `herz-der-kabbala-dev`
- Deployment directory: `herz-der-kabbala/dist`
- Workflow: `.github/workflows/deploy-herz-der-kabbala-dev.yml`

Der Workflow verwendet dieselben Repository-Secrets `CLOUDFLARE_API_TOKEN` und `CLOUDFLARE_ACCOUNT_ID`, die bereits für die DownloadThat-Website hinterlegt sind. Er greift nicht auf deren D1-Datenbank, Domains, Play-Konfiguration oder Worker-Routen zu.

## Sicherheitsgrenzen

- keine DownloadThat-Secrets im Websitecode
- keine Wiederverwendung der DownloadThat-Datenbank
- keine Änderung am Projekt `downloadthat`
- keine automatische Verbindung mit einer produktiven Domain
- Suchmaschinen bleiben während der Probe über `robots.txt` und Metatags ausgeschlossen

## Spätere Auslagerung

Nach der Probe wird der Inhalt in ein eigenes Repository verschoben. Das Cloudflare-Projekt kann bestehen bleiben und anschließend mit dem neuen Repository oder einem eigenen Deployment-Workflow verbunden werden.
