"""Automatisation de la saisie mensuelle sur l'Espace PRO Client (Decisiel).

  python main.py nouveau 2026-11          crée mois/2026-11.yaml pré-rempli
  python main.py calcul  mois/2026-11.yaml  affiche le calcul (hors ligne)
  python main.py verifier mois/2026-10.yaml compare avec la note du CRM (lecture seule)
  python main.py saisir  mois/2026-11.yaml  crée la facture brouillon dans le CRM
  python main.py connexion                 teste la connexion (lecture seule)
  python main.py brouillons                liste les factures brouillon
  python main.py supprimer 12345           supprime un brouillon
  python main.py deconnexion               oublie la session enregistrée
"""
from __future__ import annotations
import argparse
import warnings
import datetime as dt
import sys
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")
DEBUG = "--debug" in sys.argv
if DEBUG:
    sys.argv.remove("--debug")

import yaml  # noqa: E402

from saisie import calendrier, crm_session, generator, verifier  # noqa: E402

ICI = Path(__file__).resolve().parent
CONFIG = ICI / "config.yaml"

MODELE = """\
# Saisie du mois {mois} — modifie puis lance :
#   python main.py calcul mois/{mois}.yaml
mois: "{mois}"

# Jours travaillés sur site (facturés + indemnités km).
# Pré-rempli avec les jours ouvrés hors fériés{feries} : retire tes absences.
# Format : "2-6,9,10" ou liste [2, 3, 4]
jours_travailles: "{jours}"

# Charges mixtes : seulement ce qui CHANGE par rapport à config.yaml.
#   montant seul          -> taux habituel conservé
#   {{montant, taux}}      -> les deux remplacés
#   0                     -> pas de charge ce mois-ci
# Exemples :
#   EDF/GDF: 62.40
#   TELEPHONE: {{ montant: 19.99, taux: 75 }}
charges_mixtes: {{}}

# Dépenses ponctuelles (repas, parking, péage, matériel…).
# compte : personnel (remboursé dans la note) ou pro (payé avec la carte pro)
# tva : facultatif (taux habituel du type sinon)
# Exemple :
#   - {{ type: REPAS GERANT SEUL, date: 14, ttc: 18.50, libelle: "Déjeuner", compte: personnel }}
depenses: []
"""


def verifier_config():
    if not CONFIG.exists():
        sys.exit("❌ config.yaml introuvable : copie config.example.yaml en config.yaml "
                 "et renseigne tes valeurs.")


def charger_config():
    return generator.charger_yaml(CONFIG)


def connecter():
    from saisie.crm_api import CrmApi
    cfg = charger_config()
    api = CrmApi(cfg)
    session = crm_session.obtenir_session(cfg["crm"]["url_app"], api.session_valide, debug=DEBUG)
    api.utiliser_session(session)
    return api


def confirmer(question: str) -> bool:
    return input(f"{question} [o/N] ").strip().lower() in ("o", "oui", "y", "yes")


# ------------------------------------------------------------------- commandes
def cmd_nouveau(a):
    annee, m = map(int, a.mois.split("-"))
    chemin = ICI / "mois" / f"{a.mois}.yaml"
    if chemin.exists() and not a.force:
        sys.exit(f"{chemin.name} existe déjà (ajoute --force pour l'écraser).")
    fer = [f"{d.day} {n}" for d, n in calendrier.feries(annee).items() if d.month == m]
    chemin.parent.mkdir(exist_ok=True)
    chemin.write_text(MODELE.format(
        mois=a.mois, jours=calendrier.compacter(calendrier.jours_ouvres(annee, m)),
        feries=f" ({', '.join(fer)} exclus)" if fer else ""), encoding="utf-8")
    print(f"✅ Créé : {chemin.relative_to(ICI)}")


def cmd_calcul(a):
    generator.afficher(generator.generer(a.fichier, CONFIG))


def cmd_verifier(a):
    note = generator.generer(a.fichier, CONFIG)
    generator.afficher(note)
    api = connecter()
    crm = api.note_du_mois(note["debut"].year, note["debut"].month)
    if not crm:
        sys.exit(f"Aucune note de frais pour {note['mois']} dans le CRM.")
    print(f"Note CRM n°{crm['Id']} — statut : {crm.get('Status', {}).get('Value')}")
    ok = verifier.afficher(verifier.comparer(note, crm))
    sys.exit(0 if ok else 1)


