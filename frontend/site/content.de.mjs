/**
 * Deutsche Inhalte für die statischen Seiten.
 *
 * Diese Datei ist die einzige Quelle für Texte und Meta-Angaben der
 * deutschen Landing- und FAQ-Seite. Eine weitere Sprache hinzuzufügen heißt:
 * diese Datei kopieren, übersetzen und in scripts/build-site.mjs eintragen.
 */

export default {
  lang: 'de',
  // Leeres Präfix = Sprache liegt auf der Wurzel (/), andere unter /en/ usw.
  prefix: '',
  dir: 'ltr',
  label: 'Deutsch',

  nav: {
    home: 'Start',
    app: 'Zum Finder',
    faq: 'FAQ',
    otherLang: 'English',
  },

  landing: {
    title: 'FPV-Flugort finden – ruhige Spots ohne Menschen | FPV Flying Spot Finder',
    description:
      'Kostenloses Tool, das im gewählten Umkreis FPV-Flugorte findet, an denen du '
      + 'wenig Menschen begegnest und gut fliegen kannst. Basiert auf OpenStreetMap, '
      + 'Overpass und der Strava-Heatmap. Ohne Anmeldung, ohne Werbung.',
    h1: 'FPV-Flugort finden, an dem dir niemand begegnet',
    lead:
      'Du kennst das: Du willst fliegen, findest aber nur Spots, an denen Sonntagsspaziergänger, '
      + 'Hundehalter und Radfahrer unterwegs sind. Dieses Tool durchsucht deinen Umkreis nach Stellen, '
      + 'an denen statistisch kaum jemand ist – und an denen sich auch wirklich fliegen lässt.',
    ctaPrimary: 'Finder öffnen',
    ctaSecondary: 'Wie es funktioniert',

    sections: [
      {
        h2: 'Für wen das gedacht ist',
        paragraphs: [
          'Für alle, die einen ruhigen Platz zum Fliegen suchen und keine Lust haben, dafür '
          + 'erst mehrere Stellen abzuklappern. Sämtliche Bewertungskriterien lassen sich an die '
          + 'eigenen Anforderungen anpassen.',
          'Genauso nützlich für alle, die einfach wissen wollen, wo in ihrer Gegend noch '
          + 'freie Fläche ohne Publikum ist – für Drohnen-Fotografie, Modellflug oder zum '
          + 'Einfliegen einer neuen Maschine.',
        ],
      },
      {
        h2: 'Was das Tool bewertet',
        paragraphs: [
          'Jeder Punkt im Suchradius bekommt zwei Bewertungen von 0 bis 100, die anschließend '
          + 'gewichtet zusammengeführt werden.',
        ],
        list: [
          '<strong>Wie wenig Menschen</strong> dort zu erwarten sind: Abstand zu Gebäuden, '
          + 'Wohn- und Erholungsgebieten, Straßen (nach Verkehrsstärke gewichtet), Wegen, '
          + 'Spielplätzen, Parkplätzen und Gasthäusern – dazu die Landnutzung.',
          '<strong>Wie gut sich dort fliegen lässt</strong>: offenes Gelände, Eignung als '
          + 'Start- und Landeplatz, Sicherheitsabstand zu Straßen und Bahnlinien, Abstand zu '
          + 'Freileitungen und ein Bonus für Struktur in der Nähe, etwa Waldkanten.',
          '<strong>Reale Nutzung statt nur Karteneintrag</strong>: die Strava-Heatmap zeigt, '
          + 'welche Wege tatsächlich gelaufen und geradelt werden. Ein Feldweg kann in der '
          + 'Karte unauffällig aussehen und trotzdem die Hausstrecke aller Rennradfahrer sein.',
        ],
      },
      {
        h2: 'So funktioniert die Standortsuche',
        id: 'how',
        steps: [
          {
            h3: 'Startpunkt und Radius wählen',
            text: 'Adresse eingeben, aktuelle Position nutzen oder direkt auf die Karte klicken. '
              + 'Der Radius ist frei einstellbar.',
          },
          {
            h3: 'Zeitprofil einstellen',
            text: 'Ein Feldweg am Dienstagmorgen ist etwas völlig anderes als am Sonntagnachmittag. '
              + 'Das Profil gewichtet freizeitgetriebene Faktoren entsprechend.',
          },
          {
            h3: 'Karte auswerten',
            text: 'Grün heißt geeignet, rot ungeeignet. Ein Klick auf einen Punkt zeigt alle '
              + 'Einzelbewertungen, Entfernungen und Warnhinweise – etwa zu Naturschutzgebieten '
              + 'oder Freileitungen.',
          },
        ],
      },
      {
        h2: 'Welche Daten verwendet werden',
        paragraphs: [
          'Ausschließlich frei verfügbare Quellen. Es gibt keine Anmeldung, keine Nutzerkonten '
          + 'und keine Werbung.',
        ],
        list: [
          '<strong>OpenStreetMap</strong> über die Overpass-API: Landnutzung, Gebäude, Straßen, '
          + 'Wege, Schutzgebiete, Freileitungen.',
          '<strong>Strava-Heatmap</strong>: aggregierte, anonymisierte Bewegungsdaten als '
          + 'Hinweis auf tatsächlich genutzte Strecken.',
          '<strong>Eigene Sperrzonen</strong>: selbst gepflegte Gebiete, etwa Kontrollzonen '
          + 'oder Wildruhezonen.',
        ],
      },
    ],

    disclaimer: {
      h2: 'Wichtiger rechtlicher Hinweis',
      text:
        'Dieses Tool ist ein Recherchewerkzeug auf Basis offener Daten und <strong>ersetzt keine '
        + 'offizielle Luftraumprüfung</strong>. Die EU-Drohnenverordnung (VO 2019/947), die '
        + 'nationalen Regeln, aktuelle NOTAMs und geografische UAS-Gebiete musst du vor jedem '
        + 'Flug selbst prüfen – in Deutschland zum Beispiel über dipul.de oder die DFS-UAS-Karte. '
        + 'OpenStreetMap-Daten zu Schutzgebieten können unvollständig oder veraltet sein.',
    },



    faqTeaser: {
      h2: 'Häufige Fragen',
      cta: 'Alle Fragen ansehen',
    },
  },

  faq: {
    title: 'FAQ – Häufige Fragen zum FPV-Flugort-Finder',
    description:
      'Antworten zur Standortsuche für FPV-Flüge: Wie die Bewertung funktioniert, welche '
      + 'Daten genutzt werden, wie zuverlässig die Ergebnisse sind und was rechtlich gilt.',
    h1: 'Häufige Fragen',
    intro: 'Wenn deine Frage hier nicht beantwortet ist, findest du auf GitHub zu jedem '
      + 'Bewertungsschritt eine ausführliche Begründung.',

    // Diese Einträge werden zusätzlich als FAQPage-JSON-LD ausgegeben.
    items: [
      {
        q: 'Wie funktioniert die Standortsuche?',
        a: 'Das Tool legt ein Raster über den gewählten Umkreis – standardmäßig alle 150 Meter '
          + 'ein Punkt. Für jeden dieser Punkte werden die Entfernungen zu Gebäuden, Straßen, '
          + 'Wegen, Freileitungen und weiteren Objekten berechnet und mit der Landnutzung an '
          + 'dieser Stelle kombiniert. Daraus entstehen zwei Bewertungen: wie menschenleer der '
          + 'Ort voraussichtlich ist und wie gut sich dort fliegen lässt.',
      },
      {
        q: 'Welche Daten nutzt das Tool?',
        a: 'OpenStreetMap über die Overpass-API liefert Landnutzung, Gebäude, Straßen, Wege, '
          + 'Schutzgebiete und Freileitungen. Die Strava-Heatmap ergänzt, welche Wege real '
          + 'genutzt werden. Optional lässt sich ein Bevölkerungsdichte-Raster einbinden. '
          + 'Alle Quellen sind frei verfügbar, es wird kein API-Schlüssel benötigt.',
      },
      {
        q: 'Ersetzt das die Luftraumprüfung?',
        a: 'Nein, ausdrücklich nicht. Die Bewertung ist eine Heuristik auf unvollständigen '
          + 'offenen Daten. Ob an einem Ort geflogen werden darf, richtet sich nach der '
          + 'EU-Drohnenverordnung, nationalen Vorschriften, geografischen UAS-Gebieten und '
          + 'aktuellen NOTAMs. Diese Prüfung musst du vor jedem Flug selbst über die amtlichen '
          + 'Quellen vornehmen.',
      },
      {
        q: 'Warum wird ein Punkt als gesperrt angezeigt?',
        a: 'Punkte werden markiert, wenn sie eine der harten Regeln verletzen: weniger als '
          + '150 Meter zu einem Wohn- oder Erholungsgebiet (angelehnt an die EU-Kategorie A3), '
          + 'zu geringer Abstand zu Gebäuden, Straßen oder Bahnlinien, Lage in einem '
          + 'Naturschutzgebiet oder in der Nähe eines Flugplatzes. Solche Punkte werden bewusst '
          + 'nicht ausgeblendet, sondern mit Begründung angezeigt – damit sichtbar bleibt, '
          + 'warum eine Gegend ausfällt.',
      },
      {
        q: 'Was bedeutet das Zeitprofil?',
        a: 'Wochentag und Uhrzeit sind ein Eingabeparameter, keine Live-Daten. Das Profil '
          + 'steuert, wie stark freizeitgetriebene Faktoren zählen: Wege, Ausflugsziele und '
          + 'die Strava-Heatmap. Sonntagnachmittag bewertet einen Waldweg deutlich strenger '
          + 'als Dienstagmorgen, dafür fällt dann die Landwirtschaft weniger ins Gewicht.',
      },
      {
        q: 'Wie genau sind die Ergebnisse?',
        a: 'Die Ergebnisse sind so gut wie die zugrunde liegenden OpenStreetMap-Daten. In gut '
          + 'kartierten Gegenden sind sie sehr brauchbar, in dünn kartierten kann eine Fläche '
          + 'als unauffällig erscheinen, obwohl dort etwas steht. Prüfe einen Spot vor dem '
          + 'ersten Flug immer noch einmal per Satellitenbild und vor Ort.',
      },
      {
        q: 'Kostet die Nutzung etwas?',
        a: 'Nein. Es gibt keine Anmeldung, keine kostenpflichtige Version und keine künstlich '
          + 'begrenzten Funktionen. Wer die Serverkosten unterstützen möchte, kann das '
          + 'freiwillig tun – am Funktionsumfang ändert das nichts.',
      },
      {
        q: 'Kann ich die Bewertung an mein Fluggebiet anpassen?',
        a: 'Ja. Sämtliche Gewichte und Schwellenwerte lassen sich im Reiter „Gewichte“ '
          + 'verändern und für die nächste Suche übernehmen. Wer eigene Werte dauerhaft '
          + 'speichern oder eigene Sperrzonen pflegen möchte, betreibt am besten eine eigene '
          + 'Instanz – ein fertiges Docker-Image steht bereit.',
      },
      {
        q: 'Warum wird die Strava-Heatmap einbezogen?',
        a: 'OpenStreetMap sagt nur, was eine Fläche ist – nicht, wie stark sie genutzt wird. '
          + 'Ein Feldweg zwischen zwei Äckern sieht in der Karte unauffällig aus, kann aber die '
          + 'Feierabendrunde aller Rennradfahrer der Umgebung sein. Die Heatmap zeigt genau '
          + 'dieses reale Bewegungsverhalten und wertet solche Punkte ab.',
      },
      {
        q: 'Welche Daten werden über mich gespeichert?',
        a: 'Keine personenbezogenen. Es gibt keine Nutzerkonten, keine Cookies, kein Tracking '
          + 'und keine Werbung. Die abgefragten Kartendaten werden serverseitig zwischen'
          + 'gespeichert, damit spätere Suchen schneller sind – dieser Zwischenspeicher '
          + 'enthält Kartendaten, nicht die Information, wer sie angefragt hat.',
      },
    ],
  },

  footer: {
    tagline: 'Kostenloses Community-Tool · keine Konten · keine Werbung',
    source: 'GitHub',
    imprint: 'Impressum',
    privacy: 'Datenschutz',
    funding: 'Serverkosten',
    attribution: 'Kartendaten © OpenStreetMap-Mitwirkende (ODbL), Heatmap © Strava',
  },
}
