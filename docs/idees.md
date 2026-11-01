# Pistes et idées

## Charges annuelles natives du CRM

Le CRM a une notion de charges annuelles / récurrentes (`getAllAnnualCharges`). Les charges mixtes saisies à la main ne semblent pas y être rattachées (`AnnualChargeId: null`). À explorer : laisser le CRM pré-remplir les charges mixtes au lieu de les ajouter une par une.

## Rappel de fin de mois

Une tâche planifiée (launchd sur macOS) pourrait lancer `python main.py nouveau` le dernier jour ouvré du mois et afficher une notification.

## Exposer les fonctions comme tools

Rien n'est implémenté pour l'instant. Trois options :

1. **Serveur MCP local en stdio** (recommandé pour un agent compatible MCP). On expose des outils limités, par exemple `calculer_mois`, `verifier_note`, `lister_brouillons`, `creer_facture_brouillon` et `supprimer_brouillon`, qui réutilisent les fonctions Python existantes sans ouvrir de port réseau. Les écritures gardent une confirmation humaine et des contrôles de statut.
2. **Tâches VS Code** (`.vscode/tasks.json`). C'est simple pour un usage manuel, mais un agent ne les voit pas comme des outils typés.
3. **API HTTP locale**. Cette option ajoute un serveur, une surface d'attaque et de l'authentification. À éviter tant qu'un appel local suffit.

Garder séparés les outils de lecture/calcul et ceux d'écriture. N'exposer ni appel HTTP arbitraire ni validation ou envoi tant que les requêtes réelles n'ont pas été capturées. Vérifier aussi que le SDK MCP est compatible avec Python 3.9.

## Divers

- Python 3.9 n'est plus maintenu : passer à une version récente (`brew install python`) quand ce sera pratique.
- `urllib3` v2 avec LibreSSL (Python d'Apple) émet un avertissement, masqué dans `main.py`.
