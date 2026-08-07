# Privacy notice

## Who is responsible

This service is run privately and non-commercially. All contact runs through the
project repository: **{{PROJECT_URL}}** — open an issue there for any question
about data protection, including requests for access or erasure.

<!--
NOTE FOR THE OPERATOR - not rendered, deliberately left in the file.

Art. 13 GDPR expects the controller to be identifiable and reachable. A
repository link is a working contact route, but if § 5 DDG applies then a name
and address belong here too.

This text describes how the service actually runs today. Adding analytics, a
CDN or a different reverse proxy makes it wrong, and it has to be amended at
the same time - not afterwards. A note, not legal advice.
-->

## The short version

This service sets **no cookies**, uses **no analytics**, **no tracking pixels**
and **no advertising**. There are no user accounts, so nothing is tied to an
identity. Your search coordinates are used to answer your request and are not
stored in a way that links them to you.

## What is processed

**Server log data.** Like any web server, the hosting platform processes the
data your browser sends: IP address, time, requested URL, status code, user
agent. This is needed to deliver the service and to defend against abuse
(legal basis: Art. 6(1)(f) GDPR, legitimate interest in a functioning and secure
service).

**Rate limiting.** To stop a single visitor from exhausting the shared upstream
data budget, your IP address is held **in memory only**, for a few minutes, as a
request counter. It is never written to disk and disappears on restart.

**Search parameters.** The coordinates and radius you search are sent to the
server to compute a result. The map data retrieved for that area is cached on
the server so later searches are faster - that cache holds **map data, not who
requested it**.

**Local storage in your browser.** The app stores your settings (radius, weights
and so on) only in your own browser session; nothing is transmitted for that.

## Hosting

The service runs on **netcup** (netcup GmbH, Germany), with the machine located
in Nuremberg, Germany. netcup processes the server log data described above on
our behalf. As netcup is a German company operating an EU data centre, no
transfer outside the EU is involved for hosting.
Privacy policy: <https://www.netcup.de/kontakt/datenschutzerklaerung.php>

## Third-party services

Answering a search requires calls to external services. Some are made by the
server on your behalf (your IP address is not forwarded), and some are made by
**your browser directly** - in which case that provider sees your IP address,
exactly as it would on any website embedding a map.

| Service | Purpose | Who connects | Privacy policy |
|---|---|---|---|
| OpenStreetMap tile servers | the base map you see | **your browser** | <https://osmfoundation.org/wiki/Privacy_Policy> |
| Strava heatmap tiles | the heatmap overlay, when you enable it | **your browser** | <https://www.strava.com/legal/privacy> |
| Overpass API | land use, roads, buildings | the server | <https://osmfoundation.org/wiki/Privacy_Policy> |
| Nominatim | address search | the server | <https://osmfoundation.org/wiki/Privacy_Policy> |
| Strava heatmap tiles | activity intensity for the score | the server | <https://www.strava.com/legal/privacy> |
| netcup | hosting and server logs | - | <https://www.netcup.de/kontakt/datenschutzerklaerung.php> |

**Map tiles are loaded by your browser**, so the OpenStreetMap tile servers see
your IP address, and Strava does too **while the heatmap layer is switched on**.
The layer is off by default; turning it off stops those requests entirely. This
is how map tiles work on any website that shows a map.

Strava tiles are **not stored on the server**. The score component fetches the
few tiles covering your search area, reads the pixel values and discards them.

If you click the donation button you leave this site and the linked provider's
own privacy policy applies. No conversion tracking of any kind is embedded here.

## Storage duration

Server logs are kept as long as the hosting provider's defaults dictate. The map
data cache is technical data with no personal reference. In-memory rate limiting
counters expire after a few minutes.

## Your rights

You have the right of access, rectification, erasure, restriction of processing,
data portability and objection, and the right to lodge a complaint with a
supervisory authority. Since no account data is stored, a request for access
will in practice concern only the server logs mentioned above.
