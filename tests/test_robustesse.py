#!/usr/bin/env python3
"""Ce qu'une faute de frappe ne doit PAS pouvoir faire.

Le générateur savait déjà nommer un en-tête de page illisible. Ce soin
s'arrêtait là : ailleurs, une clé oubliée rendait une trace Python — et
le site engendré avait déjà été rasé.
"""

import re
import shutil
import sys
import unittest
from pathlib import Path

import appui

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'site'))


class UnePanneNeDetruitPasLeSite(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()
        appui.ecrire(self.site, 'fr/essai.md',
                     'titre: "Essai"\nlangue: "fr"\ntype: "page"\nslug: "essai"\n'
                     'statut: "publie"',
                     'Un texte d’essai, assez long pour ne pas être jugé vide.')
        self.assertEqual(appui.engendrer(self.site).returncode, 0)
        self.avant = self.combien()
        self.assertGreater(self.avant, 3)

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def combien(self):
        p = self.site / 'site' / 'public'
        return sum(1 for f in p.rglob('*') if f.is_file()) if p.is_dir() else 0

    def casser_config(self, cle):
        f = self.site / 'site' / 'config.yaml'
        f.write_text(re.sub(rf'^{cle}:.*$', '', f.read_text(encoding='utf-8'),
                            flags=re.M), encoding='utf-8')

    def test_une_cle_manquante_laisse_le_site_precedent_entier(self):
        """C'est le cœur : on n'efface pas ce qu'on ne sait pas refaire.
        1 182 fichiers étaient tombés à 0 sur un site réel."""
        self.casser_config('domaine')
        r = appui.engendrer(self.site)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.combien(), self.avant)

    def test_et_elle_est_nommee_au_lieu_d_une_trace(self):
        self.casser_config('domaine')
        sortie = appui.engendrer(self.site)
        texte = sortie.stdout + sortie.stderr
        self.assertNotIn('Traceback', texte)
        self.assertIn('domaine', texte)
        self.assertIn('config.yaml', texte)

    def test_le_chantier_ne_reste_pas_en_travers(self):
        self.casser_config('devise')
        appui.engendrer(self.site)
        self.assertTrue((self.site / 'site' / 'public').is_dir())


class UnEnteteIncompletNArretePlusTout(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()
        appui.ecrire(self.site, 'fr/serie/_index.md',
                     'titre: "Série"\nlangue: "fr"\ntype: "collection"\n'
                     'slug: "serie"\nstatut: "publie"',
                     'Une rubrique d’essai, avec assez de texte pour vivre.')

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def fiche(self, nom, entete):
        appui.ecrire(self.site, f'fr/serie/{nom}.md', entete,
                     f'Le texte de {nom}, assez long pour porter un extrait.')

    def test_une_page_sans_titre_prend_le_nom_du_fichier(self):
        """« KeyError: 'titre' » ne nommait même pas le fichier fautif."""
        self.fiche('001-sans-titre',
                   'langue: "fr"\ntype: "fiche"\ncollection: "serie"\n'
                   'rang: 10\nstatut: "publie"')
        r = appui.engendrer(self.site)
        self.assertEqual(r.returncode, 0)
        self.assertIn('001-sans-titre.md', r.stdout + r.stderr)
        self.assertIn('001 sans titre', appui.page(self.site, '/fr/serie/001-sans-titre/'))

    def test_un_rang_illisible_ne_fait_plus_tomber_la_rubrique(self):
        """Le tri comparait la chaîne à un entier : TypeError, et le site
        entier avec — pour une seule fiche."""
        self.fiche('001-a', 'titre: "A"\nlangue: "fr"\ntype: "fiche"\n'
                            'collection: "serie"\nrang: abc\nstatut: "publie"')
        self.fiche('002-b', 'titre: "B"\nlangue: "fr"\ntype: "fiche"\n'
                            'collection: "serie"\nrang: 20\nstatut: "publie"')
        self.assertEqual(appui.engendrer(self.site).returncode, 0)
        liste = appui.page(self.site, '/fr/serie/')
        self.assertIn('>A<', liste)
        self.assertIn('>B<', liste)


class LeHtmlFabriqueALaMain(unittest.TestCase):
    """Les trois Markup du générateur contournent l'échappement de
    Jinja2 : ils doivent échapper eux-mêmes."""

    @classmethod
    def setUpClass(cls):
        import generer
        cls.g = generer

    def test_un_intitule_de_menu_est_echappe(self):
        h = str(self.g.rendre_menu(
            [{'titre': 'Livres <img src=x onerror=alert(1)>', 'lien': '/fr/livres/'}], '/fr/'))
        self.assertNotIn('<img', h)
        self.assertIn('&lt;img', h)

    def test_un_guillemet_dans_le_lien_ne_sort_pas_de_l_attribut(self):
        """« /x/" onclick="… » devenait un gestionnaire d'événement."""
        h = str(self.g.rendre_menu(
            [{'titre': 'X', 'lien': '/fr/x/" onclick="alert(2)'}], '/fr/'))
        # le texte « onclick= » subsiste, mais DANS la valeur : c'est le
        # guillemet qui compte, et il ne referme plus l'attribut.
        self.assertNotIn('" onclick="', h)
        self.assertIn('&#34;', h)

    def test_un_intitule_de_rubrique_aussi(self):
        h = str(self.g.rendre_menu([{'titre': '<b>R</b>', 'entrees': [
            {'titre': 'E', 'lien': '/fr/e/'}]}], '/fr/'))
        self.assertNotIn('<b>', h)

    def test_le_sommaire_est_echappe(self):
        jetons = [{'name': f'Titre <b>{i}</b> & suite', 'id': f'i{i}', 'children': []}
                  for i in range(3)]
        h = str(self.g.fabriquer_sommaire(jetons, 'Sommaire'))
        self.assertNotIn('<b>', h)
        self.assertIn('&amp;', h)


class DatesEtPlan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import generer
        cls.g = generer

    def test_un_mois_hors_bornes_ne_devient_pas_decembre(self):
        """« int('00') - 1 » vaut -1, et Python compte alors depuis la
        fin : « 2020-00-05 » s'affichait « 5 décembre 2020 »."""
        self.assertEqual(self.g.date_lisible('2020-00-05', 'fr'), '2020-00-05')
        self.assertEqual(self.g.date_lisible('2020-13-05', 'fr'), '2020-13-05')

    def test_un_mois_normal_se_lit_toujours(self):
        self.assertEqual(self.g.date_lisible('2020-01-05', 'fr'), '5 janvier 2020')
        self.assertEqual(self.g.date_lisible('2020-12-31', 'fr'), '31 décembre 2020')


class PlanDuSite(unittest.TestCase):

    def setUp(self):
        self.site = appui.site_jetable()
        appui.ecrire(self.site, 'fr/essai.md',
                     'titre: "Essai"\nlangue: "fr"\ntype: "page"\nslug: "essai"\n'
                     'statut: "publie"', 'Un texte d’essai, assez long pour vivre.')
        appui.engendrer(self.site)

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def test_la_redirection_de_racine_n_est_pas_annoncee(self):
        """Les moteurs la rangent en « page avec redirection » : l'annoncer
        dans le plan ne sert personne."""
        plan = (self.site / 'site' / 'public' / 'sitemap.xml').read_text(encoding='utf-8')
        adresses = re.findall(r'<loc>(.*?)</loc>', plan)
        self.assertTrue(adresses)
        racines = [a for a in adresses if a.rstrip('/').count('/') == 2]
        self.assertEqual(racines, [], f'la racine est annoncée : {racines}')
