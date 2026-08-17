# src/parsers.py — JSON & title-parsing helpers for Khmer24 listing data

import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Canonical Brand Aliases (including Khmer names & variations) ───────────────
# Maps alias/regex pattern string to canonical brand name.
# Ordered from most specific to least specific.
_BRAND_ALIASES: List[Tuple[str, str]] = [
    ("mercedes-benz", "Mercedes-Benz"),
    ("mercedes benz", "Mercedes-Benz"),
    ("mercedes", "Mercedes-Benz"),
    ("benz", "Mercedes-Benz"),
    ("មែរសឺដេស", "Mercedes-Benz"),
    ("land rover", "Land Rover"),
    ("range rover", "Land Rover"),
    ("rolls-royce", "Rolls-Royce"),
    ("rolls royce", "Rolls-Royce"),
    ("aston martin", "Aston Martin"),
    ("alfa romeo", "Alfa Romeo"),
    ("great wall", "Great Wall"),
    ("vinfast", "VinFast"),
    ("toyota", "Toyota"),
    ("តូយ៉ូតា", "Toyota"),
    ("lexus", "Lexus"),
    ("ឡិចស៊ីស", "Lexus"),
    ("ford", "Ford"),
    ("ហ្វត", "Ford"),
    ("honda", "Honda"),
    ("ហុងដា", "Honda"),
    ("bmw", "BMW"),
    ("ប៊ីអឹម", "BMW"),
    ("hyundai", "Hyundai"),
    ("ហ៊ីយ៉ាន់ដាយ", "Hyundai"),
    ("kia", "Kia"),
    ("គា", "Kia"),
    ("mazda", "Mazda"),
    ("ម៉ាសដា", "Mazda"),
    ("mitsubishi", "Mitsubishi"),
    ("មីស៊ូប៊ីស៊ី", "Mitsubishi"),
    ("nissan", "Nissan"),
    ("នីសាន់", "Nissan"),
    ("isuzu", "Isuzu"),
    ("អ៊ីស៊ូហ្ស៊ុ", "Isuzu"),
    ("suzuki", "Suzuki"),
    ("ស៊ុយស៊ូគី", "Suzuki"),
    ("subaru", "Subaru"),
    ("volkswagen", "Volkswagen"),
    ("chevrolet", "Chevrolet"),
    ("chevy", "Chevrolet"),
    ("jeep", "Jeep"),
    ("dodge", "Dodge"),
    ("cadillac", "Cadillac"),
    ("lincoln", "Lincoln"),
    ("audi", "Audi"),
    ("porsche", "Porsche"),
    ("volvo", "Volvo"),
    ("peugeot", "Peugeot"),
    ("renault", "Renault"),
    ("citroën", "Citroën"),
    ("citroen", "Citroën"),
    ("acura", "Acura"),
    ("infiniti", "Infiniti"),
    ("genesis", "Genesis"),
    ("haval", "Haval"),
    ("mg", "MG"),
    ("byd", "BYD"),
    ("geely", "Geely"),
    ("chery", "Chery"),
    ("jac", "JAC"),
    ("foton", "Foton"),
    ("dfsk", "DFSK"),
    ("dongfeng", "Dongfeng"),
    ("baic", "BAIC"),
    ("gac", "GAC"),
    ("jetour", "Jetour"),
    ("changan", "Changan"),
    ("tank", "Tank"),
    ("tesla", "Tesla"),
    ("gmc", "GMC"),
]

