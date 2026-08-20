# src/parsers.py — JSON & title-parsing helpers for Khmer24 listing data

import re
import json
import logging
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Title Normalization & Invisible Character Cleaning ────────────────────────
def clean_title(title: Optional[str]) -> str:
    """
    Clean and normalize a listing title for robust regex parsing.
    
    Actions:
    - Unicode NFKC normalization.
    - Strips zero-width and invisible characters (e.g. \\u200b, \\u200c, \\u200d, \\ufeff, \\u00a0).
    - Inserts spaces between squished alphanumeric/Khmer boundaries when 4+ letter words touch year digits
      (e.g. 'Highlander01' -> 'Highlander 01', '2026Changan' -> '2026 Changan').
    - Normalizes punctuation delimiters (_, /, .) to spaces while preserving hyphens in models.
    """
    if not title:
        return ""
    text = unicodedata.normalize("NFKC", str(title))
    # Strip invisible zero-width characters and normalize non-breaking spaces
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"[\u00a0]", " ", text)

    # Insert space when 4+ letter word is squished with year digits (e.g. Highlander01, Camry2019)
    text = re.sub(r"([A-Za-z]{4,})((?:19|20)\d{2}\b)", r"\1 \2", text)
    text = re.sub(r"([A-Za-z]{4,})(0[1-9]|1[0-9]|2[0-7])\b", r"\1 \2", text)
    # Insert space when 4-digit year touches letters (e.g. 2026Changan -> 2026 Changan)
    text = re.sub(r"(\b(?:19|20)\d{2})([A-Za-z]+)", r"\1 \2", text)
    # Replace delimiters with spaces
    text = text.replace("_", " ").replace("/", " ").replace(".", " ")
    return text.strip()


# ── Canonical Brand Aliases (Multilingual: English, Khmer, Chinese) ────────────
# Maps alias/regex pattern to canonical brand name. Ordered most-specific first.
_BRAND_ALIASES: List[Tuple[str, str]] = [
    # Multi-word & Luxury brands
    (r"mercedes[- ]benz", "Mercedes-Benz"),
    (r"mercedes", "Mercedes-Benz"),
    (r"benz\b", "Mercedes-Benz"),
    (r"amg\b", "Mercedes-Benz"),
    (r"brabus\b", "Mercedes-Benz"),
    (r"មែរសឺដេស", "Mercedes-Benz"),
    (r"land[- ]rover", "Land Rover"),
    (r"range[- ]rover", "Land Rover"),
    (r"rang[- ]rover", "Land Rover"),
    (r"rr\b", "Land Rover"),
    (r"rolls[- ]royce", "Rolls-Royce"),
    (r"aston[- ]martin", "Aston Martin"),
    (r"alfa[- ]romeo", "Alfa Romeo"),
    (r"great[- ]wall", "Great Wall"),
    (r"vinfast", "VinFast"),

    # High-volume Asian & American brands
    (r"toyota", "Toyota"),
    (r"តូយ៉ូតា", "Toyota"),
    (r"lexus", "Lexus"),
    (r"ឡិចស៊ីស", "Lexus"),
    (r"ford", "Ford"),
    (r"ហ្វត", "Ford"),
    (r"honda", "Honda"),
    (r"ហុងដា", "Honda"),
    (r"bmw", "BMW"),
    (r"ប៊ីអឹម", "BMW"),
    (r"hyundai", "Hyundai"),
    (r"ហ៊ីយ៉ាន់ដាយ", "Hyundai"),
    (r"kia\b", "Kia"),
    (r"គា\b", "Kia"),
    (r"起亚", "Kia"),
    (r"mazda", "Mazda"),
    (r"ម៉ាសដា", "Mazda"),
    (r"mitsubishi", "Mitsubishi"),
    (r"មីស៊ូប៊ីស៊ី", "Mitsubishi"),
    (r"nissan", "Nissan"),
    (r"នីសាន់", "Nissan"),
    (r"isuzu", "Isuzu"),
    (r"អ៊ីស៊ូហ្ស៊ុ", "Isuzu"),
    (r"suzuki", "Suzuki"),
    (r"ស៊ុយស៊ូគី", "Suzuki"),
    (r"subaru", "Subaru"),
    (r"volkswagen", "Volkswagen"),
    (r"vw\b", "Volkswagen"),
    (r"chevrolet", "Chevrolet"),
    (r"chevy\b", "Chevrolet"),
    (r"jeep\b", "Jeep"),
    (r"dodge\b", "Dodge"),
    (r"cadillac", "Cadillac"),
    (r"lincoln\b", "Lincoln"),
    (r"gmc\b", "GMC"),
    (r"audi\b", "Audi"),
    (r"porsche", "Porsche"),
    (r"volvo\b", "Volvo"),
    (r"peugeot", "Peugeot"),
    (r"renault", "Renault"),
    (r"citroën", "Citroën"),
    (r"citroen", "Citroën"),
    (r"acura\b", "Acura"),
    (r"infiniti", "Infiniti"),
    (r"genesis\b", "Genesis"),

    # Chinese & New Energy Brands
    (r"haval", "Haval"),
    (r"mg\b", "MG"),
    (r"byd\b", "BYD"),
    (r"比亚迪", "BYD"),
    (r"denza", "Denza"),
    (r"腾势", "Denza"),
    (r"fangchengbao", "Fangchengbao"),
    (r"leopard\b", "Fangchengbao"),
    (r"yangwang", "Yangwang"),
    (r"geely", "Geely"),
    (r"zeekr", "Zeekr"),
    (r"chery", "Chery"),
    (r"icar\b", "iCar"),
    (r"jaecoo", "Jaecoo"),
    (r"omoda", "Omoda"),
    (r"jac\b", "JAC"),
    (r"foton\b", "Foton"),
    (r"dfsk\b", "DFSK"),
    (r"dongfeng", "Dongfeng"),
    (r"zna\b", "ZNA"),
    (r"baic\b", "BAIC"),
    (r"arcfox", "Arcfox"),
    (r"gac\b", "GAC"),
    (r"aion\b", "GAC"),
    (r"trumpchi", "GAC"),
    (r"jetour", "Jetour"),
    (r"changan", "Changan"),
    (r"deepal", "Changan"),
    (r"avatr", "Avatr"),
    (r"tank\b", "Tank"),
    (r"tesla\b", "Tesla"),
    (r"xpeng", "Xpeng"),
    (r"nio\b", "NIO"),
    (r"li auto", "Li Auto"),
    (r"lixiang", "Li Auto"),
    (r"hongqi", "Hongqi"),
    (r"wuling", "Wuling"),
    (r"gtv\b", "GTV"),

    # Exotic & Sports
    (r"lamborghini", "Lamborghini"),
    (r"ferrari", "Ferrari"),
    (r"bentley", "Bentley"),
    (r"maserati", "Maserati"),
    (r"mini\b", "MINI"),
]

