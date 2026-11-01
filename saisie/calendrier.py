"""Jours fériés français et jours ouvrés d'un mois."""
from __future__ import annotations
import calendar
import datetime as dt


def _paques(annee: int) -> dt.date:
    a, b, c = annee % 19, annee // 100, annee % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(annee, mois, jour)


def feries(annee: int) -> dict[dt.date, str]:
    p = _paques(annee)
    j = lambda m, d: dt.date(annee, m, d)
    return {
        j(1, 1): "Jour de l'an", p + dt.timedelta(1): "Lundi de Pâques",
        j(5, 1): "Fête du travail", j(5, 8): "Victoire 1945",
        p + dt.timedelta(39): "Ascension", p + dt.timedelta(50): "Lundi de Pentecôte",
        j(7, 14): "Fête nationale", j(8, 15): "Assomption", j(11, 1): "Toussaint",
        j(11, 11): "Armistice", j(12, 25): "Noël",
    }


def jours_ouvres(annee: int, mois: int) -> list[int]:
    f = feries(annee)
    n = calendar.monthrange(annee, mois)[1]
    return [d for d in range(1, n + 1)
            if dt.date(annee, mois, d).weekday() < 5 and dt.date(annee, mois, d) not in f]


def compacter(jours: list[int]) -> str:
    """[2,3,4,5,6,9] -> '2-6,9'"""
    plages, debut, prec = [], None, None
    for d in jours:
        if debut is None:
            debut = prec = d
        elif d == prec + 1:
            prec = d
        else:
            plages.append((debut, prec)); debut = prec = d
    if debut is not None:
        plages.append((debut, prec))
    return ",".join(f"{a}" if a == b else f"{a}-{b}" for a, b in plages)


def parser(spec) -> list[int]:
    """'1,2,5-9' -> [1,2,5,6,7,8,9] ; accepte aussi une liste d'entiers."""
    if isinstance(spec, list):
        return sorted(set(int(x) for x in spec))
    jours = set()
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = map(int, part.split("-"))
            jours.update(range(a, b + 1))
        else:
            jours.add(int(part))
    return sorted(jours)
