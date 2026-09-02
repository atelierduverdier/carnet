#!/usr/bin/env python3
# =========================================================================
# generer.py — engendre le site statique à partir du Markdown
# =========================================================================
# Lit site/contenu/<langue>/**.md + site/config.yaml + kit/, et écrit
# tout le site dans site/public/.
#
# UTILISATION :
#   python3 site/generer.py              # engendre dans site/public/
#   python3 site/generer.py --servir     # engendre puis sert sur :8000
#
# site/public/ est ENTIÈREMENT reconstruit à chaque passage : ne rien y
# éditer à la main, tout part de contenu/ et de kit/.
# =========================================================================

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

try:
    import yaml
    import markdown
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from markupsafe import Markup, escape
except ImportError as e:                                    # pragma: no cover
    sys.exit(f"generer : module manquant ({e.name}).\n"
             f"  sudo pacman -S python-yaml python-markdown python-jinja")

RACINE = Path(__file__).resolve().parent.parent
KIT = RACINE / 'kit'
THEMES = RACINE / 'themes'

# =========================================================================
# Les thèmes
# =========================================================================
# Un thème est un DOSSIER : themes/<nom>/, avec ses gabarits, sa feuille de
# style, son script, ses polices et ses images. `theme:` dans config.yaml
# dit lequel le site porte.
#
# Un thème peut en HÉRITER d'un autre (`herite:` dans son theme.yaml) : ce
# qu'il ne fournit pas est pris chez son parent. Sans cela, changer trois
# couleurs obligerait à recopier cinq gabarits et deux cents lignes de
# style — et la copie se périmerait au premier correctif.
#
# `kit/` reste compris comme un thème sans nom : les sites nés avant les
# thèmes continuent de fonctionner sans rien changer.


def theme_de(config) -> list:
    """La chaîne de dossiers où chercher un élément d'habillage.

    Du plus précis au plus général : le thème du site, puis ceux dont il
    hérite. Une boucle d'héritage s'arrête d'elle-même.
    """
    nom = str(config.get('theme') or '').strip()
    if nom and not (THEMES / nom).is_dir():
        # Une faute de frappe ne doit pas rendre le site illisible : on
        # retombe sur l'habillage disponible, mais on le DIT — sans quoi
        # l'on chercherait longtemps pourquoi la bascule « n'a rien fait ».
        dispo = sorted(d.name for d in THEMES.iterdir() if d.is_dir()) \
            if THEMES.is_dir() else []
        print(f'  ATTENTION : le thème « {nom} » n’existe pas dans themes/.')
        print(f'  Thèmes disponibles : {", ".join(dispo) or "aucun"}.'
              f' On engendre avec l’habillage par défaut.')
        nom = ''
    if not nom:
        if KIT.is_dir():
            return [KIT]
        dispo = sorted(d.name for d in THEMES.iterdir() if d.is_dir()) \
            if THEMES.is_dir() else []
        # un thème de repli doit être COMPLET : celui qui porte les
        # gabarits. Le premier par ordre alphabétique peut n'être qu'une
        # feuille de style héritée, et le site sortirait sans une page.
        nom = next((c for c in dispo if (THEMES / c / 'gabarits').is_dir()), '')
        if not nom:
            return [THEMES / (dispo[0] if dispo else 'aucun')]
    chaine, vus = [], set()
    while nom and nom not in vus and (THEMES / nom).is_dir():
        vus.add(nom)
        chaine.append(THEMES / nom)
        fiche = THEMES / nom / 'theme.yaml'
        parent = ''
        if fiche.is_file():
            try:
                parent = str((yaml.safe_load(fiche.read_text(encoding='utf-8'))
                              or {}).get('herite') or '')
            except yaml.YAMLError:
                parent = ''
        nom = parent
    return chaine


def empreinte_cumulee(chaine, quoi: str) -> str:
    """L'empreinte de tous les exemplaires empilés, du parent à l'enfant."""
    morceaux = [d / quoi for d in reversed(chaine) if (d / quoi).is_file()]
    if not morceaux:
        return ''
    return hashlib.sha256(b''.join(m.read_bytes() for m in morceaux)).hexdigest()[:8]


def dans_le_theme(chaine, quoi: str):
    """Le premier exemplaire trouvé en remontant l'héritage, ou None."""
    for dossier in chaine:
        cible = dossier / quoi
        if cible.exists():
            return cible
    return None
SITE = RACINE / 'site'
CONTENU = SITE / 'contenu'
MEDIAS = SITE / 'medias'
PUBLIC = SITE / 'public'

# ON N'EFFACE PAS CE QU'ON NE SAIT PAS ENCORE REFAIRE. Le site engendré
# était rasé AVANT le travail : la moindre panne en cours de route — un
# « titre: » oublié, une clé absente de config.yaml — laissait 0 fichier
# là où il y en avait 1 182 (mesuré trois fois). Tout s'écrit désormais
# dans un chantier, et l'on bascule à la fin, par deux renommages : le
# site précédent survit à tout ce qui peut mal tourner.
CHANTIER = SITE / '.public-en-cours'
PRECEDENT = SITE / '.public-precedent'

MOIS = {
    'fr': ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
           'août', 'septembre', 'octobre', 'novembre', 'décembre'],
    'it': ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
           'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'],
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December'],
}

# Les quelques mots d'interface. Une langue absente retombe sur le français.
MOTS = {
    'fr': {'rechercher': 'Rechercher…', 'langue': 'Langue', 'menu': 'Menu principal',
           'contact': 'Contact', 'fil': "Fil d'Ariane", 'entrees': 'entrées',
           'page': 'page', 'pagination': 'Pages', 'voisines': 'Navigation',
           'accueil': 'Accueil', 'pas_traduit': 'Pas encore traduit',
           'engendre': 'Site statique engendré par un script Python.',
           'avis_traduction': 'Cette page a été traduite avec un traducteur automatique.',
           'traduction_courte': 'traduction automatique',
           'a_la_une': 'À la une', 'toutes_annonces': 'toutes les annonces ›',
           'origine_autre': 'Témoignage écrit en {langue}, traduit.',
           'origine_autre_auto': 'Témoignage écrit en {langue}, traduit automatiquement.',
           'sommaire': 'Sommaire',
           'langue_fr': 'français', 'langue_it': 'italien', 'langue_en': 'anglais',
           'rien_trouve': 'Aucun résultat',
           'erreur_titre': 'Cette page n’existe pas',
           'erreur_texte': 'L’adresse demandée ne correspond à aucune page du '
                           'site. Elle a peut-être changé, ou comporte une '
                           'faute de frappe. Le menu ci-dessus et la recherche '
                           'vous remettront sur la voie.'},
    'it': {'rechercher': 'Cerca…', 'langue': 'Lingua', 'menu': 'Menu principale',
           'contact': 'Contatti', 'fil': 'Percorso', 'entrees': 'voci',
           'page': 'pagina', 'pagination': 'Pagine', 'voisines': 'Navigazione',
           'accueil': 'Home', 'pas_traduit': 'Non ancora tradotto',
           'engendre': 'Sito statico generato da uno script Python.',
           'avis_traduction': 'Questa pagina è stata tradotta con un traduttore automatico.',
           'traduction_courte': 'traduzione automatica',
           'a_la_une': 'In evidenza', 'toutes_annonces': 'tutti gli annunci ›',
           'origine_autre': 'Testimonianza scritta in {langue}, tradotta.',
           'origine_autre_auto': 'Testimonianza scritta in {langue}, tradotta automaticamente.',
           'sommaire': 'Sommario',
           'langue_fr': 'francese', 'langue_it': 'italiano', 'langue_en': 'inglese',
           'rien_trouve': 'Nessun risultato',
           'erreur_titre': 'Questa pagina non esiste',
           'erreur_texte': 'L’indirizzo richiesto non corrisponde a nessuna '
                           'pagina del sito. Forse è cambiato, o contiene un '
                           'errore di battitura. Il menu qui sopra e la '
                           'ricerca vi rimetteranno sulla buona strada.'},
    'en': {'rechercher': 'Search…', 'langue': 'Language', 'menu': 'Main menu',
           'contact': 'Contact', 'fil': 'Breadcrumb', 'entrees': 'entries',
           'page': 'page', 'pagination': 'Pages', 'voisines': 'Navigation',
           'accueil': 'Home', 'pas_traduit': 'Not translated yet',
           'engendre': 'Static site generated by a Python script.',
           'avis_traduction': 'This page was translated using a machine translator.',
           'traduction_courte': 'machine translation',
           'a_la_une': 'Latest', 'toutes_annonces': 'all announcements ›',
           'origine_autre': 'Account written in {langue}, translated.',
           'origine_autre_auto': 'Account written in {langue}, machine-translated.',
           'sommaire': 'Contents',
           'langue_fr': 'French', 'langue_it': 'Italian', 'langue_en': 'English',
           'rien_trouve': 'No results',
           'erreur_titre': 'This page does not exist',
           'erreur_texte': 'The requested address matches no page on this site. '
                           'It may have changed, or contain a typing mistake. '
                           'The menu above and the search will put you back on '
                           'track.'},
}


