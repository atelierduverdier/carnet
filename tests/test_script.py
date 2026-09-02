#!/usr/bin/env python3
"""Le script des thèmes, EXÉCUTÉ — pas seulement relu.

POURQUOI CET ESSAI EXISTE. Le 02/09/2026, une réécriture de
`sommaireEnColonne()` a emporté la construction de deux tables en laissant
leurs noms utilisés dix lignes plus bas. En mode strict, cela lève une
ReferenceError au démarrage : la fonction entière meurt, le sommaire se
fige, aucun repère n'apparaît. La page se rend normalement, le
vérificateur ne bronche pas, les 118 essais Python passent au vert — et le
défaut est parti en ligne, dans deux versions.

Un contrôle STATIQUE a d'abord été tenté, puis jeté : sans lexeur
JavaScript il rendait quatre-vingts faux positifs.

Ce qui marche est plus simple : charger le script pour de vrai, dans un
faux DOM minimal, et l'exercer. Voir `tests/faux-dom.js`. Sans dépendance
— `vm` est livré avec Node — parce que ce dossier voyage dans chaque site
né du squelette.

CE QU'IL A TROUVÉ DU PREMIER COUP, avant même de contrôler ce qu'il venait
contrôler : la garde de la recherche, `if (!champ || !liste) return;`,
était au PREMIER NIVEAU de la fonction anonyme du fichier. Elle ne sortait
pas de la recherche, elle terminait le SCRIPT ENTIER. Sur une page sans
champ de recherche, la loupe, les apparitions, le fil de lecture, les
boutons « Copier » et le sommaire ne s'exécutaient jamais.

CE QU'IL NE FAIT PAS. Ni navigateur, ni mise en page, ni CSS. Il dit que
le script se charge sans lever, et que le chapitre courant est correctement
désigné. L'apparence, elle, se juge en ouvrant la page.
"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
HARNAIS = Path(__file__).resolve().parent / 'faux-dom.js'

# Où chercher un moteur JavaScript. Le PATH d'abord — c'est le cas normal,
# `nodejs` installé par la distribution. Les suivants sont des replis
# OPPORTUNISTES : des binaires que d'autres logiciels embarquent. Ils
# peuvent disparaître à leur prochaine mise à jour, et c'est pour ça qu'ils
# viennent en second et que l'essai se SAUTE plutôt que de rougir quand il
# n'y a rien.
REPLIS = [
    Path.home() / '.lmstudio/.internal/utils/node',
]


def moteur_js():
    trouve = shutil.which('node') or shutil.which('nodejs')
    if trouve:
        return trouve
    for p in REPLIS:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


class Script(unittest.TestCase):

    def setUp(self):
        self.node = moteur_js()
        if not self.node:
            self.skipTest(
                'aucun moteur JavaScript — le comportement du script n’est '
                'pas contrôlé. Installer nodejs le rétablit.')

    def jouer(self, chemin: Path) -> dict:
        r = subprocess.run([self.node, str(HARNAIS), str(chemin)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    def scripts(self):
        return sorted((RACINE / 'themes').rglob('site.js'))

    def test_le_script_se_charge_sans_lever(self):
        """Une ReferenceError au chargement tue TOUT ce qui suit, en
        silence. C'est la faute qui a coûté deux versions."""
        vus = 0
        for f in self.scripts():
            vus += 1
            r = self.jouer(f)
            self.assertTrue(
                r['ok'],
                f'\n{f.relative_to(RACINE)} lève au chargement :\n'
                f'  {r.get("faute")}: {r.get("message")}\n'
                f'  Tout ce qui suit dans le fichier ne s’exécute pas.')
        self.assertTrue(vus, 'aucun site.js trouvé dans themes/')

    def test_le_chapitre_courant_est_le_bon(self):
        """Le calcul est exercé AU MILIEU de chaque chapitre, à 3000 px les
        uns des autres — le cas réel d'une page longue, et celui qu'un
        observateur d'intersection traite mal."""
        for f in self.scripts():
            r = self.jouer(f)
            if not r.get('releve'):
                continue          # ce thème n'a pas de sommaire en colonne
            faux = [x for x in r['releve'] if not x['juste']]
            self.assertEqual(
                faux, [],
                f'\n{f.relative_to(RACINE)} : le chapitre courant est mal '
                f'désigné.\n  {faux}\n'
                f'  Si tout est à `null`, le script s’est arrêté avant — '
                f'chercher un `return` au premier niveau du fichier.')

    def test_le_bouton_copier_copie_vraiment(self):
        """La fonction que je n'avais JAMAIS pu contrôler. Dans le volet
        d'aperçu, l'API du presse-papiers est refusée même page servie
        depuis localhost et document focalisé ; la seule preuve qu'elle
        marchait fut une notification du système d'exploitation.

        Ici on la tient : le faux DOM n'offre PAS `navigator.clipboard`,
        donc le script doit retomber sur `document.execCommand('copy')` —
        exactement le repli ajouté en 1.9.3 — et ce qui atterrit dans le
        presse-papiers doit être le contenu du bloc, au caractère près.
        Une commande fausse d'un signe ne dit pas qu'elle est fausse :
        elle fait autre chose."""
        for f in self.scripts():
            r = self.jouer(f)
            if 'bouton_pose' not in r:
                continue
            self.assertTrue(r['bloc_enveloppe'],
                            'le bloc de code n’est pas enveloppé')
            self.assertEqual(r['langue_affichee'], 'bash',
                             'la barre n’annonce pas le langage du bloc')
            self.assertTrue(r['bouton_pose'],
                            'sans presse-papiers moderne, le repli doit tout '
                            'de même poser le bouton')
            self.assertTrue(r['copie_juste'],
                            f'le presse-papiers ne reçoit pas le bloc : '
                            f'{r.get("presse_papiers")!r}')
            self.assertEqual(r['libelle_apres_clic'], 'Copié',
                             'le bouton ne dit pas que c’est fait — sans quoi '
                             'on clique deux fois')

    def test_rien_n_est_marque_avant_le_premier_titre(self):
        """Dans le préambule d'une page, on n'est dans aucun chapitre :
        marquer le premier serait mentir sur la position."""
        for f in self.scripts():
            r = self.jouer(f)
            if 'rien_avant_le_premier_titre' not in r:
                continue
            self.assertTrue(r['rien_avant_le_premier_titre'],
                            f'{f.relative_to(RACINE)} marque un chapitre '
                            f'alors qu’on est encore avant le premier titre')
