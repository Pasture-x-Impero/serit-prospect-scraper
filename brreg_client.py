"""
Klient for Brønnøysundregistrene Enhetsregisteret API
======================================================
Henter selskap basert på NACE-koder og fylke/kommune.
"""

import time
import logging
import requests
from typing import Optional

from config import (
    BRREG_BASE_URL,
    API_PAGE_SIZE,
    REQUEST_DELAY,
)

logger = logging.getLogger(__name__)


class BrregClient:
    """Klient for Enhetsregisteret sitt åpne API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "SeritRekrutteringsScraper/1.0",
        })
        self._kommuner_cache: Optional[list[str]] = None
        self._enhet_navn_cache: dict[str, str] = {}

    def _hent_alle_kommunenummer(self) -> list[str]:
        """Hent alle kommunenummer fra Enhetsregisteret (cachet)."""
        if self._kommuner_cache is not None:
            return self._kommuner_cache
        alle = []
        page = 0
        while True:
            data = self._get("kommuner", {"size": 200, "page": page})
            items = data.get("_embedded", {}).get("kommuner", [])
            if not items:
                break
            alle.extend(i["nummer"] for i in items)
            page_info = data.get("page", {})
            if page + 1 >= page_info.get("totalPages", 1):
                break
            page += 1
        self._kommuner_cache = alle
        return alle

    def hent_kommunenummer_for_fylke(self, fylkesnummer: str) -> list[str]:
        """Returner alle kommunenummer som tilhører et fylke."""
        alle = self._hent_alle_kommunenummer()
        return [k for k in alle if k.startswith(fylkesnummer)]

    def _get(self, endpoint: str, params: dict) -> dict:
        """Utfør GET-request med rate limiting og retry ved feil."""
        url = f"{BRREG_BASE_URL}/{endpoint}"
        max_forsøk = 3
        for forsøk in range(max_forsøk):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                time.sleep(REQUEST_DELAY)
                return response.json()
            except requests.exceptions.HTTPError as e:
                if response.status_code < 500:
                    logger.error(f"API-feil for {url}: {e}")
                    raise
                if forsøk < max_forsøk - 1:
                    vent = 2 ** forsøk
                    logger.warning(f"Serverfeil (forsøk {forsøk + 1}/{max_forsøk}), prøver igjen om {vent}s...")
                    time.sleep(vent)
                else:
                    logger.error(f"API-feil etter {max_forsøk} forsøk for {url}: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                if forsøk < max_forsøk - 1:
                    vent = 2 ** forsøk
                    logger.warning(f"Nettverksfeil (forsøk {forsøk + 1}/{max_forsøk}), prøver igjen om {vent}s...")
                    time.sleep(vent)
                else:
                    logger.error(f"Nettverksfeil etter {max_forsøk} forsøk for {url}: {e}")
                    raise

    def søk_enheter(
        self,
        naeringskode: str,
        kommunenummer: Optional[str] = None,
        organisasjonsform: Optional[str] = None,
        fraAntallAnsatte: Optional[int] = None,
        size: int = API_PAGE_SIZE,
        page: int = 0,
    ) -> dict:
        """
        Søk etter enheter i Enhetsregisteret.

        Args:
            naeringskode: NACE-kode (f.eks. '62.200')
            kommunenummer: Kommunenummer (f.eks. '0301' for Oslo)
            organisasjonsform: Organisasjonsform (f.eks. 'AS')
            fraAntallAnsatte: Minimum antall ansatte
            size: Antall resultater per side (maks 100)
            page: Sidenummer (0-indeksert)
        """
        params = {
            "naeringskode": naeringskode,
            "size": min(size, 100),
            "page": page,
        }
        if kommunenummer:
            params["kommunenummer"] = kommunenummer
        if organisasjonsform:
            params["organisasjonsform"] = organisasjonsform
        # API godtar ikke fraAntallAnsatte mellom 1-4
        if fraAntallAnsatte and fraAntallAnsatte >= 5:
            params["fraAntallAnsatte"] = fraAntallAnsatte

        return self._get("enheter", params)

    def hent_alle_enheter(
        self,
        naeringskode: str,
        fylkesnummer: Optional[str] = None,
        organisasjonsform: Optional[str] = None,
        fraAntallAnsatte: Optional[int] = None,
    ) -> list[dict]:
        """
        Hent ALLE enheter for gitte søkekriterier (paginerer automatisk).

        Returns:
            Liste med enheter (rå JSON fra API-et)
        """
        kommunenumre = (
            self.hent_kommunenummer_for_fylke(fylkesnummer)
            if fylkesnummer
            else [None]
        )

        alle_enheter = []
        sett_orgnr: set[str] = set()

        for kommunenummer in kommunenumre:
            page = 0
            while True:
                data = self.søk_enheter(
                    naeringskode=naeringskode,
                    kommunenummer=kommunenummer,
                    organisasjonsform=organisasjonsform,
                    fraAntallAnsatte=fraAntallAnsatte,
                    page=page,
                )

                embedded = data.get("_embedded", {})
                enheter = embedded.get("enheter", [])

                if not enheter:
                    break

                for enhet in enheter:
                    orgnr = enhet.get("organisasjonsnummer")
                    if orgnr in sett_orgnr:
                        continue
                    # Bruk forretningsadresse for fylkesfiltrering — API-et filtrerer
                    # på postadresse og kan returnere selskaper fysisk lokalisert andre steder
                    if kommunenummer:
                        fa_kommnr = enhet.get("forretningsadresse", {}).get("kommunenummer", "")
                        if fa_kommnr != kommunenummer:
                            continue
                    sett_orgnr.add(orgnr)
                    alle_enheter.append(enhet)

                page_info = data.get("page", {})
                total_pages = page_info.get("totalPages", 1)
                total_elements = page_info.get("totalElements", 0)

                logger.info(
                    f"  NACE {naeringskode} kommune {kommunenummer}: "
                    f"Side {page + 1}/{total_pages} ({total_elements} enheter)"
                )

                page += 1
                if page >= total_pages:
                    break

        return alle_enheter

    def hent_enhet_navn(self, orgnr: str) -> str:
        """Hent selskapsnavn for et orgnr (cachet)."""
        if not orgnr:
            return ""
        orgnr = str(orgnr)
        if orgnr in self._enhet_navn_cache:
            return self._enhet_navn_cache[orgnr]
        enhet = self.hent_enhet(orgnr)
        navn = enhet.get("navn", "") if enhet else ""
        self._enhet_navn_cache[orgnr] = navn
        return navn

    def hent_enhet(self, orgnr: str) -> Optional[dict]:
        """Hent detaljer for én enhet basert på organisasjonsnummer."""
        try:
            return self._get(f"enheter/{orgnr}", {})
        except requests.exceptions.RequestException:
            return None

    def hent_roller(self, orgnr: str) -> Optional[dict]:
        """
        Hent rolleinnehavere for et selskap (daglig leder, styreleder, etc.)
        fra Brønnøysundregistrene.
        """
        url = f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return response.json()
        except requests.exceptions.RequestException:
            # Roller-endepunktet finnes ikke for alle enheter
            logger.debug(f"Kunne ikke hente roller for {orgnr}")
            return None
