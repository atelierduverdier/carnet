#!/usr/bin/env python3
# =========================================================================
# mettre-a-jour.py — remplacer le MOTEUR d'un site, sans toucher au site
# =========================================================================
# Un site fait avec ce moteur en contient une copie. Sans cette commande,
# une correction ne remonterait jamais : il faudrait la refaire à la main
# dans chaque site, ou ne pas la faire.
#
# Ce qui est remplacé : le générateur, l'atelier, la publication, le
# vérificateur, les essais. Ce qui n'est JAMAIS touché : site/contenu,
# site/medias, site/config.yaml, et kit/ — l'habillage appartient au site,
# un client l'a peut-être modifié.
#
# UTILISATION :
#   python3 outils/mettre-a-jour.py --depuis ~/Projets/logiciels/squelette-site
#   python3 outils/mettre-a-jour.py --depuis … --pour-de-vrai
#
# À BLANC PAR DÉFAUT, comme outils/publier.py : on montre ce qui changerait
# avant de le changer.
# =========================================================================

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CARTE = RACINE / 'moteur.json'

# Ce qui EST le moteur. Tout le reste appartient au site.
MOTEUR = [
    'site/generer.py',
    'outils/atelier.py', 'outils/atelier',
    'outils/publier.py', 'outils/verifier.py', 'outils/traduire.py',
    'outils/demarrer.py', 'outils/mettre-a-jour.py',
    'tests',
    'VERSION',
]
# L'habillage : on ne l'écrase pas, on signale seulement qu'il a bougé.
#
# `kit/` est l'ancien nom, gardé pour les sites nés avant les thèmes ;
# `themes/` est l'actuel. LES DEUX SONT LÀ, et il a fallu s'en apercevoir :
# la liste ne connaissait que `kit/`, si bien qu'un site né avec un thème
# n'était JAMAIS prévenu que l'habillage de référence avait bougé. Le
# correctif d'un gabarit restait donc chez le squelette, en silence — ce
# que le CLAUDE.md du dépôt interdit précisément : une correction qui
# compte doit être DITE aux sites vivants, puisqu'on ne peut pas la leur
# appliquer. Trouvé en portant un correctif de `fiche.html` vers un site né
# la veille, qui ne l'a pas vu passer.
#
# Un chemin absent de la source est ignoré : un site n'a pas les deux.
HABILLAGE = ['kit/gabarits', 'kit/site.css', 'kit/site.js', 'themes']


def lire_carte() -> dict:
    if CARTE.is_file():
        try:
            return json.loads(CARTE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            pass
    return {}


def version_de(dossier: Path) -> str:
    f = dossier / 'VERSION'
    return f.read_text(encoding='utf-8').strip() if f.is_file() else '(inconnue)'


def differents(source: Path, cible: Path):
    """Les fichiers qui changeraient, par chemin relatif à la source."""
    changes = []
    if source.is_file():
        if not cible.is_file() or not filecmp.cmp(source, cible, shallow=False):
            changes.append(source.name)
        return changes
    for f in sorted(source.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts:
            continue
        rel = f.relative_to(source)
        vis = cible / rel
        if not vis.is_file() or not filecmp.cmp(f, vis, shallow=False):
            changes.append(str(rel))
    return changes


def depot_propre() -> bool:
    """Un dépôt sale rend la mise à jour irréversible : on refuse."""
    r = subprocess.run(['git', 'status', '--porcelain'], cwd=str(RACINE),
                       capture_output=True, text=True)
    if r.returncode != 0:
        return True          # pas un dépôt : rien à protéger, on laisse faire
    en_cours = [l for l in r.stdout.splitlines() if l.strip()]
    return not en_cours


def main():
    ap = argparse.ArgumentParser(description='Mettre à jour le moteur du site.')
    ap.add_argument('--depuis', required=True, help='le dossier du moteur de référence')
    ap.add_argument('--pour-de-vrai', action='store_true',
                    help='remplacer réellement (sinon : essai à blanc)')
    ap.add_argument('--sans-essais', action='store_true',
                    help='ne pas lancer le filet de tests après')
    args = ap.parse_args()

    source = Path(args.depuis).expanduser().resolve()
    if not (source / 'site' / 'generer.py').is_file():
        sys.exit(f'mettre-a-jour : {source} ne ressemble pas à un moteur.')
    if source == RACINE:
        sys.exit('mettre-a-jour : le moteur de référence EST ce site.')

    carte = lire_carte()
    ici, la_bas = carte.get('version', version_de(RACINE)), version_de(source)
    print(f'  moteur du site   : {ici}')
    print(f'  moteur de référence : {la_bas}   ({source})')

    total, detail = 0, []
    for quoi in MOTEUR:
        changes = differents(source / quoi, RACINE / quoi)
        if changes:
            total += len(changes)
            detail.append((quoi, changes))
    bouge = []
    for quoi in HABILLAGE:
        if not (source / quoi).exists():
            continue
        changes = differents(source / quoi, RACINE / quoi)
        if changes:
            bouge.append((quoi, changes))

    if not total:
        print('\n  Le moteur est déjà à jour — rien à remplacer.')
    else:
        print(f'\n  {total} fichier(s) du moteur seraient remplacés :')
        for quoi, changes in detail:
            print(f'    {quoi}')
            for c in changes[:6]:
                print(f'       {c}')
            if len(changes) > 6:
                print(f'       … et {len(changes) - 6} autres')

    if bouge:
        print('\n  L’HABILLAGE de référence a changé, mais il ne sera PAS touché —')
        print('  il appartient au site, et vous l’avez peut-être modifié :')
        for quoi, changes in bouge:
            print(f'    {quoi}')
            for nom in changes[:6]:
                print(f'       {nom}')
            if len(changes) > 6:
                print(f'       … et {len(changes) - 6} autres')
        print('  À comparer à la main si une nouveauté du moteur en dépend.')

    if not args.pour_de_vrai:
        print('\n  Essai à blanc. Pour remplacer réellement : --pour-de-vrai')
        return

    if not depot_propre():
        sys.exit('\nmettre-a-jour : le dossier contient du travail non versé.\n'
                 '  Committez-le d’abord — sans quoi cette mise à jour ne se '
                 'défait pas.')

    for quoi in MOTEUR:
        s, c = source / quoi, RACINE / quoi
        if not s.exists():
            continue
        if s.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            shutil.copytree(s, c, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            c.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, c)

    CARTE.write_text(json.dumps({
        'version': la_bas,
        'origine': str(source),
        'mis_a_jour': date.today().isoformat(),
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'\n  Moteur remplacé : {ici} → {la_bas}')

    if args.sans_essais:
        return
    essais = RACINE / 'tests' / 'lancer.py'
    if not essais.is_file():
        return
    print('  Le filet de tests, sur ce site :')
    r = subprocess.run([sys.executable, str(essais)], cwd=str(RACINE),
                       capture_output=True, text=True, timeout=900)
    derniere = [l for l in r.stderr.strip().splitlines() if l.strip()][-1:]
    print('   ', derniere[0] if derniere else '(pas de sortie)')
    if r.returncode != 0:
        print('\n  Le filet ROUGIT après la mise à jour. Revenez en arrière :')
        print('    git checkout -- . && git clean -fd')
        sys.exit(1)


if __name__ == '__main__':
    main()
