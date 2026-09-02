#!/usr/bin/env python3
"""L'historique : ce qu'il garde, et ce qu'il ne doit surtout pas emporter."""

import shutil
import unittest
from pathlib import Path

import appui


class Historique(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable(avec_git=True)
        self.a = appui.atelier_de(self.site)
        # git a besoin d'une identité, même pour un dépôt jetable
        appui.git(self.site, 'config', 'user.email', 'essai@exemple')
        appui.git(self.site, 'config', 'user.name', 'Essai')
        appui.ecrire(self.site, 'fr/page-historique.md',
                     'titre: "Page d’historique"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "page-historique"\nstatut: "publie"',
                     'Le texte d’origine, en entier.')
        appui.ecrire(self.site, 'fr/page-voisine.md',
                     'titre: "Page voisine"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "page-voisine"\nstatut: "publie"',
                     'La page de quelqu’un d’autre.')
        appui.git(self.site, 'add', '-A')
        appui.git(self.site, 'commit', '-qm', 'décor d’essai')

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def fichier(self, rel='fr/page-historique.md'):
        return self.a.CONTENU / rel

    def test_un_depot_est_reconnu(self):
        self.assertTrue(self.a.est_un_depot())

    def test_chaque_ecriture_laisse_une_version(self):
        f = self.fichier()
        avant = len(self.a.versions('site/contenu/fr/page-historique.md'))
        f.write_text(f.read_text(encoding='utf-8') + '\nUne phrase de plus.\n',
                     encoding='utf-8')
        self.a.journaliser('essai', f)
        apres = self.a.versions('site/contenu/fr/page-historique.md')
        self.assertEqual(len(apres), avant + 1)
        self.assertTrue(apres[0]['message'].startswith('atelier : '))

    def test_le_texte_d_avant_se_relit_et_se_retablit(self):
        """La faute que la corbeille ne rattrape pas : un paragraphe
        supprimé puis enregistré."""
        f = self.fichier()
        origine = f.read_text(encoding='utf-8')
        f.write_text('---\ntitre: "À propos"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "a-propos"\nstatut: "publie"\n---\n\nOups.\n', encoding='utf-8')
        self.a.journaliser('amputée', f)

        versions = self.a.versions('site/contenu/fr/page-historique.md')
        ancienne = self.a.contenu_a_la_version('site/contenu/fr/page-historique.md',
                                               versions[1]['version'])
        self.assertEqual(ancienne, origine)

    def test_une_version_ne_valide_QUE_les_fichiers_donnes(self):
        """Deux sessions écrivent parfois dans le même dossier : le travail
        de l'autre ne doit pas entrer dans une version faite par l'atelier."""
        mien = self.fichier('fr/page-historique.md')
        autre = self.fichier('fr/page-voisine.md')
        mien.write_text(mien.read_text(encoding='utf-8') + '\nÀ moi.\n', encoding='utf-8')
        autre.write_text(autre.read_text(encoding='utf-8') + '\nÀ quelqu’un d’autre.\n',
                         encoding='utf-8')

        self.a.journaliser('ma page', mien)

        reste = appui.git(self.site, 'status', '--porcelain').stdout
        self.assertIn('fr/page-voisine.md', reste,
                      'le travail de l’autre session a été emporté dans ma version')
        self.assertNotIn('fr/page-historique.md', reste)

    def test_sans_depot_git_rien_n_explose(self):
        sans = appui.site_jetable()          # pas de git init
        try:
            a = appui.atelier_de(sans)
            self.assertFalse(a.est_un_depot())
            self.assertIsNone(a.journaliser('essai', a.CONTENU / 'fr/page-historique.md'))
            self.assertEqual(a.versions('site/contenu/fr/page-historique.md'), [])
        finally:
            shutil.rmtree(sans, ignore_errors=True)

    def test_l_historique_se_desactive_par_la_configuration(self):
        conf = self.site / 'site/config.yaml'
        conf.write_text(conf.read_text(encoding='utf-8') + '\nhistorique: "non"\n',
                        encoding='utf-8')
        self.a._depot_verifie = None
        self.assertFalse(self.a.est_un_depot())

    def test_une_version_inventee_ne_rend_rien(self):
        self.assertIsNone(self.a.contenu_a_la_version('site/contenu/fr/page-historique.md',
                                                      'pas-une-empreinte'))


if __name__ == '__main__':
    unittest.main()
