# Saisie compta — contexte du projet

Les données personnelles (identifiants réels, chiffres de référence, état d'avancement) sont dans `CLAUDE.local.md`, non versionné. **Ne jamais recopier ces données dans un fichier versionné** : le dépôt est public.

## Objectif

Automatiser la saisie mensuelle d'un freelance (SASU) sur l'**Espace PRO Client** de son cabinet comptable, une application **Decisiel**. Chaque fin de mois :

1. **Créer la facture client** (jours travaillés × TJM) dans le CRM, puis la **valider**. Le CRM attribue alors le numéro (FC…) et génère le PDF.
2. La validation **crée la note de frais du mois**, avec la ligne « Vente » rattachée.
3. Ajouter à la note les **charges mixtes** (loyer, internet, EDF…), les **dépenses** (repas, parking…) et les **frais kilométriques** (une ligne par jour du mois).
4. **Envoyer** la note.

Il n'y a pas d'API officielle : on rejoue les appels HTTP de l'interface web relevés dans des captures HAR. Ce qu'on sait de l'API :

@docs/api-decisiel.md

## Contraintes (à respecter)

- **Exécution en local** sur macOS, avec le **Python 3.9.6** d'Apple dans `.venv`. Le code doit rester compatible 3.9 : `from __future__ import annotations` partout, pas de `match`.
- **reCAPTCHA** : on ne le contourne pas. L'utilisateur se connecte lui-même dans la fenêtre Playwright. Le mot de passe n'est **jamais** stocké ni manipulé par le script.
- **Aucun secret ni donnée personnelle dans les fichiers versionnés.** `config.yaml`, `mois/*.yaml`, `CLAUDE.local.md` et `*.har` sont ignorés par git. La session est en cache dans `~/.saisie_compta/session.json` (droits 600).
- **Pas d'écriture sur un endpoint deviné** : chaque écriture doit venir d'un appel vu dans une capture HAR, car il s'agit de la comptabilité réelle.
- **Confirmation interactive** (`[o/N]`) avant chaque écriture. L'envoi final de la note reste manuel tant que le fonctionnement n'a pas été validé sur quelques mois.
- Suppression autorisée **uniquement sur les brouillons** (`Status == "Pending"`).
- Les HAR contiennent le mot de passe en clair : ne jamais l'afficher, analyser avec des scripts qui masquent les valeurs sensibles.

## Structure

```
config.example.yaml   # modèle de config.yaml (IDs CRM, TJM, charges habituelles, trajet)
mois/exemple.yaml     # modèle de saisie mensuelle
main.py               # CLI (argparse) ; --debug global
saisie/
  catalogue.py        # types CRM (charges mixtes, dépenses, comptes, véhicules) -> IDs
  calendrier.py       # jours fériés FR, jours ouvrés, parse/compactage "2-6,9"
  generator.py        # calcul de la note (Decimal, arrondi HALF_UP)
  crm_session.py      # connexion Playwright + cache de session
  crm_api.py          # client requests de l'API Decisiel (stubs ⏳ pour le non capturé)
  verifier.py         # comparaison calcul local / note du CRM (lecture seule)
tests/                # unittest, données fictives dans tests/donnees/
docs/                 # notes d'API, pistes
```

Tests : `.venv/bin/python -m unittest`. Ils ne touchent pas au réseau.

## Règles de calcul

- **Facture** : HT = jours × TJM, TVA 20 %, datée du dernier jour du mois.
- **Charge mixte** : montant retenu = brut × taux / 100. Le CRM stocke la valeur non arrondie, mais les totaux s'affichent arrondis.
- **Kilométrique** : distance configurée par jour travaillé, 0 sinon, avec une ligne pour chaque jour du mois. Barème 7 CV et plus, tranche 5 001 à 20 000 km : `km × 0,394 + 1 515 / 12`. Le CRM fait son propre calcul ; le nôtre n'est qu'une estimation.
- **Total à rembourser** = charges mixtes + indemnité km + dépenses payées sur le compte personnel.