# ── Known Models Dictionary per Brand (sorted longest-first per brand) ────────
KNOWN_MODELS_BY_BRAND: Dict[str, List[str]] = {
    "Toyota": [
        "Land Cruiser Prado", "Land Cruiser 300", "Land Cruiser 200", "Land Cruiser 100",
        "Land Cruiser 80", "Land Cruiser 70", "Land Cruiser", "Prado",
        "Prius Alpha", "Prius Plus", "Prius C", "Prius",
        "Corolla Cross", "Corolla Altis", "Corolla", "Camry Hybrid", "Camry",
        "Hilux Revo Rally", "Hilux Revo", "Hilux Vigo", "Hilux", "Revo", "Vigo",
        "Highlander", "RAV4", "Tacoma", "Tundra", "Alphard", "Vellfire",
        "Sienna", "Fortuner", "Yaris Cross", "Yaris", "Raize", "Veloz",
        "Rush", "Vitz", "Innova", "Avanza", "Vios", "HiAce", "Crown",
        "Sequoia", "4Runner", "CHR", "C-HR", "Harrier", "Celica", "FJ Cruiser",
        "bZ4X", "Aqua",
    ],
    "Lexus": [
        "LX600", "LX570", "LX470", "LX450",
        "GX460", "GX470",
        "RX450h", "RX350", "RX330", "RX300",
        "NX350h", "NX350", "NX300h", "NX300", "NX200t", "NX250",
        "UX250h", "UX200", "TX500h", "TX350",
        "LM500h", "LM350", "LM300h",
        "LS500", "LS460", "LS430", "LS400",
        "ES350", "ES300h", "ES300", "ES250",
        "HS250h",
        "IS350", "IS300", "IS250", "IS200",
        "RC350", "RC300", "LC500", "CT200h", "RZ450e",
    ],
    "Ford": [
        "Ranger Wildtrak", "Ranger Raptor", "Ranger XLS", "Ranger XLT", "Ranger XL",
        "Ranger Stormtrak", "Ranger Sport", "Ranger",
        "F-150 Raptor", "F-150", "F-250", "F-350",
        "Everest Titanium", "Everest Sport", "Everest",
        "Explorer", "Territory", "Expedition", "Escape", "Mustang", "EcoSport",
        "Transit", "Bronco",
    ],
    "Mercedes-Benz": [
        "G63 AMG", "G63", "G500", "G-Class",
        "GLS600", "GLS450", "GLS400", "GLS",
        "GLE450", "GLE350", "GLE53", "GLE",
        "GLC300", "GLC200", "GLC",
        "GLA250", "GLA200", "GLA", "GLB200", "GLB",
        "S580", "S500", "S450", "S400", "S350", "S-Class",
        "E350", "E300", "E250", "E200", "E-Class",
        "C300", "C250", "C200", "C180", "C-Class",
        "A250", "A200", "A-Class",
        "CLA45", "CLA250", "CLA200", "CLA",
        "CLS450", "CLS350", "CLS",
        "V250", "V-Class", "Vito", "Sprinter", "EQS", "EQE", "EQB", "EQC",
    ],
    "BMW": [
        "X7", "X6", "X5", "X4", "X3", "X2", "X1", "XM",
        "M5", "M4", "M3", "M2",
        "760Li", "750Li", "745Le", "740Li", "730Li", "7 Series",
        "530i", "528i", "525i", "520i", "5 Series",
        "430i", "428i", "420i", "4 Series",
        "330i", "328i", "325i", "320i", "318i", "3 Series",
        "iX", "i7", "i4", "i8", "Z4",
    ],
    "Land Rover": [
        "Range Rover Autobiography", "Range Rover SV", "Range Rover Sport",
        "Range Rover Velar", "Range Rover Evoque", "Range Rover",
        "Defender 110", "Defender 90", "Defender 130", "Defender",
        "Discovery Sport", "Discovery",
    ],
    "Hyundai": [
        "Grand Starex", "Santa Fe", "Palisade", "Tucson", "Staria", "H-1",
        "Starex", "Creta", "Venue", "Elantra", "Sonata", "Accent",
        "Kona", "Ioniq 5", "Ioniq 6", "Custin",
    ],
    "Kia": [
        "Grand Carnival", "Carnival", "Sedona", "Sorento", "Sportage",
        "Telluride", "Seltos", "Sonet", "Carens", "Picanto", "Morning",
        "K5", "K3", "Cerato", "EV6", "EV9",
    ],
    "Mazda": [
        "CX-90", "CX-60", "CX-9", "CX-8", "CX-5", "CX-30", "CX-3",
        "BT-50", "Mazda 2", "Mazda 3", "Mazda 6",
    ],
    "Mitsubishi": [
        "Montero Sport", "Pajero Sport", "Pajero", "Triton", "L200",
        "Xpander Cross", "Xpander", "Xforce", "Outlander", "Eclipse Cross",
        "Attrage", "Mirage",
    ],
    "Nissan": [
        "Navara", "Patrol", "Terra", "X-Trail", "Kicks", "Magnite",
        "Almera", "Sunny", "Urvan", "GT-R", "Juke", "Murano", "Pathfinder",
    ],
    "Honda": [
        "CR-V", "CRV", "HR-V", "HRV", "WR-V", "Civic", "City", "Accord",
        "BR-V", "Pilot", "Passport", "Odyssey", "Jazz", "Fit",
    ],
    "Porsche": [
        "Cayenne Coupe", "Cayenne", "Macan", "Panamera", "Taycan",
        "911 Carrera", "911", "718 Cayman", "718 Boxster",
    ],
    "Audi": [
        "Q8", "Q7", "Q5", "Q3", "Q2",
        "A8", "A7", "A6", "A5", "A4", "A3",
        "e-tron", "R8",
    ],
    "BYD": [
        "Atto 3", "Dolphin", "Seal", "Song Plus", "Tang", "Han",
        "Qin Plus", "Yuan Plus", "Seagull", "Yangwang U8", "Denza D9",
    ],
    "MG": [
        "MG4 EV", "MG HS", "MG ZS", "MG RX8", "MG GT", "MG5", "Cyberster", "MG ONE",
    ],
    "Haval": [
        "H6 HEV", "H6", "Jolion", "Dargo", "Tank 500", "Tank 300", "H9",
    ],
    "Geely": [
        "Coolray", "Azkarra", "Monjaro", "Tugella", "Okavango", "Emgrand",
        "Geometry C", "Starray",
    ],
    "Tesla": [
        "Cybertruck", "Model Y", "Model 3", "Model X", "Model S",
    ],
    "Chevrolet": [
        "Colorado", "Trailblazer", "Tahoe", "Suburban", "Silverado",
        "Camaro", "Corvette", "Cruze", "Trax", "Captiva",
    ],
    "Jeep": [
        "Wrangler Rubicon", "Wrangler Sahara", "Wrangler", "Gladiator",
        "Grand Cherokee", "Cherokee", "Compass", "Renegade",
    ],
    "Suzuki": [
        "Jimny", "Swift", "Ertiga", "XL7", "Ciaz", "Grand Vitara", "Vitara", "Carry",
    ],
    "Isuzu": [
        "D-Max", "D-MAX", "MU-X", "Trooper",
    ],
    "Volkswagen": [
        "Teramont", "Touareg", "Tiguan", "Golf", "Passat", "ID.4", "ID.6", "Beetle", "Polo",
    ],
    "Volvo": [
        "XC90", "XC60", "XC40", "S90", "S60", "V90", "V60", "EX90", "EX30",
    ],
    "Jetour": [
        "Dashing", "X70 Plus", "X70", "X90 Plus", "T2", "Traveler",
    ],
    "GAC": [
        "GS8", "GS4", "GS3 Emzoom", "GN8", "M8", "Emkoo", "Aion Y Plus", "Aion S",
    ],
    "Chery": [
        "Tiggo 8 Pro", "Tiggo 7 Pro", "Tiggo 4 Pro", "Tiggo 8", "Tiggo 7", "Omoda 5", "Jaecoo 7",
    ],
    "Changan": [
        "CS75 Plus", "CS55 Plus", "CS35 Plus", "UNI-K", "UNI-T", "UNI-V",
        "Deepal S07", "Deepal L07",
    ],
}

