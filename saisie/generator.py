"""Construit la note de frais d'un mois à partir de config.yaml + mois/AAAA-MM.yaml."""
from __future__ import annotations
import calendar
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

from . import calendrier, catalogue

D = lambda x: Decimal(str(x))
r2 = lambda x: D(x).quantize(Decimal("0.01"), ROUND_HALF_UP)


def charger_yaml(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _date_du_mois(valeur, annee, mois) -> dt.date:
    if isinstance(valeur, dt.date):
        return valeur
    if isinstance(valeur, int) or str(valeur).isdigit():
        return dt.date(annee, mois, int(valeur))
    return dt.date.fromisoformat(str(valeur))


def _charges_mixtes(cfg: dict, saisie: dict, fin_mois: dt.date) -> list[dict]:
    fusion = {k.upper(): dict(v) for k, v in (cfg.get("charges_mixtes_par_defaut") or {}).items()}
    for nom, val in (saisie.get("charges_mixtes") or {}).items():
        cle = nom.upper()
        # 0 = pas de charge ce mois-ci ; {taux: 50} seul garde le montant habituel
        if val in (0, None) or (isinstance(val, dict) and "montant" in val and val["montant"] in (0, None)):
            fusion.pop(cle, None)
            continue
        base = fusion.get(cle, {})
        if isinstance(val, dict):
            base.update(val)
        else:
            base["montant"] = val
        if "montant" not in base:
            raise ValueError(f"Charge mixte « {nom} » : montant manquant (absente de la config)")
        fusion[cle] = base

    lignes = []
    for nom, v in fusion.items():
        nom_crm, (type_id, taux_defaut) = catalogue.chercher(catalogue.CHARGES_MIXTES, nom, "Type de charge mixte")
        taux = D(v.get("taux", taux_defaut))
        brut = r2(v["montant"])
        lignes.append({
            "type": nom_crm, "type_id": type_id, "libelle": v.get("libelle", nom_crm),
            "montant_brut": brut, "taux": taux, "montant_charge": r2(brut * taux / 100),
            "date": fin_mois,
        })
    return lignes


def _depenses(saisie: dict, annee: int, mois: int) -> list[dict]:
    lignes = []
    for i, d in enumerate(saisie.get("depenses") or [], 1):
        try:
            nom_crm, (type_id, tva_defaut) = catalogue.chercher(catalogue.DEPENSES, d["type"], "Type de dépense")
            tva = D(d.get("tva", tva_defaut if tva_defaut is not None else 0))
            ttc = r2(d["ttc"])
            ht = r2(ttc / (1 + tva / 100))
            compte = str(d.get("compte", "personnel")).lower()
            if compte not in catalogue.COMPTES_PAIEMENT:
                raise ValueError("compte doit valoir « personnel » ou « pro »")
            date = _date_du_mois(d["date"], annee, mois)
            if (date.year, date.month) != (annee, mois):
                raise ValueError(f"date {date} hors du mois")
        except KeyError as e:
            raise ValueError(f"Dépense n°{i} : champ manquant {e}") from None
        except ValueError as e:
            raise ValueError(f"Dépense n°{i} : {e}") from None
        lignes.append({
            "type": nom_crm, "type_id": type_id, "libelle": d.get("libelle", nom_crm),
            "date": date, "ttc": ttc, "tva_taux": tva, "tva": ttc - ht, "ht": ht,
            "compte": compte, "compte_id": catalogue.COMPTES_PAIEMENT[compte],
        })
    return sorted(lignes, key=lambda x: x["date"])


def generer(fichier_mois, config_path="config.yaml") -> dict:
    cfg = charger_yaml(config_path)
    saisie = charger_yaml(fichier_mois)

    mois_txt = str(saisie.get("mois") or Path(fichier_mois).stem)
    annee, m = map(int, mois_txt.split("-"))
    nb_jours = calendar.monthrange(annee, m)[1]
    fin_mois = dt.date(annee, m, nb_jours)
    feries = calendrier.feries(annee)

    if "jours_travailles" not in saisie:
        raise ValueError(f"{fichier_mois} : « jours_travailles » est obligatoire")
    travailles = calendrier.parser(saisie["jours_travailles"])
    invalides = [j for j in travailles if not 1 <= j <= nb_jours]
    if invalides:
        raise ValueError(f"Jours invalides pour {mois_txt} : {invalides}")

    alertes = []
    we = [j for j in travailles if dt.date(annee, m, j).weekday() >= 5]
    if we:
        alertes.append(f"Jours de week-end déclarés travaillés : {we}")
    fr = [f"{j} ({feries[dt.date(annee, m, j)]})" for j in travailles if dt.date(annee, m, j) in feries]
    if fr:
        alertes.append(f"Jours fériés déclarés travaillés : {', '.join(fr)}")

    # --- Facture
    f = cfg["facture"]
    ht = r2(D(f["tjm_ht"]) * len(travailles))
    tva = r2(ht * D(f["tva"]) / 100)
    facture = {"client": f["client_nom"], "date": fin_mois, "jours": len(travailles),
               "tjm_ht": D(f["tjm_ht"]), "taux_tva": D(f["tva"]),
               "ht": ht, "tva": tva, "ttc": ht + tva}

    # --- Charges
    charges = _charges_mixtes(cfg, saisie, fin_mois)
    depenses = _depenses(saisie, annee, m)

    # --- Kilométrique : une ligne par jour du mois, comme dans le CRM
    k = cfg["kilometrique"]
    lignes_km = []
    for j in range(1, nb_jours + 1):
        date = dt.date(annee, m, j)
        on = j in travailles
        lignes_km.append({"date": date, "trajet": k["trajet"] if on else "",
                          "client": k["client"] if on else "",
                          "distance": k["distance_km"] if on else 0,
                          "week_end": date.weekday() >= 5, "ferie": date in feries})
    total_km = sum(l["distance"] for l in lignes_km)
    indemnite = r2(D(total_km) * D(k["bareme_coef"]) + D(k["bareme_fixe_annuel"]) / 12) if total_km else Decimal("0.00")

    total_charges = sum((c["montant_charge"] for c in charges), Decimal("0"))
    depenses_perso = sum((d["ttc"] for d in depenses if d["compte"] == "personnel"), Decimal("0"))

    return {
        "mois": mois_txt, "debut": dt.date(annee, m, 1), "fin": fin_mois,
        "jours_travailles": travailles, "alertes": alertes,
        "facture": facture,
        "charges_mixtes": charges, "total_charges_mixtes": total_charges,
        "depenses": depenses,
        "kilometrique": {"vehicule": k["vehicule"], "puissance": k["puissance"],
                         "lignes": lignes_km, "total_km": total_km, "indemnite_estimee": indemnite},
        "total_a_rembourser": total_charges + indemnite + depenses_perso,
    }


def afficher(n: dict):
    eur = lambda x: f"{x:>10,.2f} €".replace(",", " ")
    f = n["facture"]
    print(f"\n══════════ Note de frais {n['mois']} ══════════")
    for a in n["alertes"]:
        print(f"⚠️  {a}")
    print(f"\nJours travaillés ({f['jours']}) : {calendrier.compacter(n['jours_travailles'])}")
    print(f"\nFACTURE  {f['client']} — {f['jours']} j × {f['tjm_ht']} €")
    print(f"  HT {eur(f['ht'])}   TVA {eur(f['tva'])}   TTC {eur(f['ttc'])}")
    print("\nCHARGES MIXTES")
    for c in n["charges_mixtes"]:
        print(f"  {c['type']:<30} {eur(c['montant_brut'])} × {c['taux']:>3}% = {eur(c['montant_charge'])}")
    print(f"  {'Total':<30} {'':>12}         {eur(n['total_charges_mixtes'])}")
    if n["depenses"]:
        print("\nDÉPENSES")
        for d in n["depenses"]:
            print(f"  {d['date']:%d/%m} {d['type']:<26} {d['libelle'][:22]:<22} "
                  f"TTC {eur(d['ttc'])} (TVA {d['tva_taux']}%) [{d['compte']}]")
    k = n["kilometrique"]
    print(f"\nKILOMÉTRIQUE  {k['total_km']} km → {eur(k['indemnite_estimee'])} (estimation)")
    print(f"\nTOTAL À REMBOURSER   {eur(n['total_a_rembourser'])}\n")
