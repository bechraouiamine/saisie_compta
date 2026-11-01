# saisie_compta

CLI Python pour préparer la saisie comptable mensuelle d'un freelance (SASU) sur l'**Espace PRO Client** d'un cabinet comptable, une application [Decisiel](https://decisiel-crmclient.fr).

À partir d'un petit fichier YAML par mois, l'outil :

- calcule la facture client (jours × TJM), les charges mixtes, les dépenses, les indemnités kilométriques et le total à rembourser ;
- crée la facture **brouillon** dans le CRM, après confirmation ;
- compare le calcul local avec la note de frais enregistrée dans le CRM.

> ⚠️ **Projet non officiel**, sans lien avec Decisiel. Les appels reproduisent ceux de l'interface web, relevés dans le navigateur. Ils peuvent cesser de fonctionner à tout moment. Il s'agit de comptabilité réelle : chaque écriture demande une confirmation.

## Installation

Python 3.9 ou plus récent.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp config.example.yaml config.yaml   # puis renseigner ses propres valeurs
```

`config.yaml` contient les identifiants CRM de la société (`CompanyId`, `ClientId`, `BankAccountId`), le TJM, les charges mixtes habituelles et le trajet domicile–client. Les identifiants se lisent dans l'onglet Network des DevTools en naviguant dans le CRM. Ce fichier n'est pas versionné.

## Utilisation

```bash
python main.py nouveau 2026-11            # crée mois/2026-11.yaml avec les jours ouvrés (hors fériés)
# … modifier le fichier : absences, charges du mois, dépenses
python main.py calcul mois/2026-11.yaml   # calcul hors ligne
python main.py saisir mois/2026-11.yaml   # crée la facture brouillon dans le CRM
# … valider la facture et compléter la note dans le CRM
python main.py verifier mois/2026-11.yaml # compare avec la note du CRM
```

| Commande | Effet | CRM |
|---|---|---|
| `nouveau [AAAA-MM]` | Crée le fichier du mois (mois courant par défaut). Refuse d'écraser un fichier existant, sauf avec `--force`. | — |
| `calcul FICHIER` | Affiche facture, charges, dépenses, kilomètres et total à rembourser. | — |
| `connexion` | Teste la session et résume les notes, factures et brouillons. | lecture |
| `brouillons` | Liste les factures brouillon. | lecture |
| `verifier FICHIER` | Compare le calcul local avec la note du mois, ligne par ligne. | lecture |
| `saisir FICHIER` | Contrôle les doublons (note existante, brouillon en cours), puis crée la facture brouillon après confirmation. Affiche ensuite ce qui reste à saisir à la main. | **écriture** |
| `supprimer ID` | Supprime une facture, uniquement si elle est encore au statut brouillon. | **écriture** |
| `deconnexion` | Efface la session en cache local. | — |

`--debug`, placé n'importe où dans la commande, trace les requêtes API vues pendant la connexion.

## Fichier du mois

Voir [`mois/exemple.yaml`](mois/exemple.yaml) :

```yaml
mois: "2026-11"
jours_travailles: "2-6,9-10,12-13,16-20,23-27,30"   # ou liste [2, 3, 4]
charges_mixtes:                 # seulement les écarts par rapport à config.yaml
  EDF/GDF: 72.40                # montant seul -> taux habituel
  INTERNET: { taux: 50 }        # taux seul -> montant habituel
  TELEPHONE: { montant: 19.99, taux: 75 }
  LOYERS: 0                     # 0 -> pas de charge ce mois-ci
depenses:
  - { type: REPAS GERANT SEUL, date: 14, ttc: 18.50, libelle: "Déjeuner", compte: personnel, tva: 10 }
```

- Les types de charges et de dépenses doivent exister dans [`saisie/catalogue.py`](saisie/catalogue.py). La casse n'a pas d'importance.
- `compte` : `personnel` (remboursé, compté dans le total ; c'est la valeur par défaut) ou `pro`.
- `tva` : facultatif. Sinon, le taux par défaut du type est utilisé.
- `date` : numéro du jour ou date ISO.

Le kilométrage compte la distance configurée pour chaque jour travaillé, avec le barème fiscal 7 CV et plus, tranche 5 001 à 20 000 km. Ce n'est qu'une estimation : le CRM fait son propre calcul.

## Connexion et sécurité

- La connexion au CRM est protégée par un reCAPTCHA. **L'outil ne le contourne pas** : à la première commande CRM, ou quand la session a expiré, une fenêtre Chrome ou Chromium s'ouvre et l'utilisateur s'y connecte lui-même.
- Le mot de passe n'est jamais lu ni stocké. Seuls le jeton XSRF et les cookies sont gardés dans `~/.saisie_compta/session.json` (droits 600). `deconnexion` efface ce fichier.
- Ne jamais partager ni versionner une capture HAR brute : elle contient le mot de passe en clair.
- Aucune écriture ne repose sur un endpoint deviné : chacune reproduit une requête réellement observée.

## État

| Étape | État |
|---|---|
| Calcul de la note | ✅ vérifié à l'euro près sur une note réelle |
| Connexion, lecture des notes et factures | ✅ |
| Création / suppression de facture brouillon | ✅ |
| Validation de la facture, ajout des charges, dépenses et kilomètres, envoi de la note | ⏳ en attente de capture des requêtes ; à faire dans l'interface du CRM |

Les endpoints connus sont documentés dans [`docs/api-decisiel.md`](docs/api-decisiel.md), les pistes dans [`docs/idees.md`](docs/idees.md).

## Développement

```bash
python -m unittest          # tests hors ligne, sur des données fictives (tests/donnees/)
```

Le code reste compatible Python 3.9 (`from __future__ import annotations`, pas de `match`).

```
main.py               CLI
saisie/
  calendrier.py       jours fériés, jours ouvrés, format "2-6,9"
  catalogue.py        types de charges/dépenses du CRM et leurs IDs
  generator.py        calcul de la note (Decimal, arrondi au centime)
  verifier.py         comparaison avec la note du CRM
  crm_session.py      connexion via Playwright, cache de session
  crm_api.py          client HTTP de l'API Decisiel
tests/
docs/
```
