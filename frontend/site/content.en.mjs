/**
 * English content for the static pages.
 *
 * Mirrors the structure of content.de.mjs exactly - the renderer is shared, so
 * adding a language means copying one of these files, translating it, and
 * registering it in scripts/build-site.mjs.
 */

export default {
  lang: 'en',
  prefix: 'en',
  dir: 'ltr',
  label: 'English',

  nav: {
    home: 'Home',
    app: 'Open the finder',
    faq: 'FAQ',
    otherLang: 'Deutsch',
  },

  landing: {
    title: 'FPV Flying Spot Finder – find quiet places to fly your drone',
    description:
      'Free tool that finds FPV flying spots near you where few people are about and '
      + 'the flying is actually good. Built on OpenStreetMap, Overpass and the Strava '
      + 'heatmap. No sign-up, no ads.',
    h1: 'Find an FPV flying spot where nobody will bother you',
    lead:
      'You know the problem: you want to fly, but every spot you can think of has dog '
      + 'walkers, hikers and cyclists on it. This tool searches the area around you for places '
      + 'where statistically almost nobody goes - and where flying actually works.',
    ctaPrimary: 'Open the finder',
    ctaSecondary: 'How it works',

    sections: [
      {
        h2: 'Who this is for',
        paragraphs: [
          'Anyone looking for a quiet place to fly who would rather not drive to three spots '
          + 'to find out. Every scoring criterion can be adjusted to your own requirements.',
          'Equally useful for anyone who just wants to know where the open, unpopulated ground '
          + 'nearby is - for drone photography, model flying, or maiden-flighting a new build.',
        ],
      },
      {
        h2: 'What the tool evaluates',
        paragraphs: [
          'Every point inside the search radius gets two scores from 0 to 100, which are then '
          + 'combined by weight.',
        ],
        list: [
          '<strong>How few people</strong> to expect: distance to buildings, residential and '
          + 'recreational areas, roads (weighted by traffic class), paths, playgrounds, car '
          + 'parks and pubs - plus the land use at that spot.',
          '<strong>How well it flies</strong>: open terrain, suitability as a take-off and '
          + 'landing spot, safety clearance from roads and railway lines, distance to power '
          + 'lines, and a bonus for nearby structure such as a tree line.',
          '<strong>Real usage, not just map data</strong>: the Strava heatmap shows which paths '
          + 'are actually walked and ridden. A farm track can look unremarkable on the map and '
          + 'still be the local after-work loop for every road cyclist around.',
        ],
      },
      {
        h2: 'How the search works',
        id: 'how',
        steps: [
          {
            h3: 'Pick a starting point and radius',
            text: 'Type an address, use your current position, or click straight on the map. '
              + 'The radius is yours to choose.',
          },
          {
            h3: 'Set the time profile',
            text: 'A farm track on a Tuesday morning is a completely different thing from a '
              + 'Sunday afternoon. The profile weights the leisure-driven factors accordingly.',
          },
          {
            h3: 'Read the map',
            text: 'Green means suitable, red means not. Clicking a point shows every individual '
              + 'score, the distances behind it and any warnings - nature reserves or power '
              + 'lines, for example.',
          },
        ],
      },
      {
        h2: 'What data it uses',
        paragraphs: [
          'Openly available sources only. There is no sign-up, no user account and no advertising.',
        ],
        list: [
          '<strong>OpenStreetMap</strong> via the Overpass API: land use, buildings, roads, '
          + 'paths, protected areas, power lines.',
          '<strong>Strava heatmap</strong>: aggregated, anonymised movement data as an '
          + 'indicator of which routes are genuinely used.',
          '<strong>Your own no-fly zones</strong>: areas you maintain yourself, such as control '
          + 'zones or wildlife refuges.',
        ],
      },
    ],

    disclaimer: {
      h2: 'Important legal notice',
      text:
        'This tool is a research aid built on open data and <strong>does not replace an '
        + 'official airspace check</strong>. The EU drone regulation (2019/947), your national '
        + 'rules, current NOTAMs and geographical UAS zones all have to be verified by you '
        + 'before every flight - in Germany for instance via dipul.de or the DFS UAS map. '
        + 'OpenStreetMap data on protected areas may be incomplete or out of date.',
    },



    faqTeaser: {
      h2: 'Frequently asked questions',
      cta: 'See all questions',
    },
  },

  faq: {
    title: 'FAQ – FPV Flying Spot Finder',
    description:
      'Answers about finding places to fly FPV: how the scoring works, what data is used, '
      + 'how reliable the results are and what the legal situation is.',
    h1: 'Frequently asked questions',
    intro: 'If your question is not answered here, GitHub explains the reasoning behind '
      + 'every scoring step in detail.',

    items: [
      {
        q: 'How does the location search work?',
        a: 'The tool lays a grid over the chosen radius - one point every 150 metres by '
          + 'default. For each of those points it computes the distances to buildings, roads, '
          + 'paths, power lines and other features, and combines them with the land use at that '
          + 'spot. That produces two scores: how deserted the place is likely to be, and how '
          + 'well it flies.',
      },
      {
        q: 'What data does the tool use?',
        a: 'OpenStreetMap via the Overpass API supplies land use, buildings, roads, paths, '
          + 'protected areas and power lines. The Strava heatmap adds which paths are actually '
          + 'used. A population density raster can optionally be added. All sources are freely '
          + 'available and no API key is required.',
      },
      {
        q: 'Does this replace an airspace check?',
        a: 'No, explicitly not. The scoring is a heuristic over incomplete open data. Whether '
          + 'you may fly somewhere is governed by the EU drone regulation, national rules, '
          + 'geographical UAS zones and current NOTAMs. You have to verify that yourself, '
          + 'before every flight, using the official sources.',
      },
      {
        q: 'Why is a point shown as blocked?',
        a: 'Points are flagged when they violate one of the hard rules: less than 150 metres to '
          + 'a residential or recreational area (following EU category A3), too little clearance '
          + 'from buildings, roads or railway lines, sitting inside a nature reserve, or being '
          + 'close to an aerodrome. Such points are deliberately not hidden but shown with a '
          + 'reason, so it stays visible why an area is unusable.',
      },
      {
        q: 'What does the time profile do?',
        a: 'Day and time are an input parameter, not live data. The profile controls how heavily '
          + 'the leisure-driven factors count: paths, attractions and the Strava heatmap. Sunday '
          + 'afternoon judges a forest track far more harshly than Tuesday morning, while '
          + 'agricultural activity then counts for less.',
      },
      {
        q: 'How accurate are the results?',
        a: 'They are as good as the underlying OpenStreetMap data. In well-mapped areas they are '
          + 'very usable; in sparsely mapped ones a field can look unremarkable even though '
          + 'something is standing on it. Always check a spot on satellite imagery and on site '
          + 'before flying it for the first time.',
      },
      {
        q: 'Does it cost anything?',
        a: 'No. There is no sign-up, no paid tier and no artificially limited features. If you '
          + 'want to help cover the hosting costs you can do so voluntarily; it changes nothing '
          + 'about what the tool does.',
      },
      {
        q: 'Can I adapt the scoring to my own area?',
        a: 'Yes. Every weight and threshold can be changed under the "Weights" tab and applied '
          + 'to your next search. If you want to save your own values permanently or maintain '
          + 'your own no-fly zones, run your own instance - a ready-made Docker image is '
          + 'available.',
      },
      {
        q: 'Why is the Strava heatmap included?',
        a: 'OpenStreetMap only tells you what an area is, not how heavily it is used. A farm '
          + 'track between two fields looks unremarkable on the map but may be the after-work '
          + 'loop for every road cyclist in the area. The heatmap captures exactly that '
          + 'real-world movement and marks such points down.',
      },
      {
        q: 'What data is stored about me?',
        a: 'Nothing personal. There are no user accounts, no cookies, no tracking and no ads. '
          + 'The map data retrieved for a search is cached on the server so later searches are '
          + 'faster - that cache holds map data, not who requested it.',
      },
    ],
  },

  footer: {
    tagline: 'Free community tool · no accounts · no ads',
    source: 'GitHub',
    imprint: 'Imprint',
    privacy: 'Privacy',
    funding: 'Running costs',
    attribution: 'Map data © OpenStreetMap contributors (ODbL), heatmap © Strava',
  },
}