# =========================================================================
# Lecture du contenu
# =========================================================================

def entier(v, defaut=0) -> int:
    """Un nombre lu dans un en-tête, sans faire tomber la régénération.

    Le tri d'une rubrique comparait le `rang` tel quel : un « rang: abc »
    écrit à la main donnait « TypeError: '<' not supported between
    instances of 'int' and 'str' » — une trace qui ne nomme NI le
    fichier, NI la rubrique, et le site engendré avec.
    """
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return defaut


def lire_yaml(chemin: Path, defaut=None):
    """Relit un YAML du site, ou dit LEQUEL ne se relit pas.

    `yaml.safe_load` nu remontait une trace qui ne nommait pas le
    fichier — sur trois menus et un magasin de textes, cela revient à ne
    rien dire. Même soin que `lire_entete` pour les pages.
    """
    try:
        return yaml.safe_load(chemin.read_text(encoding='utf-8')) or defaut
    except (OSError, yaml.YAMLError) as souci:
        detail = str(souci).replace('\n', '\n     ')
        try:
            nom = chemin.relative_to(RACINE)
        except ValueError:
            nom = chemin
        sys.exit(f"\n  CE FICHIER DE RÉGLAGES EST ILLISIBLE :\n"
                 f"     {nom}\n\n     {detail}\n\n"
                 f"  Rien n'a été engendré ; le site précédent est intact.")


def exige(config, cle: str):
    """Une clé que config.yaml DOIT porter.

    `config['domaine']` rendait « KeyError: 'domaine' » — exact, et
    illisible pour qui vient d'écrire son premier config.yaml. Trois clés
    sont dans ce cas : domaine, langue_par_defaut, devise.
    """
    if cle not in config:
        sys.exit(f"\n  IL MANQUE UN RÉGLAGE DANS site/config.yaml :\n"
                 f"     « {cle} »\n\n"
                 f"  Rien n'a été engendré ; le site précédent est intact.\n"
                 f"  Voir l'exemple livré avec le squelette.")
    return config[cle]


def lire_entete(texte: str, origine: str = ''):
    """Sépare l'en-tête YAML du corps Markdown.

    L'ORIGINE N'EST PAS DÉCORATIVE. Un seul fichier au YAML abîmé — un
    guillemet oublié, une tabulation — faisait tomber le générateur sur une
    trace Python qui nommait « ligne 2 » d'une chaîne anonyme. Sur 730
    fichiers, cela revenait à ne rien dire. On rattrape donc l'erreur pour
    la rendre à qui peut la corriger : avec le nom du fichier.
    """
    if not texte.startswith('---'):
        return {}, texte
    fin = texte.find('\n---', 3)
    if fin == -1:
        return {}, texte
    try:
        entete = yaml.safe_load(texte[3:fin]) or {}
    except yaml.YAMLError as e:
        detail = str(e).replace('\n', '\n     ')
        sys.exit(f"\n  L'EN-TÊTE DE CE FICHIER EST ILLISIBLE :\n"
                 f"     {origine or '(fichier inconnu)'}\n\n"
                 f"     {detail}\n\n"
                 f"  Rien n'a été engendré. Le plus souvent : un guillemet\n"
                 f"  ouvert et jamais refermé, ou un « : » dans une valeur\n"
                 f"  qui n'est pas entre guillemets.")
    if not isinstance(entete, dict):
        sys.exit(f"\n  L'EN-TÊTE DE CE FICHIER N'EST PAS UNE LISTE DE RÉGLAGES :\n"
                 f"     {origine or '(fichier inconnu)'}\n\n"
                 f"  Il a été lu comme {type(entete).__name__}. Rien n'a été engendré.")
    return entete, texte[fin + 4:].lstrip('\n')


def precision_de(fiche) -> str:
    """Quelle précision d'affichage mérite la date de cette fiche.

    Une date « approximative » est une date dont on ne connaît que
    l'année : l'import l'a posée au 1er janvier faute de mieux. L'afficher
    en toutes lettres — « 1 janvier 2018 » — invente un jour et un mois
    que personne n'a jamais écrits, et le lecteur y voit un défaut : c'est
    ce qui a été mesuré sur une rubrique où treize cartes portaient toutes
    un 1er janvier. On ne l'affiche donc pas. L'année, elle, reste lisible
    dans le titre de la fiche.
    """
    if str(fiche.get('date_approximative', '')).lower() in ('oui', 'true', 'vrai'):
        return 'cachee'
    return fiche.get('date_precision', 'jour')


def unite_lisible(unite, combien: int, defaut: str) -> str:
    """Le nom de ce qu'on compte, au singulier ou au pluriel.

    « 200 entrées » est un mot de base de données ; « 200 témoignages »
    dit la même chose et dit quelque chose. Chaque collection nomme donc
    ses fiches dans son _index.md, sous la forme « singulier|pluriel » —
    car l'italien ne fabrique pas son pluriel en ajoutant une lettre
    (testimonianza / testimonianze).

    La clé s'appelle « nom_des_fiches » et non « unite » : un site importé
    d'ailleurs peut déjà porter une clé « unite » qui veut dire autre chose
    (c'est le cas d'un site engendré depuis WordPress).
    """
    if not unite:
        return defaut
    formes = str(unite).split('|')
    return formes[0] if combien <= 1 and len(formes) > 1 else formes[-1]


def date_lisible(iso: str, langue: str, precision: str = 'jour') -> str:
    """Une date ne s'affiche pas plus précisément qu'on ne la connaît.

    Les annonces reprises de l'ancien accueil ne portaient parfois que
    le mois (« novembre 2023 »), et deux n'avaient aucune date. Inventer
    un jour serait plus faux que de n'en pas mettre.
    """
    try:
        an, mo, jo = str(iso).split('-')
        # le « - 1 » sans borne basse : « 2020-00-05 » donnait l'indice -1,
        # donc « 5 décembre 2020 » — faux, et silencieux.
        numero = int(mo)
        if not 1 <= numero <= 12:
            raise ValueError(mo)
        mois = MOIS.get(langue, MOIS['fr'])[numero - 1]
    except (ValueError, IndexError):
        return str(iso)
    if precision == 'cachee':
        # la date sert à ranger, mais le titre la porte déjà : l'afficher
        # deux fois sur la même carte n'apprend rien à personne
        return ''
    if precision == 'annee':
        return an
    if precision == 'mois':
        return f'{mois} {an}'
    return f'{int(jo)} {mois} {an}'


