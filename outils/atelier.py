#!/usr/bin/env python3
# =========================================================================
# atelier.py — l'interface locale pour tenir le site
# =========================================================================
# Ouvre une page dans le navigateur pour lister, écrire et relire les
# pages, déposer des photos et des PDF, puis régénérer le site.
#
# UTILISATION :
#   python3 outils/atelier.py            # ouvre http://localhost:8413
#   python3 outils/atelier.py --port 9000
#
# Côté navigateur, aucune bibliothèque. Côté serveur, la bibliothèque
# standard plus `yaml`, pour relire les menus et la configuration — les
# mêmes que ceux dont le générateur se sert.
#
# L'atelier n'écrit QUE dans site/contenu/ et site/medias/. Il ne touche
# jamais à site/public/, qui est reconstruit de zéro par generer.py.
# =========================================================================

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import unicodedata
import webbrowser
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import yaml

# LE CODE DE L'ATELIER PEUT CHANGER SOUS LUI. Python ne recharge rien à
# chaud : un serveur démarré à 15:43 tourne encore avec le code de 15:43,
# même si les fichiers ont changé depuis. Christophe l'a payé — ses
# jumelles sont parties à la fin de leur rubrique parce que le correctif,
# livré sept minutes après le démarrage, dormait sur le disque. Un
# rechargement du navigateur ne suffit pas : il ne rafraîchit que le
# JavaScript. On relève donc l'âge du code au démarrage, et l'atelier le
# dit quand il a vieilli.
SOURCES_SUIVIES = ('outils/atelier.py', 'outils/traduire.py', 'site/generer.py')

RACINE = Path(__file__).resolve().parent.parent
SITE = RACINE / 'site'
CONTENU = SITE / 'contenu'
MEDIAS = SITE / 'medias'
PUBLIC = SITE / 'public'
INTERFACE = Path(__file__).resolve().parent / 'atelier'

IMAGES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.avif'}
DOCUMENTS = {'.pdf', '.mp3', '.mp4', '.odt', '.docx', '.zip'}
ACCEPTES = IMAGES | DOCUMENTS
TAILLE_MAX = 40 * 1024 * 1024
LARGEUR_MAX = 1600   # au-delà, le site n'affiche jamais l'image en entier


def entier(v, defaut=0) -> int:
    """Un nombre lu dans un en-tête, sans faire tomber le reste.

    `int()` nu sur `rang:` faisait échouer lister() ENTIÈRE — donc la
    première requête de l'atelier, donc l'écran blanc — pour un seul
    fichier corrigé au clavier. Trois écritures suffisent à le déclencher :
    « abc », « 3.5 », et « 1 000 » avec l'espace fine des nombres français.
    Une valeur illisible vaut le défaut ; la page reste consultable, et
    verifier_entete() dira la vérité au prochain enregistrement.
    """
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return defaut


class FichierIllisible(RuntimeError):
    """Un fichier de réglages que YAML refuse — avec son nom."""


def lire_yaml(chemin: Path, defaut=None):
    """Relit un YAML du site, ou dit LEQUEL ne se relit pas.

    `yaml.safe_load` nu remontait un ScannerError jusqu'à la requête :
    l'atelier restait blanc, sans un mot, pour un `_menu.yaml` retouché
    à la main. L'exception ne nomme pas le fichier — c'est pourtant la
    seule chose qu'on ait besoin de savoir.
    """
    try:
        return yaml.safe_load(chemin.read_text(encoding='utf-8')) or defaut
    except (OSError, yaml.YAMLError) as souci:
        try:
            nom = chemin.relative_to(RACINE)
        except ValueError:
            nom = chemin
        raise FichierIllisible(f'{nom} ne se relit pas : {souci}') from souci


def limacon(t: str, defaut='page') -> str:
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode()
    t = re.sub(r"['’]", '-', t).lower()
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:70].rstrip('-') or defaut


def guillemets(v) -> str:
    """Échappe barre oblique et guillemet droit avant un « clé: "valeur" ».

    Le titre « Parution du 4éme livre : "Qu'est-ce que l'humain ?" »,
    recopié tel quel par « Jumelle », écrivait un en-tête que le YAML ne
    relisait plus : la régénération ENTIÈRE échouait sur cette page.
    Même échappement que `refaire_extrait`.
    """
    return str(v).replace('\\', '\\\\').replace('"', '\\"')


def dedans(chemin: Path, racine: Path) -> bool:
    """Le chemin reste-t-il sous la racine autorisée ?

    Sans ce garde-fou, un « ../../ » dans une requête écrirait n'importe
    où sur le disque. L'atelier tourne en local, mais un onglet malveillant
    peut lui parler comme n'importe qui d'autre.
    """
    try:
        chemin.resolve().relative_to(racine.resolve())
        return True
    except ValueError:
        return False


# =========================================================================
# Lecture / écriture du contenu
# =========================================================================

def separer(texte: str):
    if not texte.startswith('---'):
        return '', texte
    fin = texte.find('\n---', 3)
    if fin == -1:
        return '', texte
    return texte[3:fin].strip('\n'), texte[fin + 4:].lstrip('\n')


def valeur(entete: str, cle: str, defaut=''):
    """Lit une valeur de l'en-tête, guillemets d'échappement défaits.

    Un titre comme `"Parution du 4e livre : \\"Qu'est-ce que l'humain ?\\""`
    affichait ses barres obliques dans la liste.

    Un COMMENTAIRE de fin de ligne est écarté comme le ferait YAML : une
    valeur entre guillemets s'arrête au guillemet fermant, une valeur nue
    devant un « # » précédé d'un blanc. L'atelier lit l'en-tête au motif
    et non au parseur — sans cette règle, `jumelle_attendue: "non"  # …`
    se lisait « non"  # … » et le réglage ne prenait pas, alors que le
    générateur, lui, le voyait très bien. Deux lectures divergentes du
    même fichier : le pire des deux mondes.
    """
    m = re.search(rf'^{cle}:[ \t]*(.*)$', entete, re.M)
    if m is None:
        return defaut
    brut = m.group(1).strip()
    entre_guillemets = re.match(r'"((?:[^"\\]|\\.)*)"', brut)
    if entre_guillemets:
        brut = entre_guillemets.group(1)
    else:
        brut = re.sub(r'\s+#.*$', '', brut).strip()
    return brut.replace('\\"', '"').replace('\\\\', '\\')


def dossiers_de_langue():
    """Les dossiers de langue, dans l'ordre de config.yaml — la corbeille N'EN EST PAS UNE.

    Les trois endroits qui parcouraient `contenu/` prenaient tout ce qui
    est un dossier, point cachés compris. Dès que la corbeille contenait
    quelque chose, « .corbeille » apparaissait dans le choix des langues
    et ses pages jetées se mêlaient à la liste — ressuscitées à l'écran
    alors qu'on venait de les mettre au rebut.

    L'ordre alphabétique mettait l'anglais en tête dès son arrivée :
    l'atelier s'ouvrait sur les pages EN et le français passait sous la
    ligne de flottaison. C'est config.yaml qui dit l'ordre du site
    (fr, it, en) ; un dossier qui n'y figure pas se range à la fin.
    """
    ordre = {lg: i for i, lg in enumerate(config().get('langues') or {})}
    return sorted((p for p in CONTENU.iterdir()
                   if p.is_dir() and not p.name.startswith('.')),
                  key=lambda p: (ordre.get(p.name, len(ordre)), p.name))


def config():
    return lire_yaml(SITE / 'config.yaml', {})


def age_du_code() -> float:
    """La date du plus récent des fichiers dont dépend ce serveur."""
    dates = [(RACINE / f).stat().st_mtime for f in SOURCES_SUIVIES
             if (RACINE / f).is_file()]
    return max(dates, default=0.0)


CODE_AU_DEMARRAGE = age_du_code()

STATUTS = {'publie', 'brouillon'}
TYPES = {'page', 'fiche', 'collection', 'conteneur'}


def verifier_entete(entete: str, langues=None):
    """Relit l'en-tête comme le fera le générateur. Renvoie une plainte, ou None.

    L'atelier écrivait jusqu'ici l'en-tête TEL QUEL, sans le relire. Une
    apostrophe de trop dans un titre, un deux-points dans une date, et la
    page ne s'engendrait plus — sans un mot, et sans que rien ne le dise
    avant la régénération suivante. Le générateur, lui, lit ce YAML : le
    seul moment où l'on peut encore refuser proprement, c'est ici.
    """
    try:
        lu = yaml.safe_load(entete)
    except yaml.YAMLError as e:
        ligne = getattr(getattr(e, 'problem_mark', None), 'line', None)
        ou = f' (ligne {ligne + 1})' if ligne is not None else ''
        return f'les réglages ne se relisent pas{ou} : {getattr(e, "problem", e)}'
    if lu is None:
        return 'les réglages sont vides'
    if not isinstance(lu, dict):
        return 'les réglages doivent être une liste de « clé : valeur »'

    for cle in ('titre', 'langue', 'type'):
        if not str(lu.get(cle) or '').strip():
            return f'il manque « {cle} »'
    if lu['type'] not in TYPES:
        return f'type inconnu : « {lu["type"]} » — attendu {", ".join(sorted(TYPES))}'
    if langues and lu['langue'] not in langues:
        return f'langue inconnue : « {lu["langue"]} » — attendu {", ".join(langues)}'
    if str(lu.get('statut') or 'publie') not in STATUTS:
        return f'statut inconnu : « {lu["statut"]} » — attendu publie ou brouillon'

    d = lu.get('date')
    if d not in (None, ''):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(d)):
            return f'la date « {d} » ne s’écrit pas AAAA-MM-JJ'
    if lu['type'] == 'fiche' and not str(lu.get('collection') or '').strip():
        return 'une fiche doit dire à quelle collection elle appartient'

    # `rang` DOIT être un entier nu. Entre guillemets il reste une chaîne,
    # et le tri de la collection bute alors sur « str contre int » : c'est
    # toute la collection qui cesse de s'engendrer, pas la seule fiche.
    for cle in ('rang', 'ordre'):
        v = lu.get(cle)
        if v not in (None, '') and not isinstance(v, int):
            return (f'« {cle} » doit être un nombre sans guillemets '
                    f'— écrit ici {cle}: "{v}"')
    return None


def marquer_auto(entete: str) -> str:
    """La mention de traduction machine, si elle n'y est pas déjà.

    Même écriture que la case à cocher des Réglages : la ligne est posée
    ou absente, jamais mise à « non » — une clé absente et une clé à
    « non » disent la même chose, et deux façons de l'écrire divergent.
    """
    if re.search(r'^traduction_automatique:', entete, re.M):
        return entete
    return entete.rstrip('\n') + '\n\ntraduction_automatique: "oui"'


def cle_de_collection(langue: str, nom: str) -> str:
    f = CONTENU / langue / nom / '_index.md'
    if not f.is_file():
        return ''
    entete, _ = separer(f.read_text(encoding='utf-8'))
    try:
        return (yaml.safe_load(entete) or {}).get('traduction') or ''
    except yaml.YAMLError:
        return ''


def collection_jumelle(langue_source: str, nom: str, vers: str):
    """Le dossier de la MÊME rubrique dans l'autre langue, ou None.

    Les rubriques ne portent pas le même nom d'une langue à l'autre :
    `fr/temoignages-accompagne` est `it/testimonianze-pazienti`. Elles
    partagent en revanche une clé de traduction (« temoignages-patients »).
    « Jumelle » cherchait un dossier au MÊME nom : toute fiche italienne
    échouait sur « la collection testimonianze-pazienti n'existe pas
    encore en fr », y compris les trois que le tableau de bord réclame.
    """
    base = CONTENU / vers
    if not base.is_dir():
        return None
    cle = cle_de_collection(langue_source, nom)
    if cle:
        for d in sorted(base.iterdir()):
            if d.is_dir() and cle_de_collection(vers, d.name) == cle:
                return d
    d = base / nom                     # même nom : le cas simple
    return d if d.is_dir() else None


def menus():
    """Les menus du site, tels que le générateur les lit."""
    sortie = {}
    for d in dossiers_de_langue():
        f = d / '_menu.yaml'
        if f.exists():
            sortie[d.name] = lire_yaml(f, [])
    return sortie


def menu_a_plat(langue: str):
    """Le menu déplié en une liste, chaque entrée avec sa profondeur.

    Un arbre se manipule mal dans une page : monter une entrée d'un cran,
    la sortir de sa rubrique, cela se pense en LIGNES. L'arbre est donc
    aplati pour l'atelier et reconstruit à l'enregistrement.
    """
    f = CONTENU / langue / '_menu.yaml'
    if not f.exists():
        return []
    plat = []

    def marcher(entrees, profondeur):
        for e in entrees or []:
            plat.append({'titre': e.get('titre', ''),
                         'lien': e.get('lien', ''),
                         'profondeur': profondeur})
            marcher(e.get('entrees'), profondeur + 1)

    marcher(lire_yaml(f, []), 0)
    return plat


