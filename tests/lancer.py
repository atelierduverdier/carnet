#!/usr/bin/env python3
# =========================================================================
# lancer.py — le filet de tests
# =========================================================================
#   python3 tests/lancer.py            # tout
#   python3 tests/lancer.py atelier    # les essais dont le nom contient…
#
# Chaque essai monte un site jetable dans /tmp : le site rangé dans le
# dépôt n'est jamais touché, et deux exécutions ne se marchent pas dessus.
# =========================================================================

import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))


def main():
    motif = f'test_*{sys.argv[1]}*.py' if len(sys.argv) > 1 else 'test_*.py'
    essais = unittest.defaultTestLoader.discover(str(ICI), pattern=motif)
    if essais.countTestCases() == 0:
        sys.exit(f'lancer : aucun essai ne répond à « {motif} »')
    resultat = unittest.TextTestRunner(verbosity=2).run(essais)
    sys.exit(0 if resultat.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
