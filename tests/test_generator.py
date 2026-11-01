"""Calcul de la note sur une configuration fictive (tests/donnees/config_test.yaml)."""
from __future__ import annotations
import datetime as dt
import tempfile
import textwrap
import unittest
from decimal import Decimal
from pathlib import Path

from saisie import generator

CONFIG = Path(__file__).parent / "donnees" / "config_test.yaml"
OCTOBRE = '"1,2,5-9,12-16,19-23,26-30"'   # 22 jours


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def generer(self, contenu: str, nom: str = "2026-10.yaml") -> dict:
        chemin = Path(self._tmp.name) / nom
        chemin.write_text(textwrap.dedent(contenu), encoding="utf-8")
        return generator.generer(chemin, CONFIG)

    @staticmethod
    def charges(note: dict) -> dict:
        return {c["type"]: c for c in note["charges_mixtes"]}


class TestReference(Base):
    """Mois type : 22 jours, charges par défaut, aucune dépense."""

    def setUp(self):
        super().setUp()
        self.note = self.generer(f"""
            mois: "2026-10"
            jours_travailles: {OCTOBRE}
        """)

    def test_facture(self):
        f = self.note["facture"]
        self.assertEqual(f["jours"], 22)
        self.assertEqual(f["ht"], Decimal("11000.00"))
        self.assertEqual(f["tva"], Decimal("2200.00"))
        self.assertEqual(f["ttc"], Decimal("13200.00"))
        self.assertEqual(f["date"], dt.date(2026, 10, 31))

    def test_charges_mixtes(self):
        c = self.charges(self.note)
        self.assertEqual(c["LOYERS"]["montant_charge"], Decimal("160.00"))
        self.assertEqual(c["INTERNET"]["montant_charge"], Decimal("22.49"))   # 22,4925
        self.assertEqual(c["EDF/GDF"]["montant_charge"], Decimal("12.00"))
        self.assertEqual(self.note["total_charges_mixtes"], Decimal("194.49"))

    def test_kilometrique(self):
        km = self.note["kilometrique"]
        self.assertEqual(len(km["lignes"]), 31)                   # une ligne par jour du mois
        self.assertEqual(km["total_km"], 880)
        self.assertEqual(km["indemnite_estimee"], Decimal("472.97"))  # 880 × 0,394 + 1515/12

    def test_total(self):
        self.assertEqual(self.note["total_a_rembourser"], Decimal("667.46"))
        self.assertEqual(self.note["alertes"], [])


class TestChargesMixtes(Base):
    def generer_charges(self, bloc: str) -> dict:
        return self.charges(self.generer(f"""
            mois: "2026-10"
            jours_travailles: "1"
            charges_mixtes:
            {textwrap.indent(textwrap.dedent(bloc), "  ")}
        """))

    def test_montant_seul_garde_le_taux(self):
        c = self.generer_charges("EDF/GDF: 70")["EDF/GDF"]
        self.assertEqual((c["montant_brut"], c["taux"]), (Decimal("70.00"), Decimal("20")))

    def test_taux_seul_garde_le_montant(self):
        c = self.generer_charges("INTERNET: { taux: 50 }")["INTERNET"]
        self.assertEqual((c["montant_brut"], c["taux"]), (Decimal("29.99"), Decimal("50")))

    def test_zero_supprime(self):
        c = self.generer_charges("INTERNET: 0")
        self.assertNotIn("INTERNET", c)
        c = self.generer_charges("INTERNET: { montant: 0 }")
        self.assertNotIn("INTERNET", c)

    def test_nouveau_type_avec_taux_du_catalogue(self):
        c = self.generer_charges("telephone: 19.99")["TELEPHONE"]
        self.assertEqual(c["taux"], Decimal("75"))

    def test_nouveau_type_sans_montant(self):
        with self.assertRaises(ValueError):
            self.generer_charges("TELEPHONE: { taux: 50 }")

    def test_type_inconnu(self):
        with self.assertRaises(ValueError):
            self.generer_charges("NETFLIX: 12")


class TestDepenses(Base):
    def test_depenses(self):
        note = self.generer(f"""
            mois: "2026-10"
            jours_travailles: {OCTOBRE}
            depenses:
              - {{ type: PARKING, date: 20, ttc: 12, compte: pro }}
              - {{ type: repas gerant seul, date: 2026-10-14, ttc: 18.50 }}
        """)
        repas, parking = note["depenses"]               # triées par date
        self.assertEqual(repas["type"], "REPAS GERANT SEUL")
        self.assertEqual(repas["compte"], "personnel")  # valeur par défaut
        self.assertEqual(repas["ht"], Decimal("16.82"))  # 18,50 / 1,10
        self.assertEqual(parking["tva_taux"], Decimal("20"))
        # seule la dépense payée sur le compte personnel est remboursée
        self.assertEqual(note["total_a_rembourser"], Decimal("667.46") + Decimal("18.50"))

    def test_erreurs(self):
        for ligne in ("{ type: PARKING, date: 3 }",                            # ttc manquant
                      "{ type: PARKING, date: 2026-11-03, ttc: 5 }",           # hors du mois
                      "{ type: PARKING, date: 3, ttc: 5, compte: autre }"):
            with self.subTest(ligne=ligne), self.assertRaises(ValueError):
                self.generer(f"""
                    mois: "2026-10"
                    jours_travailles: "1"
                    depenses:
                      - {ligne}
                """)


class TestValidation(Base):
    def test_alertes_week_end_et_ferie(self):
        note = self.generer('mois: "2026-11"\njours_travailles: "1,7,11"', "2026-11.yaml")
        self.assertEqual(len(note["alertes"]), 2)

    def test_jour_invalide(self):
        with self.assertRaises(ValueError):
            self.generer('mois: "2026-11"\njours_travailles: "31"', "2026-11.yaml")

    def test_jours_obligatoires(self):
        with self.assertRaises(ValueError):
            self.generer('mois: "2026-11"', "2026-11.yaml")

    def test_mois_deduit_du_nom(self):
        note = self.generer('jours_travailles: "2"', "2026-11.yaml")
        self.assertEqual(note["mois"], "2026-11")


if __name__ == "__main__":
    unittest.main()
