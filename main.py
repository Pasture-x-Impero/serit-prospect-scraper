#!/usr/bin/env python3
"""
Serit Rekrutteringsscraper
==========================
Kartlegger aktuelle IT-selskap per fylke for Serit-gruppen.

Bruk:
    python main.py                     # Kjør pilot (fylke fra config)
    python main.py --fylke 11          # Kjør for Rogaland
    python main.py --fylke 11,42       # Kjør for flere fylker
    python main.py --alle-fylker       # Kjør for alle definerte fylker
    python main.py --med-nettside      # Skrap nettsider for e-post/tlf (~30–60 min)

Resultater lagres i output/-mappen som Excel-filer.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

from config import (
    NACE_KODER,
    INKLUDER_UTVIDEDE_KODER,
    UTVIDEDE_NACE_KODER,
    FYLKER,
    PILOT_FYLKE,
    TILLATTE_ORGFORMER,
    MIN_ANSATTE,
    MAX_ANSATTE,
    MAX_OMSETNING,
    KONKURRENT_KONSERN,
    KONKURRENT_NØKKELORD,
    SERIT_ORGNR,
    IRRELEVANTE_NØKKELORD,
)
from brreg_client import BrregClient
from filter import filtrer_enheter
from enricher import Enricher
from exporter import eksporter_til_excel
from supabase_client import SupabaseClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def hent_og_filtrer(client: BrregClient, fylkesnummer: str, manuelt_ekskluderte: set = None) -> tuple:
    fylke_navn = FYLKER.get(fylkesnummer, fylkesnummer)
    logger.info(f"=== Starter kartlegging for {fylke_navn} (fylke {fylkesnummer}) ===")

    nace_koder = list(NACE_KODER)
    if INKLUDER_UTVIDEDE_KODER:
        nace_koder.extend(UTVIDEDE_NACE_KODER)
    logger.info(f"Søker med {len(nace_koder)} NACE-koder: {', '.join(nace_koder)}")

    alle_enheter = []
    for nace in nace_koder:
        logger.info(f"Henter enheter med NACE {nace}...")
        if TILLATTE_ORGFORMER:
            for orgform in TILLATTE_ORGFORMER:
                enheter = client.hent_alle_enheter(
                    naeringskode=nace,
                    fylkesnummer=fylkesnummer,
                    organisasjonsform=orgform,
                    fraAntallAnsatte=MIN_ANSATTE if MIN_ANSATTE > 0 else None,
                )
                alle_enheter.extend(enheter)
        else:
            enheter = client.hent_alle_enheter(
                naeringskode=nace,
                fylkesnummer=fylkesnummer,
                fraAntallAnsatte=MIN_ANSATTE if MIN_ANSATTE > 0 else None,
            )
            alle_enheter.extend(enheter)

    logger.info(f"Totalt hentet: {len(alle_enheter)} enheter (inkl. mulige duplikater)")

    logger.info("Filtrerer...")
    filtrert, ekskluderte, statistikk = filtrer_enheter(alle_enheter, manuelt_ekskluderte=manuelt_ekskluderte)

    logger.info(f"Etter filtrering: {len(filtrert)} kandidater")
    for nøkkel, verdi in statistikk.items():
        if verdi > 0 or nøkkel in ("totalt_inn", "totalt_ut"):
            logger.info(f"  {nøkkel}: {verdi}")

    return filtrert, ekskluderte, statistikk


def bygg_rad(enhet: dict, daglig_leder: str = "", regnskap: dict = None) -> dict:
    """Bygg én resultatrad fra rådata."""
    naeringskode = enhet.get("naeringskode1", {})
    adresse_data = enhet.get("forretningsadresse", {}) or enhet.get("postadresse", {})
    adresse_deler = adresse_data.get("adresse", [])
    kommnr = (adresse_data.get("kommunenummer", "") or "")

    return {
        "organisasjonsnummer": enhet.get("organisasjonsnummer", ""),
        "navn": enhet.get("navn", ""),
        "organisasjonsform": enhet.get("organisasjonsform", {}).get("kode", ""),
        "naeringskode": naeringskode.get("kode", ""),
        "naeringsbeskrivelse": naeringskode.get("beskrivelse", ""),
        "antall_ansatte": enhet.get("antallAnsatte", 0),
        "stiftelsesdato": enhet.get("stiftelsesdato", ""),
        "adresse": ", ".join(adresse_deler) if adresse_deler else "",
        "postnummer": adresse_data.get("postnummer", ""),
        "poststed": adresse_data.get("poststed", ""),
        "fylke": FYLKER.get(kommnr[:2], ""),
        "fylkesnummer": kommnr[:2],
        "nettside": enhet.get("hjemmeside", ""),
        "nettside_kilde": "Brreg" if enhet.get("hjemmeside") else "",
        "daglig_leder": daglig_leder,
        "epost": enhet.get("epostadresse", ""),
        "telefon": enhet.get("telefon", ""),
        "omsetning": regnskap.get("omsetning") if regnskap else None,
        "driftsresultat": regnskap.get("driftsresultat") if regnskap else None,
        "egenkapital": regnskap.get("egenkapital") if regnskap else None,
        "regnskap_aar": regnskap.get("regnskap_aar", "") if regnskap else "",
    }


def kjør_for_fylke(
    client: BrregClient,
    fylkesnummer: str,
    med_nettside: bool = False,
    manuelt_ekskluderte: set = None,
) -> tuple:
    """Kjør full pipeline for ett fylke. Returnerer (berikede, ekskluderte, statistikk)."""
    filtrert, ekskluderte, statistikk = hent_og_filtrer(client, fylkesnummer, manuelt_ekskluderte)

    if not filtrert:
        logger.warning("Ingen kandidater funnet etter filtrering.")
        return [], ekskluderte, statistikk

    if med_nettside:
        logger.info("Beriker med kontaktinformasjon (dette kan ta litt tid)...")
        berikede = Enricher().berik_alle(filtrert)
    else:
        logger.info("Beriker med daglig leder og regnskap fra Brreg...")
        enricher = Enricher()
        berikede = []
        for i, enhet in enumerate(filtrert, 1):
            logger.info(f"  {i}/{len(filtrert)}: {enhet.get('navn', '?')}")
            orgnr = enhet.get("organisasjonsnummer", "")
            rad = bygg_rad(
                enhet,
                daglig_leder=enricher.hent_daglig_leder(enhet) or "",
                regnskap=enricher.hent_regnskap(orgnr),
            )
            berikede.append(rad)

    # Omsetningsfilter (etter berikelse siden data hentes fra Regnskapsregisteret)
    fjernet_omsetning = 0
    if MAX_OMSETNING > 0:
        godkjente = []
        for rad in berikede:
            omsetning = rad.get("omsetning")
            if omsetning is not None and omsetning > MAX_OMSETNING:
                fjernet_omsetning += 1
                ekskluderte.append({
                    "organisasjonsnummer": rad.get("organisasjonsnummer", ""),
                    "navn": rad.get("navn", ""),
                    "antall_ansatte": rad.get("antall_ansatte", 0),
                    "grunn": "For høy omsetning",
                    "detalj": f"{omsetning} MNOK (maks. {MAX_OMSETNING} MNOK)",
                    "fylkesnummer": rad.get("fylkesnummer", ""),
                    "fylke": rad.get("fylke", ""),
                })
            else:
                godkjente.append(rad)
        berikede = godkjente

    statistikk["fjernet_for_stor_omsetning"] = fjernet_omsetning
    statistikk["totalt_ut"] = len(berikede)

    return berikede, ekskluderte, statistikk


def slå_sammen_statistikk(alle_statistikk: list[dict]) -> dict:
    kombinert = {}
    for stat in alle_statistikk:
        for nøkkel, verdi in stat.items():
            kombinert[nøkkel] = kombinert.get(nøkkel, 0) + verdi
    return kombinert


def main():
    parser = argparse.ArgumentParser(
        description="Serit Rekrutteringsscraper – kartlegg IT-selskap per fylke"
    )
    parser.add_argument("--fylke", type=str, default=None,
        help=f"Fylkesnummer (kommaseparert for flere). Standard: {PILOT_FYLKE}")
    parser.add_argument("--alle-fylker", action="store_true",
        help="Kjør for alle definerte fylker")
    parser.add_argument("--med-nettside", action="store_true",
        help="Skrap nettsider for e-post og telefon (tar 30–60 min ekstra)")
    parser.add_argument("--verbose", "-v", action="store_true",
        help="Vis debug-meldinger")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.alle_fylker:
        fylker = list(FYLKER.keys())
    elif args.fylke:
        fylker = [f.strip() for f in args.fylke.split(",")]
    else:
        fylker = [PILOT_FYLKE]

    for f in fylker:
        if f not in FYLKER:
            logger.error(f"Ukjent fylkesnummer: {f}")
            logger.info(f"Gyldige fylker: {', '.join(f'{k} ({v})' for k, v in FYLKER.items())}")
            sys.exit(1)

    logger.info(f"Serit Rekrutteringsscraper startet")
    logger.info(f"Fylker: {', '.join(f'{f} ({FYLKER[f]})' for f in fylker)}")
    logger.info(f"Tidspunkt: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    supabase = SupabaseClient()
    manuelt_ekskluderte = supabase.hent_manuelt_ekskluderte()
    if manuelt_ekskluderte:
        logger.info(f"Hentet {len(manuelt_ekskluderte)} manuelt ekskluderte fra Supabase")

    client = BrregClient()
    alle_berikede = []
    alle_ekskluderte = []
    alle_statistikk = []

    for fylkesnummer in fylker:
        berikede, ekskluderte, statistikk = kjør_for_fylke(
            client, fylkesnummer,
            med_nettside=args.med_nettside,
            manuelt_ekskluderte=manuelt_ekskluderte,
        )
        alle_berikede.extend(berikede)
        alle_ekskluderte.extend(ekskluderte)
        alle_statistikk.append(statistikk)

    if len(fylker) == 1:
        fylke_label = fylker[0]
    else:
        fylke_label = "alle_fylker"

    kombinert_statistikk = slå_sammen_statistikk(alle_statistikk)
    filsti = eksporter_til_excel(alle_berikede, fylke_label, kombinert_statistikk, alle_ekskluderte)
    logger.info(f"Excel-fil lagret: {filsti}")

    kjort_dato = datetime.now(timezone.utc).isoformat()
    supabase.skriv_kandidater(alle_berikede, kjort_dato)
    supabase.skriv_ekskluderte(alle_ekskluderte, kjort_dato)

    aktive_nace = list(NACE_KODER) + (list(UTVIDEDE_NACE_KODER) if INKLUDER_UTVIDEDE_KODER else [])
    supabase.skriv_innstillinger({
        "nace_koder": aktive_nace,
        "min_ansatte": MIN_ANSATTE,
        "max_ansatte": MAX_ANSATTE,
        "max_omsetning": MAX_OMSETNING,
        "konkurrenter": KONKURRENT_KONSERN,
        "konkurrent_nøkkelord": KONKURRENT_NØKKELORD,
        "serit_orgnr": SERIT_ORGNR,
        "irrelevante_nøkkelord": IRRELEVANTE_NØKKELORD,
    })

    logger.info(f"=== Ferdig! Resultat lagret i: {filsti} ===")


if __name__ == "__main__":
    main()
