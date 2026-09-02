#!/usr/bin/env python3
"""Le vérificateur : ce qu'il doit VOIR, et ce qu'il doit bloquer.

Son métier est de dire « quelque chose cloche ». Un défaut qu'il affiche
sans le compter dans son code de retour n'arrête personne : publier.py ne
regarde que ce code.
"""

import re
import shutil
import unittest
from pathlib import Path

import appui


class Verificateur(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()
        appui.ecrire(self.site, 'fr/essai.md',
                     'titre: "Essai"\nlangue: "fr"\ntype: "page"\nslug: "essai"\n'
                     'statut: "publie"',
                     'Un texte d’essai, assez long pour ne pas être jugé vide '
                     'par le contrôle des pages creuses.')
        self.assertEqual(appui.engendrer(self.site).returncode, 0)
        self.public = self.site / 'site' / 'public'
        self.assertEqual(appui.verifier(self.site).returncode, 0,
                         'le site d’essai doit partir propre')

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def page(self, chemin='/fr/essai/'):
        return self.public / chemin.strip('/') / 'index.html'

    def glisser(self, html, chemin='/fr/essai/'):
        """Insère du HTML dans le corps d'une page engendrée."""
        f = self.page(chemin)
        t = f.read_text(encoding='utf-8')
        f.write_text(t.replace('</main>', html + '</main>', 1), encoding='utf-8')

    # --- ce qui doit BLOQUER ---------------------------------------

    def test_un_titre_en_double_bloque_la_publication(self):
        """Il était affiché puis IGNORÉ du code de retour : publier.py
        voyait 0, ne prévenait de rien, et publiait."""
        a, b = self.page('/fr/'), self.page('/fr/essai/')
        titre = re.search(r'<title>(.*?)</title>', a.read_text(encoding='utf-8'), re.S).group(1)
        b.write_text(re.sub(r'<title>.*?</title>', f'<title>{titre}</title>',
                            b.read_text(encoding='utf-8'), count=1, flags=re.S),
                     encoding='utf-8')
        r = appui.verifier(self.site)
        self.assertIn('double', r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_une_declinaison_manquante_est_vue(self):
        """Le srcset n'était pas contrôlé du tout : le navigateur se
        rabat sur l'original, et personne ne voit le 404."""
        self.glisser('<img src="/assets/logo.png" '
                     'srcset="/assets/logo-480.webp 480w, /assets/logo.png 900w">')
        r = appui.verifier(self.site)
        self.assertIn('srcset', r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_un_srcset_complet_ne_derange_pas(self):
        self.glisser('<img src="/assets/logo.png" srcset="/assets/logo.png 900w">')
        self.assertEqual(appui.verifier(self.site).returncode, 0)

    def test_un_lien_relatif_mort_est_vu(self):
        """« relatif : rare ici, on laisse » — rare n'est pas jamais."""
        self.glisser('<a href="../nulle-part/">là-bas</a>')
        r = appui.verifier(self.site)
        self.assertIn('href mort', r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_un_lien_relatif_valide_passe(self):
        self.glisser('<a href="../essai/">ici</a>')
        self.assertEqual(appui.verifier(self.site).returncode, 0)

    def test_un_lien_a_guillemets_simples_est_vu(self):
        """La moitié du site devenait invisible dès qu'une page en portait."""
        self.glisser("<a href='/fr/nulle-part/'>là</a>")
        self.assertEqual(appui.verifier(self.site).returncode, 1)

    def test_une_page_sans_titre_est_signalee(self):
        f = self.page()
        f.write_text(re.sub(r'<title>.*?</title>', '', f.read_text(encoding='utf-8'),
                            count=1, flags=re.S), encoding='utf-8')
        r = appui.verifier(self.site)
        self.assertIn('sans <title>', r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_une_redirection_vers_le_vide_est_signalee(self):
        """Rien ne recoud redirections.txt quand on renomme une page."""
        (self.site / 'site' / 'redirections.txt').write_text(
            '/ancienne/\t/fr/essai/\n/autre/\t/fr/disparue/\n', encoding='utf-8')
        r = appui.verifier(self.site)
        self.assertIn('redirection vers le vide', r.stdout)
        self.assertIn('/fr/disparue/', r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_des_redirections_saines_ne_derangent_pas(self):
        (self.site / 'site' / 'redirections.txt').write_text(
            '/ancienne/\t/fr/essai/\n# un commentaire\n/vers-dehors/\thttps://exemple.fr/\n',
            encoding='utf-8')
        self.assertEqual(appui.verifier(self.site).returncode, 0)

    # --- ce qui doit se DIRE sans bloquer ---------------------------

    def test_un_courriel_encode_en_entites_n_est_pas_un_lien_mort(self):
        """Markdown obfusque les courriels : « &#109;&#97;&#105;… » EST un
        mailto:, et non un lien relatif vers une page absente."""
        mailto = ''.join(f'&#{ord(c)};' for c in 'mailto:qui@exemple.fr')
        self.glisser(f'<a href="{mailto}">écrire</a>')
        self.assertEqual(appui.verifier(self.site).returncode, 0)

    def test_une_adresse_dans_un_commentaire_n_est_pas_un_lien(self):
        self.glisser('<!-- <a href="/fr/mise-de-cote/">plus tard</a> -->')
        self.assertEqual(appui.verifier(self.site).returncode, 0)