_BRAND_PATTERNS = [
    (
        re.compile(
            r"(?:\b|(?<=[\u1780-\u17FF]))" + alias + r"(?:\b|(?=[\u1780-\u17FF\s]|$))",
            re.IGNORECASE,
        ),
        canonical,
    )
    for alias, canonical in _BRAND_ALIASES
]


# ── Known Models Dictionary per Brand (sorted longest-first) ──────────────────
# Map of (brand -> list of (regex_pattern, canonical_model_name))
KNOWN_MODELS_BY_BRAND: Dict[str, List[Tuple[str, str]]] = {
    "Toyota": [
        (r"land\s*cruiser\s*prado", "Land Cruiser Prado"),
        (r"land\s*cruiser\s*300|lc\s*300", "Land Cruiser 300"),
        (r"land\s*cruiser\s*200|lc\s*200", "Land Cruiser 200"),
        (r"land\s*cruiser\s*105|lc\s*105", "Land Cruiser 105"),
        (r"land\s*cruiser\s*100|lc\s*100", "Land Cruiser 100"),
        (r"land\s*cruiser\s*80|lc\s*80", "Land Cruiser 80"),
        (r"land\s*cruiser\s*70|lc\s*70", "Land Cruiser 70"),
        (r"land\s*cruiser", "Land Cruiser"),
        (r"prado", "Land Cruiser Prado"),
        (r"prius\s*alpha", "Prius Alpha"),
        (r"prius\s*plus", "Prius Plus"),
        (r"prius\s*c", "Prius C"),
        (r"prius\s*plugin|prius\s*prime", "Prius Plugin"),
        (r"prius|pruis|prus", "Prius"),
        (r"corolla\s*cross", "Corolla Cross"),
        (r"corolla\s*altis", "Corolla Altis"),
        (r"corolla", "Corolla"),
        (r"camry\s*hybrid", "Camry Hybrid"),
        (r"camry|camri", "Camry"),
        (r"hilux\s*revo\s*rally", "Hilux Revo Rally"),
        (r"hilux\s*revo", "Hilux Revo"),
        (r"hilux\s*vigo", "Hilux Vigo"),
        (r"hilux", "Hilux"),
        (r"revo", "Hilux Revo"),
        (r"vigo", "Hilux Vigo"),
        (r"highlander", "Highlander"),
        (r"rav4", "RAV4"),
        (r"tacoma", "Tacoma"),
        (r"tundra", "Tundra"),
        (r"alphard", "Alphard"),
        (r"vellfire", "Vellfire"),
        (r"sienna", "Sienna"),
        (r"fortuner", "Fortuner"),
        (r"yaris\s*cross", "Yaris Cross"),
        (r"yaris", "Yaris"),
        (r"raize", "Raize"),
        (r"veloz", "Veloz"),
        (r"rush", "Rush"),
        (r"vitz", "Vitz"),
        (r"innova", "Innova"),
        (r"avanza", "Avanza"),
        (r"vios", "Vios"),
        (r"hiace", "HiAce"),
        (r"crown", "Crown"),
        (r"sequoia", "Sequoia"),
        (r"4runner", "4Runner"),
        (r"c-hr|chr", "C-HR"),
        (r"harrier", "Harrier"),
        (r"celica", "Celica"),
        (r"fj\s*cruiser", "FJ Cruiser"),
        (r"bz4x", "bZ4X"),
        (r"aqua", "Aqua"),
        (r"belta", "Belta"),
    ],
    "Lexus": [
        (r"lx\s*600", "LX600"),
        (r"lx\s*570", "LX570"),
        (r"lx\s*470", "LX470"),
        (r"lx\s*450", "LX450"),
        (r"gx\s*460", "GX460"),
        (r"gx\s*470", "GX470"),
        (r"rx\s*450h", "RX450h"),
        (r"rx\s*350", "RX350"),
        (r"rx\s*330", "RX330"),
        (r"rx\s*300", "RX300"),
        (r"nx\s*350h", "NX350h"),
        (r"nx\s*350", "NX350"),
        (r"nx\s*300h", "NX300h"),
        (r"nx\s*300", "NX300"),
        (r"nx\s*200t", "NX200t"),
        (r"nx\s*250", "NX250"),
        (r"ux\s*250h", "UX250h"),
        (r"ux\s*200", "UX200"),
        (r"tx\s*500h", "TX500h"),
        (r"tx\s*350", "TX350"),
        (r"lm\s*500h", "LM500h"),
        (r"lm\s*350h", "LM350h"),
        (r"lm\s*350", "LM350"),
        (r"lm\s*300h", "LM300h"),
        (r"ls\s*500", "LS500"),
        (r"ls\s*460", "LS460"),
        (r"ls\s*430", "LS430"),
        (r"ls\s*400", "LS400"),
        (r"es\s*350", "ES350"),
        (r"es\s*300h", "ES300h"),
        (r"es\s*300", "ES300"),
        (r"es\s*250", "ES250"),
        (r"hs\s*250h", "HS250h"),
        (r"is\s*350", "IS350"),
        (r"is\s*300", "IS300"),
        (r"is\s*250", "IS250"),
        (r"is\s*200", "IS200"),
        (r"rc\s*350", "RC350"),
        (r"rc\s*300", "RC300"),
        (r"lc\s*500", "LC500"),
        (r"ct\s*200h", "CT200h"),
        (r"rz\s*450e", "RZ450e"),
    ],
    "Ford": [
        (r"ranger\s*wildtrak|wildtrak", "Ranger Wildtrak"),
        (r"ranger\s*raptor|raptor", "Ranger Raptor"),
        (r"ranger\s*stormtrak|stormtrak", "Ranger Stormtrak"),
        (r"ranger\s*xls", "Ranger XLS"),
        (r"ranger\s*xlt", "Ranger XLT"),
        (r"ranger\s*xl", "Ranger XL"),
        (r"ranger\s*sport", "Ranger Sport"),
        (r"ranger", "Ranger"),
        (r"f-150\s*raptor", "F-150 Raptor"),
        (r"f-150", "F-150"),
        (r"f-250", "F-250"),
        (r"f-350", "F-350"),
        (r"everest\s*titanium", "Everest Titanium"),
        (r"everest\s*sport", "Everest Sport"),
        (r"everest", "Everest"),
        (r"explorer", "Explorer"),
        (r"territory", "Territory"),
        (r"expedition", "Expedition"),
        (r"escape", "Escape"),
        (r"mustang", "Mustang"),
        (r"ecosport", "EcoSport"),
        (r"transit", "Transit"),
        (r"bronco", "Bronco"),
    ],
    "Mercedes-Benz": [
        (r"g\s*63\s*amg|g\s*63", "G63 AMG"),
        (r"g\s*500", "G500"),
        (r"g-class", "G-Class"),
        (r"gls\s*600", "GLS600"),
        (r"gls\s*450", "GLS450"),
        (r"gls\s*400", "GLS400"),
        (r"gls", "GLS"),
        (r"gle\s*450", "GLE450"),
        (r"gle\s*350", "GLE350"),
        (r"gle\s*53", "GLE53"),
        (r"gle", "GLE"),
        (r"glc\s*300", "GLC300"),
        (r"glc\s*200", "GLC200"),
        (r"glc", "GLC"),
        (r"gla\s*250", "GLA250"),
        (r"gla\s*200", "GLA200"),
        (r"gla", "GLA"),
        (r"glb\s*200|glb", "GLB200"),
        (r"s\s*580", "S580"),
        (r"s\s*500", "S500"),
        (r"s\s*450", "S450"),
        (r"s\s*400", "S400"),
        (r"s\s*350", "S350"),
        (r"s-class", "S-Class"),
        (r"e\s*350", "E350"),
        (r"e\s*300", "E300"),
        (r"e\s*250", "E250"),
        (r"e\s*200", "E200"),
        (r"e-class", "E-Class"),
        (r"c\s*300", "C300"),
        (r"c\s*250", "C250"),
        (r"c\s*200", "C200"),
        (r"c\s*180", "C180"),
        (r"c\s*63", "C63"),
        (r"c-class", "C-Class"),
        (r"a\s*250", "A250"),
        (r"a\s*200", "A200"),
        (r"a-class", "A-Class"),
        (r"cla\s*45", "CLA45"),
        (r"cla\s*250", "CLA250"),
        (r"cla\s*200", "CLA200"),
        (r"cla", "CLA"),
        (r"cls\s*450", "CLS450"),
        (r"cls\s*350", "CLS350"),
        (r"cls", "CLS"),
        (r"v\s*250|v-class", "V250"),
        (r"vito", "Vito"),
        (r"sprinter", "Sprinter"),
        (r"amg\s*gts", "AMG GTS"),
        (r"amg\s*gt", "AMG GT"),
        (r"eqs", "EQS"),
        (r"eqe", "EQE"),
        (r"eqb", "EQB"),
        (r"eqc", "EQC"),
    ],
    "BMW": [
        (r"x7", "X7"),
        (r"x6", "X6"),
        (r"x5", "X5"),
        (r"x4", "X4"),
        (r"x3", "X3"),
        (r"x2", "X2"),
        (r"x1", "X1"),
        (r"xm", "XM"),
        (r"m5", "M5"),
        (r"m4", "M4"),
        (r"m3", "M3"),
        (r"m2", "M2"),
        (r"760li", "760Li"),
        (r"750li", "750Li"),
        (r"745le", "745Le"),
        (r"740li", "740Li"),
        (r"730li", "730Li"),
        (r"7\s*series", "7 Series"),
        (r"530i", "530i"),
        (r"528i", "528i"),
        (r"525i", "525i"),
        (r"520i", "520i"),
        (r"5\s*series", "5 Series"),
        (r"430i", "430i"),
        (r"428i", "428i"),
        (r"420i", "420i"),
        (r"4\s*series", "4 Series"),
        (r"330i", "330i"),
        (r"328i", "328i"),
        (r"325i", "325i"),
        (r"320i", "320i"),
        (r"318i", "318i"),
        (r"3\s*series", "3 Series"),
        (r"ix", "iX"),
        (r"i7", "i7"),
        (r"i4", "i4"),
        (r"i8", "i8"),
        (r"z4", "Z4"),
    ],
    "Land Rover": [
        (r"range\s*rover\s*autobiography", "Range Rover Autobiography"),
        (r"range\s*rover\s*sv", "Range Rover SV"),
        (r"range\s*rover\s*sport|rr\s*sport", "Range Rover Sport"),
        (r"range\s*rover\s*velar", "Range Rover Velar"),
        (r"range\s*rover\s*evoque", "Range Rover Evoque"),
        (r"range\s*rover\s*vogue|vogue", "Range Rover Vogue"),
        (r"range\s*rover", "Range Rover"),
        (r"defender\s*110", "Defender 110"),
        (r"defender\s*90", "Defender 90"),
        (r"defender\s*130", "Defender 130"),
        (r"defender", "Defender"),
        (r"discovery\s*sport", "Discovery Sport"),
        (r"discovery", "Discovery"),
    ],
    "Hyundai": [
        (r"grand\s*starex|starex", "Grand Starex"),
        (r"santa\s*fe", "Santa Fe"),
        (r"palisade", "Palisade"),
        (r"tucson", "Tucson"),
        (r"staria", "Staria"),
        (r"h-1", "H-1"),
        (r"creta", "Creta"),
        (r"venue", "Venue"),
        (r"elantra", "Elantra"),
        (r"sonata", "Sonata"),
        (r"accent", "Accent"),
        (r"kona", "Kona"),
        (r"ioniq\s*5", "Ioniq 5"),
        (r"ioniq\s*6", "Ioniq 6"),
        (r"custin", "Custin"),
    ],
    "Kia": [
        (r"grand\s*carnival|carnival|嘉华", "Carnival"),
        (r"sedona", "Sedona"),
        (r"sorento", "Sorento"),
        (r"sportage", "Sportage"),
        (r"telluride", "Telluride"),
        (r"seltos", "Seltos"),
        (r"sonet", "Sonet"),
        (r"carens", "Carens"),
        (r"picanto", "Picanto"),
        (r"morning", "Morning"),
        (r"ray", "Ray"),
        (r"k5", "K5"),
        (r"k3", "K3"),
        (r"cerato", "Cerato"),
        (r"ev6", "EV6"),
        (r"ev9", "EV9"),
    ],
    "Mazda": [
        (r"cx-90", "CX-90"),
        (r"cx-60", "CX-60"),
        (r"cx-9", "CX-9"),
        (r"cx-8", "CX-8"),
        (r"cx-5", "CX-5"),
        (r"cx-30", "CX-30"),
        (r"cx-3", "CX-3"),
        (r"bt-50", "BT-50"),
        (r"mazda\s*2", "Mazda 2"),
        (r"mazda\s*3", "Mazda 3"),
        (r"mazda\s*6", "Mazda 6"),
    ],
    "Mitsubishi": [
        (r"montero\s*sport", "Montero Sport"),
        (r"pajero\s*sport", "Pajero Sport"),
        (r"pajero", "Pajero"),
        (r"triton", "Triton"),
        (r"l200", "L200"),
        (r"xpander\s*cross", "Xpander Cross"),
        (r"xpander", "Xpander"),
        (r"xforce", "Xforce"),
        (r"outlander", "Outlander"),
        (r"eclipse\s*cross", "Eclipse Cross"),
        (r"attrage", "Attrage"),
        (r"mirage", "Mirage"),
    ],
    "Nissan": [
        (r"navara", "Navara"),
        (r"patrol", "Patrol"),
        (r"terra", "Terra"),
        (r"x-trail", "X-Trail"),
        (r"kicks", "Kicks"),
        (r"magnite", "Magnite"),
        (r"almera", "Almera"),
        (r"sunny", "Sunny"),
        (r"urvan", "Urvan"),
        (r"gt-r", "GT-R"),
        (r"juke", "Juke"),
        (r"murano", "Murano"),
        (r"pathfinder", "Pathfinder"),
    ],
    "Honda": [
        (r"cr-v|crv", "CR-V"),
        (r"hr-v|hrv", "HR-V"),
        (r"wr-v", "WR-V"),
        (r"civic", "Civic"),
        (r"city", "City"),
        (r"accord", "Accord"),
        (r"br-v", "BR-V"),
        (r"pilot", "Pilot"),
        (r"passport", "Passport"),
        (r"odyssey", "Odyssey"),
        (r"jazz", "Jazz"),
        (r"fit", "Fit"),
    ],
    "Porsche": [
        (r"cayenne\s*coupe", "Cayenne Coupe"),
        (r"cayenne", "Cayenne"),
        (r"macan", "Macan"),
        (r"panamera", "Panamera"),
        (r"taycan", "Taycan"),
        (r"911\s*carrera|911", "911 Carrera"),
        (r"718\s*cayman", "718 Cayman"),
        (r"718\s*boxster", "718 Boxster"),
    ],
    "Audi": [
        (r"q8", "Q8"),
        (r"q7", "Q7"),
        (r"q5", "Q5"),
        (r"q3", "Q3"),
        (r"q2", "Q2"),
        (r"a8", "A8"),
        (r"a7", "A7"),
        (r"a6", "A6"),
        (r"a5", "A5"),
        (r"a4", "A4"),
        (r"a3", "A3"),
        (r"e-tron", "e-tron"),
        (r"r8", "R8"),
    ],
    "BYD": [
        (r"atto\s*3", "Atto 3"),
        (r"dolphin", "Dolphin"),
        (r"seal", "Seal"),
        (r"song\s*plus", "Song Plus"),
        (r"tang", "Tang"),
        (r"han", "Han"),
        (r"qin\s*plus", "Qin Plus"),
        (r"yuan\s*plus", "Yuan Plus"),
        (r"seagull", "Seagull"),
        (r"yangwang\s*u8", "Yangwang U8"),
        (r"denza\s*d9", "Denza D9"),
    ],
    "Denza": [
        (r"d9", "D9"),
        (r"n8l|n8", "N8"),
        (r"n7", "N7"),
    ],
    "Fangchengbao": [
        (r"leopard\s*5|bao\s*5", "Leopard 5"),
        (r"leopard\s*7|ti7", "Leopard 7"),
        (r"leopard\s*8|bao\s*8", "Leopard 8"),
    ],
    "Changan": [
        (r"deepal\s*s05|s05", "Deepal S05"),
        (r"deepal\s*s07|s07", "Deepal S07"),
        (r"deepal\s*l07|l07", "Deepal L07"),
        (r"cs75\s*plus", "CS75 Plus"),
        (r"cs55\s*plus", "CS55 Plus"),
        (r"cs35\s*plus", "CS35 Plus"),
        (r"uni-k", "UNI-K"),
        (r"uni-t", "UNI-T"),
        (r"uni-v", "UNI-V"),
        (r"q05", "Q05"),
        (r"ez\s*60|ez\s*6", "EZ-6"),
    ],
    "Avatr": [
        (r"avatr\s*07|07", "Avatr 07"),
        (r"avatr\s*11|11", "Avatr 11"),
        (r"avatr\s*12|12", "Avatr 12"),
        (r"avatr\s*max", "Avatr Max"),
    ],
    "Xpeng": [
        (r"x9", "X9"),
        (r"g6", "G6"),
        (r"g9", "G9"),
        (r"p7", "P7"),
        (r"p5", "P5"),
    ],
    "GAC": [
        (r"gn8|gn8\s*宗师", "GN8"),
        (r"gn6pro|gn6", "GN6"),
        (r"gs8", "GS8"),
        (r"gs4", "GS4"),
        (r"gs3\s*emzoom|gs3|emzoom", "GS3 Emzoom"),
        (r"emkoo", "Emkoo"),
        (r"aion\s*y\s*plus|aion\s*y", "Aion Y Plus"),
        (r"aion\s*s", "Aion S"),
        (r"aion\s*v", "Aion V"),
        (r"aion\s*hyper", "Aion Hyper"),
    ],
    "Chery": [
        (r"tiggo\s*8\s*pro|tiggo\s*8", "Tiggo 8 Pro"),
        (r"tiggo\s*7\s*pro|tiggo\s*7", "Tiggo 7 Pro"),
        (r"tiggo\s*4\s*pro", "Tiggo 4 Pro"),
        (r"omoda\s*5", "Omoda 5"),
        (r"jaecoo\s*7", "Jaecoo 7"),
        (r"jaecoo\s*8", "Jaecoo 8"),
    ],
    "iCar": [
        (r"icar\s*v23|v23s|v23", "iCar V23"),
        (r"icar\s*03|03", "iCar 03"),
    ],
    "Geely": [
        (r"coolray", "Coolray"),
        (r"azkarra", "Azkarra"),
        (r"monjaro", "Monjaro"),
        (r"tugella", "Tugella"),
        (r"okavango", "Okavango"),
        (r"emgrand", "Emgrand"),
        (r"geometry\s*c", "Geometry C"),
        (r"starray", "Starray"),
    ],
    "Jetour": [
        (r"dashing", "Dashing"),
        (r"x70\s*plus|x70", "X70 Plus"),
        (r"x90\s*plus", "X90 Plus"),
        (r"t2|traveler", "T2"),
    ],
    "MG": [
        (r"mg4\s*ev|mg4", "MG4 EV"),
        (r"mg\s*hs", "MG HS"),
        (r"mg\s*zs", "MG ZS"),
        (r"mg\s*rx8", "MG RX8"),
        (r"mg\s*gt", "MG GT"),
        (r"mg5", "MG5"),
        (r"cyberster", "Cyberster"),
        (r"mg\s*one", "MG ONE"),
    ],
    "Haval": [
        (r"h6\s*hev|h6", "H6"),
        (r"jolion", "Jolion"),
        (r"dargo", "Dargo"),
        (r"tank\s*500", "Tank 500"),
        (r"tank\s*400", "Tank 400"),
        (r"tank\s*300", "Tank 300"),
        (r"tank\s*700", "Tank 700"),
        (r"h9", "H9"),
    ],
    "Zeekr": [
        (r"zeekr\s*001|001", "Zeekr 001"),
        (r"zeekr\s*009|009", "Zeekr 009"),
        (r"zeekr\s*x", "Zeekr X"),
        (r"zeekr\s*007|007", "Zeekr 007"),
    ],
    "Li Auto": [
        (r"li\s*l9|l9", "Li L9"),
        (r"li\s*l8|l8", "Li L8"),
        (r"li\s*l7|l7", "Li L7"),
        (r"li\s*l6|l6", "Li L6"),
    ],
    "Arcfox": [
        (r"kaola", "Kaola"),
        (r"alpha-t", "Alpha-T"),
        (r"alpha-s", "Alpha-S"),
    ],
    "GTV": [
        (r"gtv\s*kain|kain", "GTV Kain"),
        (r"gtv\s*reahu|reahu", "GTV Reahu"),
        (r"gtv\s*soben|soben", "GTV Soben"),
        (r"gtv\s*krormo|krormo", "GTV Krormo"),
    ],
    "ZNA": [
        (r"zna\s*z9\s*gt|z9\s*gt", "ZNA Z9 GT"),
        (r"zna\s*z9|z9", "ZNA Z9"),
        (r"zna\s*rich\s*6|rich\s*6", "ZNA Rich 6"),
    ],
    "Chevrolet": [
        (r"camaro\s*rs|camaro", "Camaro RS"),
        (r"corvette", "Corvette"),
        (r"silverado", "Silverado"),
        (r"colorado", "Colorado"),
        (r"trailblazer", "Trailblazer"),
        (r"tahoe", "Tahoe"),
        (r"suburban", "Suburban"),
        (r"cruze", "Cruze"),
        (r"trax", "Trax"),
        (r"captiva", "Captiva"),
    ],
    "Jeep": [
        (r"wrangler\s*rubicon|rubicon", "Wrangler Rubicon"),
        (r"wrangler\s*sahara|sahara", "Wrangler Sahara"),
        (r"wrangler", "Wrangler"),
        (r"gladiator", "Gladiator"),
        (r"grand\s*cherokee", "Grand Cherokee"),
        (r"cherokee", "Cherokee"),
        (r"compass", "Compass"),
        (r"renegade", "Renegade"),
    ],
    "Suzuki": [
        (r"jimny", "Jimny"),
        (r"swift", "Swift"),
        (r"ertiga", "Ertiga"),
        (r"xl7", "XL7"),
        (r"ciaz", "Ciaz"),
        (r"grand\s*vitara", "Grand Vitara"),
        (r"vitara", "Vitara"),
        (r"carry", "Carry"),
    ],
    "Isuzu": [
        (r"d-max|dmax", "D-Max"),
        (r"mu-x", "MU-X"),
        (r"trooper", "Trooper"),
    ],
    "Volkswagen": [
        (r"teramont", "Teramont"),
        (r"touareg", "Touareg"),
        (r"tiguan", "Tiguan"),
        (r"golf", "Golf"),
        (r"passat", "Passat"),
        (r"id\.4", "ID.4"),
        (r"id\.6", "ID.6"),
        (r"beetle", "Beetle"),
        (r"polo", "Polo"),
    ],
    "Volvo": [
        (r"xc90", "XC90"),
        (r"xc60", "XC60"),
        (r"xc40", "XC40"),
        (r"s90", "S90"),
        (r"s60", "S60"),
        (r"v90", "V90"),
        (r"v60", "V60"),
        (r"ex90", "EX90"),
        (r"ex30", "EX30"),
    ],
    "Lamborghini": [
        (r"huracan", "Huracan"),
        (r"urus", "Urus"),
        (r"aventador", "Aventador"),
    ],
}



