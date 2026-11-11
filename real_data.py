
# MASARAT - Documented Hotels and Transport Routes
# Prices and booking availability are not yet verified
# for the original AFC Asian Cup 2027 match dates.

def hotel(id, name, city, source):
    return {
        "id": id,
        "name": name,
        "city": city,
        "nightly_rate_sar": None,
        "rooms_available": None,
        "source": source
    }

HOTELS = [
    # RIYADH
    hotel("H01", "Hilton Riyadh Hotel & Residences", "Riyadh",
          "https://www.hilton.com/en/hotels/ruhchhi-hilton-riyadh-hotel-and-residences/"),

    hotel("H02", "DoubleTree Riyadh Financial District", "Riyadh",
          "https://www.hilton.com/en/hotels/ruhfddi-doubletree-riyadh-financial-district/"),

    hotel("H03", "Hilton Riyadh Olaya", "Riyadh",
          "https://www.hilton.com/en/locations/saudi-arabia/riyadh/hilton-hotels/"),

    # JEDDAH
    hotel("H04", "Jeddah Hilton", "Jeddah",
          "https://www.hilton.com/en/locations/saudi-arabia/jeddah/"),

    hotel("H05", "DoubleTree Jeddah Al Andalus Mall", "Jeddah",
          "https://www.hilton.com/en/hotels/jeddydi-doubletree-jeddah-al-andalus-mall/"),

    hotel("H06", "Waldorf Astoria Jeddah - Qasr Al Sharq", "Jeddah",
          "https://www.hilton.com/en/hotels/jedwawa-waldorf-astoria-jeddah-qasr-al-sharq/"),

    # AL KHOBAR
    hotel("H07", "Aloft Dhahran", "Al Khobar",
          "https://www.marriott.com/en-us/hotels/dhadl-aloft-dhahran/overview/"),

    hotel("H08", "Le Meridien Al Khobar", "Al Khobar",
          "https://www.marriott.com/en-us/destinations/saudi-arabia/al-khobar.mi"),

    hotel("H09", "Marriott Executive Apartments Al Khobar", "Al Khobar",
          "https://www.marriott.com/en-us/destinations/saudi-arabia/al-khobar.mi")
]


def route(id, origin, destination, mode, provider,
          source, route_details):
    return {
        "id": id,
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "provider": provider,
        "route": route_details,
        "return_cost_sar": None,
        "available": None,
        "source": source
    }


TRANSPORT_OPTIONS = [
    route("T01", "Riyadh", "Jeddah", "Flight",
          "flynas",
          "https://www.flynas.com/en/flights-to-and-from-riyadh",
          "Riyadh Airport to Jeddah Airport"),

    route("T02", "Riyadh", "Jeddah", "Flight",
          "Saudia",
          "https://www.saudia.com/",
          "Riyadh Airport to Jeddah Airport"),

    route("T03", "Riyadh", "Al Khobar", "Train + Road",
          "SAR East Train",
          "https://www.sar.com.sa/about-sar/railnetwork/",
          "Riyadh to Dammam by train, then road transfer"),

    route("T04", "Riyadh", "Al Khobar", "Flight + Road",
          "flynas",
          "https://www.flynas.com/en/flights-from-riyadh-to-dammam",
          "Riyadh to Dammam Airport, then road transfer"),

    route("T05", "Jeddah", "Al Khobar", "Flight + Road",
          "flynas",
          "https://www.flynas.com/en/flights-from-jeddah-to-dammam",
          "Jeddah to Dammam Airport, then road transfer"),

    route("T06", "Jeddah", "Riyadh", "Flight",
          "flynas",
          "https://www.flynas.com/ar/flights-to-and-from-riyadh",
          "Jeddah Airport to Riyadh Airport")
]

# Published reference rates, not live booking quotes.
# Hotel prices are for one night, including listed taxes/fees.

HOTEL_REFERENCE_RATES = {
    "H01": 821,
    "H02": 853,
    "H03": 770,
    "H04": 969,
    "H05": 421,
    "H06": 1654,
    "H07": 302,
    "H08": None,
    "H09": 630
}

# Published one-way starting fares, not round-trip totals.
TRANSPORT_REFERENCE_FARES = {
    "T01": 259,
    "T02": None,
    "T03": None,
    "T04": 179,
    "T05": 299,
    "T06": 259
}

for h in HOTELS:
    h["reference_nightly_sar"] = HOTEL_REFERENCE_RATES[h["id"]]
    h["reference_type"] = "PUBLISHED_HISTORICAL_RATE"

for t in TRANSPORT_OPTIONS:
    t["reference_oneway_sar"] = TRANSPORT_REFERENCE_FARES[t["id"]]
    t["reference_type"] = "PUBLISHED_STARTING_FARE"
