#!/usr/bin/env python3
# =========================================================================
# demarrer.py — baptiser un site neuf, fait à partir du squelette
# =========================================================================
# Écrit le nom, la devise, le domaine et les langues dans site/config.yaml,
# crée les dossiers de contenu manquants, et peut vider les pages de
# démonstration. À lancer UNE fois, juste après avoir copié le squelette.
#
# UTILISATION :
#   python3 outils/demarrer.py                       # il pose les questions
#   python3 outils/demarrer.py --titre "Le Verger" \
#           --domaine https://leverger.fr --langues fr,en --vider
# =========================================================================

import argparse
import re
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CONFIG = RACINE / 'site' / 'config.yaml'
CONTENU = RACINE / 'site' / 'contenu'

# Les mots d'interface du générateur existent dans ces trois langues.
# En ajouter une demande d'écrire son bloc dans MOTS, site/generer.py.
CONNUES = {'fr': 'Français', 'it': 'Italiano', 'en': 'English'}


# La page d'accueil de chaque langue, écrite dans cette langue : un site
# à deux langues dont l'une accueille en français n'est pas bilingue.
PREMIERS = {
    'fr': {'titre': 'Accueil',
           'corps': "## Bienvenue\n\nCette page est la première du site. "
                    "Remplacez-la depuis l'atelier."},
    'it': {'titre': 'Pagina iniziale',
           'corps': "## Benvenuti\n\nQuesta è la prima pagina del sito. "
                    "Sostituitela dall'atelier."},
    'en': {'titre': 'Home',
           'corps': "## Welcome\n\nThis is the first page of the site. "
                    "Replace it from the atelier."},
}


def demander(question, defaut):
    reponse = input(f'  {question} [{defaut}] : ').strip()
    return reponse or defaut


def poser(texte: str, cle: str, valeur: str) -> str:
    """Remplace « cle: "…" » au premier niveau, en gardant les commentaires.

    On réécrit la LIGNE, pas le fichier : passer par yaml.safe_dump
    effacerait les explications qui font tout l'intérêt de ce fichier.
    """
    motif = re.compile(rf'^{cle}:[ \t]*.*$', re.M)
    ligne = f'{cle}: "{valeur}"'
    if motif.search(texte):
        return motif.sub(ligne, texte, count=1)
    return texte.rstrip('\n') + '\n' + ligne + '\n'


def bloc_langue(code: str, nom: str, titre: str, devise: str, accueil: str) -> str:
    return (f'  {code}:\n'
            f'    nom: "{nom}"\n'
            f'    accueil: "{accueil}"\n'
            f'    titre: "{titre}"\n'
            f'    devise: "{devise}"\n')