def cmd_saisir(a):
    note = generator.generer(a.fichier, CONFIG)
    generator.afficher(note)
    if note["alertes"] and not confirmer("Il y a des alertes ci-dessus. Continuer ?"):
        return
    api = connecter()
    f = note["facture"]

    existante = api.note_du_mois(note["debut"].year, note["debut"].month)
    if existante:
        print(f"\nℹ️  Une note de frais existe déjà pour {note['mois']} "
              f"(n°{existante['Id']}, {existante.get('Status', {}).get('Value')}) : "
              "la facture a donc déjà été validée. Rien à créer.")
        return

    brouillons = api.brouillons()
    if brouillons:
        print("\n⚠️  Facture(s) brouillon déjà présente(s) dans le CRM :")
        for b in brouillons:
            print(f"   - n°{b['Id']} « {b.get('Code')} » {b.get('TotalHt')} € HT")
        print("   Valide-la ou supprime-la dans le CRM avant de relancer, "
              "pour éviter un doublon.")
        return

    print(f"\nFacture à créer : {f['client']}, {f['jours']} j × {f['tjm_ht']} € = "
          f"{f['ht']} € HT / {f['ttc']} € TTC, datée du {f['date']:%d/%m/%Y}")
    if not confirmer("Créer cette facture (brouillon) dans le CRM ?"):
        return
    inv = api.creer_facture_brouillon(f)
    ok = abs(float(inv["TotalHt"]) - float(f["ht"])) < 0.01
    print(f"{'✅' if ok else '❌'} Brouillon n°{inv['Id']} créé : "
          f"{inv['TotalHt']} € HT / {inv['TotalTtc']} € TTC, statut {inv['Status']}")
    print(f"   (si c'était un test : python main.py supprimer {inv['Id']})")

    print("\n── À faire dans le CRM pour l'instant (automatisé après la prochaine capture) ──")
    print("  1. Valider la facture → la note de frais se crée automatiquement")
    print("  2. Ajouter les charges mixtes :")
    for c in note["charges_mixtes"]:
        print(f"       {c['type']:<28} {c['montant_brut']:>9} €  taux {c['taux']} %")
    for d in note["depenses"]:
        print(f"     Dépense {d['date']:%d/%m} {d['type']} {d['ttc']} € TTC ({d['compte']})")
    print(f"  3. Kilomètres : {note['kilometrique']['total_km']} km, "
          f"jours {calendrier.compacter(note['jours_travailles'])}")
    print("  4. Puis : python main.py verifier", a.fichier)


def cmd_connexion(_):
    api = connecter()
    annee = dt.date.today().year
    notes = api.notes_de_frais(annee)
    print(f"\n✅ API accessible. {len(notes)} note(s) de frais en {annee} :")
    for n in sorted(notes, key=lambda x: x["StartDate"])[-3:]:
        print(f"   {n['StartDate'][:7]}  {n['Total']:>9} €  {n.get('Status', {}).get('Value', '')}")
    publiees = api.factures(2, page_size=3)
    print(f"Dernières factures : {', '.join(f['Code'] + ' (' + str(f['TotalHt']) + ' € HT)' for f in publiees[:3])}")
    print(f"Brouillons en cours : {len(api.brouillons())}")


def cmd_brouillons(_):
    api = connecter()
    b = api.brouillons()
    if not b:
        print("Aucune facture brouillon.")
    for x in b:
        print(f"  n°{x['Id']}  {x.get('Code')}  {x.get('TotalHt')} € HT / {x.get('TotalTtc')} € TTC")


def cmd_supprimer(a):
    api = connecter()
    cible = next((x for x in api.brouillons() if x["Id"] == a.id), None)
    if not cible:
        sys.exit(f"❌ Aucun brouillon n°{a.id} (seuls les brouillons peuvent être supprimés).")
    if confirmer(f"Supprimer le brouillon n°{a.id} ({cible.get('TotalHt')} € HT) ?"):
        api.supprimer_brouillon(a.id)
        print("✅ Supprimé.")


def cmd_deconnexion(_):
    crm_session.oublier()
    print("Session oubliée.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    n = sp.add_parser("nouveau", help="crée le fichier du mois")
    n.add_argument("mois", nargs="?", default=dt.date.today().strftime("%Y-%m"), help="AAAA-MM")
    n.add_argument("--force", action="store_true")
    n.set_defaults(fn=cmd_nouveau)
    for nom, fn, aide in (("calcul", cmd_calcul, "affiche le calcul (hors ligne)"),
                          ("verifier", cmd_verifier, "compare avec le CRM (lecture seule)"),
                          ("saisir", cmd_saisir, "crée la facture dans le CRM")):
        s = sp.add_parser(nom, help=aide)
        s.add_argument("fichier", help="mois/AAAA-MM.yaml")
        s.set_defaults(fn=fn)
    sp.add_parser("connexion", help="teste la connexion").set_defaults(fn=cmd_connexion)
    sp.add_parser("brouillons", help="liste les brouillons").set_defaults(fn=cmd_brouillons)
    s = sp.add_parser("supprimer", help="supprime un brouillon")
    s.add_argument("id", type=int)
    s.set_defaults(fn=cmd_supprimer)
    sp.add_parser("deconnexion", help="oublie la session").set_defaults(fn=cmd_deconnexion)
    a = p.parse_args()
    if a.cmd != "deconnexion":
        verifier_config()
    try:
        a.fn(a)
    except ValueError as e:
        sys.exit(f"❌ {e}")
    except OSError as e:        # fichier du mois introuvable…
        sys.exit(f"❌ {e}")
    except yaml.YAMLError as e:
        sys.exit(f"❌ YAML invalide : {e}")
    except RuntimeError as e:   # ErreurCRM, échec de connexion
        sys.exit(f"❌ {e}")
    except NotImplementedError as e:
        sys.exit(f"⏳ {e}")
    except KeyboardInterrupt:
        sys.exit("\nAnnulé.")


if __name__ == "__main__":
    main()
