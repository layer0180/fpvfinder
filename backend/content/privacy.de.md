# Datenschutzerklärung

<!--
HINWEIS FÜR DEN BETREIBER - wird nicht angezeigt.

Dieser Text beschreibt, wie der Dienst in der Standardkonfiguration läuft.
Änderst du etwas (anderer Hoster, Strava aktiviert, eigene Kartenkacheln,
weitere Dienste), musst du den Text gleichzeitig anpassen - nicht danach.
Art. 13 DSGVO verlangt einen erreichbaren Verantwortlichen: Trag unten Name und
Anschrift ein, sobald das Impressum sie ohnehin enthalten muss.
Das ist ein Hinweis, keine Rechtsberatung.
-->

## Verantwortlich

Dieser Dienst wird privat und nicht kommerziell betrieben. Kontakt für alle
Fragen zum Datenschutz, auch für Auskunfts- und Löschanfragen:
**{{CONTACT_EMAIL}}**

## Kurzfassung

- **Keine Cookies, kein Tracking, keine Werbung, keine Konten.**
- Dein Standort und deine Suchen werden nur verwendet, um die Suche zu
  beantworten, und nicht mit dir in Verbindung gebracht.
- Die Karte und das Flugwetter lädt dein Browser direkt bei den jeweiligen
  Anbietern – diese sehen dabei deine IP-Adresse, wie bei jeder Website mit
  einer Karte.

## Was verarbeitet wird

**Server-Logdaten.** Wie jeder Webserver verarbeitet der Hoster die Daten, die
dein Browser sendet: IP-Adresse, Zeitpunkt, aufgerufene Adresse, Statuscode,
Browserkennung. Das ist nötig, um den Dienst auszuliefern und vor Missbrauch zu
schützen (Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO, berechtigtes Interesse
an einem funktionierenden und sicheren Dienst).

**Begrenzung der Suchanfragen.** Damit niemand die gemeinsamen Ressourcen
allein verbraucht, wird deine IP-Adresse **nur im Arbeitsspeicher** und nur für
wenige Minuten als Zähler gehalten. Sie wird nie auf Platte geschrieben und ist
nach einem Neustart weg.

**Suchen.** Mittelpunkt und Radius deiner Suche werden an den Server geschickt.
Das Ergebnis wird – auf etwa 10 Meter gerundet und **ohne Bezug zu dir oder
deiner IP-Adresse** – bis zu 7 Tage zwischengespeichert, damit dieselbe Suche
beim nächsten Mal sofort beantwortet werden kann.

**Standort.** „Mein Standort“ fragt deinen Browser nach deiner Position. Das
geschieht nur, wenn du den Knopf drückst und es erlaubst. Die Koordinaten werden
wie eine normale Suche behandelt; zusätzlich wird der Ortsname dazu (auf etwa
100 Meter gerundet) bis zu 30 Tage zwischengespeichert.

**Geteilte Spots.** Wenn du „Teilen“ oder „Story-Bild“ nutzt, legt der Server
einen kurzen Link an und speichert dazu eine Kopie des Spots (Koordinaten,
Bewertung, Hinweise) – ohne Bezug zu dir. Diese Kopie bleibt gespeichert, damit
der Link funktioniert. Wenn du einen geteilten Link entfernt haben möchtest,
schreib uns die Adresse.

**Im Browser gespeichert.** Gemerkte Spots und dass du den Hinweis zur
Luftraumprüfung bestätigt hast, speichert dein Browser lokal (localStorage). Das
wird nie übertragen und lässt sich über die Browsereinstellungen löschen. Es
wird nur gespeichert, weil du es ausdrücklich auslöst (§ 25 Abs. 2 Nr. 2 TDDDG).

{{ANALYTICS_SECTION}}

## Hosting

Der Dienst läuft bei **netcup** (netcup GmbH, Deutschland), der Server steht in
Nürnberg. netcup verarbeitet die oben genannten Logdaten in unserem Auftrag; es
findet keine Übermittlung außerhalb der EU statt.
Datenschutzerklärung: <https://www.netcup.de/kontakt/datenschutzerklaerung.php>

## Dienste Dritter

Manche Abfragen stellt **der Server** für dich (deine IP-Adresse wird dabei nicht
weitergegeben), andere **dein Browser direkt** – dann sieht der Anbieter deine
IP-Adresse.

| Dienst | Wofür | Wer verbindet sich | Datenschutz |
|---|---|---|---|
| OpenFreeMap | Kartenkacheln, die du siehst | **dein Browser** | <https://openfreemap.org> |
| Open-Meteo (Schweiz) | Flugwetter, wenn du einen Spot öffnest | **dein Browser** | <https://open-meteo.com/en/terms> |
| NOAA Space Weather Prediction Center (USA) | Kp-Index für die GPS-Qualität (ein Wert für alle, ohne Bezug zu dir) | der Server | <https://www.weather.gov/privacy> |
| Photon (komoot, Deutschland) | Ortssuche | der Server | <https://www.komoot.com/privacy> |
| Nominatim (OpenStreetMap Foundation) | Ortssuche, falls Photon nicht antwortet | der Server | <https://osmfoundation.org/wiki/Privacy_Policy> |

Die Kartendaten für die Bewertung (OpenStreetMap) liegen auf dem Server selbst;
dafür wird bei einer Suche in Deutschland kein externer Dienst gefragt.

Klickst du auf „Route“, „Auf dipul.de prüfen“ oder den Spenden-Button, verlässt
du diese Seite; dort gilt die Datenschutzerklärung des jeweiligen Anbieters.

## Speicherdauer

Server-Logdaten nach den Vorgaben des Hosters. Zähler im Arbeitsspeicher wenige
Minuten. Zwischengespeicherte Suchergebnisse 7 Tage, Ortssuchen 30 Tage.
Geteilte Spots, bis du die Löschung verlangst.

## Deine Rechte

Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der
Verarbeitung, Datenübertragbarkeit und Widerspruch sowie das Recht, dich bei
einer Datenschutz-Aufsichtsbehörde zu beschweren. Da keine Konten existieren,
betrifft eine Auskunft in der Praxis nur die oben genannten Server-Logdaten.
