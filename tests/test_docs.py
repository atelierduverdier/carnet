#!/usr/bin/env python3
"""Les chiffres que les documents annoncent doivent être vrais.

Écrit le 02/09/2026, après avoir trouvé « Trente essais en une demi-seconde »
dans LISEZMOI.md et CLAUDE.md d'un filet qui en comptait 101 et mettait dix
secondes. Personne n'avait menti : le nombre était juste le jour où il a été
tapé, et il a vieilli tout seul.

C'est le même piège qu'une ligne VERSION recopiée à la main. La parade n'est
pas de mieux se relire, c'est de faire COMPTER la machine.

CE QU'IL VÉRIFIE, ET CE QU'IL NE VÉRIFIE PAS. Il vérifie tout nombre
d'essais ÉCRIT dans un document. Il n'EXIGE pas qu'un document en écrive un
— et cette retenue a été payée deux fois.

`tests/` fait partie du moteur : ce fichier est recopié dans chaque site né
du squelette, et un site a ses propres LISEZMOI.md et CLAUDE.md, qui parlent
de LUI. La première version exigeait un nombre partout : le premier site mis
à jour a rougi. La deuxième ne l'exigeait que des documents citant
`tests/lancer.py` : un LISEZMOI de site qui dit simplement comment lancer le
filet, sans prétendre en connaître le compte, a rougi aussi. Les deux fois,
la faute était dans l'essai.

Ce qui reste garde l'essentiel : un nombre écrit est un nombre vérifié.
Effacer la phrase désarme le garde-fou — c'est admis. La faute d'origine
était un nombre FAUX, pas un nombre absent.
"""

import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Le nombre est en CHIFFRES — écrit en lettres, il redeviendrait invisible à
# toute vérification, ce qui est précisément comment il s'est périmé.
MOTIF = re.compile(r'(\d+)\s+essais')

DOCUMENTS = ['LISEZMOI.md', 'CLAUDE.md']

# La promesse de vitesse ne se contrôle que là où l'on parle du filet.
SIGNE_QU_ON_PARLE_DU_FILET = 'tests/lancer.py'


def combien_d_essais() -> int:
    """Ce que compte réellement le filet, découvert comme lancer.py le fait."""
    ici = Path(__file__).resolve().parent
    if str(ici) not in sys.path:
        sys.path.insert(0, str(ici))
    return unittest.defaultTestLoader.discover(
        str(ici), pattern='test_*.py').countTestCases()


def documents():
    for nom in DOCUMENTS:
        chemin = RACINE / nom
        if chemin.is_file():
            yield nom, chemin.read_text(encoding='utf-8')


class Documents(unittest.TestCase):

    def test_tout_nombre_d_essais_annonce_est_le_vrai(self):
        reel = combien_d_essais()
        for nom, texte in documents():
            for n in (int(x) for x in MOTIF.findall(texte)):
                self.assertEqual(
                    n, reel,
                    f'{nom} annonce {n} essais, le filet en compte {reel}. '
                    f'Corriger le document, pas cet essai.')

    def test_le_filet_n_est_pas_promis_en_une_demi_seconde(self):
        """La durée aussi avait vieilli — d'un facteur vingt. Une durée
        exacte se périmerait à chaque essai ajouté et à chaque machine ;
        on interdit donc la promesse chiffrée, pas la mention du temps."""
        for nom, texte in documents():
            if SIGNE_QU_ON_PARLE_DU_FILET not in texte:
                continue
            self.assertNotIn(
                'demi-seconde', texte,
                f'{nom} promet une demi-seconde ; mesuré, le filet met une '
                f'dizaine de secondes. Dire « en quelques secondes ».')


if __name__ == '__main__':
    unittest.main()
