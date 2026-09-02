#!/usr/bin/env python3
"""Un thème est un dossier interchangeable — et il doit le rester."""

import re
import shutil
import unittest
from pathlib import Path

import appui


def couleur(css: str, variable: str) -> str:
    """La DERNIÈRE valeur d'une variable : c'est celle qui gagne."""
    trouves = re.findall(rf'{variable}:\s*(#[0-9a-fA-F]+)', css)
    return trouves[-1] if trouves else ''


class Themes(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()
        self.conf = self.site / 'site/config.yaml'
        # Les essais fabriquent LEURS thèmes : ceux du site d'accueil
        # portent d'autres noms, et le filet doit valoir partout.
        themes = self.site / 'themes'
        themes.mkdir(exist_ok=True)
        complet = self.theme_complet()
        (themes / 'essai-parent').mkdir(exist_ok=True)
        for element in complet.iterdir():
            cible = themes / 'essai-parent' / element.name
            if element.is_dir():
                shutil.copytree(element, cible, dirs_exist_ok=True)
            else:
                shutil.copy2(element, cible)
        (themes / 'essai-parent' / 'theme.yaml').write_text(
            'nom: "Parent d’essai"\n', encoding='utf-8')
        css = themes / 'essai-parent' / 'site.css'
        css.write_text(':root { --orange: #aa0000; }\n'
                       + (css.read_text(encoding='utf-8') if css.exists() else ''),
                       encoding='utf-8')

        (themes / 'essai-enfant').mkdir(exist_ok=True)
        (themes / 'essai-enfant' / 'theme.yaml').write_text(
            'nom: "Enfant d’essai"\nherite: essai-parent\n', encoding='utf-8')
        (themes / 'essai-enfant' / 'site.css').write_text(
            ':root { --orange: #0000bb; }\n', encoding='utf-8')

    def theme_complet(self) -> Path:
        """L'habillage du site d'accueil, quel que soit son nom."""
        themes = self.site / 'themes'
        if themes.is_dir():
            for d in sorted(themes.iterdir()):
                if (d / 'gabarits').is_dir():
                    return d
        return self.site / 'kit'

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def poser_theme(self, nom):
        t = self.conf.read_text(encoding='utf-8')
        t = re.sub(r'^theme:.*$', f'theme: "{nom}"', t, count=1, flags=re.M)
        self.conf.write_text(t, encoding='utf-8')

    def feuille(self):
        return (self.site / 'site/public/assets/site.css').read_text(encoding='utf-8')

    def test_changer_de_theme_change_la_feuille(self):
        self.poser_theme('essai-parent')
        appui.engendrer(self.site)
        avant = couleur(self.feuille(), '--orange')
        self.poser_theme('essai-enfant')
        appui.engendrer(self.site)
        apres = couleur(self.feuille(), '--orange')
        self.assertNotEqual(avant, apres, 'la bascule de thème n’a rien changé')

    def test_un_theme_herite_de_ce_qu_il_ne_fournit_pas(self):
        """L'enfant n'apporte qu'une feuille : gabarits, polices, script et
        images doivent venir du parent, sans quoi le site serait nu."""
        self.poser_theme('essai-enfant')
        r = appui.engendrer(self.site)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        assets = self.site / 'site/public/assets'
        for attendu in ('site.js', 'logo.png', 'polices', 'favicon-32.png'):
            self.assertTrue((assets / attendu).exists(), f'{attendu} n’a pas été hérité')
        self.assertIn('<title>', appui.page(self.site, '/fr/'), 'gabarit non hérité')

    def test_la_feuille_se_cumule_du_parent_vers_l_enfant(self):
        """Un thème qui hérite ne recopie pas : sa feuille s'AJOUTE, et
        c'est la dernière règle écrite qui gagne."""
        self.poser_theme('essai-enfant')
        appui.engendrer(self.site)
        css = self.feuille()
        self.assertIn('/* essai-parent */', css)
        self.assertIn('/* essai-enfant */', css)
        self.assertLess(css.index('/* essai-parent */'), css.index('/* essai-enfant */'),
                        'l’enfant doit venir APRÈS le parent')

    def test_l_empreinte_suit_le_theme(self):
        """Sans cela, le navigateur garderait la feuille de l'ancien thème :
        on croirait la bascule ratée."""
        self.poser_theme('essai-parent')
        appui.engendrer(self.site)
        avant = re.search(r'site\.css\?v=(\w+)', appui.page(self.site, '/fr/')).group(1)
        self.poser_theme('essai-enfant')
        appui.engendrer(self.site)
        apres = re.search(r'site\.css\?v=(\w+)', appui.page(self.site, '/fr/')).group(1)
        self.assertNotEqual(avant, apres)

    def test_un_theme_inconnu_ne_fait_pas_tomber_le_site(self):
        """Une faute de frappe dans config.yaml ne doit pas rendre un site
        illisible : on retombe sur l'habillage disponible."""
        self.poser_theme('nexistepas')
        r = appui.engendrer(self.site)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()


class RessourcesDesThemes(unittest.TestCase):
    """Une feuille de style ne doit pas réclamer un fichier absent.

    `themes/verdure/site.css` demandait `/assets/fond-aquarelle.jpg`, une
    image du site d'origine que le thème ne livre PAS. Toute page de tout
    site né du squelette récoltait donc deux 404 — invisibles, puisqu'un
    fond pâle manquant ne se voit pas, et hors de portée du vérificateur,
    qui lit les liens du HTML mais pas les `url()` des feuilles.
    """

    def test_aucune_url_de_css_ne_pointe_dans_le_vide(self):
        site = appui.site_jetable()
        try:
            r = appui.engendrer(site)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            public = site / 'site/public'
            feuille = (public / 'assets/site.css').read_text(encoding='utf-8')
            # Les commentaires d'abord : une `url()` citée en exemple dans un
            # commentaire n'est pas une requête, et l'essai l'accusait.
            feuille = re.sub(r'/\*.*?\*/', '', feuille, flags=re.S)
            # Les adresses ABSOLUES du site : celles qu'on peut résoudre ici.
            # On laisse de côté data:, http(s):, et le relatif des polices.
            cibles = set(re.findall(r'url\(\s*["\']?(/[^"\')\s]+)', feuille))
            manquantes = [c for c in sorted(cibles)
                          if not (public / c.lstrip('/')).is_file()]
            self.assertEqual(
                manquantes, [],
                'la feuille de style réclame des fichiers que le site ne '
                'livre pas : ' + ', '.join(manquantes))
        finally:
            shutil.rmtree(site, ignore_errors=True)
