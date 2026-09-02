#!/usr/bin/env python3
# =========================================================================
# verifier.py — contrôle le site engendré
# =========================================================================
# Passe sur site/public/ et signale ce qu'un coup d'œil ne voit pas :
# liens internes morts, images absentes, pages vides, titres en double,
# doublons d'adresse.
#
# UTILISATION :
#   python3 outils/verifier.py            # après site/generer.py
#   python3 outils/verifier.py --detail   # liste chaque cas
#
# Renvoie 1 si quelque chose cloche : utilisable dans un enchaînement.
# =========================================================================

import argparse
import html
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urljoin

RACINE = Path(__file__).resolve().parent.parent
PUBLIC = RACINE / 'site' / 'public'


EXTERNES = ('http://', 'https://', 'mailto:', 'tel:', 'data:', 'ftp://', '#')


def cible_existe(chemin: str, depuis: str = '/') -> bool:
    """Ce lien mène-t-il quelque part dans le site engendré ?

    Un lien RELATIF était admis sans contrôle — « rare ici, on laisse ».
    Rare n'est pas jamais, et un site fait avec ce squelette peut très
    bien n'écrire que du relatif. On le résout depuis la page qui le
    porte, comme le ferait le navigateur.
    """
    chemin = unquote(chemin.split('#')[0].split('?')[0])
    if not chemin:
        return True
    if not chemin.startswith('/'):
        chemin = urljoin(depuis, chemin)
    p = PUBLIC / chemin.lstrip('/')
    return p.is_file() or (p / 'index.html').is_file()


# Les liens vivent dans les attributs, et les attributs s'écrivent avec des
# guillemets doubles OU simples : la moitié du site restait invisible dès
# qu'une page en portait. Les commentaires HTML, eux, sont écartés — une
# adresse mise de côté par son auteur n'est pas un lien mort.
COMMENTAIRE = re.compile(r'<!--.*?-->', re.S)
ATTRIBUT = re.compile(r'\b(href|src|srcset)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')


def liens_de(page_html: str):
    """(attribut, adresse) de chaque lien interne de la page.

    « srcset » est découpé sur ses virgules : ses adresses n'étaient pas
    contrôlées du tout, et une déclinaison manquante ne se voyait nulle
    part — le navigateur se rabattant sur l'original, personne ne le
    remarquait.
    """
    for m in ATTRIBUT.finditer(COMMENTAIRE.sub(' ', page_html)):
        attr = m.group(1)
        brut = m.group(2) if m.group(2) is not None else m.group(3)
        # Markdown encode les courriels en entités contre les robots :
        # « &#109;&#97;&#105;… » EST un mailto:, et non un lien relatif.
        morceaux = ([x.strip().split(' ')[0] for x in brut.split(',')]
                    if attr == 'srcset' else [brut])
        for lien in morceaux:
            lien = html.unescape(lien).strip()
            if not lien or lien.lower().startswith(EXTERNES):
                continue
            yield attr, lien


