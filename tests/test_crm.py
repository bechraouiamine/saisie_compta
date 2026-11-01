"""Parties CRM testables sans réseau : payload de facture, vérification, cache de session."""
from __future__ import annotations
import stat
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from saisie import crm_session, generator, verifier
from saisie.crm_api import CrmApi

CONFIG = Path(__file__).parent / "donnees" / "config_test.yaml"


def note_test() -> dict:
    with tempfile.TemporaryDirectory() as d:
        chemin = Path(d) / "2026-10.yaml"
        chemin.write_text('jours_travailles: "1,2,5-9,12-16,19-23,26-30"', encoding="utf-8")
        return generator.generer(chemin, CONFIG)


def note_crm(note: dict) -> dict:
    """Note telle que renvoyée par ExpenseNote/GetById, construite à partir du calcul local."""
    return {
        "SalesTotalHt": float(note["facture"]["ht"]),
        "SalesTotalTtc": float(note["facture"]["ttc"]),
        "ExpenseNoteMixedCharge": [
            {"TypeName": c["type"], "BrutAmount": float(c["montant_brut"]), "Rate": float(c["taux"])}
            for c in note["charges_mixtes"]],
        "MixedChargeTotal": float(note["total_charges_mixtes"]),
        "ExploitationChargeTotalTtc": 0,
        "ExpenseNoteMileageAllowance": [{"ExpenseNoteMileageAllowanceDetail": [
            {"Date": f"{l['date']}T00:00:00", "Distance": l["distance"]}
            for l in note["kilometrique"]["lignes"]]}],
        "MileageAllowanceTotal": float(note["kilometrique"]["indemnite_estimee"]),
        "Total": float(note["total_a_rembourser"]),
    }


class TestPayloadFacture(unittest.TestCase):
    def test_payload(self):
        note = note_test()
        api = CrmApi(generator.charger_yaml(CONFIG))
        p = api.payload_facture(note["facture"])
        self.assertEqual(p["CompanyId"], 12345)
        self.assertEqual(p["ClientId"], 100)
        self.assertEqual(p["IssueDate"], "2026-10-31T00:00:00")
        self.assertEqual(p["DeliveryDate"], p["IssueDate"])
        ligne, = p["Items"]
        self.assertEqual((ligne["Quantity"], ligne["UnitPrice"], ligne["VatPercent"]), (22, 500.0, 20.0))


class TestVerifier(unittest.TestCase):
    def test_identique(self):
        note = note_test()
        self.assertTrue(all(ok for *_, ok in verifier.comparer(note, note_crm(note))))

    def test_ecarts(self):
        note = note_test()
        crm = note_crm(note)
        crm["ExpenseNoteMixedCharge"][0]["Rate"] = 50
        crm["ExpenseNoteMileageAllowance"][0]["ExpenseNoteMileageAllowanceDetail"][0]["Distance"] = 0
        en_echec = {nom for nom, *_, ok in verifier.comparer(note, crm) if not ok}
        self.assertIn("Charge LOYERS", en_echec)
        self.assertIn("Kilomètres", en_echec)
        self.assertIn("  jours différents", en_echec)

    def test_tolerance(self):
        note = note_test()
        crm = note_crm(note)
        crm["MixedChargeTotal"] = float(note["total_charges_mixtes"] + Decimal("0.004"))
        self.assertTrue(all(ok for *_, ok in verifier.comparer(note, crm)))


class TestCacheSession(unittest.TestCase):
    def test_droits_600(self):
        with tempfile.TemporaryDirectory() as d:
            dossier = Path(d) / "cache"
            fichier = dossier / "session.json"
            with mock.patch.object(crm_session, "DOSSIER", dossier), \
                 mock.patch.object(crm_session, "FICHIER", fichier):
                crm_session._ecrire_cache({"xsrf": "jeton", "cookies": []})
                self.assertEqual(stat.S_IMODE(fichier.stat().st_mode), 0o600)
                self.assertEqual(crm_session._lire_cache()["xsrf"], "jeton")
                crm_session.oublier()
                self.assertIsNone(crm_session._lire_cache())


if __name__ == "__main__":
    unittest.main()
