"""Compare la note générée localement avec la note enregistrée dans le CRM (lecture seule)."""
from __future__ import annotations
from decimal import Decimal

TOL = Decimal("0.01")


def _d(x) -> Decimal:
    return Decimal(str(x or 0))


def comparer(note: dict, crm: dict) -> list[tuple[str, str, str, bool]]:
    """Retourne des lignes (rubrique, local, CRM, ok)."""
    res = []
    eq = lambda a, b: abs(_d(a) - _d(b)) <= TOL
    add = lambda nom, a, b, ok=None: res.append((nom, str(a), str(b), eq(a, b) if ok is None else ok))

    f = note["facture"]
    add("Ventes HT", f["ht"], crm.get("SalesTotalHt"))
    add("Ventes TTC", f["ttc"], crm.get("SalesTotalTtc"))

    crm_mix = {c["TypeName"].upper(): c for c in crm.get("ExpenseNoteMixedCharge") or []}
    loc_mix = {c["type"].upper(): c for c in note["charges_mixtes"]}
    for nom in sorted(set(crm_mix) | set(loc_mix)):
        l, c = loc_mix.get(nom), crm_mix.get(nom)
        if l and c:
            ok = eq(l["montant_brut"], c["BrutAmount"]) and eq(l["taux"], c["Rate"])
            res.append((f"Charge {nom}", f"{l['montant_brut']} × {l['taux']}%",
                        f"{_d(c['BrutAmount'])} × {_d(c['Rate'])}%", ok))
        else:
            res.append((f"Charge {nom}", "présente" if l else "absente",
                        "présente" if c else "absente", False))
    add("Total charges mixtes", note["total_charges_mixtes"], crm.get("MixedChargeTotal"))

    loc_dep = sum((d["ttc"] for d in note["depenses"]), Decimal("0"))
    add("Dépenses TTC", loc_dep, crm.get("ExploitationChargeTotalTtc"))

    km = note["kilometrique"]
    crm_km = {}
    for m in crm.get("ExpenseNoteMileageAllowance") or []:
        for l in m.get("ExpenseNoteMileageAllowanceDetail") or []:
            crm_km[str(l["Date"])[:10]] = _d(l["Distance"])
    ecarts = [f"{l['date']:%d/%m}" for l in km["lignes"]
              if crm_km.get(l["date"].isoformat(), Decimal(0)) != _d(l["distance"])]
    res.append(("Kilomètres", f"{km['total_km']} km", f"{sum(crm_km.values())} km",
                not ecarts))
    if ecarts:
        res.append(("  jours différents", ", ".join(ecarts), "", False))
    add("Indemnité kilométrique", km["indemnite_estimee"], crm.get("MileageAllowanceTotal"))
    add("TOTAL à rembourser", note["total_a_rembourser"], crm.get("Total"))
    return res


def afficher(res):
    print(f"\n{'Rubrique':<32} {'Calcul local':>22} {'CRM':>22}")
    print("─" * 82)
    for nom, a, b, ok in res:
        print(f"{nom:<32} {a:>22} {b:>22}  {'✅' if ok else '❌'}")
    nb = sum(not r[3] for r in res)
    print("\n" + ("✅ Tout correspond." if nb == 0 else f"❌ {nb} écart(s) à vérifier."))
    return nb == 0
