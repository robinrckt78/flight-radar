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

## Schritt 2: Scrappa API-Key holen + als Secret hinterlegen

1. Geh auf **scrappa.co/register** und leg kostenlos ein Konto an
2. E-Mail bestaetigen
3. Im Dashboard einen **API-Key** erstellen (wird nur einmal angezeigt -
   direkt kopieren und sicher abspeichern!)
4. Du bekommst automatisch **500 kostenlose Credits/Monat**. Da wir echte
   Suchmengen brauchen, musst du danach ein kleines Guthaben aufladen
   (Pay-as-you-go, ca. **5-8$/Monat** bei unserer Suchmenge, siehe
   scrappa.co/pricing)

Dann im Repo als Secret hinterlegen:

1. Im Repo → **Settings** (oben) → links **"Secrets and variables"** → **"Actions"**
2. **"New repository secret"**
3. Name: `SCRAPPA_API_KEY`
4. Value: dein Scrappa-API-Key
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

Ein paar Regeln aus deiner Excel-Liste lassen sich mit einer automatisierten
Loesung nicht 1:1 umsetzen. Ehrlich und transparent:

- **"Nur Business Class oder hoeher"**: ✅ umgesetzt via Scrappas
  `cabin_class=business` Parameter (echte Google-Flights-Daten).
- **Kosten**: Scrappa ist NICHT komplett kostenlos (anders als urspruenglich
  mit Kiwi/Travelpayouts geplant - beide Wege haben sich als fuer private
  Projekte nicht zugaenglich herausgestellt: Kiwi ist inzwischen nur noch auf
  Einladung, Travelpayouts verlangt 50.000 monatliche Nutzer). Rechne mit
  ca. 5-8$/Monat je nach Suchmenge.
- **Ein Flughafen pro Land**: Da Scrappa einen exakten Zielflughafen braucht
  (nicht wie urspruenglich geplant ein ganzes Land), sucht das Tool pro Land
  nur zum wichtigsten internationalen Flughafen (siehe
  `data/country_airports.json`). 11 Laender ohne eigenen Flughafen (z.B.
  Vatikan, Monaco, Andorra) werden uebersprungen.
- **Nur EIN Reisefenster pro Lauf**: Das Tool sucht aktuell Business-Class-
  Fluege ca. 3 Monate im Voraus mit 10 Tagen Aufenthalt. Mehrere Zeitfenster
  gleichzeitig zu pruefen wuerde die Kosten vervielfachen.
- **"Nur Preise direkt von Airlines, nicht von Drittanbietern"**: Google
  Flights aggregiert selbst aus vielen Quellen. Eine echte "nur
  Airline-direkt"-Pruefung braucht pro Airline eine eigene technische Anbindung.
- **"Morgens/mittags/abends/mitternachts pruefen"**: aktuell wird 1x pro Lauf
  geprueft, um die Kosten im Rahmen zu halten.
- **Kartenansicht**: aktuell als farbcodierte Liste/Badges umgesetzt (Tier 1/2/3
  Farben wie gewuenscht). Eine echte geografische Weltkarte ist ein moeglicher
  naechster Ausbauschritt.
- **Departure-Flughafen**: aktuell nur ab ZRH. FRA/MUC/MIL koennen bei Bedarf
  ergaenzt werden.
- **Antwortformat von Scrappa**: Die Doku zeigt kein vollstaendiges
  Beispiel fuer das `flights`-Array. Das Script ist defensiv geschrieben
  (mehrere moegliche Feldnamen), aber beim ersten echten Testlauf lohnt
  sich ein Blick in die Logs, falls Fluege fehlen sollten - dann passen
  wir die Feldnamen gemeinsam an.
- **Buchungslink**: Scrappa liefert keine fertige Buchungs-URL (nur einen technischen
  Token). Das Tool baut stattdessen einen funktionierenden Google-Flights-
  Such-Link zusammen - du landest auf der Suchseite mit den passenden Daten,
  statt direkt auf einer Buchungsseite.
- **Vereinzelt Einweg-Preise**: Bei seltenen Strecken liefert Google Flights
  manchmal keinen kombinierbaren Rückflugtarif. Das Tool markiert das dann
  mit "(nur Hinflug)" auf der Webseite.
- **WhatsApp & E-Mail-Versand**: bewusst noch nicht eingebaut (auf deinen
  Wunsch, kommt spaeter).

## Naechste moegliche Schritte

- E-Mail-Versand (GMX) einbauen, sobald du bereit bist
- Echte Weltkarte statt Farbliste
- Mehrere Abflughaefen (FRA, MUC, MIL)
- WhatsApp-Benachrichtigung bei neuem Top-1-Flug
