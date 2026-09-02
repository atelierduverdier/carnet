#!/usr/bin/env python3
# =========================================================================
# traduire.py — traduit les pages du site avec le modèle local
# =========================================================================
# Remplace outils/translate_site.sh, qui appelait Qwen2.5-7B fichier par
# fichier avec llama-cli. Deux choses changent.
#
# LE MODÈLE. Le 7B a produit les 364 pages anglaises du 30/08/2026, et la
# vérification a rattrapé ce qu'il abîmait : un NOM DE FICHIER traduit
# (patiente.jpg devenu patient.jpg, image morte), un gabarit
# <path_to_image> laissé dans un lien, des sens inversés dans les
# Réflexions. On s'adresse maintenant au llama-server que lance
# `qwen-uncensored` — Qwen3.6-35B, déjà chargé, sur le port 8080.
#
# LES GARDE-FOUS. Rien n'est écrit tant que la traduction d'un morceau ne
# rend pas EXACTEMENT les mêmes liens, les mêmes titres, les mêmes blocs
# de code, les mêmes balises et LE MÊME NOMBRE DE LIGNES que la source.
# Ce dernier point n'est pas une coquetterie : `nl2br` fait de chaque
# retour simple un <br>, donc une ligne est du contenu. Le lot anglais du
# 7B a fondu 300 lignes du corps français — 7 059 contre 6 759 — soit
# autant de retours à la ligne perdus, sans que rien ne le signale.
# `maintenant.md` à lui seul en a perdu 59.
#
# UTILISATION :
#   python3 outils/traduire.py en                     # à blanc : ce qui serait traduit
#   python3 outils/traduire.py en --appliquer
#   python3 outils/traduire.py it --page contact.md --appliquer
#   python3 outils/traduire.py en --remplacer --appliquer   # refait des pages traduites
#
# Le serveur doit tourner : `qwen-uncensored` dans un terminal.
# Renvoie 1 si une page a été refusée : utilisable dans un enchaînement.
# =========================================================================

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atelier import CONTENU, collection_jumelle, config, guillemets, separer, valeur  # noqa: E402

SOURCE = 'fr'
HOTE = 'http://127.0.0.1:8080'
MODELE_ATTENDU = '35B'
TAILLE = 4000            # caractères par morceau ; ~1 300 jetons en entrée

NOMS = {'en': 'English', 'it': 'Italian', 'es': 'Spanish', 'de': 'German'}

# Les consignes au modèle restent en anglais : c'est la langue dans
# laquelle Qwen suit le mieux ce genre d'instruction. Ce n'est pas un
# texte d'interface, la règle du français ne s'y applique pas.
CONSIGNE = """You are a professional translator working on a website about health, \
dentistry and personal growth. Translate the user's Markdown text from French into {langue}.

ABSOLUTE RULES — one violation makes the whole answer unusable:
- Output EXACTLY the same number of lines as the input. Never merge two lines into one, \
never split one line into two, never reflow a paragraph. A single line break is meaningful \
on this site: it is rendered as <br>.
- Keep every blank line exactly where it is.
- Copy every link, image path, anchor and file name CHARACTER FOR CHARACTER. \
`patiente.jpg` stays `patiente.jpg`. Never translate a file name, a URL, an id, nor the \
value of src, href, class, rel or id — even when it reads as a French word. The `title` \
and `alt` attributes ARE read by people: translate those.
- Keep the Markdown identical: heading levels, bold, italics, lists, tables, code fences.
- Keep every HTML tag untouched, `<span class="voix-praticien">` included — it marks which \
of the two voices is speaking.
- Translate the visible text only. Answer with the translation and nothing else: no \
preamble, no comment, no explanation, no code fence wrapped around the whole answer.

{marque}Vocabulary held throughout this site: savoir = learning, connaissance = knowledge, \
le Moi = the I, fléau (of a balance) = beam, juste = right. Keep French book titles as they \
are. Gloss a pun rather than dropping it."""

