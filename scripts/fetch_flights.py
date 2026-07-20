"""
Flug-Finder - Kernscript
=========================
Holt guenstige BUSINESS-CLASS Fluege ab ZRH ueber die Scrappa Google-Flights-API,
bewertet sie nach den Regeln aus der Excel-Datei (Data Ranking Tab) und
schreibt das Ergebnis nach docs/data.json (fuer die Webseite) sowie
history/<datum>.json (fuer die 3-Tage-Historie).

Aufruf:
    python fetch_flights.py --frequency 4x   # Top1+Top2, nur international
    python fetch_flights.py --frequency 1x   # Top3 + alle Europa-Laender
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
HISTORY_DIR = ROOT / "history"

API_KEY = os.environ.get("SCRAPPA_API_KEY")
ORIGIN = "ZRH"
CURRENCY = "CHF"
SCRAPPA_ENDPOINT = "https://scrappa.co/api/flights/round-trip"

# Rule 1 ("Search only business flights or higher") wird direkt in der
# Anfrage per cabin_class=business umgesetzt.


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_flight(destination_airport, departure_date, return_date, retries=2, debug_shown=[False]):
    """Eine Scrappa-Anfrage = ein Land (ein Zielflughafen)."""
    params = {
        "origin": ORIGIN,
        "destination": destination_airport,
        "departure_date": departure_date,
        "return_date": return_date,
        "cabin_class": "business",
        "adults": 1,
        "currency": CURRENCY,
        "sort_by": "cheapest",
        "max_stops": "two_or_fewer",
    }
    headers = {"x-api-key": API_KEY}
    for attempt in range(retries):
        try:
            r = requests.get(SCRAPPA_ENDPOINT, params=params, headers=headers, timeout=20)
        except requests.RequestException as e:
            print(f"  Netzwerkfehler bei {destination_airport}: {e}", file=sys.stderr)
            return []
        if r.status_code == 429:
            print(f"  Rate-Limit (429) bei {destination_airport}, warte kurz ...", file=sys.stderr)
            time.sleep(3)
            continue
        if r.status_code != 200:
            print(f"  Warnung: {destination_airport} -> HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return []
        try:
            payload = r.json()
        except ValueError:
            return []
        flights = payload.get("flights", [])
        # Einmaliges Debug-Logging: zeigt uns die ECHTEN Feldnamen von Scrappa
        if flights and not debug_shown[0]:
            print("DEBUG - Rohes erstes Flug-Objekt von Scrappa:", file=sys.stderr)
            print(json.dumps(flights[0], indent=2, ensure_ascii=False)[:2000], file=sys.stderr)
            debug_shown[0] = True
        return flights
    print(f"  Uebersprungen nach {retries} Versuchen: {destination_airport}", file=sys.stderr)
    return []


def points_for_range(value, ranges):
    for r in ranges:
        lo = r["min"]
        hi = r["max"]
        if hi is None:
            if value >= lo:
                return r["points"]
        elif lo <= value < hi:
            return r["points"]
    return 0


def score_flight(flight, country, rules, alliances, is_europe, departure_date, return_date, destination_airport):
    """flight = ein rohes Scrappa-Ergebnis-Objekt aus dem 'flights'-Array."""
    price = flight.get("price") or flight.get("total_price")
    if price is None:
        return None
    price = round(float(price))

    airline = None
    airline_name = flight.get("airline_name")
    legs = flight.get("legs") or flight.get("outbound_legs") or []
    if legs:
        airline = legs[0].get("airline")
        if not airline_name:
            airline_name = legs[0].get("airline_name")

    is_one_way_only = flight.get("trip_type") == "one_way" and not flight.get("return_legs")
    if is_one_way_only:
        return None  # Regel: nur echte Hin+Rueck-Angebote werden bewertet

    stops = flight.get("stops")
    if stops is None:
        stops = max(len(legs) - 1, 0) if legs else 0

    points = 0
    breakdown = {}

    # Airlines
    if airline in alliances["star_alliance"]:
        p = rules["airlines"]["star_alliance"]
    elif airline in alliances["oneworld"] or airline in alliances["skyteam"]:
        p = rules["airlines"]["oneworld_skyteam"]
    else:
        p = rules["airlines"]["other"]
    breakdown["airline"] = p
    points += p

    # Preis: Europa ODER International (Regel 5)
    if is_europe:
        p = points_for_range(price, rules["pricing_europe_chf"])
    else:
        p = points_for_range(price, rules["pricing_international_chf"])
    breakdown["price"] = p
    points += p

    # Stopover
    stop_key = str(min(int(stops), 2))
    p = rules["stopover"].get(stop_key, 1)
    breakdown["stopover"] = p
    points += p

    # Departure airport - aktuell fix ZRH
    p = rules["departure_airport"]["ZRH"]
    breakdown["departure"] = p
    points += p

    # Time to departure
    dep = datetime.strptime(departure_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    days_out = (dep - datetime.now(timezone.utc)).days
    p = points_for_range(days_out, rules["time_to_departure_days"])
    breakdown["time_to_departure"] = p
    points += p

    # Season
    month = dep.month
    if month in country["high_season_months"]:
        season = "high"
    elif month in country["shoulder_season_months"]:
        season = "shoulder"
    else:
        season = "off"
    p = rules["season"][season]
    breakdown["season"] = p
    points += p

    # Interest (Top1/2/3)
    p = rules["interest_tier"][str(country["interest_tier"])]
    breakdown["interest"] = p
    points += p

    # Duration
    ret = datetime.strptime(return_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    duration_days = (ret - dep).days
    p = points_for_range(duration_days, rules["duration_days"])
    breakdown["duration"] = p
    points += p

    booking_link = flight.get("booking_link") or (
        f"https://www.google.com/travel/flights?q=Flights%20from%20{ORIGIN}%20to%20"
        f"{destination_airport}%20on%20{departure_date}%20through%20{return_date}"
    )

    return {
        "country": country["country"],
        "destination_airport": destination_airport,
        "price_chf": price,
        "airline": airline_name or airline,
        "airline_code": airline,
        "stopovers": int(stops),
        "departure_at": departure_date,
        "days_until_departure": days_out,
        "duration_days": duration_days,
        "season": season,
        "interest_tier": country["interest_tier"],
        "is_europe": is_europe,
        "cabin": "Business",
        "points": points,
        "breakdown": breakdown,
        "booking_link": booking_link,
    }


def tier_for_points(points, rules):
    t = rules["tiers"]
    if t["top1"]["min"] <= points <= t["top1"]["max"]:
        return 1
    if t["top2"]["min"] <= points <= t["top2"]["max"]:
        return 2
    if t["top3"]["min"] <= points <= t["top3"]["max"]:
        return 3
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frequency", choices=["4x", "1x"], required=True)
    parser.add_argument("--limit", type=int, default=None,
                         help="Nur die ersten N Laender pruefen (zum Testen)")
    args = parser.parse_args()

    if not API_KEY:
        print("FEHLER: Umgebungsvariable SCRAPPA_API_KEY fehlt.", file=sys.stderr)
        sys.exit(1)

    countries = load_json(DATA_DIR / "countries.json")
    rules = load_json(DATA_DIR / "ranking_rules.json")
    europe_list = set(load_json(DATA_DIR / "europe_countries.json"))
    alliances = load_json(DATA_DIR / "airline_alliances.json")
    country_airports = load_json(DATA_DIR / "country_airports.json")

    # Baue Liste der zu pruefenden Laender, gefiltert nach Frequenz-Modus
    selected_countries = []
    for c in countries:
        is_europe = c["country"] in europe_list
        airport = country_airports.get(c["country"])
        if not airport:
            continue  # kein eigener Flughafen (z.B. Vatikan, Monaco)
        if args.frequency == "4x":
            if c["interest_tier"] in (1, 2) and not is_europe:
                selected_countries.append(c)
        else:
            if c["interest_tier"] == 3 or is_europe:
                selected_countries.append(c)

    print(f"{len(selected_countries)} Laender in diesem Lauf ({args.frequency}).")

    if args.limit:
        selected_countries = selected_countries[:args.limit]
        print(f"Test-Modus: nur die ersten {len(selected_countries)} Laender.")

    # Ein Reisefenster: Abflug in ~3 Monaten, 10 Tage Aufenthalt
    departure_date = (datetime.now() + timedelta(days=95)).strftime("%Y-%m-%d")
    return_date = (datetime.now() + timedelta(days=105)).strftime("%Y-%m-%d")

    results = []
    for i, country in enumerate(selected_countries):
        airport = country_airports[country["country"]]
        print(f"[{i+1}/{len(selected_countries)}] {country['country']} ({airport}) ...")
        raw_flights = fetch_flight(airport, departure_date, return_date)
        print(f"  -> {len(raw_flights)} Rohergebnisse von Scrappa")
        is_europe = country["country"] in europe_list
        for flight in raw_flights[:3]:  # nur die 3 guenstigsten je Land verarbeiten
            trip_type = flight.get("trip_type")
            has_return = bool(flight.get("return_legs"))
            price = flight.get("price")
            print(f"     Preis={price} trip_type={trip_type} return_legs={'ja' if has_return else 'nein'}")
            scored = score_flight(flight, country, rules, alliances, is_europe, departure_date, return_date, airport)
            if scored is None:
                print("     -> uebersprungen (kein echtes Hin+Rueck-Angebot)")
                continue
            scored["tier"] = tier_for_points(scored["points"], rules)
            print(f"     -> {scored['points']} Punkte, Tier {scored['tier']}")
            if scored["tier"] is not None:
                results.append(scored)
        time.sleep(0.3)  # kleine Pause zwischen Requests

    # Regel 7: max. 2 Fluege pro Airline+Ziel; nur Top1-3 Tiers, max 100
    results.sort(key=lambda r: -r["points"])
    seen = {}
    deduped = []
    for r in results:
        key = (r["airline"], r["country"])
        seen.setdefault(key, 0)
        if seen[key] < 2:
            deduped.append(r)
            seen[key] += 1
    top_results = deduped[:100]

    # Bestehende data.json laden und mergen (4x/1x laufen unabhaengig)
    DOCS_DIR.mkdir(exist_ok=True)
    data_path = DOCS_DIR / "data.json"
    existing = {"flights": [], "last_updated": None}
    if data_path.exists():
        existing = load_json(data_path)

    other_frequency_countries = {c["country"] for c in countries} - {c["country"] for c in selected_countries}
    kept = [f for f in existing.get("flights", []) if f["country"] in other_frequency_countries]
    merged = kept + top_results
    merged.sort(key=lambda r: -r["points"])
    merged = merged[:100]

    now = datetime.now(timezone.utc).isoformat()
    output = {"flights": merged, "last_updated": now}

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Historie (letzte 3 Tage, Regel 6 der Visualization)
    HISTORY_DIR.mkdir(exist_ok=True)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(HISTORY_DIR / f"{today_str}.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history_files = sorted(HISTORY_DIR.glob("*.json"))
    for old_file in history_files[:-3]:
        old_file.unlink()

    print(f"Fertig. {len(top_results)} neue Fluege verarbeitet, {len(merged)} insgesamt in data.json.")


if __name__ == "__main__":
    main()
