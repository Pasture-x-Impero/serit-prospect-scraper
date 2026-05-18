"""
Berikelse av selskapsdata med kontaktinformasjon
================================================
Henter daglig leder, nettside, e-post og telefon.
"""

import re
import time
import logging
import requests
from typing import Optional
from urllib.parse import urlparse

from ddgs import DDGS

from config import REQUEST_DELAY, FYLKER

_UTELAT_DOMENER = [
    # Norske bedriftsregistre og aggregatorer
    "proff.no", "1881.no", "gulesider.no", "brreg.no", "purehelp.no",
    "yra.no", "b2bhint.com", "theorg.com", "europages.com", "contactout.com",
    # Sosiale medier
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    # Søkemotorer og kataloger
    "google.com", "bing.com", "finn.no",
    # Video og media
    "youtube.com", "youtu.be", "vimeo.com",
    # App-butikker
    "apps.apple.com", "play.google.com",
    # Nyheter og presse
    "helpnetsecurity.com", "securityweek.com", "bleepingcomputer.com",
    "aftenposten.no", "vg.no", "dagbladet.no", "nrk.no", "e24.no", "dn.no",
    "prnewswire.com", "businesswire.com", "cision.com",
    # Misc
    "wikipedia.org", "github.com", "hitmos.me", "an1.com", "dnb.com",
]

_STOPORD = {
    "as", "asa", "og", "the", "group", "norge", "norway", "nordic",
    "solutions", "solution", "system", "systems", "technology", "technologies",
    "consulting", "services", "data", "digital", "innovation", "hub",
    "publishing", "information", "interaktiv", "sikkerhet", "complete",
}

logger = logging.getLogger(__name__)