RAPPEL = ("\n\nYour previous answer was rejected: {ecarts}. "
          "Answer again, same text, obeying the rules to the letter.")


def marque(langue: str) -> str:
    """La phrase qui donne au modèle le nom du site, tel que config.yaml le fixe.

    Sans elle, le 35B a rendu « Humano-dentosophie » par « Human-DentoSophie »
    puis « the human dentosophy of teeth » dans la même page — et le 7B, en
    2026, par « Humanodontosphy ». Le nom de la marque ne se devine pas : il
    est écrit, par langue, dans site/config.yaml, et c'est de là qu'il vient.
    """
    try:
        langues = (config() or {}).get('langues') or {}
    except (OSError, ValueError):
        return ''
    depart = (langues.get(SOURCE) or {}).get('titre')
    arrivee = (langues.get(langue) or {}).get('titre')
    if not (depart and arrivee):
        return ''
    return (f'The site is called « {depart} » in French and « {arrivee} » in '
            f'{NOMS.get(langue, langue)}. Use that exact spelling, never another.\n\n')


LIEN = re.compile(r'\]\(([^)]*)\)|(?:src|href)="([^"]*)"')
TITRE = re.compile(r'^(#{1,6})\s', re.M)
BALISE = re.compile(r'<(/?[a-zA-Z][\w-]*)')
BAVARDAGE = ('<|im_start|>', '<|im_end|>', 'Here is the translation',
             'Here is the translated', 'Voici la traduction', 'Sure, here')

# Deux dialectes de dialogue, et aucun moyen de savoir d'avance lequel le
# modèle chargé parle. Qwen3.6 a un mode raisonnement qu'il FAUT couper ;
# Gemma 3 n'en a pas et, surtout, son gabarit n'accepte AUCUN rôle
# « système » — il refuse la requête. On commence au plus riche et on
# retire ce qui fâche, une fois pour toutes, plutôt que de faire dépendre
# le script d'une liste de modèles connus.
_sans_reflexion = False
_systeme_fondu = False


# --- le modèle ------------------------------------------------------------

def modele_charge(hote: str) -> str:
    """Le nom du modèle que sert llama-server, ou '' s'il ne répond pas."""
    try:
        with urllib.request.urlopen(hote + '/v1/models', timeout=5) as r:
            donnees = json.load(r).get('data') or []
        return donnees[0].get('id', '') if donnees else ''
    except (urllib.error.URLError, OSError, ValueError, IndexError):
        return ''


