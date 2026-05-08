"""
Filtrering og rensing av selskapsdata
=====================================
Fjerner konkurrenter, Serit-selskap, irrelevante selskap, og duplikater.
"""

import re
import logging
from typing import Optional

from config import (
    KONKURRENT_KONSERN,
    EKSKLUDERTE_ORGNR,
    KONKURRENT_NØKKELORD,
    IRRELEVANTE_NØKKELORD,
    SERIT_ORGNR,
    TILLATTE_ORGFORMER,
    MIN_ANSATTE,
    EKSKLUDER_AVVIKLEDE,
    NACE_KODER,
    INKLUDER_UTVIDEDE_KODER,
    UTVIDEDE_NACE_KODER,
)

logger = logging.getLogger(__name__)


def normaliser_orgnr(orgnr: str) -> str:
    """Fjern punktum og mellomrom fra organisasjonsnummer."""
    return orgnr.replace(".", "").replace(" ", "").strip()


def er_konkurrent(enhet: dict, konkurrent_orgnr_set: set) -> bool:
    """
    Sjekk om et selskap tilhører en konkurrerende gruppering.

    Sjekker:
    1. Om organisasjonsnummeret er direkte ekskludert
    2. Om overordnet enhet (morselskap) er i konkurrentlisten
    3. Om selskapsnavnet inneholder konkurrent-nøkkelord
    """
    orgnr = normaliser_orgnr(enhet.get("organisasjonsnummer", ""))

    # Direkte ekskludering
    if orgnr in konkurrent_orgnr_set:
        return True

    # Sjekk overordnet enhet (morselskap)
    overordnet = enhet.get("overordnetEnhet")
    if overordnet and normaliser_orgnr(str(overordnet)) in konkurrent_orgnr_set:
        return True

    # Sjekk selskapsnavn mot nøkkelord (hel-ord-match)
    navn = enhet.get("navn", "").lower()
    for nøkkelord in KONKURRENT_NØKKELORD:
        if re.search(r'\b' + re.escape(nøkkelord.lower()) + r'\b', navn):
            return True

    return False


def er_serit(enhet: dict) -> bool:
    """Sjekk om selskapet tilhører Serit-gruppen."""
    orgnr = normaliser_orgnr(enhet.get("organisasjonsnummer", ""))
    serit_set = {normaliser_orgnr(o) for o in SERIT_ORGNR}

    if orgnr in serit_set:
        return True

    overordnet = enhet.get("overordnetEnhet")
    if overordnet and normaliser_orgnr(str(overordnet)) in serit_set:
        return True

    # Sjekk navn
    navn = enhet.get("navn", "").lower()
    if "serit" in navn:
        return True

    return False


def er_irrelevant(enhet: dict) -> bool:
    """Sjekk om selskapet er irrelevant basert på nøkkelord."""
    if not IRRELEVANTE_NØKKELORD:
        return False
    navn = enhet.get("navn", "").lower()
    return any(
        re.search(r'\b' + re.escape(nøkkelord.lower()) + r'\b', navn)
        for nøkkelord in IRRELEVANTE_NØKKELORD
    )


def oppfyller_orgform(enhet: dict) -> bool:
    """Sjekk om selskapet har en tillatt organisasjonsform."""
    if not TILLATTE_ORGFORMER:
        return True
    orgform = enhet.get("organisasjonsform", {}).get("kode", "")
    return orgform in TILLATTE_ORGFORMER


def oppfyller_ansattkrav(enhet: dict) -> bool:
    """Sjekk om selskapet har tilstrekkelig antall ansatte."""
    if MIN_ANSATTE <= 0:
        return True
    ansatte = enhet.get("antallAnsatte", 0)
    return ansatte >= MIN_ANSATTE


def er_aktiv(enhet: dict) -> bool:
    """Sjekk om selskapet er aktivt (ikke under avvikling/konkurs)."""
    if not EKSKLUDER_AVVIKLEDE:
        return True
    return (
        not enhet.get("konkurs", False)
        and not enhet.get("underAvvikling", False)
        and not enhet.get("underTvangsavviklingEllerTvangsopplosning", False)
    )


def _ekskluder(ekskluderte: list, enhet: dict, grunn: str, detalj: str = ""):
    ekskluderte.append({
        "organisasjonsnummer": enhet.get("organisasjonsnummer", ""),
        "navn": enhet.get("navn", ""),
        "antall_ansatte": enhet.get("antallAnsatte", 0),
        "grunn": grunn,
        "detalj": detalj,
    })