def charger(config) -> dict:
    """Relève toutes les fiches et pages, langue par langue."""
    tout = {}
    for langue in config['langues']:
        dossier = CONTENU / langue
        if not dossier.is_dir():
            print(f"  ! aucun contenu pour « {langue} »")
            tout[langue] = []
            continue
        pages = []
        for f in sorted(dossier.rglob('*.md')):
            entete, corps = lire_entete(f.read_text(encoding='utf-8'),
                                          str(f.relative_to(RACINE)))
            if not entete:
                continue
            entete['fichier'] = f
            entete['corps'] = corps
            entete.setdefault('langue', langue)
            entete.setdefault('type', 'page')
            entete.setdefault('statut', 'publie')
            nom = f.stem
            # SANS TITRE, tout tombait sur « KeyError: 'titre' » — une trace
            # qui ne nomme pas le fichier, alors qu'on l'a sous la main. Le
            # nom du fichier fait un titre passable ; on le dit tout haut,
            # pour que ce soit corrigé plutôt que subi.
            if not str(entete.get('titre') or '').strip():
                print(f"  ! {f.relative_to(RACINE)} n’a pas de « titre: » — "
                      f"le nom du fichier en tient lieu")
                entete['titre'] = nom.replace('-', ' ').strip().capitalize() or nom
            if entete['type'] == 'collection':
                entete['slug'] = f.parent.name
                entete['url'] = f'/{langue}/{f.parent.name}/'
            elif entete['type'] == 'fiche':
                entete['slug'] = nom
                entete['url'] = f'/{langue}/{f.parent.name}/{nom}/'
                # Une annonce est souvent un simple renvoi : une vidéo, un
                # éditeur, ou une page qui existe déjà ailleurs sur le
                # site. RÈGLE : un « lien » dans l'en-tête veut dire « la
                # carte mène là », et aucune page n'est engendrée — sinon
                # on fabrique un doublon dont personne ne veut.
                entete['cible'] = entete.get('lien') or entete['url']
                entete['propre_page'] = not entete.get('lien')
                if entete.get('lien') and corps.strip():
                    entete.setdefault('extrait', corps.strip()[:180])
            else:
                entete['slug'] = entete.get('slug') or nom
                entete['url'] = f'/{langue}/{entete["slug"]}/'
            pages.append(entete)
        tout[langue] = pages
    return tout


# =========================================================================
# Rendu Markdown
# =========================================================================

def empreinte(fichier) -> str:
    """Huit caractères tirés du contenu, pour forcer le renouvellement du cache.

    Sans cela, le navigateur garde l'ancienne feuille de style après une
    régénération : on croit la modification perdue et on la refait deux
    fois. L'empreinte change avec le fichier, jamais autrement.

    Un thème peut ne pas fournir un fichier — il l'hérite, ou s'en passe :
    l'absence rend une empreinte vide, elle ne fait pas tomber le site.
    """
    if fichier is None or not Path(fichier).is_file():
        return ''
    return hashlib.sha256(Path(fichier).read_bytes()).hexdigest()[:8]


def fabriquer_convertisseur():
    """Markdown → HTML.

    `nl2br` est INDISPENSABLE : dans l'export, WordPress gardait les
    lettres avec de simples retours à la ligne (un retour = <br> à
    l'affichage). Sans cette extension, Markdown recollerait chaque
    lettre en un seul pavé — le défaut même qu'on a corrigé à l'import.

    `fenced_code` l'est tout autant dès qu'un site montre des commandes.
    Markdown seul ne connaît que le bloc INDENTÉ de quatre espaces : les
    trois accents graves, il les lit comme du code EN LIGNE. Un bloc

        ```bash
        sudo pacman -Syu
        echo ok
        ```

    sortait donc en un unique <code> d'une seule coulée, le mot « bash »
    compris dedans, les retours à la ligne mangés — et rien ne le
    signalait : ni le générateur, ni le vérificateur, qui n'y voient
    qu'un paragraphe de plus. Il fallait relire la page pour s'en
    apercevoir. Avec l'extension, le bloc devient
    <pre><code class="language-bash">, et le thème peut l'habiller.

    Pas de coloration syntaxique : elle demanderait Pygments en dur, et
    sur du shell elle ne colore guère que les guillemets et les dièses.
    Le nom du langage est posé en classe — un thème qui la veut vraiment
    a de quoi la brancher.
    """
    return markdown.Markdown(
        extensions=['tables', 'attr_list', 'sane_lists', 'nl2br', 'md_in_html',
                    'toc', 'fenced_code'],
        # Les niveaux visés sont ceux du MARKDOWN, pas ceux du rendu :
        # le sommaire est bâti par l'extension avant que
        # `normaliser_titres` ne les renumérote.
        extension_configs={'toc': {'permalink': False, 'toc_depth': '1-2'}},
        output_format='html5')


# Au-delà de cette longueur, ce n'est plus un titre mais un paragraphe que
# l'auteur a mis en valeur. UNE SEULE constante pour les deux endroits qui
# s'en servent — le sommaire et le rendu : deux 70 écrits séparément
# finiraient par diverger, et le sommaire écarterait un texte que la page
# annoncerait encore comme un titre.
LIMITE_TITRE = 70


def degrader_faux_titres(h: str) -> str:
    """Rend au paragraphe ce qui n'a jamais été un titre.

    L'ancien WordPress permettait de grossir un texte en le balisant en
    titre. La citation de Krishnamurti qui ouvre les Réflexions fait ainsi
    331 signes, et l'introduction d'« Une nouvelle vision » est un
    paragraphe entier en <h3>. Le sommaire les écartait déjà ; le HTML,
    lui, les annonçait toujours comme des titres — un lecteur d'écran les
    lisait donc comme la structure de la page, et le plan sautait des
    échelons puisque ces faux titres n'avaient aucun rang cohérent.

    L'apparence ne change pas : la classe reprend le style du niveau
    d'origine. Seule la nature de la balise change.
    """
    def juger(m):
        niveau, attrs, contenu = m.group(1), m.group(2) or '', m.group(3)
        texte = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', contenu)).strip()
        if len(texte) <= LIMITE_TITRE:
            return m.group(0)
        return f'<p class="exergue exergue-{niveau}"{attrs}>{contenu}</p>'
    return re.sub(r'<h([1-6])(\s[^>]*)?>(.*?)</h\1>', juger, h, flags=re.S)


def normaliser_titres(h: str) -> str:
    """Remet les titres du corps sur des niveaux qui se suivent, dès <h2>.

    Le gabarit pose déjà le titre de la page en <h1> : le corps commence
    donc à <h2>. Deux défauts se corrigent ici, et il faut les traiter
    ensemble.

    LE DÉCALAGE DE TÊTE. Un corps qui commence par un <h1> le mettrait en
    concurrence avec celui du gabarit ; un corps qui commence par <h3> —
    et l'ancien WordPress en produisait beaucoup — laisse un trou dans le
    plan, h1 puis h3, qui fait perdre un échelon à la navigation par
    titres des lecteurs d'écran.

    LES TROUS INTERNES. Dans les Réflexions, le corps allait de <h2> à
    <h4> sans passer par <h3>. Descendre tout d'un cran, comme on le
    faisait, ne réparait que le premier défaut.

    D'où la règle unique : on relève les niveaux RÉELLEMENT présents, on
    les renumérote à la suite à partir de 2, et l'on applique cette table.
    La hiérarchie est conservée — deux titres de rangs différents le
    restent — sans qu'aucun échelon ne manque.
    """
    presents = sorted({int(n) for n in re.findall(r'<h([1-6])[\s>]', h)})
    if not presents:
        return h
    table = {v: min(2 + i, 6) for i, v in enumerate(presents)}
    if all(v == table[v] for v in presents):
        return h
    def refaire(m):
        return f'<{m.group(1)}h{table[int(m.group(2))]}{m.group(3) or ""}>'
    return re.sub(r'<(/?)h([1-6])(\s[^>]*)?>', refaire, h)


def fabriquer_sommaire(jetons, intitule, limite=LIMITE_TITRE):
    """Bâtit le sommaire en écartant les titres qui n'en sont pas.

    L'auteur balise parfois un paragraphe entier en titre pour le mettre
    en valeur — la citation de Krishnamurti qui ouvre les Réflexions fait
    ainsi 331 caractères. Repris tel quel, le sommaire recopiait
    l'introduction en entier. Au-delà de `limite` caractères, ce n'est
    plus un titre.
    """
    def niveau(jetons, profondeur=0):
        morceaux = []
        for j in jetons:
            texte = re.sub(r'\s+', ' ', j['name']).strip()
            enfants = niveau(j.get('children') or [], profondeur + 1)
            if len(texte) > limite:
                morceaux.extend(enfants)      # on garde ses sous-titres
                continue
            morceaux.append(f'<li><a href="#{escape(j["id"])}">{escape(texte)}</a>'
                            + (f'<ul>{"".join(enfants)}</ul>' if enfants else '')
                            + '</li>')
        return morceaux

    entrees = niveau(jetons)
    if len(entrees) < 3:
        return ''
    return Markup(f'<nav class="sommaire" aria-label="{escape(intitule)}">'
                  f'<h2>{escape(intitule)}</h2><ul>{"".join(entrees)}</ul></nav>')


