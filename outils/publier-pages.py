#!/usr/bin/env python3
# =========================================================================
# publier-pages.py — régénère le carnet et le pousse sur gh-pages
# =========================================================================
# Le squelette livre `outils/publier.py`, qui dépose par rsync ou par FTP
# chez un hébergeur. Ce site-ci n'a pas d'hébergeur : il est servi par
# GitHub Pages, comme les quatre autres sites de l'atelier. D'où ce
# second outil, propre au carnet — l'autre reste en place, inutilisé.
#
# GitHub Pages sert la branche `gh-pages`. Or `site/public/` est IGNORÉ
# par git (reconstruit à chaque génération, rien à versionner) : on ne
# peut donc pas servir un sous-dossier de `main`. Ce script fait le pont,
# à la main et sans intégration continue — le style de la maison :
#
#   1. régénère public/ ;
#   2. passe le vérificateur, et REFUSE de publier s'il bloque ;
#   3. pose le CNAME ;
#   4. fabrique dans public/ un dépôt jetable d'un seul commit ;
#   5. le pousse de force sur gh-pages.
#
# L'historique de gh-pages n'a aucune valeur : c'est un produit, `main`
# porte la vraie histoire. Le force-push est donc le comportement voulu.
#
# LE CNAME EST ÉCRIT ICI, pas par le générateur. Le générateur du squelette
# ne connaît pas GitHub Pages, et lui ajouter cette notion pour un seul de
# ses sites serait le mauvais endroit. Conséquence à connaître : une
# régénération seule laisse public/ SANS CNAME. Ce n'est pas grave tant
# que ce script est le seul à pousser — et l'étape 3 vérifie qu'il y est
# avant de partir, plutôt que de le supposer.
#
# UTILISATION :
#   python3 outils/publier-pages.py           # régénère, vérifie, pousse
#   python3 outils/publier-pages.py --sec     # tout, sauf pousser
# =========================================================================

import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PUBLIC = RACINE / 'site' / 'public'
BRANCHE = 'gh-pages'
DOMAINE = 'carnet.atelierduverdier.fr'


def courir(cmd, **kw):
    r = subprocess.run(cmd, cwd=kw.pop('cwd', RACINE), text=True,
                       capture_output=True, **kw)
    if r.returncode != 0:
        sys.exit(f"publier : échec de {' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def main() -> None:
    # 1. Régénérer. Le générateur porte ses garde-fous ; on ne les répète pas.
    #    Une panne en cours de route laisse le site précédent intact.
    if subprocess.run([sys.executable, 'site/generer.py'], cwd=RACINE).returncode:
        sys.exit("publier : la génération a échoué — rien n'est poussé.")

    # 2. Vérifier. Un lien mort ou deux pages au même <title> ne partent pas
    #    en ligne parce qu'on était pressé : le vérificateur rend 1 quand il
    #    BLOQUE, et ce code-là arrête tout.
    if subprocess.run([sys.executable, 'outils/verifier.py'], cwd=RACINE).returncode:
        sys.exit("\npublier : le vérificateur bloque — rien n'est poussé.\n"
                 "  Corriger, puis relancer.")

    # 3. Le CNAME. Sans lui, GitHub sert le site sur *.github.io et le
    #    sous-domaine tombe — c'est le fichier qui fait vivre le domaine.
    (PUBLIC / 'CNAME').write_text(DOMAINE + '\n', encoding='utf-8')
    if (PUBLIC / 'CNAME').read_text(encoding='utf-8').strip() != DOMAINE:
        sys.exit('publier : le CNAME n’a pas été posé — rien n’est poussé.')
    print(f'  CNAME → {DOMAINE}')

    if '--sec' in sys.argv:
        print("  (--sec : rien n’est poussé)")
        return

    distant = courir(['git', 'remote', 'get-url', 'origin'])
    version = courir(['git', 'rev-parse', '--short', 'HEAD'])

    # 4. Un dépôt jetable dans public/, un seul commit.
    jetable = PUBLIC / '.git'
    if jetable.exists():
        courir(['rm', '-rf', str(jetable)])
    courir(['git', 'init', '-q', '-b', BRANCHE], cwd=PUBLIC)
    courir(['git', 'add', '-A'], cwd=PUBLIC)
    courir(['git', 'commit', '-q', '-m',
            f'Site engendré depuis {version} — ne pas éditer ici'], cwd=PUBLIC)

    # 5. Pousser. --force : gh-pages est un produit, pas une histoire.
    courir(['git', 'push', '--force', distant, f'{BRANCHE}:{BRANCHE}'],
           cwd=PUBLIC)
    courir(['rm', '-rf', str(jetable)])

    print(f'\n  poussé sur {BRANCHE} (engendré depuis {version})')
    print(f'  → https://{DOMAINE}')


if __name__ == '__main__':
    main()
