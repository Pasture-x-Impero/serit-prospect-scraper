# Serit Rekrutteringsscraper

Kartlegger aktuelle IT-selskap per fylke for Serit-gruppen. Henter data fra Enhetsregisteret, filtrerer bort konkurrenter og irrelevante selskap, beriker med kontaktinformasjon, og eksporterer til Excel og Supabase.

## Komme i gang

### 1. Installer avhengigheter

```bash
pip install -r requirements.txt
```

### 2. Konfigurer miljøvariabler

Opprett en `.env`-fil i prosjektmappen:

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=din-api-nokkel
```

Uten disse kjører scraperen normalt og produserer kun Excel-output.

### 3. Kjør scriptet

Det finnes to modi — velg etter behov:

| Modus | Kommando | Tid | Hva du får |
|-------|----------|-----|------------|
| Standard | `python main.py` | ~5–10 min | Alt fra Brreg inkl. daglig leder og regnskap |
| Full | `python main.py --med-nettside` | ~60–90 min | Alt over + e-post/tlf scrapt fra nettsider |

**Anbefalt for vanlig bruk:**
```bash
python main.py
```

### 4. Kjør for andre fylker

```bash
python main.py --fylke 11          # Rogaland
python main.py --fylke 11,42       # Rogaland og Agder
python main.py --alle-fylker       # Alle fylker
```

Fylkeskodene er offisielle koder fra SSB og brukes av alle offentlige registre i Norge.

| Kode | Fylke |
|------|-------|
| 03 | Oslo |
| 11 | Rogaland |
| 15 | Møre og Romsdal |
| 18 | Nordland |
| 31 | Østfold |
| 32 | Akershus |
| 33 | Buskerud |
| 34 | Innlandet |
| 39 | Vestfold |
| 40 | Telemark |
| 42 | Agder |
| 46 | Vestland |
| 50 | Trøndelag |
| 55 | Troms |
| 56 | Finnmark |

### 5. Finn resultatet

Excel-filen lagres automatisk i `output/`-mappen:
```
output/serit_kandidater_Oslo_20260505_1403.xlsx
```
Filen har tre ark: **Kandidater**, **Ekskluderte** og **Statistikk**.

Data skrives også til Supabase (hvis konfigurert) — se under.

## Hva skjer under panseret?

### 1. Henting (`brreg_client.py`)
Søker i Enhetsregisteret per NACE-kode. Siden API-et ikke lenger støtter filtrering på fylke direkte, hentes alle kommuner som tilhører fylket (basert på kommunenummer-prefiks), og det gjøres ett API-kall per kommune. Resultater pagineres automatisk og duplikater filtreres bort.

API-et forhåndsfiltrerer på organisasjonsform (AS/ASA), minimum 5 ansatte og aktive selskaper.

### 2. Filtrering (`filter.py`)
Selskaper filtreres i denne rekkefølgen:

| Steg | Hva fjernes |
|------|-------------|
| Duplikater | Samme orgnr fra flere NACE-koder |
| Manuelt ekskluderte | Selskaper ekskludert manuelt i Lovable-appen |
| Serit-selskap | Egne selskaper ekskluderes |
| Konkurrenter | Selskaper i `KONKURRENT_KONSERN` eller med konkurrent-nøkkelord i navn |
| Feil primær NACE | Primærkoden er ikke én av de aktive søkekodene |
| For mange ansatte | Over `MAX_ANSATTE` (standard: 50) |
| For høy omsetning | Over `MAX_OMSETNING` MNOK (standard: 100) — filtreres etter berikelse |
| Irrelevante nøkkelord | Selskaper med nøkkelord i `IRRELEVANTE_NØKKELORD` (holding, invest, kapital) |

Konkurrentsjekken fanger opp både direkte orgnr-treff, datterselskaper (via overordnet enhet) og navnetreff på nøkkelord som "atea", "crayon", "capgemini" osv.

> **Merk:** Brreg-API-et søker på tvers av alle registrerte NACE-koder for et selskap, ikke bare primærkoden. Et selskap med `62.200` som sekundærkode vil derfor dukke opp i søket. Filteret sjekker at primær-NACE (`naeringskode1`) er én av de aktive søkekodene — selskaper som ikke oppfyller dette, fjernes og havner i "Ekskluderte"-arket med grunn "Feil primær NACE-kode".

### 3. Berikelse (`enricher.py`)
For hvert selskap som passerer filtreringen hentes:
- **Daglig leder** — fra `/roller`-endepunktet i Enhetsregisteret
- **Regnskapstall** — fra Regnskapsregisteret (`data.brreg.no/regnskapsregisteret`): omsetning, driftsresultat og egenkapital for siste tilgjengelige år, oppgitt i MNOK
- **Nettside** — først fra Enhetsregisteret. Har Brreg ingen nettside, søkes det automatisk i DuckDuckGo (kun med `--med-nettside`).
- **E-post og telefon** — ved å skrape selskapets nettside (hoved + /kontakt, /contact, /om-oss). Kun med `--med-nettside`.

#### Nettside-oppslag med DuckDuckGo

Når et selskap mangler nettside i Brreg, søkes det på selskapsnavnet i DuckDuckGo. For å unngå feiltreff gjøres to kontroller:

1. **Blokkliste** — kjente aggregatorsider (proff.no, 1881.no, linkedin.com, youtube.com m.fl.) forkastes automatisk.
2. **Domenevalidering** — minst ett nøkkelord fra selskapsnavnet må finnes i domenet. Et søketreff på `moava.no` for "MOAVA AS" godkjennes; et treff på `dnb.com` forkastes.

Brreg-nettsider behandles aldri av DuckDuckGo — kun selskaper uten registrert nettside i Brreg går gjennom dette steget.

I Excel-filen markeres rader med DDG-funnet nettside med gul bakgrunn, og kolonnen "Nettside kilde" viser `Brreg` eller `DDG`.

### 4. Eksport (`exporter.py`)
Lager en Excel-fil i `output/`-mappen med tre ark:

**Kandidater** — ett selskap per rad, sortert på fylke og deretter ansatte (synkende):

| Kolonne | Kilde |
|---------|-------|
| Organisasjonsnummer | Enhetsregisteret |
| Selskapsnavn | Enhetsregisteret |
| Org.form | Enhetsregisteret |
| NACE-kode | Enhetsregisteret |
| Næringsbeskrivelse | Enhetsregisteret |
| Antall ansatte | Enhetsregisteret |
| Stiftelsesdato | Enhetsregisteret |
| Adresse, Postnummer, Poststed, Fylke | Enhetsregisteret |
| Nettside | Enhetsregisteret, eller DuckDuckGo-søk som fallback (`--med-nettside`) |
| Nettside kilde | `Brreg` eller `DDG` |
| Daglig leder | Brreg roller-API |
| E-post, Telefon | Brreg eller nettside-scraping (`--med-nettside`) |
| Omsetning (MNOK) | Regnskapsregisteret |
| Driftsresultat (MNOK) | Regnskapsregisteret |
| Egenkapital (MNOK) | Regnskapsregisteret |
| Regnskapsår | Regnskapsregisteret |

**Ekskluderte** — sortert på ansatte synkende, med grunn og detalj.

**Statistikk** — filtreringsrapport med antall fjernet per steg.

### 5. Supabase-integrasjon (`supabase_client.py`)
Etter kjøring skrives resultater til Supabase via REST API:

- **`kandidater`** — upsert på `organisasjonsnummer`. Manuelle felter (`mobil_daglig_leder`, `notat`) overskrives aldri av scraperen.
- **`ekskluderte`** — slettes og skrives på nytt ved hver kjøring (snapshot).
- **`manuelt_ekskluderte`** — leses ved oppstart. Selskaper i denne tabellen filtreres bort og telles som "Manuelt ekskludert" i statistikken.

## Konfigurasjon

Alt konfigureres i `config.py`:

| Innstilling | Beskrivelse |
|-------------|-------------|
| `NACE_KODER` | Næringskoder som søkes på |
| `INKLUDER_UTVIDEDE_KODER` | Slå på ekstra koder (telekom, reparasjon) |
| `PILOT_FYLKE` | Standard-fylke uten `--fylke`-flagg |
| `KONKURRENT_KONSERN` | Orgnr til konsern som ekskluderes med datterselskaper |
| `EKSKLUDERTE_ORGNR` | Enkeltselskaper som ekskluderes |
| `KONKURRENT_NØKKELORD` | Nøkkelord i selskapsnavn som trigger ekskludering |
| `IRRELEVANTE_NØKKELORD` | Nøkkelord som ekskluderer (holding, invest, kapital) |
| `MIN_ANSATTE` | Minimum antall ansatte (forhåndsfiltrert i API) |
| `MAX_ANSATTE` | Maksimalt antall ansatte (standard: 50) |
| `MAX_OMSETNING` | Maksimal omsetning i MNOK (standard: 100) |
| `REQUEST_DELAY` | Sekunder mellom API-kall |

### NACE-koder i bruk

**Offisielle koder (alltid aktive):**

| Kode | Beskrivelse |
|------|-------------|
| 62.200 | Konsulentvirksomhet tilknyttet IT og forvaltning og drift |
| 46.500 | Engroshandel med IKT-utstyr |

**Utvidede koder (aktiveres med `INKLUDER_UTVIDEDE_KODER = True`):**

| Kode | Beskrivelse |
|------|-------------|
| 62.100 | Dataprogrammeringstjenester |
| 62.900 | Andre tjenester tilknyttet informasjonsteknologi |
| 63.100 | Datainfrastruktur, -behandling, -lagring og tilknyttede tjenester |
| 61.100 | Kabelbasert telekommunikasjon |
| 61.200 | Trådløs telekommunikasjon |
| 61.900 | Annen telekommunikasjon |
| 95.100 | Reparasjon og vedlikehold av datamaskiner |

## Filstruktur

```
serit-scraper/
├── main.py              # Hovedscript – kjør dette
├── config.py            # All konfigurasjon
├── brreg_client.py      # API-klient for Enhetsregisteret
├── filter.py            # Filtrering og rensing
├── enricher.py          # Berikelse med kontaktinfo
├── exporter.py          # Excel-eksport
├── supabase_client.py   # Supabase-integrasjon
├── requirements.txt     # Python-avhengigheter
├── .env                 # Miljøvariabler (ikke i git)
└── output/              # Genererte Excel-filer
```

## Datakilder

- **Enhetsregisteret** (data.brreg.no): Selskapsdata, NACE-koder, adresse, roller
- **Regnskapsregisteret** (data.brreg.no/regnskapsregisteret): Omsetning, driftsresultat og egenkapital
- **Selskapenes nettsider**: E-post og telefon (valgfritt, kan ta tid)
- **Supabase**: Lagring og manuell overrides via Lovable-frontend
