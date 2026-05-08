# Omsetningsfilter – status og alternativer

## Bakgrunn

Prosjektleder har bedt om at selskaper filtreres på omsetning mellom **5–100 MNOK**.

## Problem

Regnskapsregisteret (Brønnøysundregistrene) tilbød tidligere et åpent REST-API for å hente regnskapsdata per organisasjonsnummer. Dette API-et er nå tatt ned og er ikke lenger tilgjengelig.

## Alternativer

### 1. Ansatte som proxy (kan gjøres nå, gratis)
Vi filtrerer allerede på minimum 5 ansatte. For IT-konsulentselskaper tilsvarer 5–100 MNOK omsetning grovt sett 5–50 ansatte. Ikke presist, men tilgjengelig i dag uten ekstra kostnad.

### 2. Bulk-nedlasting fra Brreg (manuell, gratis)
Brreg tilbyr regnskapsdata som bulk-nedlasting (CSV). Kan brukes til å berike datasettet, men egner seg ikke for automatisert filtrering i scriptet.

### 3. Kommersiell datatjeneste (automatisert, koster penger)
Tjenester som **Proff.no**, **Bisnode/Dun & Bradstreet** eller **Ravninfo** tilbyr API-er med regnskapsdata. Krever abonnement.

### 4. Filtrere manuelt i Lovable-frontend (ingen kode, gratis)
Legg til omsetning som en kolonne brukeren kan filtrere på i Lovable. Forutsetter at dataen finnes — enten via kommersiell tjeneste (alt. 3) eller manuell innhenting.

## Anbefaling

Kortsiktig: bruk **antall ansatte** som proxy (alt. 1) — allerede på plass.

Langsiktig: vurder abonnement på **Proff.no** eller tilsvarende og integrer i del 2 som et berikelsesssteg i Python-scriptet, slik at omsetning lagres i Supabase og kan filtreres i Lovable.