def menu_en_arbre(plat):
    """Refait l'arbre à partir des profondeurs. Renvoie (arbre, plainte)."""
    if not plat:
        return [], 'un menu vide effacerait la navigation du site'
    if plat[0].get('profondeur', 0) != 0:
        return None, 'la première entrée ne peut pas être en retrait'
    racine, pile = [], []
    for i, e in enumerate(plat, 1):
        titre = str(e.get('titre') or '').strip()
        if not titre:
            return None, f'l’entrée n° {i} n’a pas d’intitulé'
        p = int(e.get('profondeur') or 0)
        if p > len(pile):
            return None, (f'« {titre} » est en retrait de {p} alors que '
                          f'l’entrée du dessus ne le permet pas')
        del pile[p:]
        noeud = {'titre': titre}
        lien = str(e.get('lien') or '').strip()
        if lien:
            noeud['lien'] = lien
        (pile[-1].setdefault('entrees', []) if pile else racine).append(noeud)
        pile.append(noeud)

    # une entrée SANS lien et SANS enfant ne mène nulle part : le menu
    # afficherait un intitulé mort, cliquable pour rien.
    def verifier(noeuds, chemin=''):
        for n in noeuds:
            ou = f'{chemin} › {n["titre"]}' if chemin else n['titre']
            if not n.get('lien') and not n.get('entrees'):
                return f'« {ou} » n’a ni lien ni sous-entrée : elle ne mènerait nulle part'
            if n.get('entrees'):
                # une rubrique qui a des enfants ne porte pas de lien
                n.pop('lien', None)
                plainte = verifier(n['entrees'], ou)
                if plainte:
                    return plainte
        return None

    return racine, verifier(racine)


def ecrire_menu(langue: str, arbre) -> str:
    tete = ("# Menu du site — modifiable à la main ou depuis l'atelier.\n"
            '# Une entrée sans « lien » est un simple intitulé de rubrique.\n\n')
    lignes = []

    def poser(noeuds, retrait):
        for n in noeuds:
            marge = ' ' * retrait
            lignes.append(f'{marge}- titre: "{n["titre"].replace(chr(34), chr(92) + chr(34))}"')
            if n.get('lien'):
                lignes.append(f'{marge}  lien: "{n["lien"]}"')
            if n.get('entrees'):
                lignes.append(f'{marge}  entrees:')
                poser(n['entrees'], retrait + 4)
            if retrait == 0:
                lignes.append('')

    poser(arbre, 0)
    return tete + '\n'.join(lignes).rstrip('\n') + '\n'


# LES RANGS SONT ESPACÉS, ET C'EST TOUT LE SUJET. Collés — 1, 2, 3… — il
# n'y a aucune place entre deux fiches : insérer en tête obligeait à
# réécrire les 200 voisines, et supprimer à les resserrer. Une fiche
# créée touchait donc 201 fichiers, l'atelier annonçait « 203 à publier »
# pour trois pages, et le dépôt gagnait un commit de 201 fichiers — alors
# que le site engendré, lui, ne changeait pas d'un octet (l'ordre est le
# même, seuls les nombres avaient glissé). Mesuré le 01/09/2026.
#
# Espacés de PAS, on intercale sans toucher personne. MARGE réserve des
# crans AU-DESSUS du premier, pour que l'insertion en tête — le geste
# courant sur des témoignages classés du plus récent au plus ancien —
# trouve de la place MARGE fois avant qu'une renumérotation soit
# nécessaire.
PAS_RANG = 10
MARGE_RANG = 50


def rangs_de(dossier: Path):
    """[(rang, fichier, texte, position du nombre)], triés par rang."""
    fiches = []
    for f in sorted(dossier.glob('*.md')):
        if f.name == '_index.md':
            continue
        t = f.read_text(encoding='utf-8')
        m = re.search(r'^rang:\s*(\d+)\s*$', t, re.M)
        if m:
            fiches.append((int(m.group(1)), f, t, m))
    fiches.sort(key=lambda x: x[0])
    return fiches