def envelopper_tableaux(h: str) -> str:
    """Rend les tableaux défilables : ceux du site portent des images
    avant/après côte à côte, qui débordent sur un téléphone."""
    return re.sub(r'(<table\b.*?</table>)',
                  r'<div class="tableau-enveloppe">\1</div>', h, flags=re.S)


def rendre(md, corps: str):
    """Markdown → HTML déjà sûr.

    Jinja2 échappe tout par défaut — c'est ce qu'on veut pour les titres
    venus du contenu, mais pas pour du HTML qu'on vient de fabriquer.
    On le marque ici, une fois, plutôt que de semer des « |safe » dans
    les gabarits où l'oubli d'un seul passe inaperçu.
    """
    md.reset()
    # L'ordre compte : on écarte d'abord ce qui n'est pas un titre, sinon
    # les faux titres pèseraient sur le calcul des niveaux réellement
    # présents et fausseraient la renumérotation.
    return Markup(envelopper_tableaux(
        normaliser_titres(degrader_faux_titres(md.convert(corps)))))


BALISE_IMG = re.compile(r'<img\b[^>]*>')


def charger_textes_medias():
    """Les textes alternatifs écrits depuis l'atelier, par chemin de média."""
    f = MEDIAS / '_textes.yaml'
    if not f.is_file():
        return {}
    return lire_yaml(f, {})


def remplir_alt(html: str, langue: str, textes: dict) -> str:
    """Donne un texte alternatif aux images de /medias/ qui n'en ont pas.

    Le `alt` vivait DANS le texte de chaque page : la même image en
    portait un ici et rien là — 32 insertions renseignées sur 57 — et
    aucune ne pouvait varier selon la langue. Le magasin le porte
    désormais une fois, en trois langues.

    Un `alt` écrit à la main dans le contenu n'est JAMAIS remplacé : il
    dit ce que cette page-là veut dire de l'image, le magasin ne connaît
    que le fichier.
    """
    if not textes:
        return html

    def echapper(t):
        return (t.replace('&', '&amp;').replace('"', '&quot;')
                 .replace('<', '&lt;').replace('>', '&gt;'))

    def remplacer(m):
        balise = m.group(0)
        src = re.search(r'src="([^"]*)"', balise)
        if not src or not src.group(1).startswith('/medias/'):
            return balise
        fiche = textes.get(src.group(1)[len('/medias/'):]) or {}
        texte = str(fiche.get(langue) or '').strip()
        if not texte:
            return balise
        alt = re.search(r'\salt="([^"]*)"', balise)
        if alt and alt.group(1).strip():
            return balise
        if alt:
            return balise[:alt.start()] + f' alt="{echapper(texte)}"' + balise[alt.end():]
        return balise[:-1].rstrip() + f' alt="{echapper(texte)}">'

    return BALISE_IMG.sub(remplacer, html)



# =========================================================================
# Les images en plusieurs tailles
# =========================================================================
# Le bandeau d'accueil fait 1 600 px et partait tel quel sur un téléphone
# de 390 px de large : dix fois le poids nécessaire, sur la connexion la
# plus lente. Chaque image citée dans une page reçoit donc des versions
# plus petites, en WebP, et le navigateur choisit celle qui lui va.
#
# Rien n'est AGRANDI : une image de 700 px ne reçoit que la déclinaison de
# 480. Et l'original reste servi tel quel — c'est lui, le dernier recours.

LARGEURS_IMAGES = (480, 960, 1600)
RASTER = {'.jpg', '.jpeg', '.png'}       # ni SVG (déjà fluide), ni GIF (animé)
_a_decliner = {}                          # chemin public → largeurs à produire


def taille_image(source: Path):
    try:
        from PIL import Image
        with Image.open(source) as im:
            return im.size
    except Exception:
        return None


def adapter_images(html: str, sizes: str, differer=True) -> str:
    """Donne à chaque image ses déclinaisons, ses dimensions et son chargement.

    `width`/`height` sont posés quand ils manquent : sans eux, la page
    saute au chargement des images — le texte qu'on lisait s'échappe.
    """
    if not html:
        return html

    def refaire(m):
        balise = m.group(0)
        src = re.search(r'src="(/medias/[^"]+)"', balise)
        if not src or 'srcset=' in balise:
            return balise
        chemin = src.group(1)
        source = MEDIAS / chemin[len('/medias/'):]
        if source.suffix.lower() not in RASTER or not source.is_file():
            return balise
        taille = taille_image(source)
        if not taille:
            return balise
        largeur, hauteur = taille

        cibles = [l for l in LARGEURS_IMAGES if l < largeur]
        ajouts = []
        if cibles:
            _a_decliner.setdefault(chemin, set()).update(cibles)
            tranche = [f'{decline(chemin, l)} {l}w' for l in cibles]
            tranche.append(f'{chemin} {largeur}w')
            ajouts.append(f'srcset="{", ".join(tranche)}"')
            ajouts.append(f'sizes="{sizes}"')
        if 'width=' not in balise:
            ajouts.append(f'width="{largeur}" height="{hauteur}"')
        prioritaire = 'fetchpriority="high"' in balise
        if differer and not prioritaire and 'loading=' not in balise:
            ajouts.append('loading="lazy" decoding="async"')
        if not ajouts:
            return balise
        return balise[:-1].rstrip() + ' ' + ' '.join(ajouts) + '>'

    return BALISE_IMG.sub(refaire, html)


def decline(chemin: str, largeur: int) -> str:
    """L'adresse d'une déclinaison : /medias/a/b.jpg → /medias/a/b-960.webp"""
    base = chemin.rsplit('.', 1)[0]
    return f'{base}-{largeur}.webp'


def produire_declinaisons() -> int:
    """Fabrique les déclinaisons recensées pendant le rendu. Renvoie le compte.

    Après la copie des médias, sinon elles seraient écrasées ; et jamais
    dans site/medias/, qui est la SOURCE — le dossier public se reconstruit,
    lui, à chaque passage.
    """
    try:
        from PIL import Image
    except ImportError:
        if _a_decliner:
            print('  ATTENTION : Pillow est absent — les images partent en une '
                  'seule taille.')
        return 0
    faites = 0
    for chemin, largeurs in sorted(_a_decliner.items()):
        source = MEDIAS / chemin[len('/medias/'):]
        if not source.is_file():
            continue
        try:
            with Image.open(source) as im:
                # LE WEBP SAIT LA TRANSPARENCE, la conversion la jetait :
                # sur un petit écran — le seul à recevoir la version 480 —
                # un PNG transparent devenait un rectangle opaque.
                im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
                for l in sorted(largeurs):
                    cible = PUBLIC / decline(chemin, l).lstrip('/')
                    cible.parent.mkdir(parents=True, exist_ok=True)
                    hauteur = round(im.height * l / im.width)
                    im.resize((l, hauteur), Image.LANCZOS).save(
                        cible, 'WEBP', quality=80, method=4)
                    faites += 1
        except Exception:
            continue          # une image illisible ne fait pas tomber le site
    return faites

def premiere_image(h: str) -> str:
    """L'image d'aperçu quand la page est partagée sur un réseau ou en message.

    Aucune page ne DÉCLARE d'image — elles en portent dans leur texte. On
    prend donc la première venue, qui est presque toujours l'illustration
    d'ouverture. Sans cela, un lien partagé n'affiche qu'un rectangle gris,
    et personne ne clique dessus.
    """
    m = re.search(r'<img[^>]+src="([^"]+)"', h)
    return m.group(1) if m else ''


def texte_nu(h: str, n=None) -> str:
    t = re.sub(r'<[^>]+>', ' ', h)
    t = re.sub(r'&[a-z]+;|&#\d+;', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:n] if n else t


# =========================================================================
# Menus
# =========================================================================

