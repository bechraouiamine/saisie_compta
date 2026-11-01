"""Types reconnus par le CRM (relevés dans la capture du 01/11/2026).

nom -> (id CRM, valeur par défaut du CRM)
  - charges mixtes : la valeur par défaut est le taux d'usage pro (%)
  - dépenses (charges d'exploitation) : la valeur par défaut est le taux de TVA (%)
"""
from __future__ import annotations

CHARGES_MIXTES = {
    "LOYERS": (1, 30),
    "CHARGES LOCATIVES": (2, 30),
    "EDF/GDF": (3, 30),
    "TELEPHONE": (4, 75),
    "ASSURANCES": (5, 30),
    "TAXE D'HABITATION": (45, 30),
    "TAXES FONCIERES": (46, 30),
    "INTERNET": (47, 75),
    "FORFAIT REPAS DIRIGEANT SEUL": (49, 100),
    "DEPLACEMENTS PROFESSIONNELS": (50, 100),
    "CONSOMMATION D'EAU": (89, 30),
    "DONS AUX OEUVRES": (56, 100),
}

DEPENSES = {
    "REPAS GERANT SEUL": (6, 10),
    "REPAS CLIENT FOURNISSEUR": (7, 10),
    "FORFAIT REPAS GERANT SEUL": (60, 10),
    "FRAIS POSTAUX": (530, None),
    "PEAGES": (8, 20),
    "PARKING": (9, 20),
    "FORMATION": (10, 20),
    "SNCF": (11, None),
    "RATP": (12, None),
    "HOTEL": (13, 10),
    "BILLET D'AVION": (51, None),
    "CARBURANT DIESEL": (59, 16),
    "CARBURANT ESSENCE": (58, None),
    "ELECTRICITE VEHICULE ELECTRIQUE": (87, 20),
    "FOURNITURES DE BUREAU": (531, 20),
    "MATERIEL DE BUREAU ET MATERIEL INFORMATIQUE": (15, 20),
    "FOURNITURE ET PETIT EQUIPEMENT": (17, 20),
    "ENTRETIEN ET REPARATION": (18, 20),
    "DOCUMENTATION GENERALE": (19, 20),
    "FRAIS DE GREFFE": (21, 20),
    "HONORAIRES COMPTABLES": (22, 20),
    "FRAIS DE BANQUE": (54, 20),
    "CADEAUX CLIENTS": (57, 20),
    "PRESTATIONS DE SERVICES INFORMATIQUES": (61, 20),
    "COWORKING": (80, 20),
    "LOCATION VEHICULE DE TOURISME": (14, 0),
}

COMPTES_PAIEMENT = {"pro": 36, "personnel": 37}

VEHICULES = {"Voiture Thermique, hybride et hybride rechargeable": 25, "Voiture électrique": 62}
PUISSANCES = {"3 CV et moins": 27, "4 CV": 28, "5 CV": 29, "6 CV": 30, "7 CV et plus": 31}

TYPE_VENTE_FACTURE = 74


def chercher(table: dict, nom: str, quoi: str):
    cle = nom.strip().upper()
    for k, v in table.items():
        if k.upper() == cle:
            return k, v
    connus = "\n  - ".join(sorted(table))
    raise ValueError(f"{quoi} inconnu : « {nom} ». Types disponibles :\n  - {connus}")