def rang_jumelle(source: Path, dossier_source: Path, dossier_cible: Path) -> int:
    """Le rang qui donne à la jumelle LA MÊME PLACE qu'à son original.

    « Jumelle » posait la fiche neuve à la fin de sa rubrique — seul choix
    possible tant que les rangs étaient collés, puisque l'insérer ailleurs
    aurait bousculé toutes les voisines. Le résultat se voyait à l'œil :
    une fiche PREMIÈRE en français arrivait DERNIÈRE en italien, et les
    flèches de bas de page renvoyaient chacune à un texte différent — le
    français annonçait « Témoignage du 28 août 2026 → », l'italien
    « ← Testimonianza del 11 ottobre 2007 ». Deux ordres de lecture pour
    le même site.

    C'est la règle de outils/renumeroter_rangs.py, appliquée à la
    création : chaque fiche prend la place de sa jumelle. On repère les
    VOISINES de l'original, on cherche LEURS jumelles dans la rubrique
    d'arrivée, et l'on se glisse entre elles. Les rangs étant espacés, la
    place existe sans toucher personne.
    """
    def cle_de(f: Path) -> str:
        return valeur(separer(f.read_text(encoding='utf-8'))[0], 'traduction')

    voisines = rangs_de(dossier_source)
    place = next((i for i, (_, f, _, _) in enumerate(voisines) if f == source), None)
    arrivee = rangs_de(dossier_cible)
    if place is None or not arrivee:
        return (arrivee[-1][0] + PAS_RANG) if arrivee else MARGE_RANG * PAS_RANG

    cles = {cle_de(f): r for r, f, _, _ in arrivee if cle_de(f)}
    avant = next((cles[cle_de(f)] for _, f, _, _ in reversed(voisines[:place])
                  if cle_de(f) in cles), None)
    apres = next((cles[cle_de(f)] for _, f, _, _ in voisines[place + 1:]
                  if cle_de(f) in cles), None)

    if avant is None and apres is None:
        return arrivee[-1][0] + PAS_RANG
    if avant is None:
        return apres - PAS_RANG if apres - PAS_RANG >= 1 else max(1, apres // 2)
    if apres is None:
        return avant + PAS_RANG
    milieu = (avant + apres) // 2
    if milieu <= avant:                    # plus un cran de libre entre les deux
        espacer_rangs(dossier_cible)
        return rang_jumelle(source, dossier_source, dossier_cible)
    return milieu


def espacer_rangs(dossier: Path) -> int:
    """Réécrit les rangs espacés de PAS, en gardant l'ordre existant.

    Le seul geste qui touche encore toute une rubrique — et il ne sert
    que lorsqu'il n'y a plus de place en tête, soit une fois toutes les
    MARGE insertions. L'ORDRE N'EST PAS TOUCHÉ : le site engendré est
    identique après.
    """
    if not dossier.is_dir():
        return 0
    change = 0
    for i, (ancien, f, t, m) in enumerate(rangs_de(dossier)):
        neuf = (MARGE_RANG + i) * PAS_RANG
        if ancien != neuf:
            f.write_text(t[:m.start(1)] + str(neuf) + t[m.end(1):], encoding='utf-8')
            change += 1
    return change


def lister():
    """Toutes les pages, avec leur adresse publique.

    L'adresse est calculée EXACTEMENT comme dans site/generer.py : c'est
    par elle que l'atelier raccroche chaque page à son entrée de menu.
    """
    reglages = config()
    accueils = {lg: (m or {}).get('accueil')
                for lg, m in (reglages.get('langues') or {}).items()}
    sortie = []
    for dossier in dossiers_de_langue():
        langue = dossier.name
        for f in sorted(dossier.rglob('*.md')):
            entete, corps = separer(f.read_text(encoding='utf-8'))
            rel = str(f.relative_to(CONTENU))
            type_ = valeur(entete, 'type', 'page')
            slug = valeur(entete, 'slug') or f.stem
            if type_ == 'collection':
                url = f'/{langue}/{f.parent.name}/'
            elif type_ == 'fiche':
                url = f'/{langue}/{f.parent.name}/{f.stem}/'
            elif slug == accueils.get(langue):
                url = f'/{langue}/'
            else:
                url = f'/{langue}/{slug}/'
            sortie.append({
                'url': url,
                'lien': valeur(entete, 'lien'),
                'fichier': rel,
                'langue': langue,
                'titre': valeur(entete, 'titre') or f.stem,
                'type': valeur(entete, 'type', 'page'),
                'statut': valeur(entete, 'statut', 'publie'),
                'collection': valeur(entete, 'collection'),
                'date': valeur(entete, 'date'),
                'rang': entier(valeur(entete, 'rang')),
                'traduction_automatique': bool(valeur(entete, 'traduction_automatique')),
                'traduction': valeur(entete, 'traduction'),
                # « jumelle_attendue: non » : cette page n'a pas de
                # correspondante dans les autres langues, et c'est voulu.
                # Trois fiches italiennes sont des découpes de grandes
                # pages françaises qui, elles, existent bien : réclamer
                # leur jumelle revenait à demander de traduire deux fois
                # le même témoignage.
                'jumelle_attendue': str(valeur(entete, 'jumelle_attendue', 'oui')
                                        ).lower() not in ('non', 'false', 'no'),
                'signes': len(corps),
                # la date de l'en-tête est éditoriale (celle du témoignage) ;
                # celle-ci est celle du fichier — la seule qui dise ce qui
                # vient d'être touché.
                'modifie': f.stat().st_mtime,
            })

    # Une page « sans jumelle » est une page dont la clé de traduction ne
    # se retrouve dans AUCUNE autre langue — ou qui n'en a pas du tout.
    # Les conteneurs sont hors du compte : ils n'engendrent aucune page,
    # les signaler ne ferait que du bruit.
    langues_par_cle = {}
    for p in sortie:
        if p['traduction']:
            langues_par_cle.setdefault(p['traduction'], {})[p['langue']] = p
    toutes = list((reglages.get('langues') or {}))
    for p in sortie:
        soeurs = langues_par_cle.get(p['traduction'], {}) if p['traduction'] else {}
        p['jumelle'] = (p['type'] == 'conteneur' or len(soeurs) > 1)

        # L'ÉTAT DES TROIS LANGUES, lisible sans quitter l'arbre français :
        # traduite à la main, traduite par la machine, ou absente. C'est ce
        # que portent les pastilles F/I/E de chaque ligne — et le seul
        # moyen de voir qu'une page ajoutée d'un côté est restée seule.
        etat, jumelles = {}, {}
        for lg in toutes:
            soeur = soeurs.get(lg) if soeurs else (p if lg == p['langue'] else None)
            if not soeur:
                etat[lg] = 'absente'
                continue
            etat[lg] = 'auto' if soeur['traduction_automatique'] else 'humaine'
            jumelles[lg] = soeur['fichier']
        p['etat_langues'] = etat
        p['jumelles'] = jumelles

        # « Voir » ouvre la page ENGENDRÉE, pas le texte en cours d'écriture.
        # Tant qu'on n'a pas régénéré, on relit donc l'ancienne version — et
        # rien ne le disait : on croyait sa correction perdue. On compare ici
        # la date du fichier source à celle de la page produite.
        # Toutes les entrées n'engendrent pas une page : une RUBRIQUE ne
        # sert qu'au menu, et une annonce qui porte un « lien » renvoie
        # ailleurs — vers YouTube pour trois d'entre elles. Les signaler
        # comme « jamais engendrées » ferait avertir pour rien dix-neuf
        # fois sur sept cent trente.
        attendue = p['type'] != 'conteneur' and not p['lien']
        rendue = PUBLIC / p['url'].strip('/') / 'index.html'
        source = CONTENU / p['fichier']
        p['engendree'] = rendue.is_file() or not attendue
        p['a_jour'] = (not attendue or (rendue.is_file()
                       and rendue.stat().st_mtime >= source.stat().st_mtime))
    return sortie


# Apostrophes, guillemets, tirets et espaces ramenés à leur forme clavier.
# Le contenu mélange « l’espérance » (typographique, venue de WordPress) et
# « l'espérance » (droite, tapée ici) : la même phrase se trouvait ou non
# selon l'apostrophe. Le retour à la ligne devient un espace : une phrase
# à cheval sur deux lignes échouait aussi. Chaque remplacement garde LA
# MÊME LONGUEUR — chercher() découpe son extrait dans le texte brut avec
# les indices trouvés dans le texte aplati.
_EQUIVALENCES = str.maketrans({
    '’': "'", '‘': "'", '«': '"', '»': '"', '“': '"', '”': '"', '„': '"',
    '–': '-', '—': '-',
    '\u00a0': ' ', '\u202f': ' ', '\u2009': ' ', '\n': ' ', '\r': ' ', '\t': ' ',
})


def aplatir(t: str) -> str:
    """Sans accents ni casse : « éveil » doit répondre à « eveil » —
    et « l'espérance » à « l’espérance »."""
    t = unicodedata.normalize('NFKD', t.lower().translate(_EQUIVALENCES))
    return ''.join(c for c in t if not unicodedata.combining(c))


def suite_de_mots(plat: str, mots):
    """(début, fin) de la première suite des mots, dans l'ordre et presque
    collés (12 caractères d'écart au plus), ou None.

    « Seul les » doit trouver « Seuls les personnes » : la phrase exacte
    échoue pour une lettre, mais les mots sont là, dans l'ordre, à deux
    caractères près. Exiger l'ordre ET la quasi-adjacence est ce qui
    évite le bruit — un simple voisinage ramenait 32 pages pour « Seul
    les », « seul » vivant dans « seulement » et « les » traînant partout.
    """
    i = plat.find(mots[0])
    while i >= 0:
        pos, ok = i + len(mots[0]), True
        for m in mots[1:]:
            j = plat.find(m, pos, pos + 12 + len(m))
            if j < 0:
                ok = False
                break
            pos = j + len(m)
        if ok:
            return i, pos
        i = plat.find(mots[0], i + 1)
    return None


_cache = {}


def oublier_les_disparus(cache: dict, vus: set):
    """Retire du cache ce qui n'existe plus.

    Les caches ne gardaient que des ajouts : une page supprimée y restait
    jusqu'à l'arrêt du serveur, avec son texte entier — 54 000 mots pour
    la seule page Réflexions.
    """
    for mort in [k for k in cache if k not in vus]:
        cache.pop(mort, None)


def chercher(q: str, limite=60):
    """Cherche dans les TITRES et dans le TEXTE des pages.

    Filtrer sur les seuls titres ne trouvait pas « Krishnamurti », qui
    n'est le titre d'aucune page mais revient dans plusieurs Réflexions.
    Le contenu est gardé en mémoire et relu quand le fichier change.
    """
    besoin = re.sub(r'\s+', ' ', aplatir(q)).strip()
    if len(besoin) < 2:
        return []
    mots = [m for m in besoin.split(' ') if len(m) >= 2]
    trouves, vus = [], set()
    for f in sorted(CONTENU.rglob('*.md')):
        # la corbeille n'est pas le site : une page jetée ne doit plus
        # « se trouver » — elle gonflait le compte des résultats alors que
        # la liste, elle, l'écartait déjà.
        if any(part.startswith('.') for part in f.relative_to(CONTENU).parts):
            continue
        cle = str(f)
        vus.add(cle)
        mtime = f.stat().st_mtime
        if _cache.get(cle, (None,))[0] != mtime:
            entete, corps = separer(f.read_text(encoding='utf-8'))
            _cache[cle] = (mtime, valeur(entete, 'titre') or f.stem,
                           corps, aplatir(corps))
        _, titre, corps, plat = _cache[cle]
        dans_titre = besoin in aplatir(titre)
        rang = 1
        i = plat.find(besoin)
        fin = i + len(besoin) if i >= 0 else -1
        if i < 0 and not dans_titre and len(mots) > 1:
            # la phrase exacte échoue : la suite approchée, classée après
            bornes = suite_de_mots(plat, mots)
            if bornes:
                i, fin = bornes
                rang = 2
        if not dans_titre and i < 0:
            continue
        extrait = ''
        if i >= 0:
            d = max(0, i - 60)
            extrait = re.sub(r'\s+', ' ', corps[d:fin + 90]).strip()
            if d:
                extrait = '…' + extrait
        trouves.append({'fichier': str(f.relative_to(CONTENU)), 'titre': titre,
                        'ou': 'titre' if dans_titre else 'texte',
                        'rang': 0 if dans_titre else rang, 'extrait': extrait})
    # ON CLASSE PUIS ON COUPE, ET NON L'INVERSE. La coupe se faisait dans
    # l'ordre des noms de fichiers : une correspondance de TITRE au 61e
    # fichier n'apparaissait jamais, écartée par soixante correspondances
    # de texte moins bonnes qu'elle.
    oublier_les_disparus(_cache, vus)
    trouves.sort(key=lambda x: x['rang'])
    return trouves[:limite]


CORBEILLE = CONTENU / '.corbeille'


def lister_corbeille():
    """Ce que la corbeille contient — pages ET médias jetés, récents d'abord."""
    sortie = []
    if CORBEILLE.is_dir():
        for f in CORBEILLE.rglob('*.md'):
            entete, corps = separer(f.read_text(encoding='utf-8'))
            sortie.append({'fichier': str(f.relative_to(CORBEILLE)),
                           'titre': valeur(entete, 'titre') or f.stem,
                           'langue': f.parts[len(CORBEILLE.parts)] if len(f.parts) > len(CORBEILLE.parts) else '',
                           'signes': len(corps),
                           'jete': f.stat().st_mtime})
    if CORBEILLE_MEDIAS.is_dir():
        for f in CORBEILLE_MEDIAS.rglob('*'):
            if f.is_file():
                sortie.append({'fichier': str(f.relative_to(CORBEILLE_MEDIAS)),
                               'titre': f.name, 'langue': '', 'signes': 0,
                               'media': True, 'jete': f.stat().st_mtime})
    sortie.sort(key=lambda x: x['jete'], reverse=True)
    return sortie


CORBEILLE_MEDIAS = MEDIAS / '.corbeille'
TEXTES_MEDIAS = MEDIAS / '_textes.yaml'

# Le NOM affiché du type, et la famille qui sert de filtre. Les familles
# viennent du fonds réel — 107 images, 24 PDF, 1 mp3, 1 psd — et non d'une
# liste théorique : une rubrique « Vidéos » vide n'apprend rien.
TYPES_MEDIA = {
    '.jpg': ('JPEG', 'image'), '.jpeg': ('JPEG', 'image'), '.png': ('PNG', 'image'),
    '.gif': ('GIF', 'image'), '.webp': ('WEBP', 'image'), '.svg': ('SVG', 'image'),
    '.avif': ('AVIF', 'image'), '.pdf': ('PDF', 'pdf'), '.mp3': ('MP3', 'audio'),
    '.mp4': ('MP4', 'video'), '.odt': ('ODT', 'autre'), '.docx': ('DOCX', 'autre'),
    '.zip': ('ZIP', 'autre'), '.psd': ('PSD', 'autre'),
}


def cache_media(f: Path) -> bool:
    """Un fichier de medias/ qui n'est PAS un média.

    Les dossiers pointés (la corbeille) et les fichiers soulignés (le
    magasin des textes alternatifs) sont de la mécanique interne : ils ne
    se listent pas, et `site/generer.py` ne les publie pas non plus.
    """
    parts = f.relative_to(MEDIAS).parts
    return any(p.startswith('.') for p in parts) or f.name.startswith('_')


def lister_medias():
    sortie = []
    if MEDIAS.is_dir():
        for f in sorted(MEDIAS.rglob('*')):
            # le filtre sur le seul NOM laissait passer les dossiers pointés :
            # un fichier jeté dans medias/.corbeille/ serait resté listé.
            if f.is_file() and not cache_media(f):
                rel = str(f.relative_to(MEDIAS))
                sortie.append({'chemin': '/medias/' + rel, 'nom': f.name,
                               'poids': f.stat().st_size,
                               'image': f.suffix.lower() in IMAGES})
    sortie.sort(key=lambda x: x['chemin'], reverse=True)
    return sortie


_cache_refs = {}
_cache_dimensions = {}


def references_medias():
    """chemin public d'un média → les fichiers de contenu qui le citent.

    UNE seule définition de « utilisé », partagée par le garde-fou de la
    suppression et par le compte affiché sur chaque vignette. Les menus
    comptent autant que les pages : l'entrée de menu qui pointait vers le
    règlement intérieur aurait échappé à un contrôle limité aux pages.
    Le texte lu est gardé en mémoire et relu quand le fichier change.
    """
    refs, vus = {}, set()
    for f in sorted(CONTENU.rglob('*')):
        if not f.is_file() or f.suffix not in ('.md', '.yaml'):
            continue
        if any(p.startswith('.') for p in f.relative_to(CONTENU).parts):
            continue
        cle, mtime = str(f), f.stat().st_mtime
        vus.add(cle)
        if _cache_refs.get(cle, (None,))[0] != mtime:
            trouves = set(re.findall(r'/medias/[^)"\'\s\]>]+',
                                     f.read_text(encoding='utf-8')))
            _cache_refs[cle] = (mtime, trouves)
        for chemin in _cache_refs[cle][1]:
            refs.setdefault(chemin, []).append(str(f.relative_to(CONTENU)))
    oublier_les_disparus(_cache_refs, vus)
    return refs


def pages_qui_utilisent(chemin_public: str):
    return references_medias().get(chemin_public, [])


def dimensions(f: Path):
    """(largeur, hauteur) d'une image, ou None. 107 images en 0,05 s."""
    cle, mtime = str(f), f.stat().st_mtime
    if _cache_dimensions.get(cle, (None,))[0] != mtime:
        taille = None
        if f.suffix.lower() in IMAGES and f.suffix.lower() != '.svg':
            try:
                from PIL import Image
                with Image.open(f) as im:
                    taille = list(im.size)
            except Exception:
                taille = None
        _cache_dimensions[cle] = (mtime, taille)
    return _cache_dimensions[cle][1]


def charger_textes():
    """Le magasin des textes alternatifs, par chemin relatif de média.

    Le texte alternatif vivait DANS chaque page (`![texte](image)`) : la
    même image en portait un ici, aucun là — 32 insertions renseignées
    sur 57 —, et rien ne permettait d'en écrire un par langue. Il vit
    maintenant avec le fichier, une fois, en trois langues ; le
    générateur s'en sert pour remplir les `alt` laissés vides, sans
    jamais toucher à ceux qui sont écrits à la main dans le texte.
    """
    if not TEXTES_MEDIAS.is_file():
        return {}
    return lire_yaml(TEXTES_MEDIAS, {})


def enregistrer_textes(tous: dict):
    TEXTES_MEDIAS.parent.mkdir(parents=True, exist_ok=True)
    tete = ('# Textes alternatifs des médias, par langue — écrits depuis\n'
            "# l'atelier, lus par site/generer.py pour remplir les « alt »\n"
            '# vides. Ce fichier ne part PAS en ligne.\n\n')
    TEXTES_MEDIAS.write_text(
        tete + yaml.safe_dump(tous, allow_unicode=True, sort_keys=True),
        encoding='utf-8')


def index_medias():
    """Tout ce que la médiathèque affiche, en une fois.

    Le tri suit la date d'ajout, du plus récent au plus ancien : c'est ce
    qu'on vient chercher après un dépôt.
    """
    reglages = config()
    langues = list(reglages.get('langues') or {})
    refs = references_medias()
    pages = {p['fichier']: p for p in lister()}
    textes = charger_textes()

    fichiers, presents = [], set()
    for m in lister_medias():
        chemin = m['chemin']
        rel = chemin[len('/medias/'):]
        f = MEDIAS / rel
        presents.add(chemin)
        usages = []
        for source in refs.get(chemin, []):
            p = pages.get(source)
            usages.append({'fichier': source,
                           'titre': p['titre'] if p else source,
                           'langue': p['langue'] if p else source.split('/')[0],
                           'url': p['url'] if p else ''})
        usages.sort(key=lambda u: (u['langue'], u['titre']))
        nom_type, famille = TYPES_MEDIA.get(f.suffix.lower(),
                                            (f.suffix.lstrip('.').upper(), 'autre'))
        alt = textes.get(rel) or {}
        fichiers.append({
            'chemin': chemin, 'nom': f.name, 'dossier': str(Path(rel).parent),
            'annee': rel.split('/')[0] if '/' in rel else '',
            'type': nom_type, 'famille': famille, 'poids': f.stat().st_size,
            'dimensions': dimensions(f), 'ajoute': f.stat().st_mtime,
            'usages': usages, 'orphelin': not usages, 'existe': True,
            'alt': {lg: (alt.get(lg) or '') for lg in langues},
            'alt_auto': [lg for lg in (alt.get('auto') or []) if lg in langues],
        })
    fichiers.sort(key=lambda x: x['ajoute'], reverse=True)

    # Cité par une page mais absent du disque : une image cassée pour le
    # lecteur, et rien ne le disait. La carte prend la place du fichier.
    introuvables = []
    for chemin, sources in sorted(refs.items()):
        if chemin in presents:
            continue
        usages = [{'fichier': s, 'titre': pages[s]['titre'] if s in pages else s,
                   'langue': pages[s]['langue'] if s in pages else s.split('/')[0],
                   'url': pages[s]['url'] if s in pages else ''} for s in sources]
        nom = chemin.rsplit('/', 1)[-1]
        nom_type, famille = TYPES_MEDIA.get('.' + nom.rsplit('.', 1)[-1].lower(),
                                            ('?', 'autre'))
        introuvables.append({
            'chemin': chemin, 'nom': nom, 'dossier': '', 'annee': '',
            'type': nom_type, 'famille': famille, 'poids': 0,
            'dimensions': None, 'ajoute': 0, 'usages': usages,
            'orphelin': False, 'existe': False,
            'alt': {lg: '' for lg in langues}, 'alt_auto': [],
        })

    tout = fichiers + introuvables
    familles = {}
    for m in fichiers:
        familles[m['famille']] = familles.get(m['famille'], 0) + 1
    annees = {}
    for m in fichiers:
        if m['annee']:
            annees[m['annee']] = annees.get(m['annee'], 0) + 1
    return {
        'medias': tout, 'langues': langues,
        'total': len(fichiers), 'poids': sum(m['poids'] for m in fichiers),
        'utilisees': sum(1 for m in fichiers if not m['orphelin']),
        'orphelines': sum(1 for m in fichiers if m['orphelin']),
        'introuvables': len(introuvables),
        'familles': familles, 'annees': annees,
    }


def rendre_apercu(corps: str) -> str:
    """Rend le Markdown EXACTEMENT comme le fait le générateur."""
    # SANS CE GARDE, une entrée de plus À CHAQUE APERÇU : mesuré, 200
    # aperçus laissaient 200 fois le même dossier dans sys.path, que tout
    # import ultérieur balaie.
    if str(SITE) not in sys.path:
        sys.path.insert(0, str(SITE))
    import generer
    md = generer.fabriquer_convertisseur()
    return str(generer.rendre(md, corps))



# =========================================================================
# L'historique : chaque enregistrement laisse une trace
# =========================================================================
# La corbeille rattrape une page jetée. Elle ne rattrape RIEN d'un
# paragraphe supprimé puis enregistré — et c'est la faute la plus banale.
# Chaque écriture de l'atelier devient donc une version, dans le dépôt git
# du site, qu'on peut relire et rétablir depuis l'éditeur.
#
# La forme employée est « git commit -- <chemins> » : elle ne valide QUE
# ces fichiers-là et laisse l'index tranquille. Sans cela, l'atelier
# emporterait dans sa version le travail en cours de quelqu'un d'autre —
# deux sessions écrivent parfois dans ce dossier en même temps.

_depot_verifie = None


def version_du_moteur() -> str:
    """La version du moteur que ce site porte.

    Un site est une COPIE du moteur : sans ce numéro, impossible de savoir
    lequel il porte, ni si une correction faite ailleurs l'a atteint.
    `moteur.json` fait foi ; le fichier VERSION est le repli.
    """
    carte = RACINE / 'moteur.json'
    if carte.is_file():
        try:
            v = json.loads(carte.read_text(encoding='utf-8')).get('version')
            if v:
                return str(v)
        except json.JSONDecodeError:
            pass
    f = RACINE / 'VERSION'
    return f.read_text(encoding='utf-8').strip() if f.is_file() else ''


def est_un_depot() -> bool:
    """Le site est-il versionné ? Sinon, l'historique n'existe pas."""
    global _depot_verifie
    if _depot_verifie is None:
        if str(config().get('historique', 'oui')).lower() in ('non', 'false', 'no'):
            _depot_verifie = False
        else:
            r = git('rev-parse', '--is-inside-work-tree')
            _depot_verifie = r is not None and r.strip() == 'true'
    return _depot_verifie


def git(*arguments, entree=None):
    """Lance git dans le dossier du site. Renvoie sa sortie, ou None."""
    try:
        r = subprocess.run(['git', *arguments], cwd=str(RACINE), input=entree,
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def journaliser(message: str, *chemins: Path):
    """Enregistre une version des fichiers donnés. Silencieuse si elle échoue.

    Une écriture ne doit JAMAIS échouer parce que l'historique n'a pas
    marché : le texte de l'auteur passe avant sa trace.
    """
    if not est_un_depot():
        return None
    relatifs = []
    for c in chemins:
        try:
            relatifs.append(str(Path(c).resolve().relative_to(RACINE.resolve())))
        except (ValueError, OSError):
            continue
    if not relatifs:
        return None
    git('add', '--', *relatifs)
    # « --only » : ne valide que ces chemins, quoi qu'il y ait dans l'index.
    sortie = git('commit', '--only', '--allow-empty-message', '-m',
                 f'atelier : {message}', '--', *relatifs)
    return sortie is not None


def versions(rel: str, limite=40):
    """Les versions successives d'un fichier, la plus récente d'abord."""
    if not est_un_depot():
        return []
    sortie = git('log', f'-{limite}', '--format=%H\x1f%at\x1f%s', '--', rel)
    if not sortie:
        return []
    lot = []
    for ligne in sortie.strip().splitlines():
        morceaux = ligne.split('\x1f')
        if len(morceaux) == 3:
            lot.append({'version': morceaux[0], 'quand': int(morceaux[1]),
                        'message': morceaux[2]})
    return lot


def contenu_a_la_version(rel: str, version: str):
    """Le texte du fichier tel qu'il était à cette version, ou None."""
    if not est_un_depot() or not re.fullmatch(r'[0-9a-f]{7,40}', version):
        return None
    return git('show', f'{version}:{rel}')

# =========================================================================
# Serveur
# =========================================================================

class Atelier(BaseHTTPRequestHandler):
    server_version = 'Atelier'
    # HTTP/1.0 rouvrait une connexion PAR fichier : une page d'aperçu en
    # réclame une trentaine. Sûr ici parce que repondre() pose toujours
    # un Content-Length exact et que servir() garantit une réponse.
    protocol_version = 'HTTP/1.1'
    verrou = threading.Lock()

    def log_message(self, format, *args):
        # `str()` n'est PAS décoratif : send_error() du socle appelle
        # log_error('code %d, …', code, …) — args[0] est alors un entier.
        # Le « in » levait un TypeError EN PLEIN ENVOI de l'erreur, et le
        # client ne recevait plus rien du tout (mesuré : HTTP 000 sur une
        # méthode non gérée).
        if args and '/api/' in str(args[0]):
            sys.stderr.write(f'  {args[0]}\n')

    # --- utilitaires de réponse ---
    def repondre(self, code, corps=b'', type_mime='application/json; charset=utf-8',
                 muselee=False):
        self.repondu = True          # pour ne jamais répondre deux fois
        self.send_response(code)
        self.send_header('Content-Type', type_mime)
        # « nosniff » : le navigateur s'en tient au type annoncé au lieu
        # de deviner d'après le contenu — un .png qui commence par « <svg »
        # ne devient pas une page.
        self.send_header('X-Content-Type-Options', 'nosniff')
        if muselee:
            self.send_header('Content-Security-Policy',
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "img-src data:; sandbox")
        self.send_header('Content-Length', str(len(corps)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(corps)

    def json(self, donnees, code=200):
        self.repondre(code, json.dumps(donnees, ensure_ascii=False).encode('utf-8'))

    def erreur(self, message, code=400):
        self.json({'erreur': message}, code)

    def corps_requete(self):
        """Le corps de la requête, ou None s'il est inacceptable.

        `int()` nu levait un ValueError sur un Content-Length illisible ;
        et un NOMBRE NÉGATIF passait le test de taille pour finir en
        `rfile.read(-1)`, qui lit jusqu'à la fin du flux — c'est-à-dire
        jamais si le client ne ferme pas. Mesuré : un fil bloqué, aucune
        réponse. On borne des deux côtés.
        """
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return None
        if not 0 <= n <= TAILLE_MAX:
            return None
        return self.rfile.read(n)

    # UNE PLAINTE DOIT ARRIVER JUSQU'À L'ÉCRAN. Un réglage illisible
    # remontait en trace dans le terminal et laissait la page blanche :
    # on cherchait la panne du côté de l'atelier alors qu'un fichier du
    # site portait une virgule de trop.
    # LES HÔTES ADMIS. Le contrôle d'Origin garde les ÉCRITURES ; il ne
    # garde rien des lectures. Un nom de domaine que l'attaquant fait
    # pointer sur 127.0.0.1 (rebasculement DNS) rend l'atelier
    # « même origine » pour sa page : la politique du navigateur ne
    # protège plus, et tout le contenu se lit. Mesuré avec un simple
    # « Host: evil.example » — le fichier arrivait en entier.
    HOTES = {'localhost', '127.0.0.1', '::1', ''}

    def hote_inattendu(self):
        hote = (self.headers.get('Host') or '').strip()
        if hote.startswith('['):                    # [::1]:8413
            hote = hote[1:hote.find(']')] if ']' in hote else hote
        elif ':' in hote:
            hote = hote.rsplit(':', 1)[0]
        return hote.lower() not in self.HOTES

    def servir(self, quoi):
        """Achemine, et garantit qu'une réponse part TOUJOURS.

        Sans cela, la moindre exception laissait le navigateur attendre
        une réponse qui ne venait pas — et, en HTTP/1.1, la connexion
        dans un état dont il ne se remet pas. Une panne se lit à l'écran
        ou elle n'existe pas.
        """
        self.repondu = False
        if self.hote_inattendu():
            return self.erreur(
                'requête refusée : elle ne s’adresse pas à « localhost »', 403)
        try:
            return quoi()
        except FichierIllisible as souci:
            message = str(souci)
        except Exception as souci:                      # noqa: BLE001
            message = f'{type(souci).__name__} : {souci}'
            sys.stderr.write(f'  ✗ {self.path} — {message}\n')
        if self.repondu:
            return None
        return self.erreur(message, 500)

    def do_GET(self):
        return self.servir(self.acheminer_get)

    def do_POST(self):
        return self.servir(self.acheminer_post)

    # --- GET ---
    def acheminer_get(self):
        u = urlparse(self.path)
        chemin, q = unquote(u.path), parse_qs(u.query)

        if chemin == '/':
            return self.fichier_interface('index.html')
        if chemin.startswith('/atelier/'):
            return self.fichier_interface(chemin[len('/atelier/'):])
        if chemin.startswith('/medias/'):
            reste = chemin[len('/medias/'):]
            cible = MEDIAS / reste
            # LES DÉCLINAISONS SONT FABRIQUÉES, PAS DÉPOSÉES. Les versions
            # réduites (…-480.webp) naissent à la régénération et ne vivent
            # que dans le site engendré. L'aperçu, qui sert /medias/ depuis
            # la SOURCE, les manquait toutes : deux 404 par page sur
            # l'accueil, et des images adaptatives jamais éprouvées ici
            # alors qu'elles répondent très bien en ligne. Le navigateur
            # se rabattait sur l'original, si bien que rien ne se voyait.
            if dedans(cible, MEDIAS) and not cible.is_file():
                fabriquee = PUBLIC / 'medias' / reste
                if dedans(fabriquee, PUBLIC) and fabriquee.is_file():
                    return self.fichier_brut(fabriquee, PUBLIC, muselee=True)
            return self.fichier_brut(cible, MEDIAS)
        if chemin.startswith('/apercu/'):
            return self.fichier_site(chemin[len('/apercu/'):])

        if chemin == '/api/chercher':
            return self.json({'resultats': chercher((q.get('q') or [''])[0])})
        if chemin == '/api/corbeille':
            return self.json({'corbeille': lister_corbeille()})
        if chemin == '/api/menu':
            lg = (q.get('langue') or ['fr'])[0]
            return self.json({'entrees': menu_a_plat(lg),
                              'pages': [{'url': p['url'], 'titre': p['titre']}
                                        for p in lister()
                                        if p['langue'] == lg and p['statut'] == 'publie'],
                              'medias': [m['chemin'] for m in lister_medias()
                                         if not m['image']]})
        if chemin == '/api/medias':
            return self.json(index_medias())
        if chemin == '/api/liste':
            reglages = config()
            pages = lister()
            # ce qui est écrit mais pas encore visible par les autres
            marque = SITE / '.derniere-publication'
            depuis = marque.stat().st_mtime if marque.is_file() else 0
            en_attente = sum(1 for p in pages
                             if (CONTENU / p['fichier']).stat().st_mtime > depuis)
            # On ne pose pas une question dont la réponse est unique :
            # sans clé d'API, le moteur distant n'existe pas et l'atelier
            # traduit en local sans rien demander.
            import traduire
            return self.json({'pages': pages, 'medias': lister_medias(),
                              'menus': menus(),
                              'ia_distante': bool(traduire.cle_distante()),
                              'code_perime': age_du_code() > CODE_AU_DEMARRAGE,
                              'langues': [p.name for p in dossiers_de_langue()],
                              # Le nom et le domaine viennent de config.yaml,
                              # jamais du code : la fenêtre de publication doit
                              # annoncer le site qu'elle va RÉELLEMENT écraser.
                              # Écrits en dur, ils mentaient dès qu'on pointait
                              # l'atelier sur un autre site.
                              'site': {'titre': reglages.get('titre') or 'Le site',
                                       'domaine': reglages.get('domaine') or '',
                                       'moteur': version_du_moteur()},
                              'jamais_publie': not marque.is_file(),
                              'en_attente': en_attente,
                              'derniere_publication': (marque.read_text(encoding='utf-8')
                                                       if marque.is_file() else '')})
        if chemin == '/api/historique':
            rel = (q.get('f') or [''])[0]
            cible = CONTENU / rel
            if not rel or not dedans(cible, CONTENU):
                return self.erreur('fichier introuvable', 404)
            return self.json({'versions': versions(str((CONTENU / rel).relative_to(RACINE))),
                              'possible': est_un_depot()})
        if chemin == '/api/version':
            rel = (q.get('f') or [''])[0]
            v = (q.get('v') or [''])[0]
            cible = CONTENU / rel
            if not rel or not dedans(cible, CONTENU):
                return self.erreur('fichier introuvable', 404)
            texte = contenu_a_la_version(str(cible.relative_to(RACINE)), v)
            if texte is None:
                return self.erreur('version introuvable', 404)
            entete, corps = separer(texte)
            return self.json({'entete': entete, 'corps': corps})
        if chemin == '/api/lire':
            f = (q.get('f') or [''])[0]
            cible = CONTENU / f
            if not f or not dedans(cible, CONTENU) or not cible.is_file():
                return self.erreur('fichier introuvable', 404)
            entete, corps = separer(cible.read_text(encoding='utf-8'))
            return self.json({'fichier': f, 'entete': entete, 'corps': corps})

        # Le site engendré s'attend à vivre à la RACINE : ses feuilles de
        # style, ses polices et ses liens s'écrivent « /assets/… » et
        # « /fr/… ». Monté sous « /apercu/ », il réclamait donc des adresses
        # que l'atelier ne servait pas — la page arrivait sans style, sans
        # police, et chacun de ses liens menait à un 404. Tout ce qui n'est
        # pas une route de l'atelier est donc cherché dans le site engendré.
        return self.fichier_site(chemin.lstrip('/'))

    # --- POST ---
    def origine_refusee(self):
        """Un ordre d'écriture doit venir de l'atelier lui-même.

        Les navigateurs joignent l'en-tête « Origin » à tout envoi : une
        page web quelconque, ouverte dans le même navigateur pendant que
        l'atelier tourne, pouvait sinon lui adresser des ordres — écrire,
        jeter, déposer chez nous. Les CHEMINS étaient gardés (dedans()),
        la PROVENANCE ne l'était pas. Un outil local (curl) n'envoie pas
        d'Origin : l'absence reste admise. Renvoie l'origine fautive, ou
        None si l'ordre est recevable.
        """
        origine = self.headers.get('Origin')
        if origine is None:
            return None
        port = self.server.server_address[1]
        if origine in (f'http://localhost:{port}', f'http://127.0.0.1:{port}'):
            return None
        return origine

    def acheminer_post(self):
        origine = self.origine_refusee()
        if origine:
            return self.erreur(
                f'ordre refusé : il vient de « {origine} », pas de l’atelier', 403)
        u = urlparse(self.path)
        chemin = unquote(u.path)
        brut = self.corps_requete()
        if brut is None:
            return self.erreur('contenu trop gros', 413)

        if chemin == '/api/televerser':
            return self.televerser(brut)

        try:
            d = json.loads(brut or b'{}')
        except json.JSONDecodeError:
            return self.erreur('JSON illisible')

        if chemin == '/api/apercu':
            return self.json({'html': rendre_apercu(d.get('corps', ''))})
        if chemin == '/api/ecrire':
            return self.ecrire(d)
        if chemin == '/api/creer':
            return self.creer(d)
        if chemin == '/api/supprimer':
            return self.supprimer(d)
        if chemin == '/api/generer':
            return self.generer()
        if chemin == '/api/publier':
            return self.publier(d)
        if chemin == '/api/jumelle':
            return self.jumelle(d)
        if chemin == '/api/traduire':
            return self.traduire(d)
        if chemin == '/api/supprimer-media':
            return self.supprimer_media(d)
        if chemin == '/api/media-texte':
            return self.media_texte(d)
        if chemin == '/api/renommer-media':
            return self.renommer_media(d)
        if chemin == '/api/restaurer-media':
            return self.restaurer_media(d)
        if chemin == '/api/vider-corbeille':
            return self.vider_corbeille()
        if chemin == '/api/menu':
            return self.enregistrer_menu(d)
        if chemin == '/api/retablir':
            return self.retablir(d)
        if chemin == '/api/restaurer':
            return self.restaurer(d)
        if chemin == '/api/renommer':
            return self.renommer(d)
        return self.erreur('inconnu', 404)

    # --- actions ---
    def ecrire(self, d):
        f = d.get('fichier', '')
        cible = CONTENU / f
        if not f or not dedans(cible, CONTENU) or not cible.is_file():
            return self.erreur('fichier introuvable', 404)
        entete = (d.get('entete') or '').strip('\n')
        corps = (d.get('corps') or '').strip('\n')
        plainte = verifier_entete(entete, list(config().get('langues') or {}))
        if plainte:
            return self.erreur(f'Réglages : {plainte}. Rien n’a été enregistré.')

        # L'EXTRAIT est refait à chaque enregistrement d'une fiche. C'est
        # lui qui remplit la carte dans la liste de la rubrique : une fiche
        # écrite depuis l'atelier n'en avait aucun, et sa carte sortait nue,
        # titre seul. Le laisser figé serait pire encore — on corrigerait le
        # texte et la carte continuerait d'annoncer l'ancien.
        entete = self.refaire_extrait(entete, corps)

        # LA CLÉ D'APPARIEMENT NE SE PERD PAS PAR UN ENREGISTREMENT.
        # « Jumelle » écrit `traduction:` dans la page D'ORIGINE, sur le
        # disque, pendant que l'éditeur garde en mémoire l'en-tête d'avant.
        # Le premier « Enregistrer » qui suivait réécrivait donc le fichier
        # sans la clé, et les trois langues devenaient orphelines l'une de
        # l'autre — constaté sur « Test 6 » le 01/09/2026 : les jumelles
        # écrites à 15:29:20, le français réécrit sans clé à 15:29:41.
        # Une clé présente sur le disque et absente de ce qu'on reçoit est
        # une PERTE, jamais une intention : on la garde.
        ancienne, _ = separer(cible.read_text(encoding='utf-8'))
        cle_disque = valeur(ancienne, 'traduction')
        if cle_disque and not valeur(entete, 'traduction'):
            entete = re.sub(r'^traduction:.*$\n?', '', entete, flags=re.M).rstrip('\n')
            entete += f'\ntraduction: "{guillemets(cle_disque)}"'

        with self.verrou:
            cible.write_text(f'---\n{entete}\n---\n\n{corps}\n', encoding='utf-8')
        journaliser(f'{f} modifiée', cible)
        return self.json({'ok': True, 'fichier': f})

    @staticmethod
    def refaire_extrait(entete: str, corps: str) -> str:
        lu = yaml.safe_load(entete) or {}
        if lu.get('type') != 'fiche':
            return entete
        if str(RACINE / 'outils') not in sys.path:   # une entrée par enregistrement, sinon
            sys.path.insert(0, str(RACINE / 'outils'))
        from importer import extrait_de
        neuf = extrait_de(corps).replace('\\', '\\\\').replace('"', '\\"')
        ligne = f'extrait: "{neuf}"'
        if re.search(r'^extrait:', entete, re.M):
            return re.sub(r'^extrait:.*$', ligne, entete, count=1, flags=re.M)
        return entete.rstrip('\n') + '\n' + ligne

    def creer(self, d):
        langue = d.get('langue', 'fr')
        titre = (d.get('titre') or '').strip()
        collection = d.get('collection') or ''
        if not titre:
            return self.erreur('il faut un titre')
        # la langue se vérifie AVANT tout geste : la branche « fiche » pousse
        # les rangs des voisines d'un cran, un refus tardif les laisserait
        # décalés — et une langue inventée créerait un dossier fantôme.
        if langue not in (config().get('langues') or {}):
            return self.erreur(f'langue inconnue : « {langue} »')
        slug = limacon(titre)
        aujourdhui = date.today().isoformat()

        if collection:
            dossier = CONTENU / langue / collection
            if not dossier.is_dir():
                return self.erreur('collection inconnue')
            rangs = []
            for x in dossier.glob('*.md'):
                m = re.match(r'(\d+)-', x.name)
                if m:
                    rangs.append(int(m.group(1)))
            numero = max(rangs, default=0) + 1

            # Le RANG est l'ordre d'affichage ; le NUMÉRO en tête du nom de
            # fichier n'est qu'un identifiant. Les deux coïncidaient à
            # l'import, ils divergent dès la première insertion — et c'est
            # voulu : le nom du fichier EST l'adresse de la page. Renuméroter
            # les fichiers pour suivre l'ordre changerait les 199 adresses
            # d'un coup, et tous les liens qui y mènent.
            en_tete = d.get('place', 'tete') != 'fin'
            voisines = rangs_de(dossier)
            if en_tete:
                # Les témoignages vont du plus récent au plus ancien : le
                # nouveau se glisse AVANT le premier, dans l'espace que la
                # marge lui réserve. Aucune voisine n'est touchée — c'est
                # tout l'intérêt des rangs espacés.
                premier = voisines[0][0] if voisines else (MARGE_RANG + 1) * PAS_RANG
                rang = premier - PAS_RANG
                if rang < PAS_RANG:
                    # plus de place au-dessus : on ré-espace la rubrique une
                    # fois — l'ordre ne bouge pas, le site engendré non plus
                    espacer_rangs(dossier)
                    rang = rangs_de(dossier)[0][0] - PAS_RANG
            else:
                rang = (voisines[-1][0] + PAS_RANG) if voisines else PAS_RANG

            cible = dossier / f'{numero:03d}-{slug}.md'

            # LA FICHE NEUVE SUIT L'USAGE DE SA RUBRIQUE. Dans les
            # témoignages, le titre porte déjà la date : 170 fiches sur 199
            # la cachent (`date_precision: "cachee"` — elle classe, elle ne
            # s'affiche plus). Sans cet héritage, chaque fiche créée ici
            # affichait sa date en double au-dessus du titre, et Christophe
            # devait la retirer à la main — demandé le 28/08/2026. La
            # majorité des voisines décide : une rubrique qui affiche ses
            # dates continue de les afficher.
            cachees = sum(1 for y in dossier.glob('*.md')
                          if not y.name.startswith('_')
                          and 'date_precision: "cachee"' in y.read_text(encoding='utf-8'))
            total = sum(1 for y in dossier.glob('*.md') if not y.name.startswith('_'))
            precision = ('date_precision: "cachee"\n'
                         if total and cachees > total / 2 else '')
            entete = (f'titre: "{guillemets(titre)}"\nlangue: "{langue}"\ntype: "fiche"\n'
                      f'collection: "{collection}"\ndate: "{aujourdhui}"\n'
                      f'{precision}'
                      f'rang: {rang}\nstatut: "brouillon"')
        else:
            cible = CONTENU / langue / f'{slug}.md'
            entete = (f'titre: "{guillemets(titre)}"\nlangue: "{langue}"\ntype: "page"\n'
                      f'slug: "{slug}"\ndate: "{aujourdhui}"\nstatut: "brouillon"')

        # relu comme le générateur le lira — même garde-fou qu'« Enregistrer ».
        # Attrape aussi une langue inconnue, qui créerait un dossier fantôme.
        plainte = verifier_entete(entete, list(config().get('langues') or {}))
        if plainte:
            return self.erreur(f'Réglages : {plainte}. Rien n’a été créé.')
        if cible.exists():
            return self.erreur('une page porte déjà ce nom')
        if not dedans(cible, CONTENU):
            return self.erreur('chemin refusé')
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(f'---\n{entete}\n---\n\n', encoding='utf-8')
        journaliser(f'{cible.relative_to(CONTENU)} créée',
                    cible if not collection else cible.parent)
        return self.json({'ok': True, 'fichier': str(cible.relative_to(CONTENU))})

    def supprimer(self, d):
        """Ne supprime pas : déplace dans site/contenu/.corbeille/.

        Une page effacée par erreur se rattrape ; un fichier détruit, non.
        """
        f = d.get('fichier', '')
        cible = CONTENU / f
        if not f or not dedans(cible, CONTENU) or not cible.is_file():
            return self.erreur('fichier introuvable', 404)
        corbeille = CONTENU / '.corbeille' / f
        corbeille.parent.mkdir(parents=True, exist_ok=True)
        if corbeille.exists():
            corbeille = corbeille.with_name(
                f'{corbeille.stem}-{date.today().isoformat()}{corbeille.suffix}')
        shutil.move(str(cible), str(corbeille))
        # ON NE RESSERRE PLUS. Avec des rangs espacés, le trou laissé par
        # une fiche ôtée est exactement la place où la suivante s'insérera.
        # Resserrer réécrivait toute la rubrique pour ne rien changer à
        # l'ordre — 200 fichiers touchés pour une suppression.
        resserres = 0
        journaliser(f'{f} mise à la corbeille', cible)
        return self.json({'ok': True, 'corbeille': str(corbeille.relative_to(CONTENU)),
                          'rangs_resserres': resserres})

    def televerser(self, brut):
        nom = unquote(self.headers.get('X-Nom-Fichier') or '')
        nom = Path(nom).name
        ext = Path(nom).suffix.lower()
        if not nom or ext not in ACCEPTES:
            return self.erreur(f'type refusé ({ext or "sans extension"})')

        # REMPLACER un fichier existant : le contenu change, l'adresse ne
        # bouge pas — sinon toutes les pages qui le citent pointeraient
        # dans le vide. D'où l'exigence de la même extension.
        remplace = unquote(self.headers.get('X-Remplacer') or '')
        if remplace:
            if not remplace.startswith('/medias/'):
                return self.erreur('chemin inattendu')
            cible = MEDIAS / remplace[len('/medias/'):]
            if not dedans(cible, MEDIAS) or not cible.is_file():
                return self.erreur('fichier à remplacer introuvable', 404)
            if cible.suffix.lower() != ext:
                return self.erreur(
                    f'le remplaçant doit être un {cible.suffix.lstrip(".").upper()} '
                    f'— l’adresse du fichier ne doit pas changer')
            with self.verrou:
                cible.write_bytes(brut)
            reduite = self.reduire_image(cible) if ext in IMAGES else None
            return self.json({'ok': True, 'chemin': remplace, 'remplace': True,
                              'image': ext in IMAGES,
                              'poids': cible.stat().st_size, 'reduite': reduite})

        aujourd = date.today()
        dossier = MEDIAS / f'{aujourd.year}' / f'{aujourd.month:02d}'
        dossier.mkdir(parents=True, exist_ok=True)
        # CHOISIR LE NOM ET ÉCRIRE SOUS LE MÊME VERROU. La médiathèque
        # permet de déposer plusieurs fichiers d'un coup : deux envois
        # portant le même nom voyaient tous deux la place libre, et le
        # second écrasait le premier sans un mot.
        with self.verrou:
            tronc = limacon(Path(nom).stem, 'fichier')
            cible, n = dossier / (tronc + ext), 2
            while cible.exists():
                cible = dossier / f'{tronc}-{n}{ext}'
                n += 1
            if not dedans(cible, MEDIAS):
                return self.erreur('chemin refusé')
            cible.write_bytes(brut)
        reduite = self.reduire_image(cible) if ext in IMAGES else None
        return self.json({'ok': True, 'chemin': '/medias/' + str(cible.relative_to(MEDIAS)),
                          'image': ext in IMAGES, 'poids': cible.stat().st_size,
                          'reduite': reduite})

    def reduire_image(self, cible: Path):
        """Ramène une photo à LARGEUR_MAX. Renvoie ce qui a été fait, ou None.

        Un téléphone photographie en 4000 px et 4 Mo. Déposée telle quelle,
        l'image partait en ligne à cette taille : le site ne l'affiche
        jamais au-delà de 1 120 px, mais le lecteur la télécharge entière,
        souvent sur une connexion mobile. 1 600 px laisse de la marge pour
        la visionneuse et pour les écrans à forte densité.

        Le SVG n'est pas une image à pixels et ne se redimensionne pas ;
        les fichiers déjà petits sont laissés tels quels — les réenregistrer
        ne ferait que perdre de la qualité pour rien.
        """
        if cible.suffix.lower() == '.svg':
            return None
        try:
            from PIL import Image
        except ImportError:
            return None
        try:
            im = Image.open(cible)
            avant_l, avant_h = im.size
            avant_poids = cible.stat().st_size
            if avant_l <= LARGEUR_MAX:
                return None
            hauteur = round(avant_h * LARGEUR_MAX / avant_l)
            im = im.convert('RGB') if cible.suffix.lower() in ('.jpg', '.jpeg') else im
            im.resize((LARGEUR_MAX, hauteur), Image.LANCZOS).save(
                cible, quality=86, optimize=True)
            return {'avant': f'{avant_l}×{avant_h}', 'apres': f'{LARGEUR_MAX}×{hauteur}',
                    'octets_avant': avant_poids, 'octets_apres': cible.stat().st_size}
        except Exception:
            # une image illisible n'est pas une raison de perdre le dépôt
            return None

    def generer(self):
        try:
            with self.verrou:
                r = subprocess.run([sys.executable, str(SITE / 'generer.py')],
                                   capture_output=True, text=True,
                                   cwd=str(RACINE), timeout=900)
                v = subprocess.run([sys.executable, str(RACINE / 'outils' / 'verifier.py')],
                                   capture_output=True, text=True,
                                   cwd=str(RACINE), timeout=900)
        except subprocess.TimeoutExpired as souci:
            return self.erreur(f'{Path(souci.cmd[1]).name} ne rend pas la main '
                               f'(15 min) — interrompu.', 504)
        return self.json({'ok': r.returncode == 0,
                          'sortie': r.stdout + r.stderr,
                          'verification': v.stdout + v.stderr})

    def publier(self, d):
        """Dépose le site — sur le serveur d'essai, ou chez l'hébergeur.

        DEUX DESTINATIONS, et elles ne se valent pas. « maison » est le
        serveur d'essai : on y dépose vingt fois par jour sans conséquence.
        « en-ligne » est le site que le monde voit — il écrase l'existant et
        efface de l'hébergeur tout fichier absent d'ici.

        D'où trois verrous sur la seconde, et aucun sur la première :
          - le dépôt réel doit être demandé (« pour_de_vrai ») ;
          - la phrase « je publie en ligne » doit être tapée en toutes
            lettres — le navigateur remplace ici le clavier du terminal ;
          - le mot de passe FTP est redemandé à CHAQUE fois. Il transite par
            l'entrée standard du sous-programme, jamais par la ligne de
            commande (« ps » l'exposerait) ni par un fichier.
        """
        ou = (d.get('ou') or 'maison').strip()
        fichiers = {'maison': 'publier.conf', 'en-ligne': 'publier-en-ligne.conf'}
        if ou not in fichiers:
            return self.erreur(f'destination inconnue : « {ou} »')

        conf = RACINE / 'outils' / fichiers[ou]
        if not conf.exists():
            return self.erreur(
                f"{conf.name} est absent : l'atelier ne sait pas où déposer "
                f"le site pour la destination « {ou} ». Voir l'exemple en "
                f"tête de outils/publier.py.")

        reglages = {}
        for ligne in conf.read_text(encoding='utf-8').splitlines():
            ligne = ligne.split('#', 1)[0].strip()
            if '=' in ligne:
                cle, val = ligne.split('=', 1)
                reglages[cle.strip()] = val.strip()

        methode = reglages.get('methode', 'rsync').lower()
        public = reglages.get('role') == 'public'
        pour_de_vrai = bool(d.get('pour_de_vrai'))

        if public and pour_de_vrai:
            if (d.get('confirmation') or '').strip() != 'je publie en ligne':
                return self.erreur(
                    'Pour remplacer le site public, tapez exactement '
                    '« je publie en ligne ».')

        commande = [sys.executable, str(RACINE / 'outils' / 'publier.py'),
                    '--ou', ou]
        if pour_de_vrai:
            commande.append('--pour-de-vrai')
            commande.append('--confirme')

        # L'ESSAI À BLANC AUSSI a besoin du mot de passe : lftp se connecte
        # pour comparer les deux côtés — c'est précisément ce qui rend
        # l'essai utile, puisqu'il énumère ce qui partirait et ce qui serait
        # effacé. Sans mot de passe il n'y a pas d'essai, seulement un échec.
        entree = None
        if methode == 'ftp':
            entree = d.get('mot_de_passe') or ''
            if not entree:
                return self.erreur(
                    'Le mot de passe FTP est nécessaire, même pour l’essai à '
                    'blanc : il faut se connecter pour comparer les deux '
                    'côtés. Il n’est jamais enregistré — à retaper à chaque '
                    'fois.')
            entree += '\n'

        # sans PYTHONUNBUFFERED, les titres d'étape de publier.py sortent
        # APRÈS le texte de ses sous-programmes : le journal se lit alors
        # à l'envers, la régénération apparaissant sous son propre titre.
        env = dict(os.environ, PYTHONUNBUFFERED='1')
        try:
            with self.verrou:
                r = subprocess.run(
                    commande, capture_output=True, text=True, cwd=str(RACINE),
                    input=entree, stdin=None if entree else subprocess.DEVNULL,
                    env=env, timeout=3600)
        except subprocess.TimeoutExpired:
            # une heure sans rendre la main : le dépôt est en carafe. Sans
            # ce rattrapage, la requête mourait sans réponse et la fenêtre
            # de publication tournait indéfiniment.
            return self.erreur(
                'la publication n’a pas rendu la main au bout d’une heure — '
                'elle a été interrompue. Regardez la connexion, puis '
                'recommencez.', 504)

        sortie = r.stdout + r.stderr
        # Ceinture et bretelles : si un mot de passe se retrouvait un jour
        # dans la sortie d'un outil tiers, il ne remonterait pas au
        # navigateur pour y rester affiché.
        if entree:
            sortie = sortie.replace(entree.strip(), '••••••••')

        return self.json({'ok': r.returncode == 0,
                          'pour_de_vrai': pour_de_vrai,
                          'ou': ou, 'public': public, 'methode': methode,
                          'destination': reglages.get('hote', '?'),
                          'sortie': sortie})

    def traduire(self, d):
        """Remplit une jumelle avec la traduction de sa page d'origine.

        « Jumelle » crée la page et y recopie le texte français ; ce
        bouton-ci le remplace par sa traduction. Les deux gestes restent
        séparés : on peut créer la jumelle et traduire à la main, ou
        traduire et tout relire — la page reste en BROUILLON dans les
        deux cas, elle ne part pas en ligne toute seule.

        Deux moteurs, les MÊMES garde-fous : rien n'est écrit si la
        traduction ne rend pas le même nombre de lignes, les mêmes
        liens, les mêmes titres et les mêmes balises que le français.
        C'est `outils/traduire.py` qui les tient, pour les deux.
        """
        f = d.get('fichier', '')
        cible = CONTENU / f
        if not f or not dedans(cible, CONTENU) or not cible.is_file():
            return self.erreur('fichier introuvable', 404)

        entete, _ = separer(cible.read_text(encoding='utf-8'))
        lu = yaml.safe_load(entete) or {}
        cle, langue = lu.get('traduction'), lu.get('langue')
        if not cle:
            return self.erreur('cette page n’a pas de clé de traduction')

        # la page d'origine : celle qui porte la même clé, dans la langue
        # d'origine déclarée — à défaut, le français
        depart = lu.get('origine') or 'fr'
        source = None
        for autre in sorted((CONTENU / depart).rglob('*.md')):
            e, _ = separer(autre.read_text(encoding='utf-8'))
            if valeur(e, 'traduction') == cle:
                source = autre
                break
        if source is None:
            return self.erreur(f'pas de page « {depart} » portant la clé '
                               f'« {cle} » — rien à traduire depuis')

        _, corps = separer(source.read_text(encoding='utf-8'))
        if not corps.strip():
            return self.erreur('la page d’origine n’a pas de texte')

        # NE JAMAIS ÉCRASER UNE TRADUCTION HUMAINE PAR DE LA MACHINE.
        # L'italien du site vient de deux mains : 207 pages traduites par
        # quelqu'un — elles font foi — et 148 par la machine, marquées.
        # Une page non marquée dont le texte diffère déjà de l'original a
        # donc été traduite à la main : la remplacer d'un clic effacerait
        # un travail que rien ne reconstitue. Il faut le dire tout haut.
        _, corps_cible = separer(cible.read_text(encoding='utf-8'))
        humaine = (not valeur(entete, 'traduction_automatique')
                   and corps_cible.strip()
                   and corps_cible.strip() != corps.strip())
        if humaine and not d.get('remplacer'):
            return self.erreur(
                'cette page porte une traduction HUMAINE, non marquée comme '
                'automatique. La remplacer effacerait ce travail. Passer '
                '« remplacer » si c’est bien voulu.', 409)

        # Import PARESSEUX, et pas par élégance : traduire.py importe
        # atelier.py pour ses lecteurs d'en-tête. Au niveau du module, les
        # deux se mordent la queue et atelier.py s'exécute deux fois.
        import traduire

        moteur = d.get('moteur', 'local')
        # Le serveur éteint est le cas le plus fréquent, et « Connection
        # refused » ne dit pas quoi faire. On le nomme avant d'essayer.
        if moteur == 'local' and not traduire.modele_charge(traduire.HOTE):
            return self.erreur(
                'Le modèle local ne répond pas sur le port 8080. Ouvrir un '
                'terminal et lancer :  qwen-uncensored  — puis réessayer '
                '(le chargement prend une à deux minutes). Ou choisir l’IA '
                'externe.', 503)
        try:
            parler = traduire.demandeur(moteur, traduire.HOTE)
            texte, reprises = traduire.traduire_texte(
                traduire.HOTE, langue, corps, 4096, 900,
                lambda _: None, traduire.TAILLE, parler)
        except Exception as souci:                     # noqa: BLE001
            return self.erreur(str(souci) or 'la traduction a échoué', 502)

        # SOUS VERROU, comme « Jumelle » et « Enregistrer ». La traduction
        # dure de trente secondes à plusieurs minutes : c'est le seul geste
        # de l'atelier assez long pour qu'on enregistre la même page
        # pendant qu'il tourne. Sans le verrou, la traduction écrasait la
        # saisie sans rien dire. L'en-tête est relu ICI, et non celui qu'on
        # avait au départ, pour la même raison.
        with self.verrou:
            entete_frais, _ = separer(cible.read_text(encoding='utf-8'))
            cible.write_text(f'---\n{marquer_auto(entete_frais)}\n---\n\n{texte}',
                             encoding='utf-8')
        return self.json({'texte': texte, 'reprises': reprises,
                          'moteur': moteur, 'depuis': source.name})

    def jumelle(self, d):
        """Crée la page jumelle dans l'autre langue, et les apparie.

        L'appariement tient à une clé `traduction:` IDENTIQUE des deux
        côtés — la poser à la main dans deux fichiers, sans se tromper,
        était le seul geste que l'atelier laissait au bloc-notes.

        LE TEXTE D'ORIGINE EST RECOPIÉ dans la jumelle. Elle naissait
        vide : pour traduire, il fallait ouvrir les deux pages côte à
        côte et faire l'aller-retour — Christophe s'y est cassé les dents
        le 31/08/2026 et a fini par jeter la page créée. Le texte est
        maintenant là, à remplacer au fil de la lecture. La jumelle naît
        en BROUILLON : elle ne peut pas partir en ligne dans la langue
        d'origine par distraction.
        """
        f = d.get('fichier', '')
        source = CONTENU / f
        if not f or not dedans(source, CONTENU) or not source.is_file():
            return self.erreur('fichier introuvable', 404)
        vers = d.get('langue', '')
        reglages = config()
        if vers not in (reglages.get('langues') or {}):
            return self.erreur(f'langue inconnue : « {vers} »')

        entete, corps_source = separer(source.read_text(encoding='utf-8'))
        lu = yaml.safe_load(entete) or {}
        if lu.get('langue') == vers:
            return self.erreur('cette page est déjà dans cette langue')

        # LA CLÉ DOIT IDENTIFIER LA PAGE, PAS SA RUBRIQUE. Le repli
        # d'origine prenait le nom de la collection : deux fiches de la
        # même rubrique auraient reçu la même clé et se seraient prises
        # l'une pour la traduction de l'autre. Le dépôt n'en compte
        # aucune en double aujourd'hui — cela doit le rester.
        cle = lu.get('traduction')
        if not cle:
            # le nom du fichier sans son numéro : « temoignage-du-12-mai-2026 »
            # se lit, tient en 70 signes, et porte déjà sa date.
            cle = limacon(re.sub(r'^\d+-', '', str(lu.get('slug') or source.stem)))
            prises = {p['traduction'] for p in lister()
                      if p['traduction'] and p['fichier'] != f}
            base, n = cle, 2
            while cle in prises:
                cle = f'{base}-{n}'
                n += 1
        # une jumelle existe-t-elle déjà sous cette clé ?
        for autre in (CONTENU / vers).rglob('*.md'):
            e, _ = separer(autre.read_text(encoding='utf-8'))
            if (yaml.safe_load(e) or {}).get('traduction') == cle:
                return self.json({'ok': True, 'existait': True,
                                  'fichier': str(autre.relative_to(CONTENU))})

        neuf = dict(lu)
        neuf['langue'] = vers
        neuf['traduction'] = cle
        neuf['origine'] = lu.get('langue')
        neuf['statut'] = 'brouillon'
        neuf.pop('source_id', None)
        neuf.pop('source_url', None)
        neuf.pop('extrait', None)
        if lu.get('type') == 'fiche':
            dossier = collection_jumelle(lu.get('langue'), lu.get('collection') or '', vers)
            if dossier is None:
                return self.erreur(
                    f'la rubrique « {lu.get("collection")} » n’a pas de jumelle '
                    f'en « {vers} » — créez-la d’abord au clavier')
            neuf['collection'] = dossier.name

            # Le numéro en tête du nom de fichier est un identifiant libre
            # dans la rubrique D'ARRIVÉE : reprendre celui de la source
            # doublonnerait avec une fiche française qui porte déjà ce
            # numéro. Le rang, lui, place la fiche à la fin — c'est le seul
            # choix qui ne bouscule pas l'ordre existant, et il se corrige
            # d'un chiffre dans les Réglages.
            numeros = [int(m.group(1)) for x in dossier.glob('*.md')
                       if x.name != '_index.md'
                       for m in [re.match(r'(\d+)-', x.name)] if m]
            neuf['rang'] = rang_jumelle(source, source.parent, dossier)
            cible = dossier / (f'{max(numeros, default=0) + 1:03d}-'
                               + re.sub(r'^\d+-', '', source.stem) + '.md')
        else:
            neuf['slug'] = limacon(str(lu.get('slug') or source.stem))
            cible = CONTENU / vers / f'{neuf["slug"]}.md'
        if cible.exists():
            return self.erreur(f'{cible.relative_to(CONTENU)} existe déjà')

        # la clé doit aussi figurer côté source, sinon rien ne les apparie
        if not lu.get('traduction'):
            source.write_text(
                source.read_text(encoding='utf-8').replace(
                    '---\n', f'---\ntraduction: "{cle}"\n', 1),
                encoding='utf-8')

        lignes = []
        for k, v in neuf.items():
            if v in (None, ''):
                continue
            lignes.append(f'{k}: {v}' if isinstance(v, (int, bool))
                          else f'{k}: "{guillemets(v)}"')
        entete_neuf = '\n'.join(lignes)
        # relu comme le générateur le lira — la jumelle n'avait pas ce
        # garde-fou et pouvait écrire une page qui bloquait la régénération.
        plainte = verifier_entete(entete_neuf, list(reglages.get('langues') or {}))
        if plainte:
            return self.erreur(f'Réglages de la jumelle : {plainte}. Rien n’a été créé.')
        cible.parent.mkdir(parents=True, exist_ok=True)
        with self.verrou:
            cible.write_text(f'---\n{entete_neuf}\n---\n\n{corps_source.strip()}\n',
                             encoding='utf-8')
        journaliser(f'jumelle {cible.relative_to(CONTENU)} créée depuis {f}',
                    cible, source)
        return self.json({'ok': True, 'existait': False, 'cle': cle,
                          'fichier': str(cible.relative_to(CONTENU))})

    def supprimer_media(self, d):
        """Met un média à la corbeille des médias — jamais de destruction.

        REFUSE tant que des pages ou des menus renvoient encore vers le
        fichier : les nommer vaut mieux que laisser des liens morts que
        seul le vérificateur aurait vus, après coup.
        """
        chemin = d.get('chemin', '')
        if not chemin.startswith('/medias/'):
            return self.erreur('chemin inattendu')
        rel = chemin[len('/medias/'):]
        cible = MEDIAS / rel
        if not rel or not dedans(cible, MEDIAS) or not cible.is_file():
            return self.erreur('fichier introuvable', 404)

        usages = pages_qui_utilisent(chemin)
        if usages:
            liste = ', '.join(usages[:5]) + ('…' if len(usages) > 5 else '')
            return self.erreur(
                f'Ce fichier est encore utilisé par {len(usages)} '
                f'page(s) ou menu(s) : {liste} — retirez d’abord ces liens.')

        corbeille = CORBEILLE_MEDIAS / rel
        corbeille.parent.mkdir(parents=True, exist_ok=True)
        if corbeille.exists():
            corbeille = corbeille.with_name(
                f'{corbeille.stem}-{date.today().isoformat()}{corbeille.suffix}')
        with self.verrou:
            shutil.move(str(cible), str(corbeille))
        return self.json({'ok': True,
                          'corbeille': str(corbeille.relative_to(MEDIAS))})

    def media_texte(self, d):
        """Écrit un texte alternatif, pour une langue, dans le magasin.

        Un texte vidé RETIRE la ligne plutôt que d'enregistrer une chaîne
        vide : une clé absente et une clé vide diraient la même chose, et
        deux façons de l'écrire finiraient par diverger.
        """
        chemin = d.get('chemin', '')
        langue = d.get('langue', '')
        if not chemin.startswith('/medias/'):
            return self.erreur('chemin inattendu')
        rel = chemin[len('/medias/'):]
        if not dedans(MEDIAS / rel, MEDIAS):
            return self.erreur('chemin refusé')
        if langue not in (config().get('langues') or {}):
            return self.erreur(f'langue inconnue : « {langue} »')

        texte = str(d.get('texte') or '').strip()
        auto = bool(d.get('auto'))
        with self.verrou:
            tous = charger_textes()
            fiche = dict(tous.get(rel) or {})
            marques = [lg for lg in (fiche.get('auto') or []) if lg != langue]
            if texte:
                fiche[langue] = texte
                if auto:
                    marques.append(langue)
            else:
                fiche.pop(langue, None)
            if marques:
                fiche['auto'] = sorted(marques)
            else:
                fiche.pop('auto', None)
            if fiche:
                tous[rel] = fiche
            else:
                tous.pop(rel, None)
            enregistrer_textes(tous)
        journaliser(f'texte alternatif {langue} de {rel}', TEXTES_MEDIAS)
        return self.json({'ok': True, 'chemin': chemin, 'langue': langue,
                          'texte': texte, 'auto': auto and bool(texte)})

    def renommer_media(self, d):
        """Renomme un média ET recoud les liens qui le citent.

        Le nom d'un média est une adresse publique : le changer sans
        toucher au reste laisserait autant de liens morts qu'il y avait
        de renvois — même règle que « Adresse… » pour les pages.
        """
        chemin = d.get('chemin', '')
        if not chemin.startswith('/medias/'):
            return self.erreur('chemin inattendu')
        rel = chemin[len('/medias/'):]
        source = MEDIAS / rel
        if not dedans(source, MEDIAS) or not source.is_file():
            return self.erreur('fichier introuvable', 404)

        demande = str(d.get('nom') or '').strip()
        ext = source.suffix.lower()
        tronc = limacon(Path(demande).stem, '')
        if not tronc:
            return self.erreur('il faut un nouveau nom')
        cible = source.with_name(tronc + ext)
        if cible == source:
            return self.json({'ok': True, 'chemin': chemin, 'liens_recousus': 0})
        if cible.exists():
            return self.erreur(f'{cible.name} existe déjà dans ce dossier')

        neuf = '/medias/' + str(cible.relative_to(MEDIAS))
        recousus = 0
        with self.verrou:
            source.rename(cible)
            for f in CONTENU.rglob('*'):
                if not f.is_file() or f.suffix not in ('.md', '.yaml'):
                    continue
                if any(p.startswith('.') for p in f.relative_to(CONTENU).parts):
                    continue
                t = f.read_text(encoding='utf-8')
                if chemin in t:
                    f.write_text(t.replace(chemin, neuf), encoding='utf-8')
                    recousus += 1
            # le texte alternatif suit le fichier
            tous = charger_textes()
            if rel in tous:
                tous[str(cible.relative_to(MEDIAS))] = tous.pop(rel)
                enregistrer_textes(tous)
        return self.json({'ok': True, 'chemin': neuf, 'nom': cible.name,
                          'liens_recousus': recousus})

    def restaurer_media(self, d):
        """Remet un média de la corbeille des médias à sa place."""
        f = d.get('fichier', '')
        source = CORBEILLE_MEDIAS / f
        cible = MEDIAS / f
        if not f or not dedans(source, CORBEILLE_MEDIAS) or not source.is_file():
            return self.erreur('introuvable dans la corbeille', 404)
        if cible.exists():
            return self.erreur(f'{f} existe de nouveau dans les médias')
        if not dedans(cible, MEDIAS):
            return self.erreur('chemin refusé')
        with self.verrou:
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(cible))
            for d_ in sorted(CORBEILLE_MEDIAS.rglob('*'), reverse=True):
                if d_.is_dir() and not any(d_.iterdir()):
                    d_.rmdir()
        return self.json({'ok': True, 'chemin': '/medias/' + f})

    def retablir(self, d):
        """Remet une page dans l'état d'une version antérieure.

        Rien n'est perdu : le rétablissement est lui-même une version, donc
        on peut toujours revenir en arrière du retour en arrière.
        """
        f = d.get('fichier', '')
        v = str(d.get('version') or '')
        cible = CONTENU / f
        if not f or not dedans(cible, CONTENU):
            return self.erreur('fichier introuvable', 404)
        texte = contenu_a_la_version(str(cible.relative_to(RACINE)), v)
        if texte is None:
            return self.erreur('cette version est introuvable', 404)

        entete, corps = separer(texte)
        plainte = verifier_entete(entete, list(config().get('langues') or {}))
        if plainte:
            return self.erreur(f'Cette version ne se relit pas : {plainte}.')
        with self.verrou:
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(texte, encoding='utf-8')
        journaliser(f'{f} rétablie dans sa version {v[:8]}', cible)
        return self.json({'ok': True, 'fichier': f, 'entete': entete, 'corps': corps})

    def restaurer(self, d):
        """Remet une page de la corbeille à sa place.

        On pouvait y mettre et tout détruire, pas ressortir : jeter par
        erreur obligeait à passer par le dépôt, ce qui suppose de savoir
        s'en servir.
        """
        f = d.get('fichier', '')
        source = CORBEILLE / f
        cible = CONTENU / f
        if not f or not dedans(source, CORBEILLE) or not source.is_file():
            return self.erreur('introuvable dans la corbeille', 404)
        if cible.exists():
            return self.erreur(f'{f} existe de nouveau : renommez-la d’abord')
        if not dedans(cible, CONTENU):
            return self.erreur('chemin refusé')
        with self.verrou:
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(cible))
            journaliser(f'{f} remise en place', cible)
            for d_ in sorted(CORBEILLE.rglob('*'), reverse=True):
                if d_.is_dir() and not any(d_.iterdir()):
                    d_.rmdir()
        return self.json({'ok': True, 'fichier': f})

    def renommer(self, d):
        """Change l'adresse d'une page ET les liens qui y mènent.

        Le nom du fichier EST l'adresse. Le déplacer sans toucher au reste
        laisserait derrière lui autant de liens morts qu'il y avait de
        renvois — et rien ne l'aurait dit avant la vérification suivante.
        """
        f = d.get('fichier', '')
        source = CONTENU / f
        neuf = limacon(str(d.get('slug') or '').strip(), '')
        if not f or not dedans(source, CONTENU) or not source.is_file():
            return self.erreur('fichier introuvable', 404)
        if not neuf:
            return self.erreur('il faut une nouvelle adresse')

        entete, corps = separer(source.read_text(encoding='utf-8'))
        lu = yaml.safe_load(entete) or {}
        ancienne = next((p['url'] for p in lister() if p['fichier'] == f), None)

        if lu.get('type') == 'fiche':
            m = re.match(r'(\d+)-', source.name)
            cible = source.with_name(f'{m.group(1)}-{neuf}.md' if m else f'{neuf}.md')
        else:
            cible = source.with_name(f'{neuf}.md')
            entete = (re.sub(r'^slug:.*$', f'slug: "{neuf}"', entete, flags=re.M)
                      if re.search(r'^slug:', entete, re.M)
                      else entete.rstrip('\n') + f'\nslug: "{neuf}"')
        if cible.exists():
            return self.erreur(f'{cible.name} existe déjà')

        with self.verrou:
            source.write_text(f'---\n{entete}\n---\n\n{corps.strip()}\n', encoding='utf-8')
            source.rename(cible)
            nouvelle = next((p['url'] for p in lister()
                             if p['fichier'] == str(cible.relative_to(CONTENU))), None)
            recousus = 0
            touches = [source, cible]
            if ancienne and nouvelle and ancienne != nouvelle:
                for x in CONTENU.rglob('*.md'):
                    t = x.read_text(encoding='utf-8')
                    if ancienne in t:
                        x.write_text(t.replace(ancienne, nouvelle), encoding='utf-8')
                        touches.append(x)
                        recousus += 1
                for lg in dossiers_de_langue():
                    mn = lg / '_menu.yaml'
                    if mn.exists():
                        t = mn.read_text(encoding='utf-8')
                        if ancienne in t:
                            mn.write_text(t.replace(ancienne, nouvelle), encoding='utf-8')
                            touches.append(mn)
                            recousus += 1
        # les fichiers RÉELLEMENT touchés, pas tout site/contenu : une
        # autre session écrit parfois ici, son travail ne doit pas
        # entrer dans ma version.
        journaliser(f'{f} renommée en {cible.relative_to(CONTENU)} ({recousus} lien(s) recousu(s))', *touches)
        return self.json({'ok': True, 'fichier': str(cible.relative_to(CONTENU)),
                          'ancienne': ancienne, 'nouvelle': nouvelle,
                          'liens_recousus': recousus})

    def vider_corbeille(self):
        """Détruit pour de bon ce que la corbeille contient.

        C'est le seul geste de l'atelier qui ne se rattrape pas — d'où le
        compte rendu de ce qui a été détruit : si la confirmation a été
        donnée trop vite, on sait au moins quoi aller rechercher dans
        l'historique du dépôt.
        """
        avant = lister_corbeille()
        if not avant:
            return self.json({'ok': True, 'detruits': [], 'message': 'la corbeille était déjà vide'})
        with self.verrou:
            if not dedans(CORBEILLE, CONTENU) or not dedans(CORBEILLE_MEDIAS, MEDIAS):
                return self.erreur('chemin de corbeille inattendu', 500)
            if CORBEILLE.is_dir():
                shutil.rmtree(CORBEILLE)
            if CORBEILLE_MEDIAS.is_dir():
                shutil.rmtree(CORBEILLE_MEDIAS)
        return self.json({'ok': True, 'detruits': [x['fichier'] for x in avant]})

    def enregistrer_menu(self, d):
        """Réécrit un _menu.yaml. Refuse plutôt que d'écrire un menu bancal.

        Le menu est la seule chose du site qu'aucune page ne peut
        rattraper : une rubrique perdue rend ses pages introuvables alors
        qu'elles existent toujours. D'où la copie de sauvegarde.
        """
        langue = d.get('langue', '')
        if langue not in (config().get('langues') or {}):
            return self.erreur(f'langue inconnue : « {langue} »')
        arbre, plainte = menu_en_arbre(d.get('entrees') or [])
        if plainte:
            return self.erreur(f'{plainte}. Rien n’a été enregistré.')

        f = CONTENU / langue / '_menu.yaml'
        with self.verrou:
            if f.exists():
                garde = CONTENU / '.corbeille' / langue / f'_menu-{date.today().isoformat()}.yaml'
                garde.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, garde)
            f.write_text(ecrire_menu(langue, arbre), encoding='utf-8')
        journaliser(f'menu {langue} modifié', f)
        return self.json({'ok': True, 'entrees': menu_a_plat(langue)})

    # --- fichiers ---
    def fichier_interface(self, nom):
        cible = INTERFACE / nom
        return self.fichier_brut(cible, INTERFACE)

    def fichier_site(self, reste):
        cible = PUBLIC / reste
        if cible.is_dir() or reste == '' or reste.endswith('/'):
            cible = cible / 'index.html'
        if not cible.is_file():
            # DIRE LA VRAIE RAISON. « Régénérez le site » envoyait refaire
            # une fabrication qui n'y pouvait rien : une page en brouillon
            # n'est JAMAIS écrite, par construction (site/generer.py ne
            # garde que les publiées). Christophe a régénéré pour rien.
            adresse = '/' + reste.rstrip('/').removesuffix('/index.html') + '/'
            # lister() relit TOUT le contenu : 0,4 ms pour une page servie
            # contre 73 ms pour une absente, mesuré — et une page d'aperçu
            # réclame vingt ressources. Une image manquante n'est jamais un
            # brouillon : on ne cherche que pour une vraie adresse de page.
            brouillon = None
            if not Path(reste).suffix:
                brouillon = next((p for p in lister()
                                  if p['url'] == adresse and p['statut'] != 'publie'), None)
            if brouillon is not None:
                return self.repondre(404, (
                    f'<p style="font:15px/1.6 system-ui;margin:2rem">'
                    f'« {escape(brouillon["titre"])} » est un <b>brouillon</b> : le site ne la '
                    f'fabrique pas, et personne ne peut la voir.<br><br>'
                    f'Pour la regarder ici, mettez-la en ligne — dans l\'atelier, '
                    f'onglet <b>Réglages</b> de la page, ou depuis la liste des '
                    f'<b>Brouillons</b> — puis cliquez « Régénérer ».</p>'
                ).encode('utf-8'), 'text/html; charset=utf-8')
            return self.repondre(404, b'<p style="font:15px/1.6 system-ui;margin:2rem">'
                                      b'Page absente du site fabriqu\xc3\xa9 : cliquez '
                                      b'\xc2\xab\xc2\xa0R\xc3\xa9g\xc3\xa9n\xc3\xa9rer\xc2\xa0\xc2\xbb.</p>',
                                 'text/html; charset=utf-8')
        return self.fichier_brut(cible, PUBLIC)

    def fichier_brut(self, cible: Path, racine: Path, muselee=None):
        if not dedans(cible, racine) or not cible.is_file():
            return self.erreur('introuvable', 404)
        # UN MÉDIA DÉPOSÉ NE DOIT PAS S'EXÉCUTER. Un SVG est un document
        # XML : il peut porter un <script>. Servi en « image/svg+xml »
        # depuis l'atelier, ce script s'exécute DANS l'origine de
        # l'atelier — et peut alors appeler /api/ecrire ou /api/publier
        # avec un Origin parfaitement valide. Le contrôle d'origine est
        # contourné par l'intérieur. La règle ci-dessous le neutralise
        # sans casser l'affichage : un <img> n'exécute jamais de script,
        # et l'ouverture directe du fichier n'en exécute plus non plus.
        if muselee is None:
            muselee = racine == MEDIAS
        types = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
                 '.js': 'text/javascript; charset=utf-8', '.json': 'application/json',
                 '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                 '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp',
                 '.pdf': 'application/pdf', '.mp3': 'audio/mpeg', '.woff2': 'font/woff2'}
        self.repondre(200, cible.read_bytes(),
                      types.get(cible.suffix.lower(), 'application/octet-stream'),
                      muselee=muselee)


