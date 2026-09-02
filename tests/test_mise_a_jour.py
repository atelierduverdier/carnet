#!/usr/bin/env python3
"""Ce que `mettre-a-jour.py` doit dire — et ce qu'il ne doit pas toucher."""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import appui

RACINE = Path(__file__).resolve().parent.parent


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
        gabarit = self.site / 'themes/verdure/gabarits/fiche.html'
        self.assertTrue(gabarit.is_file(), 'le site jetable n’a pas de thème')
        gabarit.write_text('<!-- une version restée en arrière -->\n', encoding='utf-8')

        r = mettre_a_jour(self.site)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('themes', r.stdout,
                      'l’habillage a bougé et l’outil ne le dit pas')
        self.assertIn('fiche.html', r.stdout,
                      'l’outil signale le dossier mais pas LE fichier : '
                      'sans le nom, il faut comparer à la main')

    def test_l_habillage_n_est_jamais_remplacé(self):
        """Il appartient au site : le signaler, oui ; l'écraser, jamais.
        Un site peut avoir un thème aux couleurs de quelqu'un."""
        gabarit = self.site / 'themes/verdure/gabarits/fiche.html'
        marque = '<!-- retouché sur place, ne pas écraser -->\n'
        gabarit.write_text(marque, encoding='utf-8')

        # `--sans-essais` n'est pas un détail de confort : sans lui,
        # l'outil relance tests/lancer.py DANS le site qu'il vient de
        # mettre à jour — 105 essais imbriqués dans un essai, et le
        # délai d'attente expire avant la fin.
        r = mettre_a_jour(self.site, '--pour-de-vrai', '--sans-essais')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(gabarit.read_text(encoding='utf-8'), marque)


if __name__ == '__main__':
    unittest.main()
