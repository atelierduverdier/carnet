#!/usr/bin/env python3
"""Les images en plusieurs tailles : ce qui doit être servi, et à qui."""

import re
import shutil
import unittest
from pathlib import Path

import appui


def balise(html: str, morceau: str) -> str:
    m = re.search(rf'<img\b[^>]*{morceau}[^>]*>', html, re.S)
    return m.group(0) if m else ''


class Images(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        try:
            from PIL import Image
        except ImportError:                       # pragma: no cover
            raise unittest.SkipTest('Pillow est absent')
        # une grande image, et une petite : la petite ne doit PAS être agrandie
        for nom, taille in (('grande.jpg', (1800, 1200)), ('petite.jpg', (320, 240))):
            f = cls.site / 'site/medias/essai' / nom
            f.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', taille, (200, 150, 100)).save(f, quality=85)
        appui.ecrire(cls.site, 'fr/galerie.md',
                     'titre: "Galerie"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "galerie"\nstatut: "publie"',
                     'Une page avec deux images, et assez de texte pour que le\n'
                     'vérificateur ne la trouve pas vide.\n\n'
                     '![La grande](/medias/essai/grande.jpg)\n\n'
                     '![La petite](/medias/essai/petite.jpg)')
        appui.ecrire(cls.site, 'fr/avec-bandeau.md',
                     'titre: "Avec bandeau"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "avec-bandeau"\nstatut: "publie"',
                     '<figure class="hero">\n'
                     '  <img src="/medias/essai/grande.jpg" alt="Le bandeau">\n'
                     '  <figcaption><strong>Titre</strong></figcaption>\n'
                     '</figure>\n\n'
                     'Du texte sous le bandeau, en quantité suffisante pour que\n'
                     'la page ne soit pas jugée vide par le vérificateur.')
        cls.r = appui.engendrer(cls.site)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def test_une_grande_image_recoit_ses_declinaisons(self):
        b = balise(appui.page(self.site, '/fr/galerie/'), 'grande')
        self.assertIn('srcset=', b)
        for largeur in (480, 960, 1600):
            self.assertIn(f'grande-{largeur}.webp {largeur}w', b)
            self.assertTrue((self.site / f'site/public/medias/essai/grande-{largeur}.webp').is_file(),
                            f'la déclinaison {largeur} n’a pas été produite')

    def test_une_declinaison_pese_moins_que_l_original(self):
        P = self.site / 'site/public/medias/essai'
        self.assertLess((P / 'grande-480.webp').stat().st_size,
                        (P / 'grande.jpg').stat().st_size / 2,
                        'la version téléphone devrait peser bien moins')

    def test_une_petite_image_n_est_jamais_AGRANDIE(self):
        """Servir du 960 à partir d'un original de 320 px ne ferait que
        peser plus lourd pour une image plus floue."""
        b = balise(appui.page(self.site, '/fr/galerie/'), 'petite')
        self.assertNotIn('srcset=', b)
        self.assertFalse((self.site / 'site/public/medias/essai/petite-480.webp').exists())

    def test_les_dimensions_sont_posees(self):
        """Sans width/height, la page saute au chargement des images et le
        texte qu'on lisait s'échappe."""
        b = balise(appui.page(self.site, '/fr/galerie/'), 'grande')
        self.assertIn('width="1800"', b)
        self.assertIn('height="1200"', b)

    def test_une_image_du_corps_se_charge_en_differe(self):
        b = balise(appui.page(self.site, '/fr/galerie/'), 'grande')
        self.assertIn('loading="lazy"', b)
        self.assertIn('(max-width: 46rem) 100vw', b)

    def test_le_BANDEAU_ne_se_charge_pas_en_differe(self):
        """C'est l'image qu'on voit en premier : différée, elle apparaît
        après le texte. Et elle occupe toute la largeur, pas la colonne."""
        b = balise(appui.page(self.site, '/fr/avec-bandeau/'), 'grande')
        self.assertNotIn('loading="lazy"', b)
        self.assertIn('sizes="100vw"', b)

    def test_le_site_reste_valide(self):
        self.assertEqual(self.r.returncode, 0, self.r.stdout + self.r.stderr)
        self.assertIn('rien à signaler', appui.verifier(self.site).stdout)


if __name__ == '__main__':
    unittest.main()