# ── Standalone / Uniquely Identifiable Model Aliases (No Brand required) ───────
# (regex_pattern, Canonical Brand, Canonical Model or None)
STANDALONE_MODEL_MAP: List[Tuple[str, str, Optional[str]]] = [
    # Toyota models & Khmer aliases
    (r"(?:prius|pruis|prus|plugin|pluging|plug-in|plungin)", "Toyota", "Prius"),
    (r"(?:camry|camri)", "Toyota", "Camry"),
    (r"(?:highlander|high lander)", "Toyota", "Highlander"),
    (r"(?:corolla cross|corolla altis|corolla)", "Toyota", "Corolla"),
    (r"(?:land cruiser prado|land cruiser|lc\s*[_\-]?\s*(?:300|200|105|100|80|70)|prado)", "Toyota", "Land Cruiser"),
    (r"(?:hilux revo rally|hilux revo|hilux vigo|hilux|revo|vigo|rally)", "Toyota", "Hilux"),
    (r"(?:alphard|vellfire|sienna|fortuner|yaris cross|yaris|raize|veloz|rush|vitz|innova|avanza|vios|hiace|crown|sequoia|4runner|c-hr|chr|harrier|belta|aqua|celica|fj cruiser|bz4x|tacoma|tundra)", "Toyota", None),
    (r"(?:le\s*0[1-9]|le\s*[1-9][0-9]|xle\s*0[1-9]|xle\s*[1-9][0-9]|se\s*0[1-9])", "Toyota", "Camry"),

    # Lexus models & Khmer nicknames
    (r"(?:lx\s*600|lx\s*570|lx\s*470|lx\s*450)", "Lexus", None),
    (r"(?:gx\s*460|gx\s*470)", "Lexus", None),
    (r"(?:rx\s*450h|rx\s*350|rx\s*330|rx\s*300)", "Lexus", None),
    (r"(?:nx\s*350h|nx\s*350|nx\s*300h|nx\s*300|nx\s*200t|nx\s*250)", "Lexus", None),
    (r"(?:lm\s*500h|lm\s*350h|lm\s*350|lm\s*300h)", "Lexus", None),
    (r"(?:ls\s*500|ls\s*460|ls\s*430|ls\s*400)", "Lexus", None),
    (r"(?:es\s*350|es\s*300h|es\s*300|es\s*250)", "Lexus", None),
    (r"(?:is\s*350|is\s*300|is\s*250|is\s*200)", "Lexus", None),
    (r"(?:ux\s*250h|ux\s*200|tx\s*500h|tx\s*350|hs\s*250h|ct\s*200h|rz\s*450e)", "Lexus", None),
    (r"(?:ស្រីម៉ៅ|ឡានស្រីម៉ៅ)", "Lexus", "RX300"),

    # Mercedes-Benz specific models
    (r"(?:g\s*63\s*amg|g\s*63|g\s*500|gls\s*600|gls\s*450|gls\s*400|gle\s*450|gle\s*350|gle\s*53|glc\s*300|glc\s*200|gla\s*250|glb\s*200|s\s*580|s\s*500|s\s*450|s\s*400|s\s*350|e\s*350|e\s*300|e\s*250|e\s*200|c\s*300|c\s*250|c\s*200|c\s*180|c\s*63|amg\s*gts|amg\s*gt|c[- ]coupe|c[- ]coupé|cla\s*45|cla\s*250|cls\s*450|v\s*250)", "Mercedes-Benz", None),

    # Ford
    (r"ranger\s*wildtrak|wildtrak", "Ford", "Ranger Wildtrak"),
    (r"ranger\s*raptor|raptor", "Ford", "Ranger Raptor"),
    (r"ranger\s*stormtrak|stormtrak", "Ford", "Ranger Stormtrak"),
    (r"ranger\s*xls", "Ford", "Ranger XLS"),
    (r"ranger\s*xlt", "Ford", "Ranger XLT"),
    (r"ranger\s*sport", "Ford", "Ranger Sport"),
    (r"ranger\s*xl", "Ford", "Ranger XL"),
    (r"ranger", "Ford", "Ranger"),
    (r"everest\s*titanium", "Ford", "Everest Titanium"),
    (r"everest\s*sport", "Ford", "Everest Sport"),
    (r"everest", "Ford", "Everest"),
    (r"(?:f-150 raptor|f-150|f-250|f-350|explorer|territory|expedition|escape|mustang|bronco)", "Ford", None),


    # Chevrolet
    (r"(?:camaro rs|camaro|corvette|silverado|colorado|trailblazer|tahoe|suburban|cruze|trax|captiva)", "Chevrolet", None),

    # Hyundai & Kia
    (r"(?:grand starex|starex|staria|santa fe|palisade|tucson|creta|venue|elantra|sonata|accent|kona|ioniq 5|ioniq 6|custin|h-1)", "Hyundai", None),
    (r"(?:grand carnival|carnival|sedona|sorento|sportage|telluride|seltos|sonet|carens|picanto|morning|k5|k3|cerato|ev6|ev9|ray\b|嘉华)", "Kia", None),

    # Chinese EV / Modern
    (r"(?:atto 3|dolphin|seal|song plus|tang|han|qin plus|yuan plus|seagull|yangwang u8)", "BYD", None),
    (r"(?:denza d9|denza n8|denza n7|d9\b|n8l\b|n8\b|n7\b|腾势d9|腾势)", "Denza", None),
    (r"(?:leopard 5|leopard 7|leopard 8|leopard ti7|ti7\b|bao 5|bao 8)", "Fangchengbao", None),
    (r"(?:deepal s05|deepal s07|deepal l07|s05\b|s07\b|l07\b|uni-k|uni-t|uni-v|cs75 plus|cs55 plus|cs35 plus|q05\b|ez\s*60|ez\s*6)", "Changan", None),
    (r"(?:avatr 07|avatr 11|avatr 12|avatr max)", "Avatr", None),
    (r"(?:x9\b|g6\b|g9\b|p7\b|p5\b)", "Xpeng", None),
    (r"(?:gn8|gn6|gn6pro|gs8|gs4|gs3|emzoom|emkoo|aion y|aion s|aion v)", "GAC", None),
    (r"(?:icar v23|icar 03|v23\b|v23s\b)", "iCar", None),
    (r"(?:coolray|azkarra|monjaro|tugella|okavango|emgrand|starray)", "Geely", None),
    (r"(?:dashing|x70 plus|x70|x90 plus|t2|traveler)", "Jetour", None),
    (r"(?:tiggo 8 pro|tiggo 7 pro|tiggo 4 pro|tiggo 8|tiggo 7|omoda 5|jaecoo 7|jaecoo 8)", "Chery", None),
    (r"(?:mg4|mg hs|mg zs|mg rx8|mg gt|mg5|cyberster|mg one)", "MG", None),
    (r"(?:tank 300|tank 500|tank 400|tank 700|h6 hev|h6|jolion|dargo|h9)", "Haval", None),
    (r"(?:kaola|alpha-t|alpha-s)", "Arcfox", None),
    (r"(?:zeekr 001|zeekr 009|zeekr x|zeekr 007)", "Zeekr", None),
    (r"(?:li l9|li l8|li l7|li l6|l9\b|l8\b|l7\b|l6\b)", "Li Auto", None),

    # German & Other makes
    (r"(?:x7|x6|x5|x4|x3|x2|x1|xm|m5|m4|m3|m2|760li|750li|745le|740li|730li|530i|528i|525i|520i|430i|330i|328i|325i|320i|ix|i7|i4|i8|z4)\b", "BMW", None),
    (r"(?:defender 110|defender 90|defender 130|defender|range rover sport|range rover autobiography|range rover velar|range rover evoque|vogue|discovery sport|discovery)", "Land Rover", None),
    (r"(?:cayenne coupe|cayenne|macan|panamera|taycan|911 carrera|911|718 cayman|718 boxster)", "Porsche", None),
    (r"(?:q8|q7|q5|q3|q2|a8|a7|a6|a5|a4|a3|e-tron|r8)\b", "Audi", None),
    (r"(?:rubicon|sahara|wrangler|gladiator|grand cherokee|cherokee|compass|renegade)", "Jeep", None),
    (r"(?:cr-v|crv|hr-v|hrv|wr-v|civic|city|accord|br-v|pilot|passport|odyssey|fit|jazz)", "Honda", None),
    (r"(?:montero sport|pajero sport|pajero|triton|l200|xpander cross|xpander|xforce|outlander|attrage|mirage)", "Mitsubishi", None),
    (r"(?:navara|patrol|terra|x-trail|kicks|magnite|almera|sunny|urvan|gt-r|juke)", "Nissan", None),
    (r"(?:cx-90|cx-60|cx-9|cx-8|cx-5|cx-30|cx-3|bt-50|mazda 2|mazda 3|mazda 6)", "Mazda", None),
    (r"(?:d-max|dmax|mu-x|trooper)", "Isuzu", None),
    (r"(?:jimny|swift|ertiga|xl7|ciaz|grand vitara|vitara|carry)", "Suzuki", None),
    (r"(?:huracan|urus|aventador)", "Lamborghini", None),
    (r"(?:gtv kain|gtv reahu|gtv soben|gtv krormo|gtv)", "GTV", None),
    (r"(?:zna z9|zna rich|zna)", "ZNA", None),
]