class Enricher:
    """Beriker selskapsdata med kontaktinformasjon."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SeritRekrutteringsScraper/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json",
        })
        self._morselskap_cache: dict[str, str] = {}

    def hent_morselskap_navn(self, orgnr: str) -> str:
        """Hent navn på morselskap (cachet)."""
        if not orgnr:
            return ""
        orgnr = str(orgnr)
        if orgnr in self._morselskap_cache:
            return self._morselskap_cache[orgnr]
        try:
            url = f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
            response = self.session.get(url, timeout=15)
            navn = response.json().get("navn", "") if response.status_code == 200 else ""
        except requests.exceptions.RequestException:
            navn = ""
        self._morselskap_cache[orgnr] = navn
        return navn

    def _format_morselskap(self, orgnr) -> str:
        if not orgnr:
            return ""
        navn = self.hent_morselskap_navn(str(orgnr))
        return f"{navn} ({orgnr})" if navn else str(orgnr)

    def hent_regnskap(self, orgnr: str) -> dict:
        """Hent nøkkeltall fra Regnskapsregisteret (siste tilgjengelige år)."""
        tom = {"omsetning": None, "driftsresultat": None, "egenkapital": None, "regnskap_aar": ""}
        try:
            url = f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return tom
            data = response.json()
            if not data:
                return tom

            siste = data[0]
            periode = siste.get("regnskapsperiode", {})
            aar = (periode.get("tilDato") or "")[:4]

            resultat = siste.get("resultatregnskapResultat", {})
            drift = resultat.get("driftsresultat", {})
            omsetning_rå = drift.get("driftsinntekter", {}).get("sumDriftsinntekter")
            driftsres_rå = drift.get("driftsresultat")

            egenkapital_rå = (
                siste.get("egenkapitalGjeld", {})
                    .get("egenkapital", {})
                    .get("sumEgenkapital")
            )

            def til_mnok(v):
                return round(v / 1_000_000, 1) if v is not None else None

            return {
                "omsetning": til_mnok(omsetning_rå),
                "driftsresultat": til_mnok(driftsres_rå),
                "egenkapital": til_mnok(egenkapital_rå),
                "regnskap_aar": aar,
            }
        except Exception as e:
            logger.debug(f"Kunne ikke hente regnskap for {orgnr}: {e}")
            return tom

    def hent_daglig_leder(self, enhet: dict) -> Optional[str]:
        """
        Hent daglig leder fra rolledata i Enhetsregisteret.
        Forsøker /roller-endepunktet først.
        """
        orgnr = enhet.get("organisasjonsnummer", "")
        url = f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # Roller kan ligge under ulike strukturer
                roller = data if isinstance(data, list) else data.get("rollegrupper", [])

                for gruppe in roller:
                    type_data = gruppe.get("type", {})
                    rolle_kode = type_data.get("kode", "")
                    rolle_beskrivelse = type_data.get("beskrivelse", "").lower()

                    if rolle_kode == "DAGL" or "daglig leder" in rolle_beskrivelse:
                        roller_liste = gruppe.get("roller", [])
                        if roller_liste:
                            person = roller_liste[0].get("person", {})
                            navn_data = person.get("navn", {})
                            fornavn = navn_data.get("fornavn", "")
                            etternavn = navn_data.get("etternavn", "")
                            if fornavn or etternavn:
                                return f"{fornavn} {etternavn}".strip().title()

            time.sleep(REQUEST_DELAY)
        except requests.exceptions.RequestException as e:
            logger.debug(f"Kunne ikke hente roller for {orgnr}: {e}")

        return None

    def _navn_matcher_domene(self, navn: str, url: str) -> bool:
        """Sjekk at minst ett nøkkelord fra selskapsnavnet finnes i domenet."""
        domene = urlparse(url).netloc.lower().replace("www.", "")
        nøkkelord = [
            w.lower() for w in re.split(r'[\s\-]+', navn)
            if len(w) >= 4 and w.lower() not in _STOPORD
        ]
        return any(kw in domene for kw in nøkkelord)

    def _rotdomene(self, url: str) -> str:
        """Strip URL til rotdomene (scheme + netloc)."""
        if not url.startswith("http"):
            url = f"https://{url}"
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    def hent_nettside(self, enhet: dict) -> tuple[Optional[str], str]:
        """
        Hent nettside fra Brreg, med DuckDuckGo som fallback.
        Returnerer (url, kilde) der kilde er 'Brreg' eller 'DDG'.
        """
        hjemmeside = enhet.get("hjemmeside")
        if hjemmeside:
            return self._rotdomene(hjemmeside), "Brreg"

        navn = enhet.get("navn", "")
        if not navn:
            return None, ""

        try:
            for lib in ("ddgs", "primp", "httpx"):
                logging.getLogger(lib).setLevel(logging.WARNING)
            with DDGS() as ddgs:
                resultater = ddgs.text(navn, max_results=5)
                for r in resultater:
                    url = r.get("href", "")
                    if url and not any(d in url for d in _UTELAT_DOMENER):
                        rot = self._rotdomene(url)
                        if self._navn_matcher_domene(navn, rot):
                            logger.info(f"    DDG-nettside: {navn} → {rot}")
                            return rot, "DDG"
        except Exception as e:
            logger.debug(f"    DuckDuckGo-søk feilet for {navn}: {e}")

        return None, ""

    def hent_kontaktinfo_fra_nettside(self, url: str) -> dict:
        """
        Forsøk å hente e-post og telefon fra selskapets nettside.
        Sjekker hovedside og vanlige kontaktsider.
        """
        kontakt = {"epost": None, "telefon": None}

        if not url:
            return kontakt

        sider_å_sjekke = [
            url,
            f"{url.rstrip('/')}/kontakt",
            f"{url.rstrip('/')}/contact",
            f"{url.rstrip('/')}/om-oss",
            f"{url.rstrip('/')}/about",
        ]

        for side_url in sider_å_sjekke:
            try:
                response = self.session.get(side_url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    tekst = response.text

                    # Finn e-postadresser
                    if not kontakt["epost"]:
                        epost_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                        eposter = re.findall(epost_pattern, tekst)
                        # Filtrer bort vanlige irrelevante e-poster
                        relevante = [
                            e for e in eposter
                            if not any(x in e.lower() for x in [
                                "example.com", "wixpress", "wordpress",
                                "sentry.io", "schema.org", ".png", ".jpg",
                                "noreply", "no-reply"
                            ])
                        ]
                        if relevante:
                            # Prioriter post@, info@, kontakt@, hei@
                            for prefix in ["post@", "info@", "kontakt@", "hei@", "hello@"]:
                                for e in relevante:
                                    if e.lower().startswith(prefix):
                                        kontakt["epost"] = e
                                        break
                                if kontakt["epost"]:
                                    break
                            if not kontakt["epost"]:
                                kontakt["epost"] = relevante[0]

                    # Finn telefonnummer (norsk format)
                    if not kontakt["telefon"]:
                        tlf_patterns = [
                            r'(?:tlf|tel|telefon|phone)[:\s.]*(\+?47[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2})',
                            r'(\+47[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2})',
                            r'(?<!\d)(\d{2}[\s.-]\d{2}[\s.-]\d{2}[\s.-]\d{2})(?!\d)',
                            r'(?<!\d)(\d{3}[\s.-]\d{2}[\s.-]\d{3})(?!\d)',
                            r'(?<!\d)(\d{8})(?!\d)',
                        ]
                        for pattern in tlf_patterns:
                            treff = re.findall(pattern, tekst, re.IGNORECASE)
                            if treff:
                                # Rens nummeret
                                nummer = re.sub(r'[\s.-]', '', treff[0])
                                if len(nummer) >= 8:
                                    kontakt["telefon"] = nummer
                                    break

                time.sleep(REQUEST_DELAY * 0.5)

                # Stopp hvis vi har begge
                if kontakt["epost"] and kontakt["telefon"]:
                    break

            except requests.exceptions.RequestException:
                continue

        return kontakt

    def berik_enhet(self, enhet: dict) -> dict:
        """
        Berik én enhet med all tilgjengelig kontaktinformasjon.

        Returns:
            Dict med berikede data klar for output.
        """
        orgnr = enhet.get("organisasjonsnummer", "")
        navn = enhet.get("navn", "")

        logger.info(f"  Beriker: {navn} ({orgnr})")

        # Grunndata fra Enhetsregisteret
        adresse_data = enhet.get("forretningsadresse", {}) or enhet.get("postadresse", {})
        adresse_deler = adresse_data.get("adresse", [])
        adresse = ", ".join(adresse_deler) if adresse_deler else ""
        postnr = adresse_data.get("postnummer", "")
        poststed = adresse_data.get("poststed", "")
        kommnr = adresse_data.get("kommunenummer", "")
        fylke = FYLKER.get(kommnr[:2], "") if kommnr else ""
        naeringskode = enhet.get("naeringskode1", {})

        nettside, nettside_kilde = self.hent_nettside(enhet)
        epost_brreg = enhet.get("epostadresse")
        telefon_brreg = enhet.get("telefon")

        resultat = {
            "organisasjonsnummer": orgnr,
            "navn": navn,
            "organisasjonsform": enhet.get("organisasjonsform", {}).get("kode", ""),
            "naeringskode": naeringskode.get("kode", ""),
            "naeringsbeskrivelse": naeringskode.get("beskrivelse", ""),
            "antall_ansatte": enhet.get("antallAnsatte", 0),
            "stiftelsesdato": enhet.get("stiftelsesdato", ""),
            "adresse": adresse,
            "postnummer": postnr,
            "poststed": poststed,
            "fylke": fylke,
            "nettside": nettside,
            "nettside_kilde": nettside_kilde,
            "daglig_leder": None,
            "epost": epost_brreg,
            "telefon": telefon_brreg,
        }

        # Hent daglig leder
        resultat["daglig_leder"] = self.hent_daglig_leder(enhet)

        # Hent regnskapstall
        regnskap = self.hent_regnskap(orgnr)
        resultat.update(regnskap)

        # Hent kontaktinfo fra nettside kun hvis Brreg mangler data
        if nettside and (not resultat["epost"] or not resultat["telefon"]):
            kontakt = self.hent_kontaktinfo_fra_nettside(nettside)
            if not resultat["epost"]:
                resultat["epost"] = kontakt.get("epost")
            if not resultat["telefon"]:
                resultat["telefon"] = kontakt.get("telefon")

        return resultat

    def berik_alle(self, enheter: list[dict]) -> list[dict]:
        """Berik en liste med enheter."""
        berikede = []
        total = len(enheter)

        for i, enhet in enumerate(enheter, 1):
            logger.info(f"Beriker {i}/{total}...")
            try:
                beriket = self.berik_enhet(enhet)
                berikede.append(beriket)
            except Exception as e:
                logger.error(f"Feil ved berikelse av {enhet.get('navn', '?')}: {e}")
                # Legg til grunndata selv om berikelse feilet
                berikede.append({
                    "organisasjonsnummer": enhet.get("organisasjonsnummer", ""),
                    "navn": enhet.get("navn", ""),
                    "feil": str(e),
                })

        return berikede
