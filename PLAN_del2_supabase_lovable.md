# Del 2 – Supabase + Lovable-frontend

## Arkitektur

```
Lovable-frontend
    ├── leser kandidater + ekskluderte fra Supabase
    ├── skriver innstillinger til Supabase (fylke, konkurrenter, NACE-koder)
    └── trigger manuell kjøring (via GitHub Actions repository_dispatch)
                        ↑
                   Supabase
                   ├── kandidater      (selskaper som passerte filtrering)
                   ├── ekskluderte     (selskaper som ble filtrert bort, med grunn)
                   └── innstillinger   (bruker-justerbare valg)
                        ↑
GitHub Actions (schedule + manuell trigger)
    └── python main.py
            ├── henter innstillinger fra Supabase
            └── skriver kandidater + ekskluderte til Supabase
```

## Frontend-visning i Lovable

### Hoveddashboard
- Tallkort øverst: antall kandidater, ekskluderte, sist oppdatert, fylker søkt
- Hovedtabell: kandidater med søk, sortering og filtre på fylke, ansatte, NACE-kode

### Faner / seksjoner
| Fane | Innhold |
|------|---------|
| Kandidater | Søkbar/filtrerbar tabell over alle godkjente selskaper |
| Ekskluderte | Tabell med grunn og detalj — for kvalitetssikring |
| Innstillinger | Juster fylker, konkurrenter, NACE-koder, min. ansatte |

### Datamodell i Supabase
Begge tabeller tagges med `fylkesnummer` og `kjort_dato` slik at man kan filtrere per fylke og se når dataene sist ble oppdatert.

## Innstillinger – hva styres fra frontend vs. kode

### Bruker-justerbart via Lovable
| Innstilling | Frontend-komponent |
|-------------|-------------------|
| Fylke(r) å kjøre for | Flervalgsliste |
| Konkurrenter (orgnr + navn) | Tabell med legg til/fjern |
| Konkurrent-nøkkelord | Tabell med legg til/fjern |
| Minimum ansatte | Tallfeld eller slider |
| NACE-koder | Avkrysningsbokser (fast liste, ikke fritekst) |

### Beholdes i kode
| Innstilling | Grunn |
|-------------|-------|
| `REQUEST_DELAY`, `API_PAGE_SIZE` | Teknisk, ikke brukerrelevant |
| `TILLATTE_ORGFORMER` | Sjelden behov for å endre |
| `EKSKLUDER_AVVIKLEDE` | Bør alltid være på |

### NACE-koder i frontend
Vises som avkrysningsbokser med beskrivelse — ikke fritekst.

| Kode | Beskrivelse | Standard |
|------|-------------|----------|
| 62.100 | Dataprogrammeringstjenester | ✅ |
| 62.200 | Konsulentvirksomhet tilknyttet IT og forvaltning og drift | ✅ |
| 62.900 | Andre tjenester tilknyttet informasjonsteknologi | ✅ |
| 63.100 | Datainfrastruktur, -behandling, -lagring og tilknyttede tjenester | ✅ |
| 61.100 | Kabelbasert telekommunikasjon | ⬜ |
| 61.200 | Trådløs telekommunikasjon | ⬜ |
| 61.900 | Annen telekommunikasjon | ⬜ |
| 95.100 | Reparasjon og vedlikehold av datamaskiner | ⬜ |

## Steg

1. **Supabase-oppsett**
   - Opprett prosjekt på supabase.com
   - Lag tabell `kandidater` (kolonner + `fylkesnummer` + `kjort_dato`)
   - Lag tabell `ekskluderte` (orgnr, navn, ansatte, grunn, detalj, fylkesnummer, kjort_dato)
   - Lag tabell `innstillinger` (fylker, konkurrenter, nace_koder, min_ansatte)
   - Generer `SUPABASE_URL` og `SUPABASE_KEY` (service role for Python, anon for frontend)

2. **Python – hent innstillinger + skriv til Supabase**
   - Legg til `supabase-py` i `requirements.txt`
   - Ved oppstart: hent innstillinger fra Supabase i stedet for å lese `config.py`
   - Etter kjøring: upsert kandidater + ekskluderte til Supabase (på orgnr + fylkesnummer)
   - Bruk env-variabler for `SUPABASE_URL` og `SUPABASE_KEY`

3. **GitHub Actions**
   - Opprett repo på GitHub
   - Legg til workflow `.github/workflows/scrape.yml`
   - Sett `SUPABASE_URL` og `SUPABASE_KEY` som GitHub Secrets
   - Schedule: f.eks. hver mandag morgen (`cron: '0 6 * * 1'`)
   - Støtt manuell trigger (`workflow_dispatch`)
   - Støtt `repository_dispatch` for trigger fra Lovable-frontend

4. **Lovable-frontend**
   - Koble Lovable-prosjekt til Supabase
   - Bygg hoveddashboard med tallkort og kandidattabell
   - Bygg Ekskluderte-fane for kvalitetssikring
   - Bygg innstillingsside: juster fylker, konkurrenter, NACE-koder
   - Vurder: eksport til Excel direkte fra Lovable?
   - Vurder: "Kjør nå"-knapp som trigger GitHub Actions?

## Notater
- Upsert på `organisasjonsnummer` + `fylkesnummer` — én rad per selskap per fylke
- `config.py` beholdes som fallback med standardverdier hvis Supabase ikke er satt opp
- API-et filtrerer på postadresse, ikke forretningsadresse — scriptet korrigerer dette i `brreg_client.py`
