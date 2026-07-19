"""
Flug-Finder - Kernscript
=========================
Holt guenstige BUSINESS-CLASS Fluege ab ZRH ueber die Kiwi.com Tequila API,
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
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
HISTORY_DIR = ROOT / "history"

API_TOKEN = os.environ.get("KIWI_API_TOKEN")
ORIGIN = "ZRH"
CURRENCY = "chf"
KIWI_ENDPOINT = "https://tequila-api.kiwi.com/v2/search"
COUNTRY_BATCH_SIZE = 20  # mehrere Laender pro API-Call abfragen (spart Requests)

# Rule 1 ("Search only business flights or higher") wird direkt in der
# Kiwi-Anfrage per selected_cabins=C umgesetzt.


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower()
    for junk in ["republic of", "(", ")", "islamic", "democratic", "the ",
                 "federation", "kingdom of", "state of", "officially",
                 ";", "islands", "island"]:
        name = name.replace(junk, "")
    return " ".join(name.split())


# ISO-3166 Alpha-2 Codes fuer Laender, deren Namen in der Excel-Liste vom
# offiziellen Namen abweichen (fuer den Rest nutzen wir pycountry.search_fuzzy).
MANUAL_ISO_OVERRIDES = {
    "korea south": "KR",
    "korea dem. repuplic": "KP",
    "lao": "LA",
    "congo republic of": "CG",
    "democratic republic of the congo (kinshasa)": "CD",
    "taiwan (republic of china)": "TW",
    "slovakia (slovak republic)": "SK",
    "vatican city state (holy see)": "VA",
    "east timor (timor-leste)": "TL",
    "tanzania; officially the united republic of tanzania": "TZ",
    "iran (islamic republic of)": "IR",
    "russian federation": "RU",
    "cape verde": "CV",
    "brunei darussalam": "BN",
    "ivory coast": "CI",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "macau": "MO",
    "macedonia": "MK",
    "virgin islands (british)": "VG",
    "virgin islands (u.s.)": "VI",
    "netherlands antilles": "CW",
    "micronesia": "FM",
    "reunion island": "RE",
    "cocos (keeling) islands": "CC",
    "christmas island": "CX",
    "pitcairn island": "PN",
    "falkland islands": "FK",
    "french southern territories": "TF",
    "palestinian territories": "PS",
    "tibet": "CN",
    "western sahara": "MA",
    "antarctica": None,
    "french southern territories": "TF",
}


def country_name_to_iso2(country_name):
    """Wandelt Excel-Laendernamen in ISO-3166 Alpha-2 Codes fuer Kiwi um."""
    key = normalize(country_name)
    if key in MANUAL_ISO_OVERRIDES:
        return MANUAL_ISO_OVERRIDES[key]
    try:
        import pycountry
        match = pycountry.countries.search_fuzzy(country_name)
        return match[0].alpha_2
    except Exception:
        return None


def fetch_kiwi_batch(iso_codes, date_from, date_to, retries=3):
    """Ein Kiwi-Call kann mehrere Zielaender gleichzeitig abfragen (fly_to=A,B,C)."""
    params = {
        "fly_from": ORIGIN,
        "fly_to": ",".join(iso_codes),
        "date_from": date_from,
        "date_to": date_to,
        "nights_in_dst_from": 6,
        "nights_in_dst_to": 22,
        "flight_type": "round",
        "selected_cabins": "C",          # Regel 1: Business Class oder besser
        "adults": 1,
        "curr": CURRENCY,
        "sort": "price",
        "limit": 200,
        "one_for_city": 0,
    }
    headers = {"apikey": API_TOKEN}
    for attempt in range(retries):
        r = requests.get(KIWI_ENDPOINT, params=params, headers=headers, timeout=45)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json().get("data", [])
    print(f"Warnung: Rate-Limit bei Batch {iso_codes}, uebersprungen.", file=sys.stderr)
    return []


def fetch_all_flights(iso_codes):
    """Fragt alle Ziel-Laender in Batches ab (spart API-Calls)."""
    date_from = (datetime.now() + timedelta(days=3)).strftime("%d/%m/%Y")
    date_to = (datetime.now() + timedelta(days=300)).strftime("%d/%m/%Y")
    all_data = []
    batches = [iso_codes[i:i + COUNTRY_BATCH_SIZE] for i in range(0, len(iso_codes), COUNTRY_BATCH_SIZE)]
    for i, batch in enumerate(batches):
        print(f"Kiwi-Anfrage {i+1}/{len(batches)} ({len(batch)} Laender) ...")
        all_data.extend(fetch_kiwi_batch(batch, date_from, date_to))
        time.sleep(1)
    return all_data


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


def score_flight(item, country, rules, alliances, is_europe):
    """item = ein rohes Kiwi-Suchergebnis (ein Business-Class-Angebot)."""
    price = round(item["price"])
    route = item.get("route", [])
    outbound_segments = [s for s in route if not s.get("return")]
    transfers = max(len(outbound_segments) - 1, 0)
    airline = outbound_segments[0]["airline"] if outbound_segments else item.get("airlines", [""])[0]
    departure_at = item.get("local_departure")
    duration_days = item.get("nightsInDest")

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
    stop_key = str(min(transfers, 2))
    p = rules["stopover"].get(stop_key, 1)
    breakdown["stopover"] = p
    points += p

    # Departure airport - aktuell fix ZRH
    p = rules["departure_airport"]["ZRH"]
    breakdown["departure"] = p
    points += p

    # Time to departure
    days_out = None
    dep = None
    if departure_at:
        dep = datetime.fromisoformat(departure_at.replace("Z", "+00:00"))
        days_out = (dep - datetime.now(timezone.utc)).days
        p = points_for_range(days_out, rules["time_to_departure_days"])
        breakdown["time_to_departure"] = p
        points += p

    # Season
    season = None
    if dep:
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

    # Duration (Kiwi liefert nightsInDest direkt)
    if duration_days is not None:
        p = points_for_range(duration_days, rules["duration_days"])
        breakdown["duration"] = p
        points += p

    return {
        "country": country["country"],
        "price_chf": price,
        "airline": airline,
        "stopovers": transfers,
        "departure_at": departure_at,
        "days_until_departure": days_out,
        "duration_days": duration_days,
        "season": season,
        "interest_tier": country["interest_tier"],
        "is_europe": is_europe,
        "cabin": "Business",
        "points": points,
        "breakdown": breakdown,
        "booking_link": item.get("deep_link"),
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
    args = parser.parse_args()

    if not API_TOKEN:
        print("FEHLER: Umgebungsvariable KIWI_API_TOKEN fehlt.", file=sys.stderr)
        sys.exit(1)

    countries = load_json(DATA_DIR / "countries.json")
    rules = load_json(DATA_DIR / "ranking_rules.json")
    europe_list = set(load_json(DATA_DIR / "europe_countries.json"))
    alliances = load_json(DATA_DIR / "airline_alliances.json")

    # Baue Liste der zu pruefenden Laender, gefiltert nach Frequenz-Modus
    selected_countries = []
    for c in countries:
        is_europe = c["country"] in europe_list
        if args.frequency == "4x":
            # Nur Top1 + Top2, nur international (nicht Europa)
            if c["interest_tier"] in (1, 2) and not is_europe:
                selected_countries.append(c)
        else:
            # Top3 ODER Europa (unabhaengig von Tier)
            if c["interest_tier"] == 3 or is_europe:
                selected_countries.append(c)

    print(f"{len(selected_countries)} Laender in diesem Lauf ({args.frequency}). Loese ISO-Codes auf ...")

    iso_to_country = {}
    for c in selected_countries:
        iso = country_name_to_iso2(c["country"])
        if iso:
            iso_to_country[iso] = c
        else:
            print(f"  Warnung: kein ISO-Code fuer '{c['country']}' gefunden, uebersprungen.", file=sys.stderr)

    print(f"Frage Kiwi Tequila API ab ({len(iso_to_country)} Laender, Business Class) ...")
    raw_flights = fetch_all_flights(list(iso_to_country.keys()))
    print(f"{len(raw_flights)} Business-Class-Angebote erhalten.")

    results = []
    for item in raw_flights:
        country_code = (item.get("countryTo") or {}).get("code")
        if not country_code or country_code not in iso_to_country:
            continue
        country = iso_to_country[country_code]
        is_europe = country["country"] in europe_list
        scored = score_flight(item, country, rules, alliances, is_europe)
        scored["tier"] = tier_for_points(scored["points"], rules)
        if scored["tier"] is not None:
            results.append(scored)

    # Regel 7: max. 2 Fluege pro Airline+Ziel
    # Regel: nur Top 1-3 Tiers zeigen, sortiert, max 100
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