_STANDALONE_MODEL_PATTERNS = [
    (
        re.compile(
            r"(?:\b|(?<=[\u1780-\u17FF]))" + pat + r"(?:\b|(?=[\u1780-\u17FF\s]|$))",
            re.IGNORECASE,
        ),
        brand,
        canonical,
    )
    for pat, brand, canonical in STANDALONE_MODEL_MAP
]

# Pre-compiled known model patterns per brand
_KNOWN_MODEL_PATTERNS: Dict[str, List[Tuple[re.Pattern, str]]] = {
    brand: [
        (
            re.compile(
                r"(?:\b|(?<=[\u1780-\u17FF]))" + pat + r"(?:\b|(?=[\u1780-\u17FF\s]|$))",
                re.IGNORECASE,
            ),
            canonical,
        )
        for pat, canonical in models
    ]
    for brand, models in KNOWN_MODELS_BY_BRAND.items()
}


_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")

_STOP_WORDS = {
    "for", "sale", "used", "new", "good", "condition", "year",
    "km", "manual", "automatic", "auto", "diesel", "petrol",
    "electric", "hybrid", "turbo", "4wd", "awd", "4x4",
    "price", "cheap", "urgent", "negotiable", "full", "option", "opt",
    "ស្លាកលេខ", "ក្រដាសពន្ធ", "ឡានស្អាត", "ម្ចាស់ដើម", "លក់", "រថយន្ត", "បន្ទាន់",
}