# Standalone sub-model / trim aliases that distinctly identify brand and model
_STANDALONE_ALIASES: List[Tuple[str, str, str]] = [
    ("wildtrak", "Ford", "Ranger Wildtrak"),
    ("raptor", "Ford", "Ranger Raptor"),
    ("vigo", "Toyota", "Hilux Vigo"),
    ("revo", "Toyota", "Hilux Revo"),
    ("prado", "Toyota", "Land Cruiser Prado"),
    ("starex", "Hyundai", "Grand Starex"),
    ("rubicon", "Jeep", "Wrangler Rubicon"),
    ("sahara", "Jeep", "Wrangler Sahara"),
]

# Reverse lookup for uniquely identifiable standalone models (e.g. "Prius" -> Toyota)
_DISTINCT_MODELS: List[Tuple[str, str, str]] = list(_STANDALONE_ALIASES)
for _brand, _models in KNOWN_MODELS_BY_BRAND.items():
    for _m in sorted(_models, key=len, reverse=True):
        # Only register models that are not ambiguous single generic letters
        if len(_m) >= 3 or _m in ("X5", "X6", "X7", "Q7", "Q8", "M3", "M4", "M5", "K5", "K3"):
            _DISTINCT_MODELS.append((_m.lower(), _brand, _m))
_DISTINCT_MODELS.sort(key=lambda x: len(x[0]), reverse=True)

# Year pattern — used to strip year digits leaking into model tokens
_YEAR_RE = re.compile(r'^(?:19|20)\d{2}$')

# Non-model stop words — stop collecting heuristic model tokens when any is hit
_STOP_WORDS = {
    "for", "sale", "used", "new", "good", "condition", "year",
    "km", "manual", "automatic", "auto", "diesel", "petrol",
    "electric", "hybrid", "turbo", "4wd", "awd", "4x4",
    "price", "cheap", "urgent", "negotiable", "full", "option",
    "ស្លាកលេខ", "ក្រដាសពន្ធ", "ឡានស្អាត", "ម្ចាស់ដើម", "លក់",
}


