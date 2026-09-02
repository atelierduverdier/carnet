#!/usr/bin/env python3
# =========================================================================
# faire_captures.py — les vignettes de tuile, engendrées depuis le VRAI
# =========================================================================
# Chaque fiche du carnet raconte une commande. Sa vignette montre donc
# cette commande, et ce qu'elle répond ICI, sur cette machine.
#
# POURQUOI UN SCRIPT PLUTÔT QUE CINQ IMAGES DESSINÉES UNE FOIS. C'est la
# règle de la maison, celle de la ligne VERSION restée 44 versions en
# retard : une valeur figée dans une image ne se périme pas moins vite
# qu'une valeur recopiée dans un fichier — elle se périme en silence, et
# personne ne rouvre un PNG pour vérifier.
#
# Ici les commandes sont RELANCÉES à chaque passage. Si la sortie a
# changé — une version de paquet, un symbole qui apparaît —, la vignette
# le montre. Si une commande ne répond plus, le script le dit et refuse
# d'écrire une image mensongère.
#
# CE QU'IL N'EST PAS : une capture d'écran. Il n'y a pas de fenêtre, pas
# de thème de terminal, pas de curseur. C'est un rendu, régulier d'une
# fiche à l'autre, taillé au rapport des vignettes (16/7).
#
# UTILISATION :
#   python3 outils/faire_captures.py            # engendre tout
#   python3 outils/faire_captures.py --montrer   # affiche la sortie sans écrire
# =========================================================================

import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / 'site' / 'medias' / 'captures'

# Le rapport des vignettes (16/7), et de quoi rester net sur un écran dense.
LARGEUR, HAUTEUR = 1600, 700

# COMBIEN DE LIGNES TIENNENT VRAIMENT. Pas ce qui entre dans l'image :
# ce qui SURVIT au recadrage.
#
# La grande tuile de l'accueil occupe toute la largeur, et sa bande est
# plafonnée à 13 rem : mesuré, 1118 × 208, soit un rapport de 5,38 contre
# 2,29 pour l'image. `object-fit: cover` ne garde donc qu'environ 43 % de
# la hauteur, pris au centre — le reste est coupé, en haut comme en bas.
#
# Une carte de neuf lignes serait donc parfaite dans le fichier et amputée
# sur la page. Six lignes centrées tiennent dans la fenêtre du recadrage ;
# au-delà, le script REFUSE plutôt que d'écrire une image dont on ne verra
# pas la moitié.
BUDGET_LIGNES = 4

# Les couleurs de la livrée sombre du carnet — les mêmes jetons que le
# thème, pour que la vignette ne jure pas avec la page qui la porte.
FOND = (18, 21, 26)
ENCRE = (230, 233, 238)
ENCRE_DOUCE = (168, 176, 188)
ORANGE = (255, 154, 31)
FILET = (42, 48, 56)

POLICE = '/usr/share/fonts/TTF/DejaVuSansMono.ttf'
POLICE_GRASSE = '/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf'

# Chaque capture : le fichier, les commandes à lancer, et le nombre de
# lignes de sortie qu'on garde. On COUPE plutôt que de réduire le corps :
# une vignette illisible ne sert à rien, et le détail est dans la fiche.
CAPTURES = [
    {'fichier': 'glx-symbole.png',
     'lignes_max': 2,
     'commandes': [
         "nm -Du /usr/lib/libgallium-*.so | grep init2",
         "nm -D /usr/lib/libdrm_amdgpu.so.1 | grep init2",
     ]},
    {'fichier': 'pgrep-se-trouve.png',
     'lignes_max': 2,
     # LE MOTIF N'EXISTE NULLE PART sur la machine, et pgrep répond quand
     # même : c'est le shell qui se trouve lui-même. Il faut qu'il ait
     # AUTRE CHOSE à faire (« || echo ») — sans quoi bash se remplace par
     # pgrep, qui s'exclut, et la démonstration ne se produit pas.
     'commandes': [
         """bash -c 'pgrep -af motifabsent || echo non'""",
     ]},
    {'fichier': 'timer-calendrier.png',
     'lignes_max': 2,
     'commandes': [
         "systemd-analyze calendar 'Tue *-*-* 19:00:00'",
     ]},
    {'fichier': 'chezmoi-gere.png',
     'lignes_max': 3,
     'commandes': [
         "chezmoi managed | wc -l",
     ]},
    {'fichier': 'pacman-epingle.png',
     'lignes_max': 2,
     'commandes': [
         "grep -n '^IgnorePkg' /etc/pacman.conf",
         "pacman -Q freecad",
     ]},
]


# CE QU'UNE CAPTURE NE DOIT JAMAIS EMPORTER. Elle part sur un site
# public, et une image ne se relit pas : personne ne rouvre un PNG pour
# vérifier ce qu'il y a écrit dans un coin.
#
# Vu de près : la première version de la capture de `pgrep` avait ramassé
# le chemin d'un dossier privé, parce que le processus qui lançait le
# script portait lui-même le motif cherché. Le script REFUSE désormais
# d'écrire une image qui contiendrait l'un de ces fragments — il ne les
# efface pas, il s'arrête : effacer en silence, c'est apprendre à ne plus
# regarder.
INTERDITS = ('/home/', '.claude', '.ssh', 'passphrase', 'password',
             'token', 'coffre', '192.168.', '10.0.', '.lan')


