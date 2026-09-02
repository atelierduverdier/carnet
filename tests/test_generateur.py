#!/usr/bin/env python3
"""Ce que le générateur doit garantir — les fautes qui coûtent cher."""

import re
import shutil
import unittest
from pathlib import Path

import appui


class Generateur(unittest.TestCase):
    """Un seul site engendré pour tous ces essais : la génération est la
    partie lente, et aucun de ces contrôles ne modifie le contenu."""

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        appui.ecrire(cls.site, 'fr/brouillon-secret.md',
                     'titre: "Brouillon secret"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "brouillon-secret"\nstatut: "brouillon"',
                     'Ceci ne doit apparaître nulle part.')
        appui.ecrire(cls.site, 'fr/retours.md',
                     'titre: "Retours"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "retours"\nstatut: "publie"',
                     'Première ligne\nDeuxième ligne\n\nAutre paragraphe')
        appui.ecrire(cls.site, 'fr/commandes.md',
                     'titre: "Commandes"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "commandes"\nstatut: "publie"',
                     'Une page qui montre des commandes, comme en montre tout\n'
                     'carnet technique. Il lui faut un peu de texte autour, sinon\n'
                     'le vérificateur la dit quasi vide.\n\n'
                     '```bash\n'
                     'sudo pacman -Syu\n'
                     'echo "ok"\n'
                     '```\n\n'
                     'Et `une commande en ligne` au fil de la phrase.')
        # Une FICHE avec sommaire : la clé était honorée par le générateur
        # et jetée par le gabarit.
        appui.ecrire(cls.site, 'fr/actualites/003-fiche-longue.md',
                     'titre: "Fiche longue"\nlangue: "fr"\ntype: "fiche"\n'
                     'collection: "actualites"\ndate: "2026-03-01"\nrang: 3\n'
                     'sommaire: "oui"\nstatut: "publie"',
                     'Une fiche assez longue pour mériter un plan.\n\n'
                     '## Premier point\n\nDu texte.\n\n'
                     '## Deuxième point\n\nDu texte.\n\n'
                     '## Troisième point\n\nDu texte.')
        cls.image = appui.media(cls.site, 'essai/image-essai.png')
        appui.ecrire(cls.site, 'fr/images.md',
                     'titre: "Images"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "images"\nstatut: "publie"',
                     'Une page d’images a besoin d’un peu de texte, sinon le\n'
                     'vérificateur la dit quasi vide — et il a raison.\n\n'
                     f'![Décrit à la main]({cls.image})\n\n'
                     'La même image, sans texte alternatif dans la page : c’est le\n'
                     'magasin qui doit le fournir.\n\n'
                     f'![]({cls.image})')
        (cls.site / 'site/medias/_textes.yaml').write_text(
            'essai/image-essai.png:\n  fr: "Texte venu du magasin"\n', encoding='utf-8')
        (cls.site / 'site/medias/.corbeille').mkdir(parents=True, exist_ok=True)
        (cls.site / 'site/medias/.corbeille/jete.jpg').write_bytes(b'x')
        cls.r = appui.engendrer(cls.site)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def test_le_generateur_aboutit(self):
        self.assertEqual(self.r.returncode, 0, self.r.stdout + self.r.stderr)

    def test_un_brouillon_n_est_pas_engendre(self):
        """Le piège le plus coûteux de l'atelier : on écrit, on publie, et
        la page n'est nulle part. Elle ne doit pas non plus fuiter par la
        recherche ou le plan du site."""
        self.assertEqual(appui.page(self.site, '/fr/brouillon-secret/'), '')
        plan = (self.site / 'site/public/sitemap.xml').read_text(encoding='utf-8')
        self.assertNotIn('brouillon-secret', plan)
        index = (self.site / 'site/public/recherche-fr.json').read_text(encoding='utf-8')
        self.assertNotIn('Brouillon secret', index)

    def test_un_retour_a_la_ligne_est_du_contenu(self):
        """WordPress posait les <br> à l'affichage ; sans nl2br, mille
        lettres de témoignage s'aplatissent en un seul pavé, sans qu'aucun
        contrôle ne bronche."""
        h = appui.page(self.site, '/fr/retours/')
        self.assertIn('<br', h, 'le retour simple a disparu : nl2br manque')
        self.assertEqual(h.count('<p>Première ligne<br'), 1)

    def test_un_bloc_de_code_reste_un_bloc(self):
        """Markdown seul lit les trois accents graves comme du code EN
        LIGNE : le bloc sortait en un unique <code> d'une seule coulée,
        avec le mot « bash » dedans et les retours à la ligne mangés.
        Rien ne le signalait — ni le générateur, ni le vérificateur, qui
        n'y voient qu'un paragraphe. Il fallait relire la page.

        On contrôle les trois choses que la panne emportait : la balise
        de bloc, le langage annoncé en classe, et le fait que le mot
        « bash » ne soit PAS devenu du code à taper."""
        h = appui.page(self.site, '/fr/commandes/')
        self.assertIn('<pre>', h, 'le bloc est resté du code en ligne : '
                                  'fenced_code manque')
        self.assertIn('class="language-bash"', h)
        bloc = h.split('<pre>')[1].split('</pre>')[0]
        self.assertNotIn('bash\n', bloc, 'le nom du langage a fini dans le code')
        self.assertIn('sudo pacman -Syu', bloc)
        self.assertIn('echo', bloc)
        # nl2br ne doit pas semer de <br> dans un bloc préformaté : les
        # retours y sont déjà signifiants.
        self.assertNotIn('<br', bloc)
        # Le code EN LIGNE, lui, continue de marcher.
        self.assertIn('<code>une commande en ligne</code>', h)

    def test_une_fiche_aussi_a_droit_a_son_sommaire(self):
        """`sommaire: oui` était calculé par le générateur pour TOUTE page,
        puis jeté par fiche.html, qui ne l'affichait pas. La clé ne faisait
        donc rien sur une fiche — en silence, ce qui est le pire des cas :
        on l'écrit dans l'en-tête, rien n'apparaît, et rien ne dit
        pourquoi. Une fiche technique de cinq sections en a autant besoin
        qu'une page."""
        h = appui.page(self.site, '/fr/actualites/003-fiche-longue/')
        self.assertIn('class="sommaire"', h,
                      'le sommaire d’une fiche est encore jeté par le gabarit')
        self.assertIn('Premier point', h)
        self.assertIn('#deuxieme-point', h)

    def test_la_une_nomme_sa_rubrique_plutot_que_des_annonces(self):
        """Le lien « voir tout » de l'accueil portait « toutes les
        annonces », en dur : le squelette supposait que la rubrique en
        vedette est une rubrique d'actualités. Sur un site dont elle
        s'appelle « Pannes » ou « Recettes », le mot était simplement
        faux — et rien ne le signalait, puisqu'une phrase fausse est une
        phrase valide.

        Le titre NU, sans article : le genre ne se devine pas d'un nom,
        et « toutes les témoignages » serait pire que le défaut.

        L'ESSAI NE NOMME AUCUNE RUBRIQUE. Une première version attendait
        « Actualités ›», le titre de la démonstration : elle rougissait
        chez le premier site dont la rubrique en vedette s'appelle
        autrement. Ce fichier VOYAGE — `tests/` fait partie du moteur et
        se recopie dans chaque site. On contrôle donc la propriété, pas
        la valeur : le lien porte le titre de la page vers laquelle il
        mène, quelle qu'elle soit."""
        h = appui.page(self.site, '/fr/')
        lien = re.search(r'<a class="alaune-toutes" href="([^"]+)"[^>]*>(.*?)</a>',
                         h, re.S)
        if not lien:
            self.skipTest('ce site n’a pas de rubrique en vedette')
        url, libelle = lien.group(1), lien.group(2).strip().rstrip('›').strip()

        # CE QUE LE MOTEUR GARANTIT : le lien mène à la rubrique en vedette.
        # C'est vrai quel que soit le thème, et c'est le second défaut que
        # 1.10.0 corrigeait — l'adresse était lue dans le réglage global au
        # lieu de la rubrique de la LANGUE.
        cible = appui.page(self.site, url)
        self.assertTrue(cible, f'le lien de la une mène dans le vide : {url}')
        titre = re.search(r'<h1[^>]*>(.*?)</h1>', cible, re.S)
        self.assertTrue(titre, 'la rubrique visée n’a pas de <h1>')

        # CE QUE LE THÈME EN FAIT : afficher ce titre, ou garder le mot
        # générique. Le moteur passe `a_la_une_titre` ; s'en servir est une
        # décision d'habillage, et un site en ligne peut légitimement ne pas
        # vouloir changer un texte visible. On ne contrôle donc le libellé
        # que si le thème a choisi de l'utiliser.
        if 'annonc' in libelle.lower() or 'annunc' in libelle.lower():
            self.skipTest('ce thème garde le libellé générique')
        self.assertEqual(
            libelle, titre.group(1).strip(),
            'le thème affiche un titre, mais pas celui de la rubrique '
            'vers laquelle le lien mène')

    def test_l_alt_ecrit_a_la_main_n_est_jamais_ecrase(self):
        """Le magasin ne connaît que le fichier ; la page, elle, sait ce
        qu'elle veut dire de l'image."""
        h = appui.page(self.site, '/fr/images/')
        self.assertIn('alt="Décrit à la main"', h)
        self.assertIn('alt="Texte venu du magasin"', h)

    def test_la_mecanique_interne_ne_part_pas_en_ligne(self):
        """La corbeille des médias et le magasin des textes restent chez
        nous : publiés, ils exposeraient des fichiers jetés."""
        public = self.site / 'site/public/medias'
        self.assertFalse((public / '_textes.yaml').exists())
        self.assertFalse((public / '.corbeille').exists())
        self.assertTrue((public / 'essai/image-essai.png').is_file())

    def test_le_site_a_ses_annexes(self):
        for annexe in ('sitemap.xml', 'robots.txt', '404.html'):
            self.assertTrue((self.site / 'site/public' / annexe).is_file(), annexe)

    def test_le_verificateur_ne_signale_rien(self):
        r = appui.verifier(self.site)
        self.assertIn('rien à signaler', r.stdout, r.stdout)
        self.assertEqual(r.returncode, 0)


