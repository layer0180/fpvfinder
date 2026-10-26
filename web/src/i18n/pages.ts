/**
 * Body copy of the static pages, per language. Kept out of the .astro files so
 * that a translation is one object to fill in, not markup to edit.
 *
 * Strings may contain <strong>/<a> and are rendered with set:html - they are
 * our own text, never user input.
 */
import type { Lang } from './site'

export interface FaqItem {
  q: string
  a: string
}

const faqDe: FaqItem[] = [
  {
    q: 'Wie findet das Tool einen guten FPV-Spot?',
    a: 'Es legt ein Raster über deinen Umkreis – standardmäßig alle 150 Meter ein Punkt – und bewertet jeden Punkt doppelt: wie wenig Menschen dort voraussichtlich sind und wie gut sich dort fliegen lässt. Dafür zählen die Abstände zu Gebäuden, Wohngebieten, Straßen, Wegen, ausgeschilderten Wander- und Radrouten, Ausflugszielen, Freileitungen und Bahnlinien sowie die Landnutzung an der Stelle.',
  },
  {
    q: 'Darf ich an einem vorgeschlagenen Spot fliegen?',
    a: 'Das kann das Tool nicht entscheiden – und es behauptet es auch nicht. Die Bewertung ist eine Heuristik auf offenen Kartendaten. Ob du fliegen darfst, richtet sich nach der EU-Drohnenverordnung (2019/947), der Luftverkehrs-Ordnung, geografischen UAS-Gebieten und aktuellen NOTAMs. Prüfe das vor jedem Flug selbst, in Deutschland am einfachsten auf <a href="https://www.dipul.de/homepage/de/" rel="noopener">dipul.de</a>. Jeder Spot im Finder hat dafür einen direkten Link.',
  },
  {
    q: 'Warum ist ein Punkt ausgegraut oder gesperrt?',
    a: 'Er verletzt eine harte Regel: weniger als 150 Meter zu einem Wohn-, Gewerbe- oder Erholungsgebiet (angelehnt an die EU-Kategorie A3), zu nah an Gebäuden, Straßen oder Bahnlinien, in einem Naturschutzgebiet oder nahe einem Flugplatz. Solche Punkte bleiben sichtbar, damit du siehst, warum eine Gegend ausfällt.',
  },
  {
    q: 'Was bringen die Begründungen bei jedem Spot?',
    a: 'Statt nur einer Zahl siehst du, warum ein Ort gut abschneidet – etwa „nächster Weg 420 m entfernt“ oder „offenes Gelände“. So kannst du die Bewertung vor Ort und auf dem Satellitenbild nachprüfen.',
  },
  {
    q: 'Was bedeutet das Zeitprofil?',
    a: 'Ein Feldweg am Dienstagmorgen ist etwas anderes als am Sonntagnachmittag. Das Zeitprofil gewichtet Wege, Ausflugsziele und Freizeitflächen je nach Wochentag und Uhrzeit. Standardmäßig wählt der Finder das Profil, das zu jetzt passt.',
  },
  {
    q: 'Wie aktuell und wie genau sind die Daten?',
    a: 'Die Kartendaten stammen aus OpenStreetMap und werden regelmäßig neu eingelesen. In gut kartierten Gegenden sind die Ergebnisse sehr brauchbar; in dünn kartierten kann eine Fläche leer wirken, obwohl dort etwas steht. Schau dir einen Spot vor dem ersten Flug auf dem Satellitenbild und vor Ort an.',
  },
  {
    q: 'Welche Gebiete werden abgedeckt?',
    a: 'Ganz Deutschland. Suchen am Rand der Abdeckung funktionieren, Punkte jenseits der Grenze werden aber nicht bewertet.',
  },
  {
    q: 'Wie wird das Flugwetter ermittelt?',
    a: 'Für den gewählten Spot fragt dein Browser die Vorhersage direkt bei Open-Meteo ab: Wind und Böen in 10 und 80 Metern Höhe, Regenwahrscheinlichkeit, Temperatur und Sonnenuntergang. Die Ampel ist eine grobe Einschätzung für kleine Copter, keine Wetterberatung.',
  },
  {
    q: 'Kostet das etwas, und was passiert mit meinen Daten?',
    a: 'Nichts und nichts: keine Anmeldung, keine Cookies, keine Werbung, kein Tracking. Dein Standort wird nur für die Suche an den Server geschickt und nicht gespeichert. Wer die Serverkosten unterstützen will, kann das freiwillig tun – am Funktionsumfang ändert das nichts.',
  },
  {
    q: 'Kann ich die Bewertung anpassen oder das Tool selbst betreiben?',
    a: 'Teilweise: Im Finder lassen sich unter „Experte“ Radius, Raster und Zeitprofil einstellen. Wer die Gewichtung selbst festlegen will, betreibt eine eigene Instanz – es gibt ein fertiges Docker-Image, alle Gewichte stehen in einer Datei, und der Quellcode ist frei (AGPL-3.0).',
  },
]