def extract_brand_model(title: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the car brand and model name from a listing title string.

    Strategy:
    1. Clean title: NFKC normalize, strip zero-width chars, expand squished digits/text.
    2. Scan for a known brand / alias (multilingual English, Khmer, Chinese).
    3. If brand matched:
       a. Search within the title for a known curated model for that brand.
       b. Search standalone models registered under this brand.
       c. Fallback: Parse tokens immediately following the brand, stopping at years/stop words.
    4. If no brand matched directly:
       a. Scan for distinct standalone models (e.g. "Prius", "RX350", "Wildtrak", "C300", "D9")
          to infer both the canonical Brand and Model.

    Returns:
        (brand, model) — either or both may be None.
    """
    if not title or not isinstance(title, str):
        return None, None

    clean_t = clean_title(title)
    if not clean_t:
        return None, None

    # ── Stage 1: Search for Known Brand / Alias ────────────────────────────────
    detected_brand: Optional[str] = None
    brand_match_end: int = -1

    for pattern, canonical_brand in _BRAND_PATTERNS:
        m = pattern.search(clean_t)
        if m:
            detected_brand = canonical_brand
            brand_match_end = m.end()
            break

    # ── Stage 2: If Brand is found, extract Model ─────────────────────────────
    if detected_brand:
        # 2a. Check curated models for this brand (longest-match first)
        for model_pat, model_candidate in _KNOWN_MODEL_PATTERNS.get(detected_brand, []):
            if model_pat.search(clean_t):
                return detected_brand, model_candidate

        # 2b. Check standalone models registered under this brand
        for model_pat, m_brand, canonical_model in _STANDALONE_MODEL_PATTERNS:
            if m_brand == detected_brand:
                m = model_pat.search(clean_t)
                if m:
                    return detected_brand, canonical_model or m.group(0).strip()

        # 2c. Heuristic fallback: tokens immediately after the brand occurrence
        after = clean_t[brand_match_end:].strip()
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

    # ── Stage 3: No direct brand found — Search for Distinct Standalone Models ─
    for model_pat, inferred_brand, canonical_model in _STANDALONE_MODEL_PATTERNS:
        m = model_pat.search(clean_t)
        if m:
            return inferred_brand, canonical_model or m.group(0).strip()

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
            s = str(val).strip()
            if s:
                return s
    return None


def parse_mileage(raw: Any) -> Optional[int]:
    """
    Parse a mileage / odometer value to an integer (km).

    Handles formats like "150,000", "150000 km", "150K km", "85.5k".
    Returns None if unparseable or negative.
    """
    if raw is None:
        return None
    s = str(raw).lower().replace(",", "").replace(" ", "")
    # Handle "150k" shorthand
    if s.endswith("k"):
        try:
            val = int(float(s[:-1]) * 1000)
            return val if val >= 0 else None
        except ValueError:
            return None
    # Strip trailing "km"
    s = re.sub(r"km$", "", s).strip()
    try:
        val = int(float(s))
        return val if val >= 0 else None
    except (ValueError, TypeError):
        return None


def parse_engine_cc(raw: Any) -> Optional[int]:
    """
    Parse engine displacement / CC to an integer.

    Handles formats like "2.0L" -> 2000, "1500 cc" -> 1500, "3,500" -> 3500.
    Returns None if unparseable or outside plausible bounds (300 to 10,000 cc).
    """
    if raw is None:
        return None
    s = str(raw).lower().replace(",", "").strip()
    # Match Liter formats like "2.0l" or "2.0 l"
    liters_match = re.match(r"^(\d+(?:\.\d+)?)\s*l(?:iter)?$", s)
    if liters_match:
        try:
            cc = int(float(liters_match.group(1)) * 1000)
            return cc if 300 <= cc <= 10000 else None
        except ValueError:
            pass
    # Strip "cc"
    s = re.sub(r"cc$", "", s).strip()
    try:
        cc = int(float(s))
        return cc if 300 <= cc <= 10000 else None
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
    Extract and parse window.__NUXT_DATA__ or inline JSON from a Khmer24 server-rendered page.
    Used as a fallback when the REST API is unavailable or for post detail extraction.
    """
    if not html_content or not isinstance(html_content, str):
        return None
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
