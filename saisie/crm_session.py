"""Connexion au CRM.

La page de connexion est protégée par un reCAPTCHA : c'est TOI qui te connectes
dans la fenêtre ouverte par Playwright. Le script n'a jamais ton mot de passe ;
il récupère seulement la session (jeton XSRF + cookies) une fois connecté.
La session est gardée dans ~/.saisie_compta/session.json tant qu'elle reste valide.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path

DOSSIER = Path.home() / ".saisie_compta"
FICHIER = DOSSIER / "session.json"


def _lire_cache():
    try:
        data = json.loads(FICHIER.read_text())
        return data if data.get("xsrf") else None
    except (OSError, ValueError):
        return None


def _ecrire_cache(session: dict):
    DOSSIER.mkdir(mode=0o700, exist_ok=True)
    # Créé directement en 600 : le fichier n'est jamais lisible par d'autres, même un instant.
    fd = os.open(FICHIER, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({**session, "date": time.strftime("%Y-%m-%d %H:%M")}, f)
    os.chmod(FICHIER, 0o600)   # au cas où un ancien fichier existait avec d'autres droits


def oublier():
    if FICHIER.exists():
        FICHIER.unlink()


def _lancer_navigateur(p):
    """Google Chrome s'il est installé (le plus proche de ton usage normal), sinon Chromium."""
    try:
        return p.chromium.launch(channel="chrome", headless=False)
    except Exception:
        return p.chromium.launch(headless=False)


def connexion_navigateur(url_app: str, est_valide, delai_minutes: int = 5, debug: bool = False) -> dict:
    from playwright.sync_api import Error as PwError, sync_playwright

    print("\n🔐 Une fenêtre va s'ouvrir : connecte-toi au CRM comme d'habitude.")
    print("   Ne la ferme pas : elle se fermera toute seule une fois la connexion détectée.")
    print(f"   (attente maximale : {delai_minutes} minutes)\n")

    candidats, vus = [], set()

    def ajouter(jeton, source):
        if jeton and jeton not in vus:
            vus.add(jeton)
            candidats.append(jeton)
            if debug:
                print(f"   [debug] jeton candidat via {source}")

    def sur_reponse(r):
        url = r.url.lower()
        if "/api/" in url and debug:
            print(f"   [debug] {r.request.method} {r.status} {r.url.split('/api/')[-1][:70]}")
        if "account/login" in url and r.request.method == "POST":
            try:
                corps = r.json()
            except Exception:
                corps = {}
            if corps.get("IsError") or not r.ok:
                print(f"   ❌ Connexion refusée par le CRM (HTTP {r.status}), réessaie dans la fenêtre.")
            ajouter(corps.get("XsrfToken"), "réponse de connexion")

    def sur_requete(req):
        url = req.url.lower()
        if "/api/" in url and "account/login" not in url:
            ajouter(req.headers.get("x-xsrf-token"), f"en-tête de {req.url.split('/api/')[-1][:50]}")

    with sync_playwright() as p:
        nav = _lancer_navigateur(p)
        ctx = nav.new_context()
        page = ctx.new_page()
        ctx.on("response", sur_reponse)   # toutes les pages, même un nouvel onglet
        ctx.on("request", sur_requete)
        try:
            page.goto(url_app)
            fin = time.time() + delai_minutes * 60
            while time.time() < fin:
                while candidats:
                    session = {"xsrf": candidats.pop(), "cookies": ctx.cookies()}
                    if est_valide(session):
                        print("✅ Connexion détectée.")
                        return session
                    if debug:
                        print("   [debug] candidat refusé par l'API")
                # On attend sur n'importe quel onglet encore ouvert : la connexion
                # peut s'ouvrir dans un nouvel onglet et l'onglet de départ se fermer.
                ouverts = [pg for pg in ctx.pages if not pg.is_closed()]
                if not ouverts:
                    raise RuntimeError("La fenêtre a été fermée avant que la connexion soit détectée.")
                try:
                    ouverts[-1].wait_for_timeout(1000)
                except PwError:
                    continue   # l'onglet vient de se fermer : on passe au suivant
            raise RuntimeError("Délai dépassé : connexion non détectée "
                               "(relance avec --debug et envoie-moi la sortie).")
        finally:
            try:
                nav.close()
            except Exception:
                pass


def obtenir_session(url_app: str, est_valide, debug: bool = False) -> dict:
    """Réutilise la session en cache si elle marche encore, sinon ouvre le navigateur."""
    session = _lire_cache()
    if session and est_valide(session):
        print("✅ Session précédente encore valide.")
        return session
    session = connexion_navigateur(url_app, est_valide, debug=debug)
    _ecrire_cache(session)
    return session
