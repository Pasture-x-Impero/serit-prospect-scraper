# Del 2 – Supabase + Lovable-frontend

## Arkitektur

```
Lovable-frontend
    ├── leser kandidater + ekskluderte fra Supabase
    ├── skriver manuell_ekskluderte + overrides til Supabase
    └── trigger manuell kjøring (via GitHub Actions repository_dispatch)
                        ↑
                   Supabase
                   ├── kandidater         (selskaper som passerte filtrering)
                   ├── ekskluderte        (automatisk filtrert bort, snapshot per kjøring)
                   ├── manuelt_ekskluderte (manuelt ekskludert via Lovable)
                   └── [innstillinger]    (fremtidig)
                        ↑
GitHub Actions (schedule + manuell trigger)
    └── python main.py
            ├── leser manuelt_ekskluderte fra Supabase
            └── skriver kandidater + ekskluderte til Supabase
```

## Status

### ✅ Fullført

**Supabase-oppsett**
- Prosjekt opprettet via Lovable
- Tabeller opprettet: `kandidater`, `ekskluderte`, `manuelt_ekskluderte`
- Miljøvariabler i `.env` (lokalt) og GitHub Secrets (Actions)

**Python – Supabase-integrasjon**
- `supabase_client.py` bruker `requests` direkte mot PostgREST (supabase-pakken er ikke kompatibel med Python 3.14)
- Upsert av kandidater på `organisasjonsnummer` — manuelle felter (`mobil_daglig_leder`, `notat`) bevares
- Slett + re-insert av ekskluderte ved hver kjøring
- Leser `manuelt_ekskluderte` ved oppstart og filtrerer disse bort

**Lovable-frontend**
- Dashboard med tallkort og kandidattabell
- Ekskluderte-fane
- Kobling mot Supabase

### 🔲 Gjenstår

**GitHub Actions**
- Opprett workflow `.github/workflows/scrape.yml`
- Schedule: f.eks. hver mandag morgen (`cron: '0 6 * * 1'`)
- Støtt manuell trigger (`workflow_dispatch`)
- Støtt `repository_dispatch` for trigger fra Lovable-frontend
- Legg til `SUPABASE_URL` og `SUPABASE_KEY` som GitHub Secrets

**Lovable — manuell redigering**
- Ekskludering av selskaper (skriver til `manuelt_ekskluderte`)
- Redigering av kontaktinfo: e-post, telefon, nettside
- Legg inn mobilnummer til daglig leder (`mobil_daglig_leder`)
- Notatfelt per selskap
- Gjenopprett manuelt ekskluderte selskaper

**Lovable — innstillinger (fremtidig, lav prioritet)**
- Juster fylker, konkurrenter, NACE-koder fra frontend

---

## Supabase-tabeller

```sql
-- Kandidater (upsert på orgnr)
create table kandidater (
  organisasjonsnummer text primary key,
  navn text, organisasjonsform text, naeringskode text,
  naeringsbeskrivelse text, antall_ansatte integer,
  stiftelsesdato text, adresse text, postnummer text,
  poststed text, fylke text, fylkesnummer text,
  nettside text, nettside_kilde text, daglig_leder text,
  epost text, telefon text,
  mobil_daglig_leder text,  -- manuelt felt, overskrives ikke av scraper
  omsetning float, driftsresultat float, egenkapital float,
  regnskap_aar text,
  notat text,               -- manuelt felt, overskrives ikke av scraper
  kjort_dato timestamptz
);

-- Ekskluderte (snapshot, slettes og skrives på nytt per kjøring)
create table ekskluderte (
  organisasjonsnummer text primary key,
  navn text, antall_ansatte integer,
  grunn text, detalj text,
  fylke text, fylkesnummer text,
  kjort_dato timestamptz
);

-- Manuelt ekskluderte (styres av Lovable)
create table manuelt_ekskluderte (
  organisasjonsnummer text primary key,
  navn text, grunn text,
  ekskludert_dato timestamptz default now()
);
```

## Notater
- `supabase`-pakken er ikke kompatibel med Python 3.14 (pyiceberg-dependency krever C++ build tools). Løsning: bruk `requests` direkte mot PostgREST-APIet.
- Manuelle felter i `kandidater` (`mobil_daglig_leder`, `notat`) ekskluderes bevisst fra upsert-payloaden — PostgREST med `resolution=merge-duplicates` oppdaterer kun kolonner som er med i requesten.
- `ekskluderte` slettes og re-insertes ved hver kjøring siden det er et snapshot. `manuelt_ekskluderte` er separat og berøres ikke.