def main():
    ap = argparse.ArgumentParser(description='Baptiser un site neuf.')
    ap.add_argument('--titre')
    ap.add_argument('--devise')
    ap.add_argument('--domaine')
    ap.add_argument('--courriel')
    ap.add_argument('--langues', help='codes séparés par des virgules, ex. fr,en')
    ap.add_argument('--vider', action='store_true',
                    help='efface les pages de démonstration')
    args = ap.parse_args()

    if not CONFIG.is_file():
        sys.exit('demarrer : site/config.yaml est introuvable — êtes-vous à la '
                 'racine du squelette ?')

    interactif = not any([args.titre, args.domaine, args.langues])
    if interactif:
        print('\n  Baptême du site — entrée vide = la valeur entre crochets.\n')
    titre = args.titre or (demander('Nom du site', 'Mon site') if interactif else 'Mon site')
    devise = args.devise or (demander('Devise (une phrase)', 'La phrase qui dit ce qu’on y trouve.')
                             if interactif else '')
    domaine = args.domaine or (demander('Domaine', 'https://exemple.fr') if interactif else '')
    courriel = args.courriel or (demander('Courriel de contact', 'bonjour@exemple.fr')
                                 if interactif else '')
    brut = args.langues or (demander('Langues (codes séparés par des virgules)', 'fr')
                            if interactif else 'fr')
    langues = [c.strip().lower() for c in brut.split(',') if c.strip()]

    inconnues = [c for c in langues if c not in CONNUES]
    if inconnues:
        sys.exit(f'demarrer : langue(s) sans mots d’interface : {", ".join(inconnues)}.\n'
                 f'  Ajoutez leur bloc dans MOTS, en tête de site/generer.py, '
                 f'puis relancez.')

    t = CONFIG.read_text(encoding='utf-8')
    t = poser(t, 'titre', titre)
    if devise:
        t = poser(t, 'devise', devise)
    if domaine:
        t = poser(t, 'domaine', domaine)
    if courriel:
        t = poser(t, 'courriel', courriel)
    t = re.sub(r'^langue_par_defaut:.*$', f'langue_par_defaut: {langues[0]}', t, count=1, flags=re.M)

    # le bloc « langues » est réécrit en entier : chaque langue a son
    # accueil, et une langue sans accueil n'est pas engendrée.
    accueils = {'fr': 'accueil', 'it': 'home', 'en': 'home'}
    blocs = ''.join(bloc_langue(c, CONNUES[c], titre, devise, accueils[c]) for c in langues)
    t = re.sub(r'^langues:\n(?:[ \t]+.*\n|\n)*', 'langues:\n' + blocs, t, count=1, flags=re.M)
    CONFIG.write_text(t, encoding='utf-8')

    if args.vider or (interactif and demander('Effacer les pages de démonstration ? (o/n)', 'n')
                      .lower().startswith('o')):
        for d in CONTENU.iterdir():
            if d.is_dir() and not d.name.startswith('.'):
                shutil.rmtree(d)
                d.mkdir()
        print('  pages de démonstration effacées')

    # UNE LANGUE SANS ACCUEIL N'EST PAS ENGENDRÉE, et le sélecteur de
    # langue de toutes les pages pointe alors dans le vide — 1 419 liens
    # morts d'un coup, la première fois. Chaque langue déclarée reçoit
    # donc sa page d'accueil, appariée aux autres par la clé `traduction`.
    for c in langues:
        (CONTENU / c).mkdir(parents=True, exist_ok=True)
        cible = CONTENU / c / f'{accueils[c]}.md'
        if any((CONTENU / c).glob('*.md')) and cible.exists():
            continue
        if any(f'slug: "{accueils[c]}"' in p.read_text(encoding='utf-8')
               for p in (CONTENU / c).glob('*.md')):
            continue
        cible.write_text(
            f'---\ntitre: "{PREMIERS[c]["titre"]}"\nlangue: "{c}"\n'
            f'type: "page"\nslug: "{accueils[c]}"\ntraduction: "accueil"\n'
            f'statut: "publie"\n---\n\n{PREMIERS[c]["corps"]}\n',
            encoding='utf-8')

    # La carte d'identité du moteur : le site sait de quelle version il
    # est né, et « mettre-a-jour.py » sait quoi comparer.
    import json
    version = (RACINE / 'VERSION').read_text(encoding='utf-8').strip() \
        if (RACINE / 'VERSION').is_file() else '(inconnue)'
    (RACINE / 'moteur.json').write_text(json.dumps({
        'version': version, 'origine': '', 'mis_a_jour': str(__import__('datetime').date.today()),
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'\n  {titre} est baptisé. Langues : {", ".join(langues)}.')
    print(f'  Moteur {version}.')
    print('  La suite :')
    print('    1. remplacer kit/logo.png et les deux favicons ;')
    print('    2. les couleurs et les polices sont en tête de kit/site.css ;')
    print('    3. python3 outils/atelier.py   (puis écrire, et publier).')
    if len(langues) > 1:
        print(f'    Chaque langue a reçu sa page d’accueil : '
              f'site/contenu/{{{",".join(langues)}}}/.')
        print('\n  Une chose à faire tout de suite : TRADUIRE la devise de chaque')
        print('  langue dans site/config.yaml. Tant qu’elles sont identiques, les')
        print('  accueils portent le même titre d’onglet, et le vérificateur le dit.')


if __name__ == '__main__':
    main()