def _konkurrent_detalj(enhet: dict, konkurrent_orgnr_set: set) -> str:
    orgnr = normaliser_orgnr(enhet.get("organisasjonsnummer", ""))
    if orgnr in konkurrent_orgnr_set:
        return f"Orgnr {orgnr} i ekskluderingslisten"
    overordnet = enhet.get("overordnetEnhet")
    if overordnet and normaliser_orgnr(str(overordnet)) in konkurrent_orgnr_set:
        navn = KONKURRENT_KONSERN.get(normaliser_orgnr(str(overordnet)), overordnet)
        return f"Datterselskap av {navn} ({overordnet})"
    navn = enhet.get("navn", "").lower()
    for nøkkelord in KONKURRENT_NØKKELORD:
        if re.search(r'\b' + re.escape(nøkkelord.lower()) + r'\b', navn):
            return f"Nøkkelord i navn: «{nøkkelord}»"
    return ""


def filtrer_enheter(enheter: list[dict]) -> tuple:
    """
    Kjør alle filtre på en liste med enheter.

    Returns:
        (filtrert_liste, ekskludert_liste, statistikk)
    """
    konkurrent_orgnr_set = {normaliser_orgnr(o) for o in KONKURRENT_KONSERN.keys()}
    konkurrent_orgnr_set.update(normaliser_orgnr(o) for o in EKSKLUDERTE_ORGNR)

    gyldige_nace = set(NACE_KODER)
    if INKLUDER_UTVIDEDE_KODER:
        gyldige_nace.update(UTVIDEDE_NACE_KODER)

    statistikk = {
        "totalt_inn": len(enheter),
        "fjernet_feil_nace": 0,
        "fjernet_konkurrent": 0,
        "fjernet_serit": 0,
        "fjernet_irrelevant": 0,
        "fjernet_orgform": 0,
        "fjernet_ansatte": 0,
        "fjernet_inaktiv": 0,
        "fjernet_duplikat": 0,
    }

    filtrert = []
    ekskluderte = []
    sett_orgnr = set()

    for enhet in enheter:
        orgnr = normaliser_orgnr(enhet.get("organisasjonsnummer", ""))

        if orgnr in sett_orgnr:
            statistikk["fjernet_duplikat"] += 1
            continue
        sett_orgnr.add(orgnr)

        primær_nace = enhet.get("naeringskode1", {}).get("kode", "")
        if primær_nace not in gyldige_nace:
            statistikk["fjernet_feil_nace"] += 1
            _ekskluder(ekskluderte, enhet, "Feil primær NACE", f"Primærkode: {primær_nace}")
            continue

        if not er_aktiv(enhet):
            statistikk["fjernet_inaktiv"] += 1
            _ekskluder(ekskluderte, enhet, "Inaktiv", "Under avvikling, konkurs eller tvangsoppløsning")
            continue

        if not oppfyller_orgform(enhet):
            statistikk["fjernet_orgform"] += 1
            orgform = enhet.get("organisasjonsform", {}).get("kode", "?")
            _ekskluder(ekskluderte, enhet, "Organisasjonsform", f"Orgform: {orgform}")
            continue

        if not oppfyller_ansattkrav(enhet):
            statistikk["fjernet_ansatte"] += 1
            ansatte = enhet.get("antallAnsatte", 0)
            _ekskluder(ekskluderte, enhet, "For få ansatte", f"{ansatte} ansatte (min. {MIN_ANSATTE})")
            continue

        if er_konkurrent(enhet, konkurrent_orgnr_set):
            statistikk["fjernet_konkurrent"] += 1
            detalj = _konkurrent_detalj(enhet, konkurrent_orgnr_set)
            logger.info(f"  Fjernet konkurrent: {enhet.get('navn')} ({orgnr})")
            _ekskluder(ekskluderte, enhet, "Konkurrent", detalj)
            continue

        if er_serit(enhet):
            statistikk["fjernet_serit"] += 1
            _ekskluder(ekskluderte, enhet, "Serit-selskap", "")
            continue

        if er_irrelevant(enhet):
            statistikk["fjernet_irrelevant"] += 1
            navn = enhet.get("navn", "").lower()
            treff = next((k for k in IRRELEVANTE_NØKKELORD
                          if re.search(r'\b' + re.escape(k.lower()) + r'\b', navn)), "")
            _ekskluder(ekskluderte, enhet, "Irrelevant", f"Nøkkelord i navn: «{treff}»")
            continue

        filtrert.append(enhet)

    statistikk["totalt_ut"] = len(filtrert)
    return filtrert, ekskluderte, statistikk
