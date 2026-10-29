"""Map friendly business terms to OpenStreetMap tags."""

from __future__ import annotations

# term -> list of (key, value) OSM tag pairs
CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "plumber": [("craft", "plumber")],
    "electrician": [("craft", "electrician")],
    "carpenter": [("craft", "carpenter")],
    "painter": [("craft", "painter")],
    "hvac": [("craft", "hvac")],
    "roofer": [("craft", "roofer")],
    "locksmith": [("craft", "locksmith"), ("shop", "locksmith")],
    "dentist": [("amenity", "dentist"), ("healthcare", "dentist")],
    "doctor": [("amenity", "doctors"), ("healthcare", "doctor")],
    "physiotherapist": [("healthcare", "physiotherapist")],
    "veterinarian": [("amenity", "veterinary")],
    "pharmacy": [("amenity", "pharmacy")],
    "gym": [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
    "hairdresser": [("shop", "hairdresser")],
    "beauty": [("shop", "beauty")],
    "spa": [("leisure", "spa"), ("shop", "massage")],
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "bar": [("amenity", "bar"), ("amenity", "pub")],
    "bakery": [("shop", "bakery")],
    "hotel": [("tourism", "hotel"), ("tourism", "guest_house")],
    "car_repair": [("shop", "car_repair")],
    "car_dealer": [("shop", "car")],
    "lawyer": [("office", "lawyer")],
    "accountant": [("office", "accountant")],
    "real_estate": [("office", "estate_agent")],
    "insurance": [("office", "insurance")],
    "driving_school": [("amenity", "driving_school")],
    "florist": [("shop", "florist")],
    "optician": [("shop", "optician")],
    "furniture": [("shop", "furniture")],
}

ALIASES: dict[str, str] = {
    "plumbers": "plumber",
    "plumbing": "plumber",
    "electricians": "electrician",
    "dentists": "dentist",
    "dental": "dentist",
    "doctors": "doctor",
    "clinic": "doctor",
    "vet": "veterinarian",
    "vets": "veterinarian",
    "gyms": "gym",
    "fitness": "gym",
    "barber": "hairdresser",
    "barbers": "hairdresser",
    "salon": "hairdresser",
    "restaurants": "restaurant",
    "cafes": "cafe",
    "coffee": "cafe",
    "hotels": "hotel",
    "mechanic": "car_repair",
    "garage": "car_repair",
    "lawyers": "lawyer",
    "accountants": "accountant",
    "realtor": "real_estate",
    "estate agent": "real_estate",
}


def resolve(term: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (canonical_name, tags) for a term. Unknown terms return empty tags,
    which tells the caller to fall back to a name search."""
    key = term.strip().lower().replace("-", " ")
    key = ALIASES.get(key, key).replace(" ", "_")
    if key in CATEGORIES:
        return key, CATEGORIES[key]
    if key.endswith("s") and key[:-1] in CATEGORIES:
        return key[:-1], CATEGORIES[key[:-1]]
    return term.strip(), []