def main():
    ap = argparse.ArgumentParser(description='Contrôle le site engendré.')
    ap.add_argument('--detail', action='store_true')
    args = ap.parse_args()

    if not PUBLIC.is_dir():
        sys.exit('verifier : site/public/ absent — lancer site/generer.py.')

    pages = sorted(PUBLIC.rglob('index.html'))
    soucis = defaultdict(list)          # bloquant : code de retour 1
    remarques = defaultdict(list)       # à savoir : n'arrête pas la publication
    liens_par_cible = Counter()
    titres = Counter()

    for page in pages:
        url = '/' + str(page.parent.relative_to(PUBLIC)).replace('\\', '/') + '/'
        url = url.replace('/./', '/')
        h = page.read_text(encoding='utf-8', errors='replace')

        # `find` rend -1 quand la balise fermante manque : le corps était
        # alors tronqué d'un caractère au lieu d'être pris en entier.
        debut, fin = h.find('<main'), h.find('</main>')
        corps = h[debut:fin] if debut >= 0 and fin > debut else h
        texte = re.sub(r'<[^>]+>', ' ', corps)
        texte = re.sub(r'\s+', ' ', texte).strip()
        if len(texte) < 40:
            soucis['page quasi vide'].append(url)

        t = re.search(r'<title>(.*?)</title>', h, re.S)
        if t and t.group(1).strip():
            titres[t.group(1).strip()] += 1
        else:
            # comptée sous « (sans titre) », elle était ensuite écartée des
            # doublons : le défaut n'était donc signalé nulle part.
            soucis['page sans <title>'].append(url)

        h1 = re.findall(r'<h1[^>]*>(.*?)</h1>', corps, re.S)
        if len(h1) > 1:
            soucis['plusieurs <h1>'].append(url)
        # Un titre court comme « Interview » se retrouve forcément dans le
        # texte : ne signaler que les titres assez longs pour que la
        # répétition soit une vraie maladresse.
        nu = re.sub(r'<[^>]+>', '', h1[0]).strip() if h1 else ''
        if len(nu) > 25 and corps.count(nu) > 2:
            # maladresse de style, pas défaut : elle ne doit pas faire
            # demander confirmation avant de publier, comme un lien mort.
            remarques['titre répété dans le corps'].append(url)

        for attr, lien in liens_de(h):
            liens_par_cible[lien] += 1
            if not cible_existe(lien, url):
                soucis[f'{attr} mort'].append(f'{url} → {lien}')

    # LES REDIRECTIONS AUSSI SONT DES LIENS. Les anciennes adresses
    # renvoient vers des pages d'ici, et rien ne recoud ce fichier quand
    # on renomme une page depuis l'atelier : le jour où cela arrive, un
    # moteur suit un 301 vers le vide et personne ne le sait.
    carte = RACINE / 'site' / 'redirections.txt'
    if carte.is_file():
        for n, ligne in enumerate(carte.read_text(encoding='utf-8').splitlines(), 1):
            ligne = ligne.split('#', 1)[0].strip()
            if '\t' not in ligne:
                continue
            ancien, nouveau = (x.strip() for x in ligne.split('\t', 1))
            if not (ancien and nouveau) or nouveau == '?':
                continue
            if nouveau.lower().startswith(EXTERNES):
                continue
            if not cible_existe(nouveau):
                soucis['redirection vers le vide'].append(
                    f'redirections.txt l.{n} : {ancien} → {nouveau}')

    doublons = {t: n for t, n in titres.items() if n > 1}

    print('=== VÉRIFICATION ===')
    # dire QUEL site l'on vérifie : sur une machine qui en porte
    # plusieurs, la sortie se ressemblait d'un site à l'autre.
    try:
        import yaml as _y
        _nom = (_y.safe_load((RACINE / 'site' / 'config.yaml').read_text(encoding='utf-8'))
                or {}).get('titre')
        if _nom:
            print(f'  site               {_nom}')
    except Exception:
        pass
    print(f'  pages              {len(pages)}')
    print(f'  liens internes     {sum(liens_par_cible.values())} '
          f'({len(liens_par_cible)} cibles distinctes)')
    total = 0
    for k, v in sorted(soucis.items(), key=lambda x: -len(x[1])):
        total += len(v)
        print(f'  {k:<28} {len(v)}')
        for x in (v if args.detail else v[:3]):
            print(f'      {x}')
        if not args.detail and len(v) > 3:
            print(f'      … et {len(v) - 3} autres (--detail)')
    if doublons:
        # ILS COMPTENT DANS LE TOTAL. Ils étaient affichés puis ignorés du
        # code de retour — or c'est tout ce que publier.py regarde : il
        # voyait 0, ne prévenait de rien, et publiait. Le rapport défilait.
        total += len(doublons)
        print(f'  titres <title> en double     {len(doublons)}')
        for t, n in list(doublons.items())[:5]:
            print(f'      ×{n}  {t}')
    for k, v in sorted(remarques.items(), key=lambda x: -len(x[1])):
        print(f'  · {k:<26} {len(v)}   (n’arrête pas la publication)')
        for x in (v if args.detail else v[:3]):
            print(f'      {x}')
        if not args.detail and len(v) > 3:
            print(f'      … et {len(v) - 3} autres (--detail)')
    if not total:
        print('  rien à signaler.' if not remarques
              else '  rien de bloquant.')
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
