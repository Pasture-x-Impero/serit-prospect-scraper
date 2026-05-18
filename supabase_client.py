"""
Supabase-integrasjon via REST API
==================================
Bruker requests direkte mot PostgREST-APIet — ingen supabase-pakke trengs.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_MANUELLE_FELTER = {"mobil_daglig_leder", "notat"}


class SupabaseClient:
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.key = os.environ.get("SUPABASE_KEY", "")
        self.enabled = bool(self.url and self.key)
        if not self.enabled:
            logger.warning("Supabase ikke konfigurert — hopper over databaseskriving")

    @property
    def _headers(self) -> dict:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def hent_manuelt_ekskluderte(self) -> set:
        """Hent organisasjonsnumre som er manuelt ekskludert i Lovable."""
        if not self.enabled:
            return set()
        try:
            r = requests.get(
                f"{self.url}/rest/v1/manuelt_ekskluderte?select=organisasjonsnummer",
                headers=self._headers,
                timeout=15,
            )
            if r.status_code == 200:
                return {row["organisasjonsnummer"] for row in r.json()}
            logger.warning(f"Kunne ikke hente manuelt_ekskluderte: {r.status_code} {r.text}")
        except Exception as e:
            logger.warning(f"Kunne ikke hente manuelt_ekskluderte: {e}")
        return set()

    def skriv_kandidater(self, data: list[dict], kjort_dato: str) -> bool:
        """
        Upsert kandidater. Manuelle felter (mobil_daglig_leder, notat)
        skrives ikke — eksisterende verdier bevares på re-kjøring.
        """
        if not self.enabled or not data:
            return False

        rader = [
            {k: v for k, v in rad.items() if k not in _MANUELLE_FELTER}
            | {"kjort_dato": kjort_dato}
            for rad in data
        ]

        logger.info(f"Skriver {len(rader)} kandidater til Supabase...")
        return self._upsert_batch("kandidater", rader, pk="organisasjonsnummer")

    def skriv_ekskluderte(self, data: list[dict], kjort_dato: str) -> bool:
        """Erstatt alle ekskluderte med fersk snapshot fra siste kjøring."""
        if not self.enabled:
            return False

        self._slett_alle("ekskluderte")

        if not data:
            return True

        rader = [
            {k: v for k, v in rad.items() if v is not None}
            | {"kjort_dato": kjort_dato}
            for rad in data
        ]

        logger.info(f"Skriver {len(rader)} ekskluderte til Supabase...")
        return self._upsert_batch("ekskluderte", rader, pk="organisasjonsnummer")

    def _upsert_batch(self, table: str, data: list[dict], pk: str, batch_size: int = 500) -> bool:
        headers = {**self._headers, "Prefer": f"resolution=merge-duplicates,return=minimal"}
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            try:
                r = requests.post(
                    f"{self.url}/rest/v1/{table}",
                    headers=headers,
                    json=batch,
                    timeout=60,
                )
                r.raise_for_status()
            except Exception as e:
                logger.error(f"Supabase upsert feilet ({table}, batch {i}): {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Respons: {e.response.text}")
                return False
        return True

    def _slett_alle(self, table: str) -> bool:
        try:
            r = requests.delete(
                f"{self.url}/rest/v1/{table}?organisasjonsnummer=not.is.null",
                headers=self._headers,
                timeout=30,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Supabase slett feilet ({table}): {e}")
            return False