def demander(hote: str, systeme: str, texte: str, jetons: int, delai: int) -> str:
    """Une traduction, ou lève ValueError si la réponse n'est pas exploitable.

    LE RAISONNEMENT EST COUPÉ, et ce n'est pas un détail. Qwen3.6 réfléchit
    avant de répondre : mesuré ici, 367 jetons de réflexion pour traduire
    « Bonjour, voici la photo de la patiente. » — sept mots, 16,6 secondes.
    Sur une page entière, la réflexion mangeait le budget de jetons en
    entier : le champ `content` revenait VIDE au bout de trois minutes,
    et la page était refusée sans qu'on sache pourquoi. Avec
    `enable_thinking: false`, la même phrase coûte 20 jetons et 1,3 s.
    Douze fois plus rapide, et la réponse arrive.
    """
    global _sans_reflexion, _systeme_fondu

    def batir():
        if _systeme_fondu:
            messages = [{'role': 'user', 'content': systeme + '\n\n---\n\n' + texte}]
        else:
            messages = [{'role': 'system', 'content': systeme},
                        {'role': 'user', 'content': texte}]
        demande = {'messages': messages, 'temperature': 0.1,
                   'max_tokens': jetons, 'stream': False}
        if not _sans_reflexion:
            demande['chat_template_kwargs'] = {'enable_thinking': False}
        return json.dumps(demande).encode('utf-8')

    for tentative in (1, 2, 3):
        requete = urllib.request.Request(
            hote + '/v1/chat/completions', data=batir(),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(requete, timeout=delai) as r:
                reponse = json.load(r)
            break
        except urllib.error.HTTPError as refus:
            if not _sans_reflexion:
                _sans_reflexion = True       # le gabarit ignore l'option de raisonnement
            elif not _systeme_fondu:
                _systeme_fondu = True        # le gabarit n'accepte pas de rôle « système »
            else:
                raise ValueError(f'le serveur refuse la requête ({refus.code})')
    choix = reponse['choices'][0]
    rendu = choix['message'].get('content') or ''
    if choix.get('finish_reason') == 'length':
        raise ValueError(f'réponse coupée à {jetons} jetons — augmenter --jetons '
                         f'ou baisser la taille des morceaux')
    if not rendu.strip() and choix['message'].get('reasoning_content'):
        raise ValueError('le modèle a réfléchi sans répondre — le raisonnement '
                         "devrait pourtant être coupé, vérifier qu'il s'agit bien "
                         'du serveur de qwen-uncensored')
    return rendu


CONF_DISTANTE = Path(__file__).resolve().parent / 'traduire.conf'
MODELE_DISTANT = 'claude-opus-5'


def cle_distante():
    """La clé d'API, lue dans outils/traduire.conf — jamais ailleurs.

    Même règle que publier.conf : le fichier est ignoré par git, la clé ne
    quitte pas cette machine et n'apparaît dans aucun exemple.
    """
    if not CONF_DISTANTE.is_file():
        return ''
    for ligne in CONF_DISTANTE.read_text(encoding='utf-8').splitlines():
        if ligne.strip().startswith('#') or '=' not in ligne:
            continue
        nom, _, valeur = ligne.partition('=')
        if nom.strip() == 'cle_api':
            return valeur.strip()
    return ''


def demander_distant(systeme: str, texte: str, jetons: int, delai: int) -> str:
    """La même demande, adressée à Claude plutôt qu'au modèle de la maison.

    Le paquet `anthropic` n'est PAS une dépendance de ce dépôt : l'atelier
    tourne avec la bibliothèque standard et `yaml`. L'import est donc fait
    ici, au moment de s'en servir, et son absence est une phrase lisible
    plutôt qu'une trace d'exécution.
    """
    try:
        import anthropic
    except ImportError:
        raise ValueError(
            "Le paquet « anthropic » n'est pas installé. Sur cette machine, "
            'pip est bloqué (PEP 668) : passer par l\'AUR — '
            'yay -S python-anthropic') from None
    cle = cle_distante()
    if not cle:
        raise ValueError(f'Pas de clé d\'API. Écrire « cle_api = … » dans '
                         f'{CONF_DISTANTE.name}, à côté de publier.conf.')
    client = anthropic.Anthropic(api_key=cle, timeout=float(delai))
    reponse = client.beta.messages.create(
        model=MODELE_DISTANT,
        max_tokens=jetons,
        system=systeme,
        messages=[{'role': 'user', 'content': texte}],
        output_config={'effort': 'low'},          # traduire ne demande pas de réflexion
        betas=['server-side-fallback-2026-07-01'],
        fallbacks='default',
    )
    if reponse.stop_reason == 'refusal':
        raise ValueError('le service a refusé de traiter ce passage')
    return ''.join(b.text for b in reponse.content if getattr(b, 'type', '') == 'text')


def demandeur(moteur: str, hote: str):
    """Rend la fonction qui parlera au moteur choisi. Les garde-fous, eux,
    ne changent pas : c'est tout l'intérêt de passer par ici."""
    if moteur == 'distant':
        return lambda systeme, texte, jetons, delai: demander_distant(
            systeme, texte, jetons, delai)
    return lambda systeme, texte, jetons, delai: demander(
        hote, systeme, texte, jetons, delai)


# --- découpe et recollage -------------------------------------------------

def morceler(corps: str, taille: int):
    """Coupe le corps sur les lignes vides, jamais dans un bloc de code.

    Les morceaux se recollent bout à bout : ''.join(morceler(c)) == c.
    """
    morceaux, courant, longueur, code = [], [], 0, False
    for ligne in corps.splitlines(keepends=True):
        if ligne.lstrip().startswith(('```', '~~~')):
            code = not code
        courant.append(ligne)
        longueur += len(ligne)
        if not code and not ligne.strip() and longueur >= taille:
            morceaux.append(''.join(courant))
            courant, longueur = [], 0
    if courant:
        morceaux.append(''.join(courant))
    return morceaux or ['']


def nettoyer(source: str, brut: str) -> str:
    """Rogne ce que le modèle ajoute autour, et rend les sauts de ligne du bord."""
    texte = brut.strip('\n')
    lignes = texte.splitlines()
    # une réponse enveloppée dans une clôture de code, alors que la source
    # n'en ouvre pas : le modèle a « encadré » sa traduction
    if (len(lignes) > 2 and lignes[0].startswith('```')
            and lignes[-1].startswith('```') and '```' not in source):
        texte = '\n'.join(lignes[1:-1])
    devant = len(source) - len(source.lstrip('\n'))
    derriere = len(source) - len(source.rstrip('\n'))
    texte = '\n' * devant + texte + '\n' * derriere
    # Le modèle termine volontiers ses lignes par deux espaces — la coupure
    # forcée de Markdown. La source n'en a pas : on rend à chaque ligne la
    # fin de la sienne, quand les deux se correspondent une pour une.
    lignes_source, lignes_traduites = source.splitlines(), texte.splitlines()
    if len(lignes_source) == len(lignes_traduites):
        rendues = []
        for origine, traduite in zip(lignes_source, lignes_traduites):
            queue = origine[len(origine.rstrip()):]
            rendues.append(traduite.rstrip() + queue if traduite.strip() else traduite.rstrip())
        texte = '\n'.join(rendues) + ('\n' if texte.endswith('\n') else '')
    return texte


# --- les garde-fous -------------------------------------------------------

def empreinte(texte: str) -> dict:
    """Ce qui doit survivre à une traduction, mot pour mot."""
    lignes = texte.splitlines()
    return {
        'lignes': len(lignes),
        'vides': tuple(i for i, l in enumerate(lignes) if not l.strip()),
        'liens': sorted(a or b for a, b in LIEN.findall(texte)),
        'titres': sorted(m.group(1) for m in TITRE.finditer(texte)),
        'cloture': texte.count('```'),
        'balises': sorted(m.group(1).lower() for m in BALISE.finditer(texte)),
    }


def controler(source: str, traduit: str):
    """La liste des écarts entre la source et sa traduction. Vide = bon."""
    if not traduit.strip():
        return ['réponse vide']
    a, b = empreinte(source), empreinte(traduit)
    ecarts = []
    if a['lignes'] != b['lignes']:
        ecarts.append(f"{a['lignes']} lignes en français, {b['lignes']} traduites")
    elif a['vides'] != b['vides']:
        ecarts.append('les lignes vides ont bougé')
    if a['liens'] != b['liens']:
        perdus = sorted(set(a['liens']) - set(b['liens']))
        inventes = sorted(set(b['liens']) - set(a['liens']))
        detail = ' / '.join(filter(None, [', '.join(perdus[:3]), ', '.join(inventes[:3])]))
        ecarts.append(f'liens ou images modifiés : {detail}')
    if a['titres'] != b['titres']:
        ecarts.append('les niveaux de titre ne correspondent plus')
    if a['cloture'] != b['cloture']:
        ecarts.append('les blocs de code ne se referment plus pareil')
    if a['balises'] != b['balises']:
        manque = sorted(set(a['balises']) - set(b['balises']))
        if manque:
            ecarts.append('balises HTML perdues : ' + ', '.join(manque[:4]))
        else:
            ecarts.append('balises HTML ajoutées ou déplacées')
    for marqueur in BAVARDAGE:
        if marqueur in traduit:
            ecarts.append(f'bavardage du modèle : « {marqueur} »')
            break
    return ecarts


# --- les pages ------------------------------------------------------------

def index(langue: str) -> dict:
    """{clé de traduction: fichier} — l'appariement dont le site se sert."""
    trouve = {}
    dossier = CONTENU / langue
    if not dossier.is_dir():
        return trouve
    for f in sorted(dossier.rglob('*.md')):
        entete, _ = separer(f.read_text(encoding='utf-8'))
        cle = valeur(entete, 'traduction')
        if cle:
            trouve.setdefault(cle, f)
    return trouve


def noms_calques(langue: str, jumelles: dict) -> bool:
    """La langue reprend-elle les noms de fichiers français, ou les traduit-elle ?

    Le nom du fichier EST l'adresse de la page : il ne se décide pas au
    jugé. L'anglais déposé en août 2026 a gardé les noms français —
    `3eme-livre.md`, `actualite.md`. L'italien vient de l'ancien site
    avec ses propres adresses — `libro-3.md`, `attualita.md`. On mesure
    ce que la langue fait déjà, plutôt que de le supposer.
    """
    memes = total = 0
    for f in (CONTENU / SOURCE).glob('*.md'):
        entete, _ = separer(f.read_text(encoding='utf-8'))
        cible = jumelles.get(valeur(entete, 'traduction'))
        if cible is None:
            continue
        total += 1
        memes += cible.name == f.name
    return total > 0 and memes >= 0.8 * total


def destination(f_source: Path, langue: str, calque: bool):
    """Où écrire une page sans jumelle, ou None si ce n'est pas à nous d'en décider.

    On ne crée un fichier que là où son nom ne fait aucun doute : une page
    de premier niveau, dans une langue qui reprend déjà les noms français.
    Dans une rubrique, ou dans une langue qui traduit ses adresses, le nom
    et la numérotation appartiennent à « Jumelle », dans l'atelier :
    `fr/001-cas-clinique-1` s'y appelle `it/001-caso-clinico-1`.
    """
    relatif = f_source.relative_to(CONTENU / SOURCE)
    if len(relatif.parts) == 1 and calque:
        return CONTENU / langue / relatif.name
    return None


def entete_neuf(entete: str, langue: str, titre: str) -> str:
    """L'en-tête de la source, porté dans la langue d'arrivée."""
    lignes = []
    for ligne in entete.splitlines():
        if ligne.startswith('titre:'):
            lignes.append(f'titre: "{guillemets(titre)}"')
        elif ligne.startswith('langue:'):
            lignes.append(f'langue: "{langue}"')
            lignes.append(f'origine: "{SOURCE}"')
        elif ligne.startswith(('origine:', 'traduction_automatique:')):
            continue
        else:
            lignes.append(ligne)
    return '\n'.join(lignes) + '\n\ntraduction_automatique: "oui"'


def marquer_auto(entete: str) -> str:
    """La mention de traduction machine, si elle n'y est pas déjà."""
    if re.search(r'^traduction_automatique:', entete, re.M):
        return entete
    return entete.rstrip('\n') + '\n\ntraduction_automatique: "oui"'


def etat(f_source: Path, jumelles: dict):
    """(état, fichier d'arrivée) pour une page française.

    « vide » n'est pas un manque : neuf pages du site n'ont pas de corps
    du tout — `livres`, `temoignages`, les fiches « À la une »… leur
    contenu est la liste de leur rubrique, engendrée. Sans ce cas, elles
    se signalaient comme « en attente » dans les deux langues (leur corps
    vide égale bien celui du français) et le modèle aurait été appelé
    pour traduire rien.
    """
    entete, corps = separer(f_source.read_text(encoding='utf-8'))
    cle = valeur(entete, 'traduction')
    cible = jumelles.get(cle) if cle else None
    if not corps.strip():
        return 'vide', cible
    if cible is None:
        return 'absente', None
    _, corps_cible = separer(cible.read_text(encoding='utf-8'))
    if corps_cible.strip() == corps.strip():
        return 'en attente', cible          # jumelle créée par l'atelier, texte encore français
    return 'traduite', cible


# --- le travail -----------------------------------------------------------

def traduire_texte(hote, langue, texte, jetons, delai, dire, taille=TAILLE,
                   parler=None):
    """Traduit un texte en respectant sa structure, ou lève ValueError.

    Rend (traduction, reprises). « reprises » compte les morceaux que le
    modèle a d'abord rendus de travers : c'est la mesure la plus directe
    de sa docilité, et elle sert à comparer deux modèles sur les mêmes
    pages sans avoir à les lire.
    """
    systeme = CONSIGNE.format(langue=NOMS.get(langue, langue), marque=marque(langue))
    parler = parler or (lambda s, t, j, d: demander(hote, s, t, j, d))
    sortie, reprises = [], 0
    morceaux = morceler(texte, taille)
    for n, morceau in enumerate(morceaux, 1):
        if not morceau.strip():
            sortie.append(morceau)
            continue
        depart = time.monotonic()
        consigne, ecarts = systeme, []
        for essai in (1, 2):
            brut = parler(consigne, morceau, jetons, delai)
            propre = nettoyer(morceau, brut)
            ecarts = controler(morceau, propre)
            if not ecarts:
                break
            reprises += 1
            consigne = systeme + RAPPEL.format(ecarts='; '.join(ecarts))
            dire(f"      morceau {n} : {'; '.join(ecarts)} — on redemande")
        if ecarts:
            raise ValueError('; '.join(ecarts))
        sortie.append(propre)
        dire(f'      morceau {n}/{len(morceaux)} — {time.monotonic() - depart:.0f} s')
    return ''.join(sortie), reprises


def traduire_titre(hote, langue, titre, delai):
    systeme = (f'{marque(langue)}Translate this short web page title from French into '
               f'{NOMS.get(langue, langue)}. Answer with the translation only, '
               f'on a single line, no quotes around it.')
    rendu = demander(hote, systeme, titre, 200, delai).strip().strip('"').splitlines()
    return rendu[0].strip() if rendu else titre


def main():
    a = argparse.ArgumentParser(description='Traduit les pages du site avec le modèle local.')
    a.add_argument('langue', help="langue d'arrivée : en, it…")
    a.add_argument('--page', help='une seule page, chemin relatif à site/contenu/fr')
    a.add_argument('--appliquer', action='store_true', help='écrire (sinon : à blanc)')
    a.add_argument('--remplacer', action='store_true', help='refaire les pages déjà traduites')
    a.add_argument('--hote', default=HOTE)
    a.add_argument('--modele', default=MODELE_ATTENDU,
                   help='motif attendu dans le nom du modèle chargé '
                        "(-  ou vide pour n'exiger aucun modèle en particulier)")
    a.add_argument('--jetons', type=int, default=4096)
    a.add_argument('--taille', type=int, default=TAILLE,
                   help='caractères par morceau ; plus court = plus docile, plus lent')
    a.add_argument('--delai', type=int, default=900, help='secondes par morceau')
    opt = a.parse_args()

    if not (CONTENU / opt.langue).is_dir():
        sys.exit(f"Pas de dossier site/contenu/{opt.langue}.")

    racine = CONTENU / SOURCE
    if opt.page:
        pages = [racine / opt.page]
        if not pages[0].is_file():
            sys.exit(f'Page introuvable : {pages[0]}')
    else:
        pages = sorted(p for p in racine.rglob('*.md') if not p.name.startswith('_'))

    jumelles = index(opt.langue)
    calque = noms_calques(opt.langue, jumelles)
    a_faire, absentes, deja, vides = [], [], [], []
    for f in pages:
        situation, cible = etat(f, jumelles)
        if situation == 'vide':
            vides.append(f)
        elif situation == 'absente':
            ou = destination(f, opt.langue, calque)
            (a_faire if ou else absentes).append((f, ou))
        elif situation == 'en attente':
            a_faire.append((f, cible))
        elif opt.remplacer:
            a_faire.append((f, cible))
        else:
            deja.append(f)

    print(f'{len(pages)} pages françaises · {len(deja)} déjà traduites en {opt.langue} '
          f'· {len(a_faire)} à traduire · {len(vides)} sans corps '
          f'· {len(absentes)} sans jumelle possible')
    for f, ou in a_faire[:200]:
        print(f'  à traduire  {f.relative_to(racine)}'
              f"{'' if ou.exists() else '   (page neuve)'}")
    if absentes:
        raison = ("cette langue traduit ses noms de fichiers"
                  if not calque else "la numérotation de la rubrique lui appartient")
        for f, _ in absentes[:200]:
            print(f"  jumelle à créer dans l'atelier ({f.relative_to(racine)}) : {raison}")

    if not opt.appliquer:
        print('\nÀ blanc. Rien n\'a été écrit — ajouter --appliquer.')
        return 0
    if not a_faire:
        return 0

    charge = modele_charge(opt.hote)
    if not charge:
        sys.exit(f"Rien ne répond sur {opt.hote}. Lancer le serveur : qwen-uncensored")
    if opt.modele not in ('', '-', '—') and opt.modele.lower() not in charge.lower():
        sys.exit(f"Le modèle chargé est « {charge} », pas un « {opt.modele} ».\n"
                 f"C'est le 7B qui avait abîmé le lot anglais : on ne recommence pas par "
                 f'distraction. Lancer `qwen-uncensored`, ou passer --modele -')
    print(f'\nModèle : {charge}\n')

    traduites, refusees, total_reprises = 0, [], 0
    for f, ou in a_faire:
        nom = f.relative_to(racine)
        print(f'  {nom}')
        entete, corps = separer(f.read_text(encoding='utf-8'))
        try:
            texte, reprises = traduire_texte(opt.hote, opt.langue, corps,
                                             opt.jetons, opt.delai, print, opt.taille)
            titre = traduire_titre(opt.hote, opt.langue, valeur(entete, 'titre'), opt.delai)
        except (ValueError, urllib.error.URLError, OSError, KeyError) as souci:
            print(f'      REFUSÉE — {souci}')
            refusees.append((nom, souci))
            continue
        if ou.exists():
            entete_cible, _ = separer(ou.read_text(encoding='utf-8'))
            sortie = marquer_auto(entete_cible)
        else:
            sortie = entete_neuf(entete, opt.langue, titre)
        ou.parent.mkdir(parents=True, exist_ok=True)
        ou.write_text(f'---\n{sortie}\n---\n\n{texte}', encoding='utf-8')
        print(f'      écrit dans {ou.relative_to(CONTENU)}'
              + (f' — {reprises} morceau(x) repris' if reprises else ''))
        traduites += 1
        total_reprises += reprises

    print(f'\n{traduites} pages écrites, {len(refusees)} refusées, '
          f'{total_reprises} morceaux repris.')
    for nom, souci in refusees:
        print(f'  {nom} : {souci}')
    if refusees:
        print('\nUne page refusée n\'a rien écrit du tout : le fichier d\'arrivée est '
              'intact. Relancer sur elle seule avec --page.')
    return 1 if refusees else 0


if __name__ == '__main__':
    sys.exit(main())
