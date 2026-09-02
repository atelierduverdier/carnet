#!/usr/bin/env python3
"""Les refus de l'atelier : ce qu'il doit empêcher, et pourquoi."""

import shutil
import re
import unittest
from pathlib import Path

import appui


class LectureDeLEntete(unittest.TestCase):
    """L'atelier lit l'en-tête au motif, le générateur au parseur YAML.
    Les deux doivent dire la même chose, sans quoi un réglage s'applique
    au site et pas dans l'atelier — le pire des deux mondes."""

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        cls.a = appui.atelier_de(cls.site)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def test_un_commentaire_de_fin_de_ligne_est_ecarte(self):
        self.assertEqual(
            self.a.valeur('jumelle_attendue: "non"   # la raison', 'jumelle_attendue'),
            'non')

    def test_les_guillemets_echappes_reviennent_entiers(self):
        ligne = 'titre: "Parution du 4e livre : \\"Qu\u2019est-ce que l\u2019humain ?\\""'
        self.assertEqual(self.a.valeur(ligne, 'titre'),
                         'Parution du 4e livre : "Qu\u2019est-ce que l\u2019humain ?"')

    def test_un_diese_dans_une_valeur_citee_reste(self):
        self.assertEqual(self.a.valeur('titre: "Couleur #178897"', 'titre'),
                         'Couleur #178897')

    def test_une_valeur_nue_se_lit(self):
        self.assertEqual(self.a.valeur('rang: 12', 'rang'), '12')


class RefusDeLEntete(unittest.TestCase):
    """verifier_entete est le dernier endroit où l'on peut refuser
    proprement : après, c'est le générateur qui casse, en silence."""

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        cls.a = appui.atelier_de(cls.site)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def base(self, extra=''):
        return ('titre: "Essai"\nlangue: "fr"\ntype: "page"\nstatut: "publie"' + extra)

    def test_un_entete_correct_passe(self):
        self.assertIsNone(self.a.verifier_entete(self.base(), ['fr']))

    def test_un_rang_entre_guillemets_est_refuse(self):
        """Entre guillemets, `rang` reste une chaîne : le tri de la
        rubrique bute sur « str contre int » et c'est la rubrique ENTIÈRE
        qui cesse de s'engendrer, pas la seule fiche."""
        plainte = self.a.verifier_entete(self.base('\nrang: "7"'), ['fr'])
        self.assertIsNotNone(plainte)
        self.assertIn('rang', plainte)

    def test_une_fiche_sans_rubrique_est_refusee(self):
        plainte = self.a.verifier_entete(
            'titre: "F"\nlangue: "fr"\ntype: "fiche"', ['fr'])
        self.assertIn('collection', plainte)

    def test_une_langue_inconnue_est_refusee(self):
        self.assertIn('langue', self.a.verifier_entete(self.base(), ['it']))

    def test_une_date_mal_ecrite_est_refusee(self):
        self.assertIn('date', self.a.verifier_entete(self.base('\ndate: "12/05/2026"'), ['fr']))

    def test_un_yaml_illisible_est_refuse_sans_exploser(self):
        plainte = self.a.verifier_entete('titre: "sans fin\nlangue: "fr"', ['fr'])
        self.assertIsNotNone(plainte)