def main():
    ap = argparse.ArgumentParser(description="L'atelier : interface locale du site.")
    ap.add_argument('--port', type=int, default=8413)
    ap.add_argument('--sans-navigateur', action='store_true')
    args = ap.parse_args()

    if not CONTENU.is_dir():
        sys.exit("atelier : site/contenu/ absent — lancer d'abord "
                 "python3 outils/importer.py")

    adresse = f'http://localhost:{args.port}/'
    try:
        srv = ThreadingHTTPServer(('127.0.0.1', args.port), Atelier)
    except OSError as souci:
        # Le cas courant : un atelier tourne déjà. Une trace de vingt
        # lignes ne le dit pas, et c'est pourtant tout ce qu'il faut savoir.
        sys.exit(f"atelier : impossible d'écouter sur le port {args.port} "
                 f"({souci.strerror or souci}).\n"
                 f"  Un atelier tourne peut-être déjà — ouvrez {adresse}\n"
                 f"  ou fermez-le :  kill $(ss -tlnp | grep ':{args.port} ' | "
                 f"grep -oE 'pid=[0-9]+' | cut -d= -f2)\n"
                 f"  ou choisissez un autre port :  --port {args.port + 1}")
    print(f"  L'atelier est ouvert sur {adresse}")
    print(f"  {len(lister())} pages, {len(lister_medias())} médias")
    print('  Ctrl+C pour fermer.')
    if not args.sans_navigateur:
        threading.Timer(0.6, lambda: webbrowser.open(adresse)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n  fermé')


if __name__ == '__main__':
    main()
