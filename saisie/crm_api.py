"""Appels à l'API du CRM Decisiel (relevés dans les captures réseau).

✅ = appel vu dans une capture, format connu
⏳ = pas encore capturé : à compléter après la capture de fin novembre
"""
from __future__ import annotations
import datetime as dt

import requests


class ErreurCRM(RuntimeError):
    pass


class CrmApi:
    def __init__(self, cfg: dict, session: dict | None = None):
        self.cfg = cfg
        self.base = cfg["crm"]["url_api"].rstrip("/")
        self.societe = cfg["crm"]["societe_id"]
        self.s = requests.Session()
        self.s.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Origin": cfg["crm"]["url_app"],
            "Referer": cfg["crm"]["url_app"] + "/",
            "X-Requested-With": "XMLHttpRequest",
            "AUDIT-PROGRAM": "CrmClient Web",
            "ApplicationName": "DECISIEL",
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
        })
        if session:
            self.utiliser_session(session)

    def utiliser_session(self, session: dict):
        """session = {"xsrf": ..., "cookies": [cookies Playwright]}"""
        self.s.headers["X-XSRF-TOKEN"] = session["xsrf"]
        self.s.cookies.clear()
        for c in session.get("cookies") or []:
            self.s.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))

    # ---------------------------------------------------------------- bas niveau
    def _appel(self, methode: str, chemin: str, **kw):
        r = self.s.request(methode, f"{self.base}/{chemin.lstrip('/')}", timeout=30, **kw)
        if r.status_code in (401, 403):
            raise ErreurCRM("Session expirée ou refusée (relance pour te reconnecter).")
        if not r.ok:
            raise ErreurCRM(f"{methode} {chemin} → HTTP {r.status_code} : {r.text[:300]}")
        return r.json() if r.content else None

    # ---------------------------------------------------------------- session ✅
    def session_valide(self, session: dict) -> bool:
        """Appel qui exige d'être connecté : la liste des sociétés de l'utilisateur."""
        self.utiliser_session(session)
        try:
            r = self._appel("GET", "societe/GetListSocietesAsKeyValueObjectByPersonEmail")
            return bool(r)
        except (ErreurCRM, requests.RequestException, ValueError):
            return False

    # ---------------------------------------------------------- notes de frais ✅
    def notes_de_frais(self, annee: int) -> list[dict]:
        r = self._appel("POST", "ExpenseNote/All", json={
            "PageNumber": 1, "PageSize": 50, "SortColumn": None, "IsPortage": False,
            "SocietesIds": [self.societe], "StartDate": None, "EndDate": None,
            "FilterStatusEnum": None, "Year": annee})
        return r["ExpenseNoteList"]["Items"]

    def note(self, note_id: int) -> dict:
        return self._appel("GET", "ExpenseNote/GetById", params={"id": note_id})

    def note_du_mois(self, annee: int, mois: int) -> dict | None:
        debut = f"{annee:04d}-{mois:02d}-01"
        for n in self.notes_de_frais(annee):
            if str(n.get("StartDate", "")).startswith(debut):
                return self.note(n["Id"])
        return None

    # ---------------------------------------------------------------- factures ✅
    def factures(self, statut, page_size: int = 50) -> list[dict]:
        """statut : 2 = publiées, "Pending" = brouillons (vus dans les captures)."""
        params = {"PageNumber": 1, "PageSize": page_size, "CompanyId": self.societe, "Status": statut}
        return self._appel("GET", "ElectronicInvoice", params=params)["Items"]

    def facture(self, facture_id: int) -> dict:
        return self._appel("GET", f"ElectronicInvoice/{facture_id}")

    def brouillons(self) -> list[dict]:
        return self.factures("Pending")

    def supprimer_brouillon(self, facture_id: int):
        """DELETE ElectronicInvoice/{id} — refusé si ce n'est pas un brouillon."""
        if facture_id not in {b["Id"] for b in self.brouillons()}:
            raise ErreurCRM(f"La facture n°{facture_id} n'est pas un brouillon : suppression refusée.")
        r = self._appel("DELETE", f"ElectronicInvoice/{facture_id}")
        if not (r or {}).get("IsSuccess"):
            raise ErreurCRM(f"Suppression refusée par le CRM : {r}")

    def payload_facture(self, facture: dict) -> dict:
        """Corps identique à celui envoyé par l'interface (capture du 01/11/2026)."""
        f = self.cfg["facture"]
        jour = facture["date"].isoformat() + "T00:00:00"
        return {
            "CompanyId": self.societe, "ClientId": f["client_id"],
            "BankAccountId": f["compte_bancaire_id"],
            "PaymentTerms": f["delai_paiement"], "PaymentMethod": f["mode_paiement"],
            "LatePaymentInterest": "None", "IntroductionText": None,
            "ConclusionText": None, "FooterText": None,
            "IssueDate": jour, "CustomDueDate": None, "CustomPaymentTermsLabel": None,
            "DeliveryDate": jour,
            "Items": [{"Title": f["intitule"], "Quantity": facture["jours"], "TvaType": 0,
                       "UnitPrice": float(facture["tjm_ht"]), "VatPercent": float(facture["taux_tva"]),
                       "Type": 0, "DiscountPercent": None}],
            "CompanyTvaNumber": self.cfg["crm"]["tva_intracom"], "IsOutOfTvaScope": False,
            "IsJudicialLiquidation": False, "DeliveryDetails": {}, "TaxRepresentative": {},
            "Type": 1, "ParentInvoiceId": None, "AssuranceType": None, "AssuranceName": None,
            "AssuranceContractIdentifier": None, "AssuranceGeographicCoverage": None,
            "DiscountPercent": None, "PurchaseOrderCode": None, "CustomLatePaymentInterest": None,
            "VatPaymentType": 2, "DisplayMessage": 1, "LogoUrl": None,
        }

    def creer_facture_brouillon(self, facture: dict) -> dict:
        r = self._appel("POST", "ElectronicInvoice", json=self.payload_facture(facture))
        return r["Invoice"]

    # --------------------------------------------------------- à compléter ⏳
    def valider_facture(self, facture_id: int):
        raise NotImplementedError("Validation de facture : endpoint pas encore capturé.")

    def ajouter_charge_mixte(self, note_id: int, charge: dict):
        raise NotImplementedError("Ajout de charge mixte : endpoint pas encore capturé.")

    def ajouter_depense(self, note_id: int, depense: dict):
        raise NotImplementedError("Ajout de dépense : endpoint pas encore capturé.")

    def enregistrer_kilometres(self, note_id: int, km: dict):
        raise NotImplementedError("Enregistrement des kilomètres : endpoint pas encore capturé.")

    def envoyer_note(self, note_id: int):
        raise NotImplementedError("Envoi de la note : endpoint pas encore capturé.")