def fuite(lignes) -> str:
    for l in lignes:
        for mot in INTERDITS:
            if mot in l:
                return mot
    return ''


def lancer(commande: str):
    """La sortie réelle d'une commande, sortie d'erreur comprise."""
    r = subprocess.run(['bash', '-c', commande], capture_output=True, text=True,
                       timeout=60)
    sortie = (r.stdout + r.stderr).rstrip('\n')
    return sortie.split('\n') if sortie else []


def rendre(capture: dict, blocs: list, cible: Path):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new('RGB', (LARGEUR, HAUTEUR), FOND)
    d = ImageDraw.Draw(img)

    # Le liseré orange du haut : la marque de la maison, et rien d'autre.
    d.rectangle([0, 0, LARGEUR, 6], fill=ORANGE)

    # LE CORPS EST CALCULÉ, PAS CHOISI. Une tuile ordinaire fait 362 px
    # de large, mesuré, pour une image de 1600 : le texte y est réduit de
    # 4,4 fois. À 30 px il s'affichait donc à 6,8 px — illisible, vérifié à
    # l'écran. À 48 px il en fait 11, ce qui se lit.
    #
    # Une capture d'écran de terminal ne survit pas à cette réduction : il
    # faut peu de signes et gros, donc des commandes COURTES. C'est la
    # contrainte qui a taillé la liste ci-dessus, pas l'inverse.
    corps = 48
    f_cmd = ImageFont.truetype(POLICE_GRASSE, corps)
    f_out = ImageFont.truetype(POLICE, corps)
    interligne = int(corps * 1.55)
    marge = 56

    # Le bloc est CENTRÉ verticalement, pas posé en haut : c'est la partie
    # centrale que le recadrage de la grande tuile conserve.
    lignes_total = sum(1 + len(s) for _, s in blocs)
    hauteur_bloc = lignes_total * interligne + (len(blocs) - 1) * int(interligne * 0.35)
    y = max(40, (HAUTEUR - hauteur_bloc) // 2)

    for commande, sortie in blocs:
        # L'invite en orange, la commande en clair : on distingue d'un coup
        # ce qu'on tape de ce que la machine répond.
        d.text((marge, y), '$', font=f_cmd, fill=ORANGE)
        d.text((marge + int(corps * 1.2), y), commande, font=f_cmd, fill=ENCRE)
        y += interligne
        for ligne in sortie:
            d.text((marge, y), ligne, font=f_out, fill=ENCRE_DOUCE)
            y += interligne
        y += int(interligne * 0.35)

    # Le filet du bas, et d'où vient l'image : une capture sans provenance
    # est une capture qu'on ne peut pas contredire.
    d.rectangle([0, HAUTEUR - 2, LARGEUR, HAUTEUR], fill=FILET)
    cible.parent.mkdir(parents=True, exist_ok=True)
    img.save(cible, optimize=True)


def main():
    montrer = '--montrer' in sys.argv
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit('faire-captures : il faut Pillow.')

    # À 48 px, un signe de DejaVu Sans Mono fait 29 px : la ligne tient
    # environ 51 signes entre les marges. Au-delà, on coupe — et on le voit,
    # ce qui pousse à raccourcir la commande plutôt qu'à laisser un « … ».
    largeur_utile = (LARGEUR - 2 * 56) // 29
    faites = 0
    for c in CAPTURES:
        blocs, lignes = [], 0
        for commande in c['commandes']:
            sortie = lancer(commande)
            if not sortie:
                sys.exit(f"faire-captures : « {commande} » ne répond rien.\n"
                         f"  {c['fichier']} n'a pas été écrite — mieux vaut pas "
                         f"d'image qu'une image qui ment.")
            reste = c['lignes_max'] - lignes
            gardees = [l[:largeur_utile] for l in sortie[:max(0, reste)]]
            mot = fuite(gardees + [commande])
            if mot:
                sys.exit(
                    f"faire-captures : « {mot} » apparaît dans la sortie de\n"
                    f"  {commande}\n\n"
                    f"  {c['fichier']} n'a PAS été écrite. Une capture part sur\n"
                    f"  un site public, et une image ne se relit pas.\n"
                    f"  Si la commande a ramassé un chemin privé, c'est souvent\n"
                    f"  qu'un processus voisin porte le motif cherché : la\n"
                    f"  relancer seule suffit en général.")
            lignes += len(gardees)
            blocs.append((commande if len(commande) <= largeur_utile
                          else commande[:largeur_utile - 1] + '…', gardees))
        total = sum(1 + len(s) for _, s in blocs)
        if total > BUDGET_LIGNES:
            sys.exit(f"faire-captures : {c['fichier']} ferait {total} lignes, "
                     f"le budget est de {BUDGET_LIGNES}.\n"
                     f"  Au-delà, la grande tuile de l'accueil en coupe la "
                     f"moitié — l'image serait parfaite et la page amputée.\n"
                     f"  Baisser « lignes_max », ou raccourcir la commande.")
        if montrer:
            print(f"--- {c['fichier']}")
            for cmd, out in blocs:
                print(f'  $ {cmd}')
                for l in out:
                    print(f'    {l}')
            continue
        rendre(c, blocs, CIBLE / c['fichier'])
        print(f"  {c['fichier']}")
        faites += 1
    if not montrer:
        print(f"\n  {faites} vignette(s) dans {CIBLE.relative_to(RACINE)}")


if __name__ == '__main__':
    main()
