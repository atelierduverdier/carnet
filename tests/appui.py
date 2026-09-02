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
    if avec_git:
        git(dossier, 'init', '-q')
        git(dossier, 'add', '-A')
        git(dossier, '-c', 'user.email=essai@exemple', '-c', 'user.name=Essai',
            'commit', '-qm', 'départ')
    return dossier


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