const faqEn: FaqItem[] = [
  {
    q: 'How does the tool find a good FPV spot?',
    a: 'It lays a grid over your search area – one point every 150 metres by default – and rates every point twice: how few people are likely to be there, and how good the flying is. It weighs the distance to buildings, residential areas, roads, paths, signposted hiking and cycling routes, popular destinations, power lines and railways, plus the land use at the spot itself.',
  },
  {
    q: 'Am I allowed to fly at a suggested spot?',
    a: 'The tool cannot decide that and does not claim to. The rating is a heuristic over open map data. Whether you may fly depends on the EU drone regulation (2019/947), national law, geographical UAS zones and current NOTAMs. Check before every flight – in Germany most easily on <a href="https://www.dipul.de/homepage/en/" rel="noopener">dipul.de</a>. Every spot in the finder links straight to it.',
  },
  {
    q: 'Why is a point greyed out or blocked?',
    a: 'It breaks a hard rule: less than 150 metres from a residential, commercial or recreational area (following EU category A3), too close to buildings, roads or railways, inside a nature reserve or near an aerodrome. Such points stay visible so you can see why an area is ruled out.',
  },
  {
    q: 'What are the reasons shown for each spot?',
    a: 'Instead of a bare number you see why a place scores well – "nearest path 420 m away" or "open terrain". That lets you check the rating on the satellite image and on the ground.',
  },
  {
    q: 'What does the time profile do?',
    a: 'A farm track on a Tuesday morning is not the same place on a Sunday afternoon. The time profile weighs paths, destinations and recreational land by day and time. By default the finder picks the profile that matches right now.',
  },
  {
    q: 'How current and accurate is the data?',
    a: 'Map data comes from OpenStreetMap and is re-imported regularly. In well-mapped areas the results are very usable; in sparsely mapped ones an area can look empty although something is there. Look at a spot on the satellite image and in person before your first flight.',
  },
  {
    q: 'Which areas are covered?',
    a: 'All of Germany. Searches near the edge work, but points beyond the border are not rated.',
  },
  {
    q: 'Where does the flight weather come from?',
    a: 'For the selected spot your browser asks Open-Meteo directly for the forecast: wind and gusts at 10 and 80 metres, chance of rain, temperature and sunset. The traffic light is a rough guide for small quads, not a weather briefing.',
  },
  {
    q: 'Does it cost anything, and what happens to my data?',
    a: 'Nothing and nothing: no sign-up, no cookies, no ads, no tracking. Your location is sent to the server for the search only and is not stored. If you want to help with the server costs you can, voluntarily – it changes nothing about the features.',
  },
  {
    q: 'Can I tune the rating or run it myself?',
    a: 'Partly: under "Expert" in the finder you can set radius, grid and time profile. To set the weighting yourself, run your own instance – there is a ready Docker image, every weight lives in one file, and the source is free (AGPL-3.0).',
  },
]

