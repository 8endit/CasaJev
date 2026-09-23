# CasaJev Desktop 0.5.1 — macOS Intel

1. `CasaJev-Desktop-macOS-0.5.1.zip` entpacken.
2. `CasaJev.app` öffnen.
3. Beim ersten Start richtet CasaJev über das vorhandene `uv` eine lokale
   Python-Umgebung unter `~/Library/Application Support/CasaJev` ein.

Die App verwendet ein einziges sichtbares, sandboxed Chromium-WebView. Derselbe
WebView liefert die Beobachtungen und erhält die begrenzten Aktionsbefehle. Die
Webseite bekommt keinen Node-Zugriff. Browserberechtigungen, Downloads, Pop-ups und
private Netzwerkziele werden blockiert.

Das Bundle ist lokal/ad-hoc signiert und nach ZIP-Entpacken erfolgreich mit
`codesign --verify --deep --strict` geprüft. Es ist noch nicht mit einem bezahlten
Apple-Developer-Zertifikat signiert oder notarisiert. Dieses Bundle ist für Intel-
macOS (`x64`) gebaut; Apple Silicon ist noch nicht separat paketiert.

SHA-256 der Desktop-ZIP:

`18434676880d1975b937f6614f60389c802885380c99e77e770967850f5999ca`