class VerificateurQuiCrie(unittest.TestCase):
    """Un vérificateur qui ne voit pas les liens morts ne sert à rien."""

    def test_un_lien_mort_est_signale(self):
        site = appui.site_jetable()
        try:
            appui.ecrire(site, 'fr/cassee.md',
                         'titre: "Cassée"\nlangue: "fr"\ntype: "page"\n'
                         'slug: "cassee"\nstatut: "publie"',
                         'Un lien vers [nulle part](/fr/inexistante/).')
            appui.engendrer(site)
            r = appui.verifier(site)
            self.assertIn('mort', r.stdout)
            self.assertNotEqual(r.returncode, 0, 'le vérificateur doit rendre 1')
        finally:
            shutil.rmtree(site, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()


class SiteMasque(unittest.TestCase):
    """« moteurs: non » — un site en ligne mais pas encore montrable.

    Il y a un moment où un site EST en ligne et pas prêt : on le remplit,
    on regarde le rendu sur un vrai téléphone. Un moteur qui passe là
    l'indexe dans l'état, et une page à moitié écrite reste des semaines
    dans les résultats après avoir été finie.

    Ne pas mettre de lien ne suffit pas : les moteurs trouvent aussi par
    les certificats TLS, qui sont publics. Il faut donc les trois volets
    à la fois — et cet essai les contrôle un par un, parce qu'un seul qui
    manque laisse la porte ouverte.
    """

    def setUp(self):
        self.site = appui.site_jetable()

    def tearDown(self):
        shutil.rmtree(self.site, ignore_errors=True)

    def masquer(self):
        appui.regler(self.site, 'moteurs', 'non')

    def test_un_site_ordinaire_reste_indexable(self):
        """Le réglage est OPTIONNEL : sans lui, rien ne change."""
        appui.engendrer(self.site)
        public = self.site / 'site/public'
        robots = (public / 'robots.txt').read_text(encoding='utf-8')
        self.assertIn('Allow: /', robots)
        self.assertNotIn('Disallow: /', robots)
        self.assertTrue((public / 'sitemap.xml').is_file())
        self.assertNotIn('noindex', appui.page(self.site, '/fr/'))

    def test_les_trois_volets_du_masque(self):
        self.masquer()
        r = appui.engendrer(self.site)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        public = self.site / 'site/public'

        robots = (public / 'robots.txt').read_text(encoding='utf-8')
        self.assertIn('Disallow: /', robots)
        self.assertNotIn('Allow: /', robots)
        self.assertNotIn('Sitemap:', robots,
                         'robots.txt refuse tout et annonce quand même un plan')

        self.assertFalse((public / 'sitemap.xml').exists(),
                         'le plan du site est justement ce qu’un moteur lit '
                         'en premier quand il en trouve un')

        # La balise `noindex` est posée par le GABARIT. Le moteur fournit
        # `hors_moteurs` ; un thème peut ne pas s'en servir — et alors
        # robots.txt reste seul, ce qui ne protège pas une adresse trouvée
        # ailleurs. On le contrôle donc là où c'est promis : dans le thème
        # qui le déclare.
        base = self.site / 'themes'
        declare = any('hors_moteurs' in g.read_text(encoding='utf-8')
                      for g in base.rglob('gabarits/base.html'))
        if not declare:
            return
        self.assertIn('noindex', appui.page(self.site, '/fr/'),
                      'le gabarit déclare `hors_moteurs` et ne pose pourtant '
                      'pas la balise — robots.txt ne protège pas, seul, une '
                      'adresse trouvée ailleurs')

    def test_le_generateur_le_dit_a_chaque_passage(self):
        """C'est un réglage qu'on oublie d'enlever, et l'oublier revient à
        ne jamais être trouvé. Il doit se voir dans la sortie."""
        self.masquer()
        r = appui.engendrer(self.site)
        self.assertIn('masqué', r.stdout,
                      'rien dans la sortie ne rappelle que le site est masqué')


class SommaireEnColonne(unittest.TestCase):
    """`sommaire: "cote"` — le sommaire reste à l'écran pendant la lecture.

    Mesuré sur la page qui a motivé la fonction : 54 042 mots, 158 écrans,
    un titre tous les 7,2 écrans, et un sommaire de 27 entrées qui occupe
    83 % du premier écran PUIS DISPARAÎT. La carte n'existait qu'avant de
    partir.
    """

    @classmethod
    def setUpClass(cls):
        cls.site = appui.site_jetable()
        corps = 'Une page longue.\n\n' + '\n\n'.join(
            f'## Chapitre {i}\n\nDu texte pour le chapitre {i}.' for i in range(1, 7))
        appui.ecrire(cls.site, 'fr/livre.md',
                     'titre: "Livre"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "livre"\nsommaire: "cote"\nstatut: "publie"', corps)
        appui.ecrire(cls.site, 'fr/livre-bloc.md',
                     'titre: "Livre en bloc"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "livre-bloc"\nsommaire: "oui"\nstatut: "publie"', corps)
        # UN SEUL grand titre, et des sous-titres dessous : la forme la plus
        # ordinaire d'un long document, et celle qui n'obtenait rien.
        appui.ecrire(cls.site, 'fr/livre-imbrique.md',
                     'titre: "Livre imbriqué"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "livre-imbrique"\nsommaire: "cote"\nstatut: "publie"',
                     '# Le grand titre\n\nDu texte.\n\n'
                     + '\n\n'.join(f'## Sous-titre {i}\n\nDu texte.'
                                    for i in range(1, 6)))
        appui.ecrire(cls.site, 'fr/livre-court.md',
                     'titre: "Livre court"\nlangue: "fr"\ntype: "page"\n'
                     'slug: "livre-court"\nsommaire: "cote"\nstatut: "publie"',
                     'Deux sections seulement, ce qui ne fait pas un sommaire.\n\n'
                     '## Un\n\nDu texte.\n\n## Deux\n\nDu texte.')
        cls.r = appui.engendrer(cls.site)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.site, ignore_errors=True)

    def test_la_colonne_monte_sa_grille(self):
        h = appui.page(self.site, '/fr/livre/')
        self.assertIn('class="colonne avec-cote"', h,
                      'sans cette classe, le CSS ne monte aucune grille')
        self.assertIn('sommaire-cote', h)
        self.assertIn('<div class="corps-long">', h,
                      'le texte doit être enveloppé, sinon chacun de ses blocs '
                      'devient une cellule de la grille')

    def test_le_tiroir_est_ouvert_dans_le_html(self):
        """Sans JavaScript, le sommaire doit être DÉPLIÉ : le confort ne
        conditionne pas le contenu. C'est le script qui referme, et
        seulement sous le seuil de largeur."""
        h = appui.page(self.site, '/fr/livre/')
        self.assertIn('<details class="sommaire-tiroir" open>', h)
        self.assertIn('<summary>', h)

    def test_le_bloc_en_tete_ne_change_pas(self):
        """`sommaire: "oui"` est le comportement historique : les sites
        existants ne doivent rien voir bouger."""
        h = appui.page(self.site, '/fr/livre-bloc/')
        self.assertIn('class="sommaire"', h)
        self.assertNotIn('sommaire-cote', h)
        self.assertNotIn('avec-cote', h)
        self.assertNotIn('corps-long', h)

    def test_moins_de_trois_entrees_ne_monte_pas_de_grille(self):
        """`fabriquer_sommaire` rend une chaîne vide sous trois entrées. La
        grille ne doit pas se monter autour d'un sommaire absent : la page
        aurait une colonne vide et un texte poussé à droite."""
        h = appui.page(self.site, '/fr/livre-court/')
        self.assertNotIn('class="sommaire', h,
                         'un sommaire est rendu là où il ne devait pas y en avoir')
        self.assertNotIn('avec-cote', h,
                         'la grille se monte alors que le sommaire est vide')
        self.assertNotIn('corps-long', h)

    def test_le_seuil_compte_TOUTES_les_entrees(self):
        """Le seuil de trois entrées ne comptait que le PREMIER NIVEAU.

        `entrees` ne contient que les <li> de tête ; les sous-titres y sont
        imbriqués. Une page bâtie « un seul grand titre, puis des
        sous-titres » — la forme la plus ordinaire d'un long document —
        n'avait donc qu'UNE entrée, et n'obtenait aucun sommaire, quoi
        qu'on écrive dans son en-tête. Rien ne le disait.

        Trouvé sur une page de 73 Ko qui demandait un sommaire depuis des
        années et n'en a jamais eu."""
        h = appui.page(self.site, '/fr/livre-imbrique/')
        self.assertIn('class="sommaire', h,
                      'un seul titre de niveau 1 et cinq de niveau 2 : le '
                      'sommaire compte encore un seul niveau')
        self.assertIn('Sous-titre 3', h)
        self.assertIn('avec-cote', h,
                      'sans sommaire, la grille ne se monte pas non plus')

    def test_une_valeur_inconnue_arrete_tout(self):
        """`sommaire: "coté"` — l'accent au mauvais endroit — est la faute
        de frappe la plus probable de cette clé. Traitée avec indulgence,
        elle ne donne AUCUN sommaire : on écrit le réglage, on régénère,
        rien n'apparaît, et rien ne dit pourquoi. Sur une page de 158
        écrans, c'est la fonction dont on avait besoin qui manque, en
        silence. Le générateur doit nommer la faute et s'arrêter."""
        site = appui.site_jetable()
        try:
            appui.ecrire(site, 'fr/faute.md',
                         'titre: "Faute"\nlangue: "fr"\ntype: "page"\n'
                         'slug: "faute"\nsommaire: "coté"\nstatut: "publie"',
                         '## Un\n\nt\n\n## Deux\n\nt\n\n## Trois\n\nt')
            r = appui.engendrer(site)
            self.assertNotEqual(r.returncode, 0,
                                'une valeur inconnue passe en silence')
            sortie = r.stdout + r.stderr
            self.assertIn('coté', sortie, 'la valeur fautive n’est pas nommée')
            self.assertIn('cote', sortie, 'les valeurs admises ne sont pas dites')
        finally:
            shutil.rmtree(site, ignore_errors=True)

    def test_les_ancres_du_sommaire_visent_de_vrais_titres(self):
        """Le script apparie les liens aux titres par leur id : un lien
        qui ne vise rien laisse le chapitre sans repère, en silence."""
        h = appui.page(self.site, '/fr/livre/')
        som = h.split('sommaire-cote')[1].split('</nav>')[0]
        ancres = re.findall(r'href="#([^"]+)"', som)
        self.assertEqual(len(ancres), 6)
        for a in ancres:
            self.assertIn(f'id="{a}"', h, f'l’ancre #{a} ne vise aucun titre')