export const pages = {
  de: {
    landing: {
      title: 'FPV-Spots finden – ruhige Flugorte ohne Zuschauer | FPV Flying Spot Finder',
      description:
        'Kostenloser Finder für FPV- und Drohnen-Spots in Deutschland: zeigt Orte mit wenig Menschen und freiem Gelände, mit Begründung, Warnhinweisen und Flugwetter. Ohne Anmeldung.',
      eyebrow: 'Kostenlos · ohne Anmeldung · ganz Deutschland',
      h1: 'Finde FPV-Spots, an denen dir niemand zuschaut',
      lead: 'Der Finder durchsucht deinen Umkreis nach Stellen mit wenig Menschen und freiem Gelände – und sagt dir bei jedem Spot, warum er passt und worauf du achten musst.',
      searchLabel: 'Ort oder Adresse',
      searchPlaceholder: 'z. B. Bad Urach',
      searchButton: 'Spots finden',
      locate: 'Meinen Standort nutzen',
      steps: [
        { h3: 'Ort wählen', text: 'Ort eintippen oder deinen Standort nutzen. Mehr musst du nicht einstellen.' },
        {
          h3: 'Top-Spots ansehen',
          text: 'Du bekommst die besten Stellen im Umkreis als Liste und auf der Karte – mit Punktzahl und Begründung.',
        },
        {
          h3: 'Prüfen und los',
          text: 'Warnhinweise, Flugwetter und ein Direktlink zu dipul.de helfen beim Check. Dann Route starten.',
        },
      ],
      stepsH2: 'So funktioniert’s',
      ratesH2: 'Was in die Bewertung einfließt',
      rates: [
        {
          h3: 'Wenig Menschen',
          items: [
            'Abstand zu Wohngebieten, Gebäuden und Straßen',
            'Abstand zu Wegen und ausgeschilderten Wander- und Radrouten',
            'Ausflugsziele wie Parkplätze, Spielplätze und Aussichtspunkte',
            'Wochentag und Uhrzeit: Sonntagnachmittag ist anders als Dienstagmorgen',
          ],
        },
        {
          h3: 'Gut fliegen',
          items: [
            'Offenes Gelände und ein brauchbarer Start- und Landeplatz',
            'Sicherheitsabstand zu Straßen, Bahnlinien und Freileitungen',
            'Struktur zum Umfliegen: Waldkanten, Baumreihen, Ufer',
            'Naturschutzgebiete und Flugplätze werden gesperrt',
          ],
        },
      ],
      legalH2: 'Wichtig: kein Ersatz für die Luftraumprüfung',
      legal:
        'Der Finder ist ein Recherchewerkzeug auf Basis offener Daten. Ob du an einem Ort fliegen darfst, musst du vor jedem Flug selbst prüfen – nach EU-Drohnenverordnung, Luftverkehrs-Ordnung, geografischen UAS-Gebieten und NOTAMs, am einfachsten auf <a href="https://www.dipul.de/homepage/de/" rel="noopener">dipul.de</a>.',
      faqH2: 'Häufige Fragen',
      faqMore: 'Alle Fragen ansehen',
      guidesH2: 'Ratgeber: Regeln und gute Spots',
      guidesMore: 'Alle Ratgeber',
      regionsLink: 'FPV-Spots rund um die Großstädte',
      dataNote: 'Kartendaten: OpenStreetMap. Keine Cookies, kein Tracking.',
    },
    faq: {
      title: 'FAQ – FPV-Spots finden, Regeln und Datenquellen | FPV Flying Spot Finder',
      description:
        'Antworten zum FPV-Spot-Finder: wie die Bewertung funktioniert, ob du an einem Spot fliegen darfst, wie aktuell die Daten sind und was mit deinen Daten passiert.',
      h1: 'Häufige Fragen',
      items: faqDe,
    },
    start: {
      title: 'FPV-Spots in deiner Nähe | FPV Flying Spot Finder',
      description: 'Ein Tipp – und du siehst die ruhigsten FPV-Spots in deiner Umgebung. Kostenlos, ohne Anmeldung.',
      h1: 'Ruhige FPV-Spots in deiner Nähe',
      lead: 'Ein Tipp genügt. Kostenlos, ohne Anmeldung, ohne Tracking.',
      locate: 'Spots in meiner Nähe',
      or: 'oder',
      searchPlaceholder: 'Ort eingeben',
      searchButton: 'Suchen',
      proof: ['Ganz Deutschland', 'Mit Begründung & Warnhinweisen', 'Flugwetter für jeden Spot'],
    },
  },
  en: {
    landing: {
      title: 'Find FPV spots – quiet places to fly without an audience | FPV Flying Spot Finder',
      description:
        'Free finder for FPV and drone spots in Germany: shows places with few people and open terrain, with reasons, warnings and flight weather. No sign-up.',
      eyebrow: 'Free · no sign-up · all of Germany',
      h1: 'Find FPV spots where nobody is watching',
      lead: 'The finder searches your area for places with few people and open ground – and tells you for every spot why it works and what to watch out for.',
      searchLabel: 'Place or address',
      searchPlaceholder: 'e.g. Bad Urach',
      searchButton: 'Find spots',
      locate: 'Use my location',
      steps: [
        { h3: 'Pick a place', text: 'Type a town or use your location. Nothing else to set up.' },
        {
          h3: 'See the top spots',
          text: 'You get the best places nearby as a list and on the map – with a score and the reasons behind it.',
        },
        {
          h3: 'Check and go',
          text: 'Warnings, flight weather and a direct link to dipul.de help with the check. Then start the route.',
        },
      ],
      stepsH2: 'How it works',
      ratesH2: 'What goes into the rating',
      rates: [
        {
          h3: 'Few people',
          items: [
            'Distance to residential areas, buildings and roads',
            'Distance to paths and signposted hiking and cycling routes',
            'Destinations such as car parks, playgrounds and viewpoints',
            'Day and time: Sunday afternoon is not Tuesday morning',
          ],
        },
        {
          h3: 'Good flying',
          items: [
            'Open terrain and a usable take-off and landing spot',
            'Safety distance to roads, railways and power lines',
            'Structure to fly around: forest edges, tree rows, shorelines',
            'Nature reserves and aerodromes are blocked',
          ],
        },
      ],
      legalH2: 'Important: not a substitute for an airspace check',
      legal:
        'The finder is a research tool built on open data. Whether you may fly somewhere is yours to check before every flight – against the EU drone regulation, national law, geographical UAS zones and NOTAMs, most easily on <a href="https://www.dipul.de/homepage/en/" rel="noopener">dipul.de</a>.',
      faqH2: 'Frequently asked questions',
      faqMore: 'See all questions',
      guidesH2: 'Guides: rules and good spots',
      guidesMore: 'All guides',
      regionsLink: 'FPV spots around large cities',
      dataNote: 'Map data: OpenStreetMap. No cookies, no tracking.',
    },
    faq: {
      title: 'FAQ – finding FPV spots, rules and data sources | FPV Flying Spot Finder',
      description:
        'Answers about the FPV spot finder: how the rating works, whether you may fly at a spot, how current the data is and what happens to your data.',
      h1: 'Frequently asked questions',
      items: faqEn,
    },
    start: {
      title: 'FPV spots near you | FPV Flying Spot Finder',
      description: 'One tap and you see the quietest FPV spots around you. Free, no sign-up.',
      h1: 'Quiet FPV spots near you',
      lead: 'One tap is all it takes. Free, no sign-up, no tracking.',
      locate: 'Spots near me',
      or: 'or',
      searchPlaceholder: 'Enter a place',
      searchButton: 'Search',
      proof: ['All of Germany', 'With reasons & warnings', 'Flight weather for every spot'],
    },
  },
} satisfies Record<Lang, unknown>
