#!/usr/bin/env python3
# =========================================================================
# appui.py — de quoi monter un site jetable pour les essais
# =========================================================================
# Chaque essai travaille sur une COPIE dans /tmp : rien de ce qui suit ne
# touche au site rangé dans le dépôt. C'est la même règle que partout
# ailleurs ici — on n'essaie jamais sur les données de quelqu'un.
# =========================================================================

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def site_jetable(avec_git=False) -> Path:
    """Une copie complète du squelette, dans un dossier temporaire."""
    dossier = Path(tempfile.mkdtemp(prefix='essai-site-'))
    # « kit » reste listé pour les sites nés avant les thèmes : le montage
    # copie ce qui existe, et ignore le reste.
    for quoi in ('site/contenu', 'site/medias', 'site/config.yaml',
                 'site/generer.py', 'themes', 'kit', 'outils'):
        if not (RACINE / quoi).exists():
            continue
        source = RACINE / quoi
        cible = dossier / quoi
        cible.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, cible)
        else:
            shutil.copy2(source, cible)
    neutraliser(dossier)
    if avec_git:
        git(dossier, 'init', '-q')
        git(dossier, 'add', '-A')
        git(dossier, '-c', 'user.email=essai@exemple', '-c', 'user.name=Essai',
            'commit', '-qm', 'départ')
    return dossier


# Les réglages du site source qu'un site JETABLE ne doit pas hériter.
#
# Le harnais copie `site/config.yaml` tel quel — c'est voulu, il faut bien
# un site qui se tienne. Mais `tests/` fait partie du moteur : il voyage
# dans chaque site né du squelette, et copie donc la configuration de CE
# site-là. Un réglage ambiant devient alors une condition d'essai qu'on
# n'a pas choisie.
#
# Payé le 02/09/2026 : un site passé en « moteurs: non » (masqué aux
# moteurs, le temps d'être rempli) a fait rougir QUATRE essais d'un coup —
# ils cherchaient un sitemap.xml que le générateur, à raison, n'écrivait
# plus. Aucun ne parlait de moteurs ; tous supposaient un site ordinaire.
#
# Un site jetable part donc NEUTRE, et l'essai qui veut un réglage le pose
# lui-même. C'est la même règle que partout ici : contrôler ce qu'on a mis,
# pas ce qu'on a trouvé.
REGLAGES_AMBIANTS = ('moteurs',)


def neutraliser(dossier: Path) -> None:
    """Retire du config.yaml copié les réglages qui ne regardent pas l'essai."""
    f = dossier / 'site' / 'config.yaml'
    if not f.is_file():
        return
    gardees = [l for l in f.read_text(encoding='utf-8').splitlines()
               if not any(l.lstrip().startswith(c + ':')
                          for c in REGLAGES_AMBIANTS)]
    f.write_text('\n'.join(gardees) + '\n', encoding='utf-8')


def regler(dossier: Path, cle: str, valeur: str) -> None:
    """Pose un réglage de premier niveau dans le config.yaml du site jetable."""
    f = dossier / 'site' / 'config.yaml'
    f.write_text(f.read_text(encoding='utf-8').rstrip('\n')
                 + f'\n{cle}: "{valeur}"\n', encoding='utf-8')


def git(dossier: Path, *arguments):
    return subprocess.run(['git', *arguments], cwd=str(dossier),
                          capture_output=True, text=True)


def engendrer(dossier: Path):
    """Lance le générateur comme on le lance à la main, et rend sa sortie."""
    r = subprocess.run([sys.executable, 'site/generer.py'], cwd=str(dossier),
                       capture_output=True, text=True, timeout=180)
    return r


def verifier(dossier: Path):
    r = subprocess.run([sys.executable, 'outils/verifier.py'], cwd=str(dossier),
                       capture_output=True, text=True, timeout=180)
    return r


def page(dossier: Path, chemin: str) -> str:
    """Le HTML d'une page engendrée, ou '' si elle n'existe pas."""
    f = dossier / 'site' / 'public' / chemin.strip('/') / 'index.html'
    return f.read_text(encoding='utf-8') if f.is_file() else ''


def ecrire(dossier: Path, rel: str, entete: str, corps: str):
    f = dossier / 'site' / 'contenu' / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f'---\n{entete.strip()}\n---\n\n{corps}\n', encoding='utf-8')
    return f


def media(dossier: Path, rel: str, octets=b'\x89PNG\r\n\x1a\n' + b'0' * 64) -> str:
    """Dépose un média d'essai et rend son adresse publique."""
    f = dossier / 'site' / 'medias' / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(octets)
    return '/medias/' + rel


def atelier_de(dossier: Path):
    """Le module atelier.py, repointé sur le site jetable.

    Ses chemins sont des constantes calculées à l'import : les repointer
    toutes, sinon la corbeille et le magasin des textes visent encore le
    vrai dépôt.
    """
    sys.path.insert(0, str(RACINE / 'outils'))
    import atelier
    atelier.RACINE = dossier
    atelier.SITE = dossier / 'site'
    atelier.CONTENU = atelier.SITE / 'contenu'
    atelier.MEDIAS = atelier.SITE / 'medias'
    atelier.PUBLIC = atelier.SITE / 'public'
    atelier.CORBEILLE = atelier.CONTENU / '.corbeille'
    atelier.CORBEILLE_MEDIAS = atelier.MEDIAS / '.corbeille'
    atelier.TEXTES_MEDIAS = atelier.MEDIAS / '_textes.yaml'
    atelier._cache.clear()
    atelier._cache_refs.clear()
    atelier._cache_dimensions.clear()
    atelier._depot_verifie = None
    return atelier