class Medias(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        cls.a = appui.atelier_de(cls.site)
        # chaque essai fabrique SON décor : ainsi le filet vaut pour
        # n'importe quel site fait avec ce moteur, pas seulement celui-ci.
        cls.image = appui.media(cls.site, 'essai/citee.png')
        cls.orpheline = appui.media(cls.site, 'essai/orpheline.png')
        appui.ecrire(cls.site, 'fr/page-a-image.md',
                     'titre: "Page à image"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "page-a-image"\nstatut: "publie"',
                     f'Du texte, puis ![]({cls.image}).')
        cls.a._cache_refs.clear()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def test_un_media_cite_par_une_page_est_dit_utilise(self):
        self.assertIn('fr/page-a-image.md', self.a.pages_qui_utilisent(self.image))

    def test_un_media_que_personne_ne_cite_est_orphelin(self):
        self.assertEqual(self.a.pages_qui_utilisent(self.orpheline), [])

    def test_un_media_cite_par_un_MENU_compte_aussi(self):
        """L'entrée de menu qui pointait vers un PDF aurait échappé à un
        contrôle limité aux pages : le fichier aurait été supprimé et le
        menu serait resté à pointer dans le vide."""
        pdf = appui.media(self.site, 'essai/notice.pdf', b'%PDF-1.4')
        menu = self.a.CONTENU / 'fr/_menu.yaml'
        menu.write_text((menu.read_text(encoding='utf-8') if menu.exists() else '')
                        + f'\n- titre: "Un document"\n  lien: "{pdf}"\n',
                        encoding='utf-8')
        self.a._cache_refs.clear()
        self.assertIn('fr/_menu.yaml', self.a.pages_qui_utilisent(pdf))

    def test_la_mecanique_interne_n_est_pas_un_media(self):
        M = self.a.MEDIAS
        (M / '.corbeille').mkdir(parents=True, exist_ok=True)
        (M / '.corbeille/jete.jpg').write_bytes(b'x')
        (M / '_textes.yaml').write_text('a: b\n', encoding='utf-8')
        chemins = [m['chemin'] for m in self.a.lister_medias()]
        self.assertNotIn('/medias/_textes.yaml', chemins)
        self.assertFalse([c for c in chemins if 'corbeille' in c])


class Jumelage(unittest.TestCase):
    """Les rubriques ne portent pas le même nom d'une langue à l'autre."""

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        cls.a = appui.atelier_de(cls.site)
        C = cls.a.CONTENU
        # deux rubriques jumelles aux noms de dossier DIFFÉRENTS : c'est
        # tout le sujet — fr/temoignages-accompagne est it/testimonianze-pazienti.
        for langue, dossier, titre in (('fr', 'rubrique-essai', 'Rubrique d’essai'),
                                       ('it', 'rubrica-prova', 'Rubrica di prova')):
            d = C / langue / dossier
            d.mkdir(parents=True, exist_ok=True)
            (d / '_index.md').write_text(
                f'---\ntitre: "{titre}"\nlangue: "{langue}"\ntype: "collection"\n'
                f'slug: "{dossier}"\nstatut: "publie"\ntraduction: "essai-jumelage"\n---\n\n',
                encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def test_la_rubrique_jumelle_se_trouve_par_sa_cle(self):
        d = self.a.collection_jumelle('fr', 'rubrique-essai', 'it')
        self.assertIsNotNone(d, 'la rubrique jumelle n’a pas été retrouvée')
        self.assertEqual(d.name, 'rubrica-prova')

    def test_sans_jumelle_on_ne_devine_pas(self):
        self.assertIsNone(self.a.collection_jumelle('fr', 'rubrique-essai', 'es'))


if __name__ == '__main__':
    unittest.main()


class UnFichierAbimeNEteintPasLAtelier(unittest.TestCase):
    """Un réglage écrit à la main ne doit pas rendre l'atelier BLANC.

    lister() est la première requête de l'interface : une exception
    dedans, et il n'y a plus rien à l'écran — pas une page en défaut,
    toutes. Trois écritures suffisaient : « abc », « 3.5 », et
    « 1 000 » avec l'espace fine des nombres français.
    """

    def setUp(self):
        self.site = appui.site_jetable()
        self.a = appui.atelier_de(self.site)
        (self.a.CONTENU / 'fr').mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def page(self, rang):
        (self.a.CONTENU / 'fr' / 'essai.md').write_text(
            f'---\ntitre: "P"\nlangue: "fr"\ntype: "page"\nrang: {rang}\n---\n\ntexte\n',
            encoding='utf-8')
        return [p for p in self.a.lister() if p['fichier'].endswith('essai.md')][0]

    def test_un_rang_illisible_vaut_zero_au_lieu_de_tout_casser(self):
        for ecrit in ('abc', '3.5', '1 000', ''):
            with self.subTest(rang=ecrit):
                self.assertEqual(self.page(ecrit)['rang'], 0)

    def test_un_rang_correct_se_lit_toujours(self):
        self.assertEqual(self.page('12')['rang'], 12)

    def test_un_yaml_abime_nomme_le_fichier_fautif(self):
        f = self.a.CONTENU / 'fr' / '_menu.yaml'
        f.write_text('- titre: "A\n  lien: [', encoding='utf-8')
        with self.assertRaises(self.a.FichierIllisible) as pris:
            self.a.menus()
        self.assertIn('_menu.yaml', str(pris.exception))


class RefusDuServeur(unittest.TestCase):
    """Ce que le serveur doit refuser AVANT de lire quoi que ce soit."""

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        cls.a = appui.atelier_de(cls.site)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def poste(self, entetes):
        """Un gabarit de requête, sans ouvrir de connexion."""
        h = object.__new__(self.a.Atelier)
        h.headers = entetes
        return h

    def test_un_content_length_negatif_est_refuse(self):
        """« read(-1) » lit jusqu'à la fin du flux : le fil restait bloqué
        et le client n'obtenait JAMAIS de réponse."""
        self.assertIsNone(self.poste({'Content-Length': '-1'}).corps_requete())

    def test_un_content_length_illisible_est_refuse(self):
        self.assertIsNone(self.poste({'Content-Length': 'abc'}).corps_requete())

    def test_un_content_length_trop_grand_est_refuse(self):
        gros = str(self.a.TAILLE_MAX + 1)
        self.assertIsNone(self.poste({'Content-Length': gros}).corps_requete())

    def test_les_hotes_locaux_passent(self):
        for hote in ('localhost:8413', '127.0.0.1:8413', 'localhost', '[::1]:8413'):
            with self.subTest(hote=hote):
                self.assertFalse(self.poste({'Host': hote}).hote_inattendu())

    def test_un_hote_etranger_est_refuse(self):
        """Le contrôle d'Origin garde les écritures, pas les lectures : un
        nom que l'attaquant fait pointer sur 127.0.0.1 rendait l'atelier
        « même origine » pour sa page, et tout le contenu se lisait."""
        for hote in ('evil.example:8413', 'quelquechose.fr'):
            with self.subTest(hote=hote):
                self.assertTrue(self.poste({'Host': hote}).hote_inattendu())


class ReglagesDeLEnTete(unittest.TestCase):
    """Un réglage affiché doit être BRANCHÉ des deux côtés.

    Le formulaire des réglages et le script qui les écrit vivent dans deux
    fichiers. Rien n'oblige l'un à connaître l'autre : on peut ajouter une
    liste déroulante à l'interface et oublier de l'écouter, ce qui donne le
    pire des résultats — un réglage qui a l'air de marcher, qu'on croit
    avoir posé, et qui ne change rien.

    Ces essais ne lancent pas l'atelier : ils lisent les deux fichiers et
    vérifient qu'ils parlent l'un de l'autre.
    """

    ICI = Path(__file__).resolve().parent.parent / 'outils' / 'atelier'

    def fichiers(self):
        return ((self.ICI / 'index.html').read_text(encoding='utf-8'),
                (self.ICI / 'atelier.js').read_text(encoding='utf-8'))

    def test_chaque_reglage_fait_quelque_chose(self):
        """Un champ `r-*` doit soit RÉAGIR, soit REFLÉTER.

        Réagir : un écouteur, qui écrit dans l'en-tête quand on le change.
        Refléter : le script lui pose une valeur, et il montre l'état.

        La première version n'admettait que la première forme. Elle a
        refusé le champ de la vignette, qui est en LECTURE SEULE : on n'y
        tape pas un chemin, on le choisit dans la médiathèque, et deux
        boutons s'en chargent. Un champ d'affichage n'est pas un réglage
        mort — c'est un réglage qui se remplit autrement."""
        html, js = self.fichiers()
        champs = sorted(set(re.findall(r'id="(r-[\w-]+)"', html)))
        self.assertTrue(champs, 'aucun réglage trouvé dans le formulaire')
        # On cherche un ABONNEMENT ou une ÉCRITURE, pas une simple mention :
        # l'identifiant figure aussi dans la relecture à l'ouverture, si bien
        # qu'une première version trouvait « branché » un réglage dont
        # l'écouteur venait d'être supprimé.
        ecoutes = set(re.findall(r"\$\('#(r-[\w-]+)'\)\s*\.addEventListener", js))
        remplis = set(re.findall(r"\$\('#(r-[\w-]+)'\)\s*\.value\s*=", js))
        muets = [c for c in champs if c not in ecoutes | remplis]
        self.assertEqual(
            muets, [],
            f'ces réglages sont affichés et ne font RIEN : {muets}\n'
            '  Ni écouteur, ni valeur posée : ils ont l’air de marcher.')

    def test_chaque_reglage_est_relu_a_l_ouverture(self):
        """Un réglage écouté mais jamais RELU repart à sa valeur par défaut
        quand on rouvre la page — et le premier enregistrement efface ce
        qu'on avait posé la veille."""
        html, js = self.fichiers()
        champs = sorted(set(re.findall(r'id="(r-[\w-]+)"', html)))
        bloc = js[js.index('function relireReglagesClairs'):]
        bloc = bloc[:bloc.index('\n}\n') + 3]
        oublies = [c for c in champs if f"'#{c}'" not in bloc]
        self.assertEqual(
            oublies, [],
            f'ces réglages ne sont pas relus à l’ouverture : {oublies}\n'
            '  Rouvrir la page les remet à zéro, et enregistrer les efface.')


class OutilsExecutables(unittest.TestCase):
    """Un outil qui porte un shebang doit pouvoir se lancer.

    Trois des six outils étaient exécutables, trois ne l'étaient pas — tous
    portant `#!/usr/bin/env python3`, et rien ne distinguait les deux
    groupes. Christophe a tapé `outils/publier.py --pour-de-vrai` au moment
    de mettre un site en ligne et a reçu « Permission non accordée », ce qui
    ne dit pas quoi faire.

    `shutil.copy2` préserve les droits : le correctif se propage aux sites
    à leur prochaine mise à jour du moteur.
    """

    def test_tout_outil_a_shebang_est_executable(self):
        import os
        racine = Path(__file__).resolve().parent.parent
        muets = []
        for f in sorted((racine / 'outils').glob('*.py')):
            if not f.read_text(encoding='utf-8').startswith('#!'):
                continue
            if not os.access(f, os.X_OK):
                muets.append(f.name)
        self.assertEqual(
            muets, [],
            f'ces outils annoncent un interpréteur et ne se lancent pas : '
            f'{muets}\n  chmod +x, sinon le shebang ment.')
