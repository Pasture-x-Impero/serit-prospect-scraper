"""
Konfigurasjon for Serit Rekrutteringsscraper
=============================================
Juster innstillingene her for å tilpasse søk og filtrering.
"""

# --- NACE-koder for IT-selskap ---
# Disse kodene brukes til å søke i Enhetsregisteret.
# Legg til/fjern koder etter behov.
NACE_KODER = [
    "62.200",  # Konsulentvirksomhet tilknyttet IT og forvaltning og drift
    "46.500",  # Engroshandel med IKT-utstyr
]

# Valgfrie tilleggskoder (sett INKLUDER_UTVIDEDE_KODER = True for å bruke)
INKLUDER_UTVIDEDE_KODER = False
UTVIDEDE_NACE_KODER = [
    "61.100",  # Kabelbasert telekommunikasjon
    "61.200",  # Trådløs telekommunikasjon
    "61.900",  # Annen telekommunikasjon
    "62.100",  # Dataprogrammeringstjenester
    "62.900",  # Andre tjenester tilknyttet informasjonsteknologi
    "63.100",  # Datainfrastruktur, -behandling, -lagring og tilknyttede tjenester
    "95.100",  # Reparasjon og vedlikehold av datamaskiner og kommunikasjonsutstyr
]

# --- Fylkesnumre ---
# Norske fylker med fylkesnummer (2024-struktur).
# Velg ett eller flere fylker å søke i.
FYLKER = {
    "03": "Oslo",
    "11": "Rogaland",
    "15": "Møre og Romsdal",
    "18": "Nordland",
    "31": "Østfold",
    "32": "Akershus",
    "33": "Buskerud",
    "34": "Innlandet",
    "39": "Vestfold",
    "40": "Telemark",
    "42": "Agder",
    "46": "Vestland",
    "50": "Trøndelag",
    "55": "Troms",
    "56": "Finnmark",
}

# Hvilket fylke som brukes i piloten (fylkesnummer)
PILOT_FYLKE = "42"  # Agder

# --- Konkurrentgrupper å ekskludere ---
# Organisasjonsnummer til morselskap/holdingselskap.
# Alle datterselskap under disse filtreres bort.
KONKURRENT_KONSERN = {
    # Atea-konsernet
    "920237126": "Atea ASA",
    "976239997": "Atea AS",
    # Bouvet-konsernet
    "974442167": "Bouvet ASA",
    "996756246": "Bouvet Norge AS",
    # CGI
    "937412983": "CGI AS",
    "919562390": "CGI Norge AS",
    # Computas-konsernet
    "987747390": "Computas Holding AS",
    "986352325": "Computas AS",
    # Crayon-konsernet
    "997602234": "Crayon Group Holding ASA",
    "981125592": "Crayon Group AS",
    "991124810": "Crayon AS",
    # Evidi-konsernet
    "927120291": "Evidi Holding AS",
    "927119781": "Evidi AS",
    # Itera-konsernet
    "980250547": "Itera ASA",
    "967948748": "Itera Norge AS",
    # Kantega
    "985815534": "Kantega AS",
    # Knowit-konsernet
    "997725646": "Knowit AS",
    # Miles-konsernet
    "825979182": "Miles Bidco AS",
    "988340316": "Miles AS",
    # Netcompany
    "881886472": "Netcompany Norway AS",
    # TietoEVRY
    "933012867": "TietoEVRY Norway AS",
    # Visma-konsernet
    "936796702": "Visma AS",
    # Webstep-konsernet
    "996394638": "Webstep ASA",
    "941612474": "Webstep AS",
    # Iteam
    "923456317": "Iteam AS",
}

# Eksakte organisasjonsnummer å ekskludere (enkeltselskap)
EKSKLUDERTE_ORGNR = set()

# Nøkkelord i selskapsnavn som indikerer konkurrerende grupperinger
KONKURRENT_NØKKELORD = [
    # Norske konsern
    "atea",
    "bouvet",
    "cgi",
    "computas",
    "crayon",
    "evidi",
    "itera",
    "iteam",
    "kantega",
    "knowit",
    "miles",
    "netcompany",
    "sopra steria",
    "tietoevry",
    "visma",
    "webstep",
    # Internasjonale
    "accenture",
    "capgemini",
    "cognizant",
    "hcl",
    "ibm",
    "infosys",
    "wipro",
]

# Nøkkelord i selskapsnavn som indikerer selskap som IKKE er relevante
# (f.eks. rene konsulentselskap med enkeltpersoner, osv.)
IRRELEVANTE_NØKKELORD = [
    "holding",
    "invest",
    "kapital",
]

# --- Serit-selskap (ekskluder oss selv) ---
SERIT_ORGNR = {
    "997843703": "Serit AS",
    "997536533": "Serit Holding AS",
    "980155889": "Eltele AS",
    "983616097": "IT Partner Harstad AS",
    "934620437": "Binero Tromsø AS",
    "937079001": "Binero Trondheim AS",
    "991586253": "Itum Notodden AS",
    "914419921": "IT Innovasjon AS",
    "990700435": "C C Solution AS",
    "998703468": "Prodata Cloud AS",
    "930721921": "Impero IT AS",
    "985092400": "Moveo AS",
    "987493348": "Abacus IT AS",
    "928178056": "Oceanbox AS",
}

# --- Filtrering ---
# Organisasjonsformer å inkludere (tom liste = alle)
TILLATTE_ORGFORMER = ["AS", "ASA"]  # Aksjeselskap og Allmennaksjeselskap

# Minimum antall ansatte (0 = ingen filter)
# NB: Enhetsregisteret godtar ikke verdier 1-4 i API-søk.
# Sett til 5 for å filtrere i API-kallet, eller 0 for å hente alle
# og filtrere lokalt etterpå.
MIN_ANSATTE = 5

# Maksimalt antall ansatte (0 = ingen filter)
MAX_ANSATTE = 50

# Maksimal omsetning i MNOK (0 = ingen filter). Filtreres etter berikelse.
MAX_OMSETNING = 100.0

# Ekskluder selskap under avvikling/konkurs
EKSKLUDER_AVVIKLEDE = True

# --- API-innstillinger ---
BRREG_BASE_URL = "https://data.brreg.no/enhetsregisteret/api"
API_PAGE_SIZE = 100  # Maks 100 per side
REQUEST_DELAY = 0.5  # Sekunder mellom API-kall (vær snill mot API-et)

# --- Output ---
OUTPUT_DIR = "output"
