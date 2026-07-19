# Flug-Radar ab ZRH

Automatisiertes Tool, das guenstige Fluege findet, nach deinen eigenen
Regeln bewertet (siehe `data/ranking_rules.json`, 1:1 aus deiner Excel-Datei)
und als Webseite anzeigt. Laeuft komplett kostenlos ueber GitHub Actions +
GitHub Pages.

## Schritt 1: Dieses Paket zu einem GitHub-Repository machen

1. Geh auf **github.com** → oben rechts auf **"+"** → **"New repository"**
2. Name z.B. `flug-radar`, Sichtbarkeit **Private** (empfohlen, da dein API-Token
   sonst niemand sehen soll, auch wenn der Token selbst als Secret sicher ist)
3. **"Create repository"** klicken
4. Auf der neuen, leeren Repo-Seite: **"uploading an existing file"** anklicken
5. Alle Dateien und Ordner aus diesem Paket (entpackt) per Drag & Drop reinziehen
   - Wichtig: die Ordnerstruktur muss erhalten bleiben (`.github/workflows/`,
     `data/`, `docs/`, `scripts/`)
6. Unten **"Commit changes"** klicken

## Schritt 2: Kiwi.com Tequila API Zugang holen + als Secret hinterlegen

1. Geh auf **tequila.kiwi.com/portal/login/register** und registrier dich
   kostenlos
2. Nach dem Login: im Portal einen neuen "Application"-Eintrag erstellen
   (Name z.B. "Flug-Radar") → du bekommst einen **API-Key**
3. Kopier dir den Key

Dann im Repo als Secret hinterlegen:

1. Im Repo → **Settings** (oben) → links **"Secrets and variables"** → **"Actions"**
2. **"New repository secret"**
3. Name: `KIWI_API_TOKEN`
4. Value: dein Kiwi-API-Key
5. **"Add secret"**

## Schritt 3: GitHub Pages aktivieren (deine Webseite)

1. Im Repo → **Settings** → links **"Pages"**
2. Bei **"Source"**: **"Deploy from a branch"** waehlen
3. Branch: **main**, Ordner: **/docs** → **Save**
4. Nach ca. 1-2 Minuten ist deine Webseite live unter:
   `https://DEIN-USERNAME.github.io/flug-radar/`

## Schritt 4: Automatisierung testen

1. Im Repo → Tab **"Actions"** oben
2. Falls eine Meldung kommt "Workflows aktivieren" → bestaetigen
3. Links siehst du zwei Workflows: **"Flug-Check 4x taeglich"** und
   **"Flug-Check 1x taeglich"**
4. Klick auf einen → rechts **"Run workflow"** → **"Run workflow"** (Button)
5. Nach 1-2 Minuten sollte ein gruener Haken erscheinen → dann auf deiner
   Webseite neu laden, die ersten Fluege sollten erscheinen

Ab jetzt laeuft alles automatisch nach dem hinterlegten Zeitplan (siehe
`.github/workflows/*.yml`), du musst nichts mehr manuell tun.

## Was das Tool tut

- **4x taeglich:** prueft Fluege zu allen Top-1- und Top-2-Laendern
  (ausserhalb Europas)
- **1x taeglich:** prueft Fluege zu allen Top-3-Laendern und allen
  europaeischen Laendern
- Bewertet jeden Flug nach deinen Punkteregeln (Airline, Preis, Stopover,
  Abflughafen, Vorlaufzeit, Season, Interesse, Reisedauer)
- Zeigt nur Fluege der Top-1-3-Tier-Punktebereiche (25+ Punkte)
- Max. 2 Fluege pro Airline+Land, max. 100 Fluege insgesamt
- Behaelt eine 3-Tage-Historie (`history/`-Ordner)

## Bekannte Einschraenkungen (bitte lesen)

Ein paar Regeln aus deiner Excel-Liste lassen sich mit einer kostenlosen,
automatisierten Loesung nicht 1:1 umsetzen. Ehrlich und transparent:

- **"Nur Business Class oder hoeher"**: ✅ umgesetzt via Kiwi's
  `selected_cabins=C` Parameter. Einschraenkung: Kiwi zeigt nur Business
  Class an (nicht zusaetzlich First Class als "hoeher"). Kann bei Bedarf
  erweitert werden.
- **"Nur Preise direkt von Airlines, nicht von Drittanbietern"**: Kiwi ist ein
  Aggregator und nutzt teils "virtuelles Interlining" (kombiniert separate
  Tickets verschiedener Airlines zu einer Reise). Das kann von "direkt bei
  der Airline gebucht" abweichen. Eine echte "nur Airline-direkt"-Pruefung
  braucht pro Airline eine eigene technische Anbindung.
- **"Morgens/mittags/abends/mitternachts pruefen"**: aktuell wird 1x pro Lauf
  geprueft (nicht 4x pro Tageszeit zusaetzlich), um die Anzahl API-Calls im
  kostenlosen Rahmen zu halten.
- **Kartenansicht**: aktuell als farbcodierte Liste/Badges umgesetzt (Tier 1/2/3
  Farben wie gewuenscht). Eine echte geografische Weltkarte ist ein moeglicher
  naechster Ausbauschritt.
- **Departure-Flughafen**: aktuell nur ab ZRH. FRA/MUC/MIL koennen bei Bedarf
  ergaenzt werden.
- **Kiwi Rate-Limits**: Der kostenlose Kiwi-Zugang hat Limits, die nicht
  oeffentlich exakt dokumentiert sind. Das Script fragt mehrere Laender pro
  Call ab (spart Requests) und wartet bei Rate-Limit-Fehlern automatisch.
  Falls trotzdem oefter Daten fehlen, ist der Wechsel zu Scrappa (~5-8$/Monat,
  echte Google-Flights-Daten) die naechste Eskalationsstufe.
- **WhatsApp & E-Mail-Versand**: bewusst noch nicht eingebaut (auf deinen
  Wunsch, kommt spaeter).

## Naechste moegliche Schritte

- E-Mail-Versand (GMX) einbauen, sobald du bereit bist
- Echte Weltkarte statt Farbliste
- Mehrere Abflughaefen (FRA, MUC, MIL)
- WhatsApp-Benachrichtigung bei neuem Top-1-Flug
