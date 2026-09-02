#!/usr/bin/env python3
"""Une date ne s'affiche pas plus précisément qu'on ne la connaît."""

import re
import shutil
import unittest

import appui


class DatesApproximatives(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def fiche(self, extra):
        appui.ecrire(self.site, 'fr/serie/_index.md',
                     'titre: "Série"\nlangue: "fr"\ntype: "collection"\n'
                     'slug: "serie"\nstatut: "publie"',
                     'Une rubrique d’essai, avec assez de texte pour ne pas '
                     'être jugée vide par le générateur.')
        appui.ecrire(self.site, 'fr/serie/001-fiche.md',
                     'titre: "Témoignage 2018"\nlangue: "fr"\ntype: "fiche"\n'
                     'collection: "serie"\nrang: 1\nstatut: "publie"\n'
                     'date: "2018-01-01"\n' + extra,
                     'Le texte du témoignage, assez long pour que la carte '
                     'porte un extrait lisible.')
        appui.engendrer(self.site)
        return (appui.page(self.site, '/fr/serie/'),
                appui.page(self.site, '/fr/serie/001-fiche/'))

    def dates(self, html):
        return [' '.join(re.sub(r'<[^>]+>', '', m).split()) for m in
                re.findall(r'class="date-fiche"[^>]*>(.*?)</', html, re.S)]

    def test_une_date_approximative_ne_s_affiche_pas(self):
        """L'import l'a posée au 1er janvier faute de mieux : l'écrire en
        toutes lettres inventerait un jour et un mois."""
        carte, fiche = self.fiche('date_approximative: oui')
        self.assertNotIn('1 janvier 2018', carte)
        self.assertNotIn('1 janvier 2018', fiche)

    def test_mais_l_annee_reste_lisible_dans_le_titre(self):
        """Rien n'est perdu : c'est le titre qui porte l'année."""
        carte, fiche = self.fiche('date_approximative: oui')
        self.assertIn('Témoignage 2018', carte)
        self.assertIn('Témoignage 2018', fiche)

    def test_une_date_connue_s_affiche_toujours(self):
        """Le retrait ne vaut QUE pour les dates approximatives."""
        carte, fiche = self.fiche('date_approximative: non')
        self.assertIn('1 janvier 2018', ' '.join(self.dates(carte)))
        self.assertIn('1 janvier 2018', ' '.join(self.dates(fiche)))

    def test_une_fiche_sans_mention_garde_sa_date(self):
        """Un site qui ignore ce réglage ne change pas de comportement."""
        carte, _ = self.fiche('rang: 1')
        self.assertIn('1 janvier 2018', ' '.join(self.dates(carte)))