def elaguer_menu(entrees, existantes: set, perdus: list):
    """Retire les entrées visant une page qui n'existe pas.

    Le menu italien appelait « formazione », restée en BROUILLON : 218
    liens morts sur tout le site, un par page. Une rubrique qui perd
    tous ses enfants disparaît à son tour.
    """
    gardees = []
    for e in entrees:
        e = dict(e)
        lien = e.get('lien')
        enfants = elaguer_menu(e.get('entrees') or [], existantes, perdus)
        externe = bool(lien) and (lien.startswith(('http://', 'https://', 'mailto:'))
                                  or lien.startswith('/medias/'))
        valide = externe or (lien in existantes if lien else False)
        if lien and not valide:
            perdus.append((e.get('titre', ''), lien))
            e.pop('lien', None)
        e['entrees'] = enfants
        if e.get('lien') or enfants:
            gardees.append(e)
    return gardees


def rendre_menu(entrees, url_courante: str, profondeur=0) -> str:
    if not entrees:
        return ''
    morceaux = ['<ul>']
    for e in entrees:
        lien = e.get('lien')
        titre = e.get('titre', '')
        enfants = e.get('entrees') or []
        actif = lien == url_courante
        if lien:
            marque = ' aria-current="page"' if actif else ''
            # ÉCHAPPER, ici comme ailleurs. Ce Markup contourne
            # l'échappement de Jinja2 avec des données TAPÉES — et le menu
            # est rendu dans toutes les pages de la langue. Un guillemet
            # dans le lien sortait de l'attribut : « /x/" onclick="… »
            # devenait un gestionnaire d'événement.
            morceaux.append(
                f'<li><a href="{escape(lien)}"{marque}>{escape(titre)}</a>')
        else:
            # `tabindex` n'est pas décoratif : l'intitulé de rubrique n'est
            # pas un lien, donc pas focusable, et les liens du sous-menu sont
            # en `visibility: hidden` — donc infocusables eux aussi. Sans ce
            # point d'entrée, `:focus-within` ne peut jamais se déclencher et
            # 24 des 32 liens du menu étaient hors d'atteinte au clavier.
            morceaux.append(
                f'<li><span class="intitule" tabindex="0">{escape(titre)}</span>')
        morceaux.append(rendre_menu(enfants, url_courante, profondeur + 1))
        morceaux.append('</li>')
    morceaux.append('</ul>')
    return Markup(''.join(morceaux))


def charger_menu(langue):
    f = CONTENU / langue / '_menu.yaml'
    if not f.exists():
        return []
    return lire_yaml(f, [])


# =========================================================================
# Traductions
# =========================================================================

def apparier(tout: dict, config) -> dict:
    """Associe chaque page à ses versions dans les autres langues.

    Polylang n'avait gardé qu'UNE paire pour 61 pages : on ne peut pas
    s'y fier. On apparie sur la clé « traduction » quand elle est
    présente dans l'en-tête, et sinon sur la page d'accueil déclarée
    dans config.yaml. Une page sans équivalent voit sa langue grisée
    dans le sélecteur, plutôt que de renvoyer le visiteur à l'accueil
    sans prévenir — c'était le défaut de l'ancien site.
    """
    # ON N'APPARIE QUE DES PAGES PUBLIÉES. Le filtre des brouillons vit
    # plus bas, au moment d'écrire ; l'appariement, lui, se faisait sur
    # TOUTES les pages. Une jumelle en brouillon entrait donc dans le
    # sélecteur de langue de sa sœur publiée, sans qu'aucun fichier ne
    # soit écrit pour elle : le bouton menait à une page absente. Mesuré
    # sur une jumelle fraîchement créée — deux href morts que le
    # vérificateur a relevés. Une jumelle non publiée doit laisser sa
    # langue GRISÉE, ce que fait déjà l'absence de clé.
    publiees = {lg: [p for p in pages if p.get('statut', 'publie') == 'publie']
                for lg, pages in tout.items()}
    par_cle = {}
    for langue, pages in publiees.items():
        for p in pages:
            cle = p.get('traduction')
            if cle:
                par_cle.setdefault(cle, {})[langue] = p['url']

    # Une fiche n'a pas de jumelle : un témoignage français n'a pas été
    # écrit en italien. Mais sa COLLECTION, elle, peut avoir sa
    # traduction — et renvoyer le lecteur vers la liste équivalente vaut
    # mieux que 541 boutons morts. C'est un repli honnête : on annonce la
    # rubrique, pas la même page.
    cle_de_collection = {}
    for langue, pages in publiees.items():
        for p in pages:
            if p['type'] == 'collection' and p.get('traduction'):
                cle_de_collection[(langue, p['slug'])] = p['traduction']

    accueils = {lg: f'/{lg}/' for lg in config['langues']}
    versions = {}
    for langue, pages in tout.items():
        for p in pages:
            cle = p.get('traduction')
            if not cle and p['type'] == 'fiche':
                cle = cle_de_collection.get((langue, p.get('collection')))
            v = dict(par_cle.get(cle, {})) if cle else {}
            v[langue] = p['url']
            if p.get('est_accueil'):
                v = dict(accueils)
            versions[p['url']] = v
    return versions


# =========================================================================
# Écriture
# =========================================================================

_ecrits = {}


def ecrire(chemin: Path, contenu: str, origine: str = ''):
    """Écrit une page — et refuse d'en écraser une autre.

    Deux pages visant la même adresse, c'est une page perdue sans le
    moindre lien mort pour le signaler : la galerie « Cas cliniques »
    avait ainsi recouvert l'index de la collection du même nom, rendant
    ses 26 fiches inatteignables. Le générateur ne peut pas deviner
    laquelle garder — il s'arrête.
    """
    if chemin in _ecrits and _ecrits[chemin] != origine:
        sys.exit(f"generer : deux pages visent {chemin.relative_to(PUBLIC)} —\n"
                 f"  « {_ecrits[chemin]} » puis « {origine} ».\n"
                 f"  Changez le « slug » de l'une des deux dans son en-tête.")
    _ecrits[chemin] = origine
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding='utf-8')


def bornes_pagination(courante: int, total: int):
    """Numéros de page à montrer : 1 … 4 5 6 … 23."""
    if total <= 9:
        montrer = list(range(1, total + 1))
    else:
        montrer = sorted({1, 2, total - 1, total} |
                         set(range(max(1, courante - 2), min(total, courante + 2) + 1)))
    sortie, precedent = [], 0
    for n in montrer:
        if n - precedent > 1:
            sortie.append((None, None))
        sortie.append((n, None))
        precedent = n
    return sortie


# =========================================================================
# Programme principal
# =========================================================================

# =========================================================================
#  Ce que les moteurs et le serveur attendent, en plus des pages
# =========================================================================

def lire_redirections() -> list:
    """Les anciennes adresses WordPress et leur nouvelle destination.

    Produit par outils/cartographier_redirections.py, puis RELU À LA MAIN :
    les rubriques que la refonte a fait disparaître n'ont pas d'équivalent
    calculable. Sans ce fichier, les 54 adresses que Google connaît depuis
    2016 tomberaient toutes sur une erreur, et leur ancienneté serait
    perdue au lieu d'être reportée.
    """
    fichier = SITE / 'redirections.txt'
    if not fichier.exists():
        return []
    paires = []
    for n, ligne in enumerate(fichier.read_text(encoding='utf-8').splitlines(), 1):
        ligne = ligne.split('#', 1)[0].strip()
        if not ligne:
            continue
        if '\t' not in ligne:
            print(f'  ! redirections.txt ligne {n} : pas de tabulation, ignorée')
            continue
        ancien, nouveau = (x.strip() for x in ligne.split('\t', 1))
        if not (ancien and nouveau) or nouveau == '?':
            continue
        # UNE ADRESSE NE SE REDIRIGE PAS VERS ELLE-MÊME. Quatre pages
        # italiennes n'avaient pas changé de place (/it/casi-clinici/,
        # /it/contatti/…) : la règle les renvoyait sur elles-mêmes, en
        # boucle, et elles devenaient INACCESSIBLES. Le piège est invisible
        # à l'en-tête — un 301 vers la bonne adresse, parfaitement correct —
        # et ne se voit qu'en SUIVANT la redirection.
        if ancien.rstrip('/') == nouveau.rstrip('/'):
            print(f'  ! redirections.txt ligne {n} : {ancien} pointe sur '
                  f'elle-même, ignorée (boucle)')
            continue
        paires.append((ancien, nouveau))
    return paires


