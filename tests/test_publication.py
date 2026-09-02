#!/usr/bin/env python3
"""Ce que la publication doit refuser.

C'est le seul outil du squelette qui EFFACE à distance : « rsync --delete »
et « mirror --delete » emportent chez l'hébergeur tout fichier absent d'ici.
Ses refus valent donc plus que ses réussites.
"""

import io
import json
import shutil
import sys
import unittest
from pathlib import Path

import appui

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'outils'))
import publier                                                # noqa: E402


class FauxTuyau:
    """Retient ce qu'on lui écrit, et survit à son close()."""

    def __init__(self):
        self.texte = ''

    def write(self, x):
        self.texte += x

    def close(self):
        pass


class FauxProcessus:
    """lftp, en trompe-l'œil : rien n'est envoyé, tout est noté."""

    dernier = None

    def __init__(self, argv, **kw):
        FauxProcessus.dernier = self
        self.argv = argv
        self.stdin = FauxTuyau()
        self.stdout = iter(['ftp://moi:le-secret@hote/page.html\n'])

    @property
    def script(self):
        return self.stdin.texte

    def wait(self):
        return 0


class LeMotDePasseNeSAfficheNullePart(unittest.TestCase):
    """« ps » est lisible par TOUT utilisateur de la machine, et un dépôt
    de 65 Mo dure plusieurs minutes."""

    def setUp(self):
        self.vrai_popen = publier.subprocess.Popen
        self.vrai_which = publier.shutil_which
        publier.subprocess.Popen = FauxProcessus
        publier.shutil_which = lambda n: '/usr/bin/lftp'
        self.vrai_stdin = sys.stdin

    def tearDown(self):
        publier.subprocess.Popen = self.vrai_popen
        publier.shutil_which = self.vrai_which
        sys.stdin = self.vrai_stdin

    def deposer(self, mdp='le-secret'):
        sys.stdin = io.StringIO(mdp + '\n')
        sys.stdin.isatty = lambda: False
        conf = {'hote': 'ftp.exemple.com', 'login': 'moi',
                'distant': '/www/', 'role': 'public'}
        sortie = io.StringIO()
        vrai = sys.stdout
        sys.stdout = sortie
        try:
            publier.par_ftp(conf, pour_de_vrai=False)
        finally:
            sys.stdout = vrai
        return FauxProcessus.dernier, sortie.getvalue()

    def test_rien_d_identifiant_dans_la_ligne_de_commande(self):
        proc, _ = self.deposer()
        self.assertEqual(proc.argv, ['lftp'])
        self.assertNotIn('le-secret', ' '.join(proc.argv))

    def test_il_passe_par_le_script_sur_l_entree_standard(self):
        proc, _ = self.deposer()
        self.assertIn('le-secret', proc.script)
        self.assertIn('open -u', proc.script)

    def test_les_reglages_de_chiffrement_precedent_la_connexion(self):
        """Posés après « open », ils ne s'appliqueraient pas à la connexion
        en cours : le chiffrement se réglerait une fois la poignée de main
        faite, c'est-à-dire trop tard."""
        script = self.deposer()[0].script
        self.assertLess(script.index('ssl-force'), script.index('open -u'))
        self.assertLess(script.index('verify-certificate'), script.index('open -u'))

    def test_il_ne_ressort_pas_dans_la_sortie(self):
        _, affiche = self.deposer()
        self.assertNotIn('le-secret', affiche)
        self.assertIn('••••••••', affiche)

    def test_un_mot_de_passe_a_caracteres_speciaux_est_guillemete(self):
        proc, _ = self.deposer('a"b\\c d')
        script = proc.script
        self.assertIn(r'"a\"b\\c d"', script)

    def test_un_mot_de_passe_vide_est_refuse_sans_clavier(self):
        with self.assertRaises(SystemExit):
            self.deposer('')

    def test_un_mot_de_passe_vide_est_refuse_AU_CLAVIER_aussi(self):
        """La branche clavier ne vérifiait pas, elle. Or vide,
        `remplacer('', …)` insère le masque ENTRE CHAQUE CARACTÈRE et
        toute la sortie devient illisible."""
        vrai = publier.getpass.getpass
        publier.getpass.getpass = lambda *a, **k: ''
        sys.stdin = io.StringIO('')
        sys.stdin.isatty = lambda: True
        try:
            with self.assertRaises(SystemExit):
                publier.par_ftp({'hote': 'h', 'login': 'moi', 'distant': '/w/',
                                 'role': 'public'}, pour_de_vrai=False)
        finally:
            publier.getpass.getpass = vrai


