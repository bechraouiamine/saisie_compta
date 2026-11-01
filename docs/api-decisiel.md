# API Decisiel — notes de rétro-ingénierie

Il n'existe ni API publique ni import. Tout ce qui suit vient de captures HAR de l'interface web (DevTools → Network). Rien n'est garanti : l'éditeur peut changer ces appels à tout moment.

- Front : `https://decisiel-crmclient.fr`
- API : `https://api.decisiel-crmclient.fr/api/v1.0`

Dans les exemples, `{societe}` désigne le `CompanyId` de la société (`crm.societe_id` dans `config.yaml`).

Légende : ✅ appel capturé et implémenté · 📖 capturé, lecture seule · ⏳ pas encore capturé.

## Authentification ✅

- `POST account/Login` avec `{Email, Password, RememberMe, RecaptchaToken}`. La réponse contient `XsrfToken`, `FullName`, `IsError`, `User{...}`.
- La page est protégée par un reCAPTCHA Google. **On ne le contourne pas** : l'utilisateur se connecte dans une fenêtre Playwright, puis le script récupère le jeton XSRF et les cookies (`saisie/crm_session.py`).
- Les appels suivants envoient l'en-tête `X-XSRF-TOKEN`. L'export HAR de Chrome retire les cookies : on les reprend donc aussi depuis le contexte Playwright.
- En-têtes envoyés par l'interface : `AUDIT-PROGRAM: CrmClient Web`, `ApplicationName: DECISIEL`, `Origin`, `X-Requested-With: XMLHttpRequest`, `Content-Type: application/json`.
- Test de session : `GET societe/GetListSocietesAsKeyValueObjectByPersonEmail` renvoie une liste non vide.

## Factures ✅

| Appel | Rôle |
|---|---|
| `GET ElectronicInvoice?PageNumber=1&PageSize=50&CompanyId={societe}&Status=<s>` | Liste. `Status=2` : publiées ; `Status=Pending` : brouillons (`Code="Provisoire"`). Réponse `{Items:[{Id, Code, Status, TotalHt, TotalTtc,…}], TotalCount}` |
| `GET ElectronicInvoice/{id}` | Détail |
| `GET ElectronicInvoice/{societe}/New` | Modèle vide |
| `POST ElectronicInvoice` | Création d'un brouillon. Corps : `CrmApi.payload_facture()`. Réponse `{Invoice:{Id, Status:"Pending", Code:"Provisoire",…}}` |
| `DELETE ElectronicInvoice/{id}` | Suppression d'un brouillon. Réponse `{"IsSuccess":true}` |

Champs clés de la création : `Items:[{Title, Quantity, UnitPrice, VatPercent, TvaType: 0, Type: 0}]`, `Type: 1`, `VatPaymentType: 2`, `PaymentTerms: "Days30"`, `PaymentMethod: "PayoutSepa"`, `IssueDate`/`DeliveryDate` au dernier jour du mois.

La **validation** d'une facture lui attribue son numéro définitif (`FC…`), génère le PDF et crée la note de frais du mois avec une ligne « Vente » rattachée.

## Notes de frais 📖

| Appel | Rôle |
|---|---|
| `POST ExpenseNote/All` | Liste. Corps `{PageNumber, PageSize, SortColumn:null, IsPortage:false, SocietesIds:[{societe}], StartDate:null, EndDate:null, FilterStatusEnum:null, Year}`. Réponse `ExpenseNoteList.Items[]` |
| `GET ExpenseNote/GetById?id=<id>` | Détail (voir ci-dessous) |
| `POST ExpenseNote/BuildMileageAllowance` | Calcule les lignes kilométriques **sans les enregistrer**. Corps `{StartDate, EndDate, OldMileageAllowance:{…}, ExpenseNoteId}` |
| `POST ExpenseNote/MileageAllowanceSynthesis` | Synthèse kilométrique |
| `POST expenseNote/getAllAnnualCharges` | Charges annuelles / récurrentes |
| `GET expenseNote/GetHistory?expenseNoteId=` | Historique |

Contenu du détail d'une note :

- `ExpenseNoteMixedCharge[]` : `{MixedChargeTypeId, TypeName, Name, BrutAmount, Rate, Amount, Date, AnnualChargeId}`. `Amount` est stocké non arrondi (ex. 27,891), mais les totaux s'affichent arrondis.
- `ExpenseNoteSales[]` : `{SalesTypeId: 74, TypeName:"Facture", Name:"FC… - CLIENT", InvoiceCode, AmountHt, AmountTtc, VatRate, ExpenseNoteFileId, ExpenseNoteTva[]}`
- `ExpenseNoteMileageAllowance[]` : `{TransportMeanModelId, TransportMeanId, ScaleLevelNumber, MileageAllowanceTotal, ExpenseNoteMileageAllowanceDetail[]}`, avec une ligne par jour du mois : `{Date, Path, Customer, Distance, MileageAllowance, IsFreeDay, IsWeekend}`
- `ExpenseNoteExploitationCharge[]` : dépenses (format pas encore observé)
- `ExpenseNoteFiles[]` : PDF de la facture
- Totaux : `SalesTotalHt`, `SalesTotalTtc`, `MixedChargeTotal`, `ExploitationChargeTotalTtc`, `MileageAllowanceTotal`, `Total`

## Référentiels 📖

`POST ExpenseNoteParameterValue/All` avec `{PageNumber:0, PageSize:1000, ParameterId:<n>, IsActive:true}` :

| ParameterId | Contenu |
|---|---|
| 1 | Types de charges mixtes |
| 2 | Types de dépenses |
| 3 | Véhicules |
| 4 | Puissances fiscales (`ParentId` = véhicule) |
| 5 | Comptes de paiement (pro / personnel) |
| 6 | Types de vente |

Les valeurs sont recopiées dans `saisie/catalogue.py`.

## À capturer ⏳

Stubs `NotImplementedError` dans `saisie/crm_api.py` :

1. Validation de la facture (Provisoire → FC…)
2. Ajout d'une charge mixte à la note
3. Ajout d'une dépense (charge d'exploitation)
4. Enregistrement des frais kilométriques (après `BuildMileageAllowance`)
5. Envoi de la note

## Analyser une capture HAR sans fuite

Un HAR contient le mot de passe en clair dans le corps de `account/Login`, ainsi que les jetons de session. Il ne doit jamais être versionné (le `.gitignore` exclut `*.har` et `captures/`). Pour l'analyser, utiliser un script qui masque `Password`, `RecaptchaToken`, `XsrfToken`, `X-XSRF-TOKEN` et les cookies avant affichage.