def ecrire_annexes(config, env, contextes, menus_langue):
    domaine = str(exige(config, 'domaine')).rstrip('/')

    # --- plan du site ----------------------------------------------------
    # Volontairement SANS « lastmod » : la date de dernière modification
    # d'un fichier engendré est celle de l'engendrement, pas celle du texte.
    # L'écrire reviendrait à annoncer 737 pages fraîches à chaque passage —
    # un mensonge que les moteurs finissent par ignorer en bloc.
    adresses = sorted(
        '/' + str(f.parent.relative_to(PUBLIC)) + '/'
        for f in PUBLIC.rglob('index.html'))
    adresses = [a.replace('/./', '/') for a in adresses]
    # « / » est la page de redirection vers la langue par défaut : les
    # moteurs la rangent en « page avec redirection » plutôt que de
    # l'indexer. L'annoncer dans le plan ne sert donc personne.
    adresses = [a for a in adresses if a != '/']
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for a in adresses:
        lignes.append(f'  <url><loc>{domaine}{a}</loc></url>')
    lignes.append('</urlset>')
    ecrire(PUBLIC / 'sitemap.xml', '\n'.join(lignes) + '\n')

    # --- robots.txt ------------------------------------------------------
    # L'adresse du plan doit rester /sitemap.xml : c'est celle que l'ancien
    # robots.txt annonçait, donc celle que Google a en mémoire.
    ecrire(PUBLIC / 'robots.txt',
           'User-agent: *\n'
           'Allow: /\n'
           '\n'
           f'Sitemap: {domaine}/sitemap.xml\n')

    # --- .htaccess -------------------------------------------------------
    # RedirectMatch et non Redirect : « Redirect /livres/ » attraperait
    # aussi /livres/nimporte-quoi, alors qu'on vise une page précise. Les
    # ancres ^…$ et le « /? » final couvrent l'adresse avec et sans barre
    # oblique — les deux circulent dans les vieux courriels.
    paires = lire_redirections()
    ht = ['# Engendré par site/generer.py — ne pas modifier ici.',
          '# Les redirections viennent de site/redirections.txt.',
          '',
          'Options -Indexes',
          'ErrorDocument 404 /404.html',
          '',
          '<IfModule mod_headers.c>',
          '  <FilesMatch "\\.html$">',
          '    Header set Cache-Control "no-cache, must-revalidate"',
          '  </FilesMatch>',
          '</IfModule>',
          '']
    if paires:
        ht.append(f'# --- {len(paires)} anciennes adresses WordPress ---')
        ht.append('<IfModule mod_alias.c>')
        for ancien, nouveau in paires:
            motif = re.escape(ancien.rstrip('/'))
            ht.append(f'  RedirectMatch 301 ^{motif}/?$ {nouveau}')
        ht.append('</IfModule>')
    ecrire(PUBLIC / '.htaccess', '\n'.join(ht) + '\n')

    # --- les mêmes redirections, pour nginx ------------------------------
    # L'hébergeur tourne sous Apache et lira le .htaccess ; le serveur
    # d'essai de la maison tourne sous nginx et l'ignore. Sans ce second
    # fichier, les 54 redirections partiraient en ligne SANS AVOIR ÉTÉ
    # ESSAYÉES UNE SEULE FOIS — or c'est justement le genre de chose qui
    # se révèle fausse à l'usage, pas à la relecture.
    ng = ['# Engendré par site/generer.py — inclus par le vhost nginx.',
          f'# {len(paires)} anciennes adresses WordPress.',
          '',
          '# INDISPENSABLE. Sans cela, nginx fabrique l’adresse de',
          '# destination à partir de son propre server_name et renvoie vers',
          '# http://srv.leverdier.lan/… quel que soit le domaine par lequel',
          '# on est arrivé : un visiteur venu par le tunnel serait expédié',
          '# vers une adresse injoignable depuis l’extérieur. En relatif, le',
          '# navigateur résout sur le domaine courant, et c’est toujours bon.',
          'absolute_redirect off;',
          '']
    for ancien, nouveau in paires:
        ng.append(f'rewrite ^{re.escape(ancien.rstrip("/"))}/?$ {nouveau} permanent;')
    ecrire(PUBLIC / 'redirections.nginx', '\n'.join(ng) + '\n')

    # --- page d'erreur ---------------------------------------------------
    # Rendue avec le gabarit ordinaire : une erreur qui garde le bandeau et
    # le menu reste dans le site, et le visiteur peut repartir. Une page
    # nue donne l'impression d'être sorti.
    defaut = exige(config, 'langue_par_defaut')
    commun = contextes.get(defaut)
    if commun:
        mots = commun['mots']
        page = {'type': 'page', 'url': '/404.html', 'titre': mots['erreur_titre'],
                'traduction_automatique': False}
        html = env.get_template('page.html').render(
            **commun, page=page, corps=Markup(f'<p>{mots["erreur_texte"]}</p>'),
            menu_html=menus_langue.get(defaut, ''), titre_masque=False,
            titre_affiche=mots['erreur_titre'], a_la_une=[], ouverture='',
            mention_origine='', mention_machine='', sommaire='',
            a_la_une_url='', versions={}, url_page='/404.html',
            titre_page=mots['erreur_titre'], description=mots['erreur_texte'],
            type='page', fil='', image_partage='/assets/logo.png')
        ecrire(PUBLIC / '404.html', html)

    print(f'  {"sitemap":<12} {len(adresses)} adresses')
    print(f'  {"redirections":<12} {len(paires)}')