class LaDestinationSaitCeQuElleEst(unittest.TestCase):
    """La confirmation ne s'accrochait qu'au « role » écrit dans le
    fichier — le seul que git ne surveille pas."""

    def setUp(self):
        self.dossier = Path(appui.site_jetable())
        self.vraies = dict(publier.DESTINATIONS)
        publier.DESTINATIONS['maison'] = self.dossier / 'maison.conf'
        publier.DESTINATIONS['en-ligne'] = self.dossier / 'en-ligne.conf'

    def tearDown(self):
        publier.DESTINATIONS.clear()
        publier.DESTINATIONS.update(self.vraies)
        shutil.rmtree(self.dossier, ignore_errors=True)

    def ecrire(self, ou, texte):
        publier.DESTINATIONS[ou].write_text(texte, encoding='utf-8')

    def test_un_role_conforme_passe(self):
        self.ecrire('en-ligne', 'role = public\nhote = h\ndistant = /w/\n')
        self.assertEqual(publier.lire_conf('en-ligne')['role'], 'public')

    def test_en_ligne_qui_se_dit_essai_est_refuse(self):
        """Sinon : dépôt chez l'hébergeur, avec --delete, sans un mot."""
        self.ecrire('en-ligne', 'role = essai\nhote = h\ndistant = /w/\n')
        with self.assertRaises(SystemExit):
            publier.lire_conf('en-ligne')

    def test_maison_qui_se_dit_public_est_refuse_aussi(self):
        self.ecrire('maison', 'role = public\nhote = h\ndistant = /w/\n')
        with self.assertRaises(SystemExit):
            publier.lire_conf('maison')

    def test_une_cle_repetee_reste_refusee(self):
        self.ecrire('maison', 'role = essai\nhote = a\nhote = b\ndistant = /w/\n')
        with self.assertRaises(SystemExit):
            publier.lire_conf('maison')

    def test_un_port_qui_n_est_pas_un_nombre_est_refuse(self):
        """« port = 22 -o ProxyCommand=… » glisserait des options à ssh."""
        self.ecrire('maison',
                    'role = essai\nhote = h\ndistant = /w/\nport = 22 -o Bidule=x\n')
        with self.assertRaises(SystemExit):
            publier.lire_conf('maison')


class UnSiteQuiAFonduNePartPas(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(appui.site_jetable())
        self.vrai_etat = publier.ETAT_DEPOT
        publier.ETAT_DEPOT = self.dossier / '.dernier-depot.json'

    def tearDown(self):
        publier.ETAT_DEPOT = self.vrai_etat
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_sans_historique_on_ne_sait_rien(self):
        self.assertIsNone(publier.compte_precedent('maison'))

    def test_le_compte_se_garde_par_destination(self):
        publier.noter_depot('maison', 1182, 65_000_000)
        publier.noter_depot('en-ligne', 900, 40_000_000)
        self.assertEqual(publier.compte_precedent('maison'), 1182)
        self.assertEqual(publier.compte_precedent('en-ligne'), 900)

    def test_un_fichier_d_etat_abime_ne_fait_pas_tomber_la_publication(self):
        publier.ETAT_DEPOT.write_text('{ pas du json', encoding='utf-8')
        self.assertIsNone(publier.compte_precedent('maison'))

    def test_la_chute_toleree_reste_franche(self):
        """3 fichiers après 1 182 doit alerter ; 1 100 non."""
        publier.noter_depot('maison', 1182, 1)
        seuil = publier.compte_precedent('maison') * (1 - publier.CHUTE_TOLEREE)
        self.assertLess(3, seuil)
        self.assertGreater(1100, seuil)