def extract_brand_model(title: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the car brand and model name from a listing title string.

    Strategy:
    1. Scan for a known brand / alias (case-insensitive & multilingual).
    2. If brand matched:
       a. Search within the title for a known curated model for that brand.
       b. Fallback: Parse the tokens following the brand, stopping at years/stop words.
    3. If no brand matched directly:
       a. Scan for distinct standalone models (e.g. "Prius", "RX350", "Wildtrak")
          to infer both the canonical Brand and Model.

    Returns:
        (brand, model) — either or both may be None.
    """
    if not title or not isinstance(title, str):
        return None, None

    title_clean = title.strip()
    if not title_clean:
        return None, None

    # ── Stage 1: Search for Known Brand / Alias ────────────────────────────────
    detected_brand: Optional[str] = None
    brand_match_end: int = -1

    for alias, canonical_brand in _BRAND_ALIASES:
        pattern = re.compile(r'(?:\b|(?<=[\u1780-\u17FF]))' + re.escape(alias) + r'(?:\b|(?=[\u1780-\u17FF\s]|$))', re.IGNORECASE)
        m = pattern.search(title_clean)
        if m:
            detected_brand = canonical_brand
            brand_match_end = m.end()
            break

    # ── Stage 2: If Brand is found, extract Model ─────────────────────────────
    if detected_brand:
        # 2a. Check known curated models for this brand (longest-match first)
        known_models = KNOWN_MODELS_BY_BRAND.get(detected_brand, [])
        for model_candidate in known_models:
            # Case-insensitive substring match with boundary checks
            m_pat = re.compile(r'\b' + re.escape(model_candidate) + r'\b', re.IGNORECASE)
            m_found = m_pat.search(title_clean)
            if m_found:
                # If exact casing matched in title, or canonical casing from dictionary
                return detected_brand, model_candidate

        # 2b. Heuristic fallback: tokens immediately after the brand occurrence
        after = title_clean[brand_match_end:].strip()
        tokens = after.split()
        model_tokens = []
        for tok in tokens[:4]:
            if tok.lower() in _STOP_WORDS:
                break
            if _YEAR_RE.match(tok):
                continue
            model_tokens.append(tok)
            if len(model_tokens) == 3:
                break

        model = " ".join(model_tokens) if model_tokens else None
        return detected_brand, model

    # ── Stage 3: No direct brand found — Search for Distinct Models ───────────
    for model_lower, inferred_brand, canonical_model in _DISTINCT_MODELS:
        m_pat = re.compile(r'\b' + re.escape(model_lower) + r'\b', re.IGNORECASE)
        if m_pat.search(title_clean):
            return inferred_brand, canonical_model

    return None, None


def extract_spec_value(specs: Dict[str, Any], *keys: str) -> Optional[str]:
    """
    Return the first non-None value found in `specs` for any of the given keys.
    Normalizes the result to a stripped string.
    """
    if not isinstance(specs, dict):
        return None
    for key in keys:
        val = specs.get(key)
        if val is not None:
            return str(val).strip() or None
    return None


def parse_mileage(raw: Any) -> Optional[int]:
    """
    Parse a mileage / odometer value to an integer (km).

    Handles formats like "150,000", "150000 km", "150K km".
    Returns None if unparseable.
    """
    if raw is None:
        return None
    s = str(raw).lower().replace(",", "").replace(" ", "")
    # Handle "150k" shorthand
    if s.endswith("k"):
        try:
            return int(float(s[:-1]) * 1000)
        except ValueError:
            return None
    # Strip trailing "km"
    s = re.sub(r"km$", "", s).strip()
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def flatten_feed_response(raw: Any) -> List[Dict[str, Any]]:
    """
    Safely extract the ``data`` list from a Khmer24 Posts API JSON response.
    Returns an empty list if the response is malformed.
    """
    if not isinstance(raw, dict):
        return []
    return raw.get("data", []) or []


def extract_nuxt_hydration_data(html_content: str) -> Optional[dict]:
    """
    Extract and parse window.__NUXT_DATA__ from a Khmer24 server-rendered page.
    Used as a fallback when the REST API is unavailable.
    """
    match = re.search(
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        html_content,
        re.DOTALL,
    )
    if not match:
        match = re.search(
            r'window\.__NUXT_DATA__\s*=\s*(\[.*?\]);', html_content, re.DOTALL
        )
    if not match:
        logger.debug("No Nuxt hydration data found in page HTML.")
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to decode Nuxt hydration JSON: {exc}")
        return None
