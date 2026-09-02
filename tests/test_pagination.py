#!/usr/bin/env python3
"""La pagination : on ne fait pas cliquer pour deux cartes."""

import re
import shutil
import unittest
from pathlib import Path

import appui


class Pagination(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()
        self.conf = self.site / 'site/config.yaml'
        self.conf.write_text(self.conf.read_text(encoding='utf-8')
                             + '\nfiches_par_page: 10\n', encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def peupler(self, combien):
        """Une rubrique d'essai, avec autant de fiches qu'on veut."""
        appui.ecrire(self.site, 'fr/serie/_index.md',
                     'titre: "Série"\nlangue: "fr"\ntype: "collection"\n'
                     'slug: "serie"\nstatut: "publie"',
                     'Une rubrique pour éprouver la pagination, avec assez de '
                     'texte pour ne pas être jugée vide.')
        for i in range(1, combien + 1):
            appui.ecrire(self.site, f'fr/serie/{i:03d}-fiche-{i}.md',
                         f'titre: "Fiche {i}"\nlangue: "fr"\ntype: "fiche"\n'
                         f'collection: "serie"\nrang: {i}\nstatut: "publie"',
                         f'Le texte de la fiche numéro {i}, assez long pour '
                         f'que la carte porte un extrait lisible.')
        appui.engendrer(self.site)

    def cartes(self, chemin):
        return len(re.findall('class="fiche-carte"', appui.page(self.site, chemin)))

    def test_deux_fiches_orphelines_rejoignent_la_page_precedente(self):
        """12 fiches par pages de 10 : « 10 puis 2 » ferait cliquer pour
        deux cartes. Une seule page de 12 vaut mieux."""
        self.peupler(12)
        self.assertEqual(self.cartes('/fr/serie/'), 12)
        self.assertEqual(appui.page(self.site, '/fr/serie/page-2/'), '',
                         'la page orpheline ne devrait pas exister')

    def test_une_vraie_seconde_page_reste(self):
        """18 fiches : 10 puis 8, personne ne clique pour rien."""
        self.peupler(18)
        self.assertEqual(self.cartes('/fr/serie/'), 10)
        self.assertEqual(self.cartes('/fr/serie/page-2/'), 8)

    def test_aucune_fiche_n_est_perdue_en_route(self):
        """Le vrai risque de ce genre de règle : escamoter des entrées."""
        for combien in (9, 10, 11, 12, 21, 22):
            with self.subTest(fiches=combien):
                self.peupler(combien)
                vues = self.cartes('/fr/serie/')
                n = 2
                while True:
                    ici = self.cartes(f'/fr/serie/page-{n}/')
                    if not ici:
                        break
                    vues += ici
                    n += 1
                self.assertEqual(vues, combien,
                                 f'{combien} fiches, {vues} affichées')

    def test_le_compte_annonce_dit_le_vrai_nombre(self):
        self.peupler(12)
        self.assertIn('12', appui.page(self.site, '/fr/serie/'))


if __name__ == '__main__':
    unittest.main()


class NomDesFiches(unittest.TestCase):
    """« 200 entrées » est un mot de base de données ; « 200 témoignages »
    dit la même chose et dit quelque chose."""

    def setUp(self):
        self.site = appui.site_jetable()

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def rubrique(self, combien, nom=None):
        entete = ('titre: "Série"\nlangue: "fr"\ntype: "collection"\n'
                  'slug: "serie"\nstatut: "publie"')
        if nom:
            entete += f'\nnom_des_fiches: "{nom}"'
        appui.ecrire(self.site, 'fr/serie/_index.md', entete,
                     'Une rubrique d’essai, avec assez de texte pour ne pas '
                     'être jugée vide par le générateur.')
        for i in range(1, combien + 1):
            appui.ecrire(self.site, f'fr/serie/{i:03d}-fiche-{i}.md',
                         f'titre: "Fiche {i}"\nlangue: "fr"\ntype: "fiche"\n'
                         f'collection: "serie"\nrang: {i}\nstatut: "publie"',
                         f'Le texte de la fiche numéro {i}, assez long pour '
                         f'que la carte porte un extrait lisible.')
        appui.engendrer(self.site)
        return re.sub(r'<[^>]+>', ' ', re.search(
            r'<p class="compteur">.*?</p>',
            appui.page(self.site, '/fr/serie/'), re.S).group(0))

    def test_la_rubrique_nomme_ses_fiches(self):
        compteur = self.rubrique(3, 'témoignage|témoignages')
        self.assertIn('témoignages', compteur)
        self.assertNotIn('entrées', compteur)

    def test_une_seule_fiche_prend_le_singulier(self):
        """L'italien ne fabrique pas son pluriel en ajoutant une lettre :
        les deux formes sont écrites, pas devinées."""
        self.assertIn('témoignage', self.rubrique(1, 'témoignage|témoignages'))
        self.assertNotIn('témoignages', self.rubrique(1, 'témoignage|témoignages'))

    def test_sans_nom_le_mot_de_la_langue_sert_encore(self):
        """Un site qui ne nomme rien garde le comportement d'avant."""
        self.assertIn('entrées', self.rubrique(3))
