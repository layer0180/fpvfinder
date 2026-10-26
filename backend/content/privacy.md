# Privacy notice

<!--
NOTE FOR THE OPERATOR - not rendered.

This describes the default configuration. Change the setup (another host,
Strava switched on, your own map tiles, further services) and this text has to
change at the same time - not afterwards. Keep it in step with privacy.de.md.
A note, not legal advice.
-->

## Who is responsible

This service is run privately and non-commercially. For any question about
data protection, including requests for access or erasure: **{{CONTACT_EMAIL}}**

## The short version

- **No cookies, no tracking, no ads, no accounts.**
- Your location and your searches are used to answer the search and are not
  tied to you.
- Your browser loads the map and the flight weather directly from those
  providers, so they see your IP address - as on any website with a map.

## What is processed

**Server logs.** Like any web server, the host processes what your browser
sends: IP address, time, requested URL, status code, user agent. This is needed
to deliver the service and to defend against abuse (Art. 6(1)(f) GDPR).

**Rate limiting.** Your IP address is held **in memory only**, for a few
minutes, as a request counter. It is never written to disk.

**Searches.** Centre and radius of your search are sent to the server. The
result is cached for up to 7 days, rounded to about 10 metres and **without any
link to you or your IP address**, so that the same search is answered instantly
next time.

**Location.** "My location" asks your browser for your position, only when you
press it and allow it. The coordinates are treated like a normal search; the
place name for them (rounded to about 100 metres) is cached for up to 30 days.

**Shared spots.** "Share" and "Story image" create a short link and store a copy
of the spot (coordinates, rating, notes) with no link to you, so that the link
keeps working. To have a shared link removed, send us its address.

**Stored in your browser.** Saved spots, and that you acknowledged the airspace
notice, are kept in your browser's localStorage. They are never transmitted.

{{ANALYTICS_SECTION}}

## Hosting

The service runs on **netcup** (netcup GmbH, Germany), with the machine in
Nuremberg. netcup processes the server logs on our behalf; nothing is
transferred outside the EU.
Privacy policy: <https://www.netcup.de/kontakt/datenschutzerklaerung.php>

## Third-party services

Some requests are made by **the server** on your behalf (your IP address is not
forwarded); others by **your browser directly**, in which case that provider
sees your IP address.

| Service | Purpose | Who connects | Privacy |
|---|---|---|---|
| OpenFreeMap | the map tiles you see | **your browser** | <https://openfreemap.org> |
| Open-Meteo (Switzerland) | flight weather when you open a spot | **your browser** | <https://open-meteo.com/en/terms> |
| NOAA Space Weather Prediction Center (USA) | Kp index for GPS quality (one value for everyone, not tied to you) | the server | <https://www.weather.gov/privacy> |
| Photon (komoot, Germany) | place search | the server | <https://www.komoot.com/privacy> |
| Nominatim (OpenStreetMap Foundation) | place search when Photon does not answer | the server | <https://osmfoundation.org/wiki/Privacy_Policy> |

The map data used for the rating (OpenStreetMap) is stored on the server
itself; a search in Germany asks no external service for it.

## Storage duration

Server logs as set by the host. In-memory counters a few minutes. Cached
search results 7 days, place searches 30 days. Shared spots until you ask for
their removal.

## Your rights

You have the right of access, rectification, erasure, restriction, data
portability and objection, and the right to lodge a complaint with a
supervisory authority. With no accounts, access in practice concerns only the
server logs above.
