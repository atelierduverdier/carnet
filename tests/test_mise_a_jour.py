#!/usr/bin/env python3
"""Ce que `mettre-a-jour.py` doit dire — et ce qu'il ne doit pas toucher."""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import appui

RACINE = Path(__file__).resolve().parent.parent


def un_gabarit(dossier: Path):
    """N'importe quel gabarit du site, quel que soit le NOM de son thème.

    Ces essais visaient `themes/verdure/...` en dur. Or `tests/` voyage
    dans chaque site né du squelette, et un site a le thème qu'il veut —
    celui de dentosophie s'appelle « dentosophie » et n'hérite de rien.
    L'essai y cherchait un fichier qui n'existe pas, et rougissait pour
    une raison qui n'a rien à voir avec ce qu'il contrôle.
    """
    for g in sorted((dossier / 'themes').rglob('gabarits/*.html')):
        return g
    return None


def mettre_a_jour(dossier: Path, *arguments):
    return subprocess.run(
        [sys.executable, 'outils/mettre-a-jour.py', '--depuis', str(RACINE), *arguments],
        cwd=str(dossier), capture_output=True, text=True, timeout=120)


class MiseAJour(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def test_un_theme_qui_a_divergé_est_nommé(self):
        """La liste de l'habillage ne connaissait que `kit/`. Un site né
        avec un thème n'était donc JAMAIS prévenu qu'un gabarit de
        référence avait bougé : le correctif restait chez le squelette, en
        silence — exactement ce que la règle de la maison interdit, puisque
        l'outil ne peut pas l'appliquer et doit donc le DIRE.

        On simule un site dont le gabarit est resté en arrière, et on
        vérifie que l'outil le nomme, avec le fichier."""
        gabarit = un_gabarit(self.site)
        self.assertTrue(gabarit, 'le site jetable n’a pas de thème')
        gabarit.write_text('<!-- une version restée en arrière -->\n', encoding='utf-8')

        r = mettre_a_jour(self.site)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('themes', r.stdout,
                      'l’habillage a bougé et l’outil ne le dit pas')
        self.assertIn(gabarit.name, r.stdout,
                      'l’outil signale le dossier mais pas LE fichier : '
                      'sans le nom, il faut comparer à la main')

    def test_l_habillage_n_est_jamais_remplacé(self):
        """Il appartient au site : le signaler, oui ; l'écraser, jamais.
        Un site peut avoir un thème aux couleurs de quelqu'un."""
        gabarit = un_gabarit(self.site)
        self.assertTrue(gabarit, 'le site jetable n’a pas de thème')
        marque = '<!-- retouché sur place, ne pas écraser -->\n'
        gabarit.write_text(marque, encoding='utf-8')

        # `--sans-essais` n'est pas un détail de confort : sans lui,
        # l'outil relance tests/lancer.py DANS le site qu'il vient de
        # mettre à jour — 105 essais imbriqués dans un essai, et le
        # délai d'attente expire avant la fin.
        r = mettre_a_jour(self.site, '--pour-de-vrai', '--sans-essais')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(gabarit.read_text(encoding='utf-8'), marque)


class GardeFouDuTravailEnCours(unittest.TestCase):
    """Ce que le refus protège : la RÉVERSIBILITÉ, et rien d'autre."""

    def setUp(self):
        self.site = appui.site_jetable(avec_git=True)

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def test_une_modification_du_moteur_bloque(self):
        """Écraser `site/generer.py` alors qu'il porte une correction non
        versée perd cette correction sans recours. C'est le seul risque, et
        il doit bloquer."""
        f = self.site / 'site/generer.py'
        f.write_text(f.read_text(encoding='utf-8') + '\n# retouche locale\n',
                     encoding='utf-8')
        r = mettre_a_jour(self.site, '--pour-de-vrai', '--sans-essais')
        self.assertNotEqual(r.returncode, 0,
                            'une retouche du moteur est écrasée en silence')
        self.assertIn('generer.py', r.stdout + r.stderr,
                      'le refus ne NOMME pas le fichier en péril')

    def test_un_fichier_non_versionne_ne_bloque_pas(self):
        """Le garde-fou refusait sur TOUT dépôt sale, fichiers non
        versionnés compris — qui ne se défont de toute façon pas par git,
        et n'ont donc aucun rapport avec la réversibilité.

        Payé le 02/09/2026 : deux scripts d'une autre session travaillant
        dans le même dossier bloquaient une mise à jour qui ne les touchait
        pas, et le message demandait de VERSER LE TRAVAIL DE QUELQU'UN
        D'AUTRE. Plusieurs sessions partagent ce dossier ; le cas est
        ordinaire."""
        (self.site / 'outils/brouillon-d-une-autre-session.py').write_text(
            '# travail en cours, pas le mien\n', encoding='utf-8')
        r = mettre_a_jour(self.site, '--pour-de-vrai', '--sans-essais')
        self.assertEqual(r.returncode, 0,
                         'un fichier non versionné, étranger au moteur, bloque '
                         'encore la mise à jour :\n' + r.stdout + r.stderr)
        self.assertTrue((self.site / 'outils/brouillon-d-une-autre-session.py').is_file(),
                        'la mise à jour a emporté un fichier qui ne lui '
                        'appartenait pas')

    def test_une_modification_hors_moteur_ne_bloque_pas(self):
        """Le contenu, les médias, l'habillage : la mise à jour n'y touche
        pas, donc ils n'ont rien à faire dans ce refus."""
        f = self.site / 'site/contenu/fr/accueil.md'
        if f.is_file():
            f.write_text(f.read_text(encoding='utf-8') + '\nUn ajout.\n',
                         encoding='utf-8')
        r = mettre_a_jour(self.site, '--pour-de-vrai', '--sans-essais')
        self.assertEqual(r.returncode, 0,
                         'une modification du CONTENU bloque la mise à jour :\n'
                         + r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