def main():
    ap = argparse.ArgumentParser(description='Engendre le site statique.')
    ap.add_argument('--servir', action='store_true',
                    help='sert le résultat sur http://localhost:8000')
    ap.add_argument('--port', type=int, default=8000)
    args = ap.parse_args()

    config = lire_yaml(SITE / 'config.yaml', {})
    habillage = theme_de(config)
    env = Environment(loader=FileSystemLoader([str(d / 'gabarits') for d in habillage]),
                      autoescape=select_autoescape(['html']),
                      trim_blocks=True, lstrip_blocks=True)
    md = fabriquer_convertisseur()
    tout = charger(config)
    contextes, menus_langue = {}, {}

    # marquer les pages d'accueil
    for langue, meta in config['langues'].items():
        for p in tout.get(langue, []):
            if p.get('slug') == meta.get('accueil') and p['type'] != 'fiche':
                p['est_accueil'] = True
                p['url'] = f'/{langue}/'
    versions = apparier(tout, config)

    # PUBLIC est relu par ecrire(), ecrire_annexes() et
    # produire_declinaisons() : on le fait pointer sur le chantier le
    # temps du travail, et on le remet en place à la fin.
    global PUBLIC
    sortie = PUBLIC
    for reste in (CHANTIER, PRECEDENT):
        if reste.exists():
            shutil.rmtree(reste)
    CHANTIER.mkdir(parents=True)
    PUBLIC = CHANTIER

    # l'empreinte porte sur le CUMUL : sinon, changer une variable dans le
    # thème enfant ne renouvellerait pas le cache du navigateur.
    empreintes = {'css': empreinte_cumulee(habillage, 'site.css'),
                  'js': empreinte_cumulee(habillage, 'site.js'),
                  'logo': empreinte(dans_le_theme(habillage, 'logo.png'))}
    compte = {'page': 0, 'fiche': 0, 'collection': 0, 'ignore': 0, 'renvoi': 0}
    index_recherche = {lg: [] for lg in config['langues']}
    textes_medias = charger_textes_medias()

    for langue, pages in tout.items():
        mots = MOTS.get(langue, MOTS['fr'])
        menu = charger_menu(langue)
        publiees = [p for p in pages if p.get('statut') == 'publie']
        collections = {p['slug']: p for p in publiees if p['type'] == 'collection'}
        fiches_de = {}
        for p in publiees:
            if p['type'] == 'fiche':
                fiches_de.setdefault(p.get('collection'), []).append(p)
        for nom_col, lot in fiches_de.items():
            annonces = {config.get('a_la_une', {}).get('collection')} | {
                v.get('a_la_une') for v in config['langues'].values()} - {None}
            if nom_col in annonces:
                # « À la une » se range par date décroissante : c'est la
                # date qui classe, pas la main.
                lot.sort(key=lambda x: str(x.get('date') or ''), reverse=True)
            else:
                # `entier` et non la valeur brute : un « rang: abc » écrit
                # à la main comparait une chaîne à un entier, et toute la
                # régénération tombait sur une trace qui ne nommait rien.
                lot.sort(key=lambda x: (entier(x.get('rang')), x['slug']))

        site_langue = dict(config)
        site_langue['devise'] = config['langues'][langue].get(
            'devise', exige(config, 'devise'))
        site_langue['titre'] = config['langues'][langue].get(
            'titre', exige(config, 'titre'))
        commun = dict(site=site_langue, langue=langue, mots=mots,
                      annee=date.today().year, empreintes=empreintes)
        # Gardé pour la page 404, engendrée après la boucle : elle doit
        # porter le même bandeau et le même menu que les autres, sinon
        # l'erreur ressemble à une sortie du site.
        contextes[langue] = commun

        # le menu est élagué une fois par langue, pas à chaque page
        existantes = {p['url'] for p in publiees
                      if p['type'] != 'conteneur' or p.get('est_accueil')}
        perdus = []
        menu = elaguer_menu(menu, existantes, perdus)
        for titre, lien in perdus:
            print(f'  ! menu {langue} : « {titre} » visait {lien}, '
                  f'page absente — entrée dégradée en intitulé')

        for p in publiees:
            # Un conteneur est une simple rubrique de menu, sans texte —
            # sauf s'il porte l'accueil de la langue : cette page DOIT
            # exister, sinon tous les sélecteurs de langue du site
            # pointent dans le vide (1 419 liens morts à la mesure).
            if p['type'] == 'conteneur' and not p.get('est_accueil'):
                compte['ignore'] += 1
                continue

            corps = Markup(remplir_alt(str(rendre(md, p['corps'])),
                                       langue, textes_medias))
            # Une page de 327 000 caractères — les Réflexions — ne se
            # parcourt pas sans plan. « sommaire: oui » en pose un.
            sommaire = ''
            if str(p.get('sommaire', '')).lower() in ('oui', 'true'):
                sommaire = fabriquer_sommaire(getattr(md, 'toc_tokens', []),
                                              mots['sommaire'])
            menu_html = rendre_menu(menu, p['url'])
            menus_langue[langue] = menu_html
            v = versions.get(p['url'], {langue: p['url']})
            desc = p.get('extrait') or texte_nu(corps, 155)
            # Un <title> doit distinguer la page dans un onglet ou un
            # résultat de recherche : « Intro » ou « Accompagnant » à
            # l'identique sur quatre pages n'y aide personne.
            titre_page = p['titre']
            if p.get('est_accueil'):
                # « Dentosophie » à l'identique sur les deux accueils ne
                # distingue rien dans un onglet : la devise de la langue
                # fait la différence.
                # le nom de la marque DANS CETTE LANGUE, sinon le titre
                # italien mêle « Humano-dentosophie » et « Umano-dentosofia »
                titre_page = f'{site_langue["titre"]} — {site_langue["devise"]}'
            elif p['type'] == 'fiche':
                col = collections.get(p.get('collection'))
                if col:
                    titre_page = f'{p["titre"]} — {col["titre"]}'
            # Sur l'accueil, le titre de la page n'a pas à s'afficher : le
            # logo dit déjà où l'on est, et « Intro » n'était qu'une
            # obligation de WordPress, qui exigeait un titre par page. On
            # le garde POUR LES LECTEURS D'ÉCRAN, hors de l'écran : une
            # page sans <h1> les laisse sans point de repère.
            # Une personne a écrit dans SA langue. Lue dans une autre, la
            # page le dit — sans quoi un lecteur italien croit lire un
            # témoignage italien.
            #
            # Quand la fiche vient d'une autre langue ET que c'est moi qui
            # l'ai traduite, les deux mentions disaient la même chose l'une
            # sous l'autre : « Testimonianza scritta in francese, tradotta »
            # puis « traduzione automatica ». 127 fiches le répétaient. Une
            # seule phrase porte les deux renseignements.
            origine = p.get('origine')
            mention_origine = ''
            mention_machine = False
            if origine and origine != langue:
                nom_langue = mots.get(f'langue_{origine}', origine)
                cle = ('origine_autre_auto' if p.get('traduction_automatique')
                       else 'origine_autre')
                mention_origine = mots[cle].format(langue=nom_langue)
                mention_machine = bool(p.get('traduction_automatique'))

            titre_masque = bool(p.get('est_accueil')
                                or str(p.get('titre_masque', '')).lower() in ('oui', 'true'))
            titre_affiche = (f'{site_langue["titre"]} — {site_langue["devise"]}'
                             if p.get('est_accueil') else p['titre'])
            # L'image d'ouverture est écrite dans le contenu, mais elle
            # doit paraître AVANT les annonces : un visiteur qui arrive
            # doit savoir où il est avant qu'on lui donne des nouvelles.
            ouverture = ''
            m_hero = re.search(r'<figure class="hero">.*?</figure>', corps, re.S)
            if m_hero:
                # LE BANDEAU S'ADAPTE À PART, et après avoir été retiré du
                # corps : occupant toute la largeur et se voyant avant tout
                # le reste, il ne prend ni la largeur de la colonne ni le
                # chargement différé. Adapté dans le corps, il héritait des
                # deux — l'image la plus visible de la page attendait les
                # autres.
                corps = Markup(corps.replace(m_hero.group(0), '', 1))
                ouverture = Markup(adapter_images(m_hero.group(0), '100vw',
                                                  differer=False))
            # la colonne de lecture fait ~44 rem ; au-delà, une image du
            # corps ne sert jamais plus large que ça.
            corps = Markup(adapter_images(
                str(corps), '(max-width: 46rem) 100vw, 44rem'))

            reglage = config.get('a_la_une') or {}
            # chaque langue peut nommer SA collection d'annonces : les
            # slugs diffèrent (« a-la-une » / « in-primo-piano »)
            col_une = config['langues'][langue].get('a_la_une') or reglage.get('collection')
            une = []
            if p.get('est_accueil') and col_une:
                une = fiches_de.get(col_une, [])[:reglage.get('nombre', 3)]
                for f in une:
                    f['date_lisible'] = (date_lisible(f['date'], langue,
                                                      precision_de(f))
                                         if f.get('date') else '')
            base = dict(commun, page=p, corps=corps, menu_html=menu_html,
                        titre_masque=titre_masque, titre_affiche=titre_affiche,
                        a_la_une=une, ouverture=ouverture,
                        mention_origine=mention_origine,
                        mention_machine=mention_machine,
                        sommaire=sommaire,
                        a_la_une_url=(collections.get(reglage.get('collection'), {}) or {}).get('url', ''),
                        versions=v, url_page=p['url'], titre_page=titre_page,
                        description=desc, type=p['type'], fil='',
                        image_partage=(premiere_image(corps)
                                       or premiere_image(ouverture)
                                       or '/assets/logo.png'))

            # PAS de lien « Accueil » : le logo y mène déjà, et un fil
            # réduit à ce seul maillon n'apprend rien. Ne subsiste que le
            # retour vers la rubrique, sur les fiches — celui-là sert :
            # il ramène à la liste d'où l'on vient.
            if p['type'] == 'fiche':
                col = collections.get(p.get('collection'))
                if col:
                    base['fil'] = Markup(
                        f'<a href="{col["url"]}">‹ {col["titre"]}</a>')

            if p['type'] == 'collection':
                lot = fiches_de.get(p['slug'], [])
                par_page = config.get('fiches_par_page', 24)
                total_pages = max(1, (len(lot) + par_page - 1) // par_page)

                # PAS DE PAGE ORPHELINE. Vingt-six fiches se coupaient en
                # « 24 puis 2 » : on cliquait « page 2 » pour trouver deux
                # cartes perdues. Quand le reste tiendrait sur un quart de
                # page, on l'ajoute à la précédente — la dernière page
                # déborde un peu, personne ne clique pour rien.
                orphelines = len(lot) - (total_pages - 1) * par_page
                if total_pages > 1 and orphelines <= max(1, par_page // 4):
                    total_pages -= 1

                for n in range(1, total_pages + 1):
                    debut = (n - 1) * par_page
                    # la dernière page ramasse tout ce qui reste
                    tranche = lot[debut:] if n == total_pages else lot[debut:debut + par_page]
                    for f in tranche:
                        f['date_lisible'] = (date_lisible(f['date'], langue,
                                              precision_de(f))
                                 if f.get('date') else '')
                    liens = [(num, None if num is None else
                              (p['url'] if num == 1 else f'{p["url"]}page-{num}/'))
                             for num, _ in bornes_pagination(n, total_pages)]
                    # CHAQUE PAGE DE PAGINATION EST UNE PAGE À PART ENTIÈRE.
                    # Le contexte commun portait l'adresse de la collection,
                    # si bien que page-2, page-3… annonçaient toutes un
                    # « canonical » vers la première : Google lisait « ces
                    # pages sont des doublons, leur contenu appartient à la
                    # première ». Seuls les 24 premiers témoignages auraient
                    # été indexés, les 176 autres devenant invisibles. Il faut
                    # donc corriger l'adresse propre à la page — canonical,
                    # og:url — et le hreflang qui la désigne elle-même.
                    url_n = p['url'] if n == 1 else f'{p["url"]}page-{n}/'
                    html = env.get_template('collection.html').render(
                        **{**base,
                           'titre_page': (p['titre'] if n == 1 else
                                          f'{p["titre"]} — {mots["page"]} {n}'),
                           'url_page': url_n,
                           'versions': {**v, langue: url_n}},
                        fiches=tranche, total=len(lot), page_courante=n,
                        pages_total=total_pages, liens_pages=liens,
                        unite=unite_lisible(p.get('nom_des_fiches'), len(lot),
                                            mots['entrees']))
                    cible = PUBLIC / p['url'].strip('/') / 'index.html' if n == 1 else \
                        PUBLIC / p['url'].strip('/') / f'page-{n}' / 'index.html'
                    ecrire(cible, html, str(p['fichier'].name))
                compte['collection'] += 1

            elif p['type'] == 'fiche':
                if not p.get('propre_page', True):
                    compte['renvoi'] += 1
                    continue
                lot = fiches_de.get(p.get('collection'), [])
                i = lot.index(p) if p in lot else -1
                html = env.get_template('fiche.html').render(
                    **base,
                    # la PRÉCISION doit suivre jusqu'ici : sans elle, « cachee »
                    # masquait la date sur la carte mais pas sur la fiche,
                    # où le titre la répétait juste au-dessous.
                    date_lisible=date_lisible(p['date'], langue,
                                              precision_de(p))
                    if p.get('date') else '',
                    precedente=lot[i - 1] if i > 0 else None,
                    suivante=lot[i + 1] if 0 <= i < len(lot) - 1 else None)
                ecrire(PUBLIC / p['url'].strip('/') / 'index.html', html,
                       str(p['fichier'].relative_to(CONTENU)))
                compte['fiche'] += 1

            else:
                html = env.get_template('page.html').render(**base)
                ecrire(PUBLIC / p['url'].strip('/') / 'index.html', html,
                       str(p['fichier'].relative_to(CONTENU)))
                compte['page'] += 1

            # Le TEXTE ENTIER, pas un extrait : avec 140 caractères, une
            # phrase prise au milieu d'un témoignage ne trouvait rien —
            # constaté par Christophe le 31/08/2026. L'index passe de
            # ~107 ko à ~1,1 Mo par langue ; il n'est chargé qu'au premier
            # geste dans le champ de recherche, et compressé au transport.
            index_recherche[langue].append(
                {'t': p['titre'], 'u': p['url'],
                 'e': texte_nu(corps),
                 'c': collections.get(p.get('collection'), {}).get('titre', '')})

    # index de recherche, un par langue
    for langue, entrees in index_recherche.items():
        ecrire(PUBLIC / f'recherche-{langue}.json',
               json.dumps(entrees, ensure_ascii=False, separators=(',', ':')))

    # racine : redirection vers la langue par défaut
    defaut = exige(config, 'langue_par_defaut')
    ecrire(PUBLIC / 'index.html',
           env.get_template('redirection.html').render(site=config, langue=defaut))

    ecrire_annexes(config, env, contextes, menus_langue)

    # ressources
    assets = PUBLIC / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    # Chaque élément est pris dans le thème, ou chez celui dont il hérite :
    # un thème peut n'être qu'une feuille de style.
    # La feuille et le script se CUMULENT du parent vers l'enfant : un
    # thème qui hérite n'a plus qu'à redéfinir ses variables, au lieu de
    # recopier deux cents lignes qui se périmeraient au premier correctif.
    # C'est la nature même du CSS — la dernière règle écrite l'emporte.
    for ressource in ('site.css', 'site.js'):
        morceaux = [d / ressource for d in reversed(habillage)
                    if (d / ressource).is_file()]
        if morceaux:
            (assets / ressource).write_text(
                '\n'.join(f'/* {m.parent.name} */\n' + m.read_text(encoding='utf-8')
                          for m in morceaux), encoding='utf-8')
    # Les images et les polices, elles, ne se cumulent pas : le premier
    # exemplaire trouvé en remontant l'héritage gagne.
    for ressource in ('logo.png', 'favicon-32.png', 'favicon-180.png',
                      'fond-aquarelle.jpg'):
        source = dans_le_theme(habillage, ressource)
        if source and source.is_file():
            shutil.copy2(source, assets / ressource)
    polices = dans_le_theme(habillage, 'polices')
    if polices and polices.is_dir():
        shutil.copytree(polices, assets / 'polices', dirs_exist_ok=True)
    declinaisons = 0
    if MEDIAS.is_dir():
        # la mécanique interne de l'atelier reste chez nous : la corbeille
        # des médias (.corbeille) et le magasin des textes alternatifs
        # (_textes.yaml) ne partent jamais en ligne.
        shutil.copytree(MEDIAS, PUBLIC / 'medias', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.*', '_*'))
        # après la copie, sinon elles seraient écrasées
        declinaisons = produire_declinaisons()

    # LA BASCULE, en deux renommages plutôt qu'un effacement : entre les
    # deux, le site est toujours quelque part. Une interruption laisse au
    # pire « .public-precedent » à renommer à la main, jamais le vide.
    if sortie.exists():
        sortie.rename(PRECEDENT)
    CHANTIER.rename(sortie)
    shutil.rmtree(PRECEDENT, ignore_errors=True)
    PUBLIC = sortie

    poids = sum(f.stat().st_size for f in PUBLIC.rglob('*') if f.is_file())
    print('=== SITE ENGENDRÉ ===')
    for k, v in compte.items():
        print(f'  {k:<12} {v}')
    if declinaisons:
        print(f'  {"images":<12} {declinaisons} déclinaison(s) en WebP')
    print(f'  {"fichiers":<12} {sum(1 for f in PUBLIC.rglob("*") if f.is_file())}')
    print(f'  {"poids":<12} {poids / 1e6:.1f} Mo')
    print(f'  → {PUBLIC}')

    if args.servir:
        import http.server, socketserver, functools

        class SansCache(http.server.SimpleHTTPRequestHandler):
            """Sert les pages en interdisant leur mise en cache.

            Sans cela, le navigateur garde la version précédente après une
            régénération : on croit une correction perdue et on la refait
            deux fois. Les feuilles de style portent une empreinte pour
            la même raison, mais les PAGES n'en ont pas.
            """

            def end_headers(self):
                self.send_header('Cache-Control',
                                 'no-store, no-cache, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                super().end_headers()

            def log_message(self, *a):
                pass

            # sans quoi le port reste bloqué une minute après un Ctrl+C
            allow_reuse_address = True

        gest = functools.partial(SansCache, directory=str(PUBLIC))
        # « 127.0.0.1 » et non « » : l'atelier prend soin de ne pas
        # s'ouvrir au réseau local, celui-ci le faisait sans le dire.
        with socketserver.TCPServer(('127.0.0.1', args.port), gest) as srv:
            print(f'\n  http://localhost:{args.port}/   (Ctrl+C pour arrêter)')
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                print('\n  arrêté')


if __name__ == '__main__':
    main()
