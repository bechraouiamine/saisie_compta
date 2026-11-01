from __future__ import annotations
import datetime as dt
import unittest

from saisie import calendrier


class TestCalendrier(unittest.TestCase):
    def test_paques(self):
        self.assertEqual(calendrier._paques(2026), dt.date(2026, 4, 5))
        self.assertEqual(calendrier._paques(2027), dt.date(2027, 3, 28))

    def test_feries_mobiles(self):
        f = calendrier.feries(2026)
        self.assertEqual(f[dt.date(2026, 4, 6)], "Lundi de Pâques")
        self.assertEqual(f[dt.date(2026, 5, 14)], "Ascension")
        self.assertEqual(f[dt.date(2026, 5, 25)], "Lundi de Pentecôte")

    def test_jours_ouvres_novembre_2026(self):
        # 1er (Toussaint, dimanche) et 11 (Armistice) exclus
        jours = calendrier.jours_ouvres(2026, 11)
        self.assertEqual(calendrier.compacter(jours), "2-6,9-10,12-13,16-20,23-27,30")

    def test_parser(self):
        self.assertEqual(calendrier.parser("1,2, 5-7"), [1, 2, 5, 6, 7])
        self.assertEqual(calendrier.parser([3, 1, 3]), [1, 3])
        self.assertEqual(calendrier.parser(""), [])

    def test_compacter(self):
        self.assertEqual(calendrier.compacter([]), "")
        self.assertEqual(calendrier.compacter([4]), "4")
        self.assertEqual(calendrier.compacter([1, 2, 3, 5, 7, 8]), "1-3,5,7-8")

    def test_aller_retour(self):
        spec = "1-2,5-9,12-16,19-23,26-30"
        self.assertEqual(calendrier.compacter(calendrier.parser(spec)), spec)


if __name__ == "__main__":
    unittest.main()
