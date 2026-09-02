#!/usr/bin/env python3
# =========================================================================
# publier.py — dépose le site engendré chez l'hébergeur
# =========================================================================
# Régénère, vérifie, puis envoie site/public/ sur le serveur.
#
# UTILISATION :
#   python3 outils/publier.py                      # ESSAI À BLANC, vers la maison
#   python3 outils/publier.py --pour-de-vrai       # dépôt réel sur le serveur d'essai
#   python3 outils/publier.py --ou en-ligne        # essai à blanc vers l'hébergeur
#   python3 outils/publier.py --ou en-ligne --pour-de-vrai   # LE SITE PUBLIC
#
# DEUX DESTINATIONS :
#   « maison »   → outils/publier.conf          — le serveur d'essai (par défaut)
#   « en-ligne » → outils/publier-en-ligne.conf — l'hébergeur, le site public
#
# Le dépôt est à blanc PAR DÉFAUT, et le dépôt réel « en-ligne » demande une
# phrase tapée en toutes lettres. Publier écrase le site que le monde voit,
# et efface de l'hébergeur tout fichier absent de site/public/ : la manœuvre
# doit être demandée explicitement, pas obtenue par distraction.
#
# Les identifiants ne sont PAS dans le dépôt (`outils/publier*.conf` est
# ignoré par git). Format :
#
#     role     = essai          # « essai » ou « public » — obligatoire
#     methode  = rsync
#     hote     = login@serveur.example
#     distant  = /var/www/monsite/
#     port     = 22
#
# ou, pour un hébergement mutualisé sans SSH :
#
#     role     = public
#     methode  = ftp
#     hote     = ftp.example.com
#     login    = monlogin
#     distant  = /www/
#     # le mot de passe est demandé au clavier, jamais écrit sur le disque
# =========================================================================

import argparse
import getpass
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PUBLIC = RACINE / 'site' / 'public'
OUTILS = Path(__file__).resolve().parent

# DEUX DESTINATIONS, DEUX FICHIERS. Le serveur de la maison sert d'essai ;
# l'hébergeur porte le site que le monde voit. Un seul fichier de
# configuration obligerait à le réécrire à chaque changement de cible —
# et un jour on publierait chez l'un en croyant déposer chez l'autre.
DESTINATIONS = {
    'maison':   OUTILS / 'publier.conf',
    'en-ligne': OUTILS / 'publier-en-ligne.conf',
}

# ET CHACUNE SAIT CE QU'ELLE EST. La confirmation ne s'accrochait qu'au
# « role » écrit dans le fichier : un publier-en-ligne.conf portant
# « role = essai » — copié depuis l'autre, ou rempli à la hâte — publiait
# chez l'hébergeur SANS rien demander, avec --delete. Toute la sûreté
# tenait à une ligne qu'on écrit soi-même, dans le seul fichier que git
# ne surveille pas.
ROLE_ATTENDU = {'maison': 'essai', 'en-ligne': 'public'}

# Le compte du dernier dépôt réussi, par destination. Un site ne perd pas
# le tiers de ses pages par accident heureux.
ETAT_DEPOT = RACINE / 'site' / '.dernier-depot.json'
CHUTE_TOLEREE = 0.30


def lire_conf(ou: str = 'maison') -> dict:
    chemin = DESTINATIONS[ou]
    attendu = ROLE_ATTENDU[ou]
    if not chemin.exists():
        sys.exit(f"publier : {chemin} manquant.\n"
                 f"  Créez-le en suivant l'exemple en tête de ce fichier.")
    conf = {}
    for n, ligne in enumerate(chemin.read_text(encoding='utf-8').splitlines(), 1):
        ligne = ligne.split('#', 1)[0].strip()
        if '=' not in ligne:
            continue
        cle, val = (x.strip() for x in ligne.split('=', 1))

        # DEUX CONFIGURATIONS DANS UN SEUL FICHIER : le piège du 21/08/2026.
        # La lecture écrasait silencieusement, et la destination « maison »
        # se retrouvait à pointer vers le site public — sans que rien ne le
        # signale. Une clé répétée est désormais une erreur, pas un écrasement.
        if cle in conf:
            sys.exit(
                f"publier : {chemin.name}, ligne {n} — « {cle} » est défini deux fois\n"
                f"  (« {conf[cle]} », puis « {val} »).\n"
                f"  Deux destinations dans un seul fichier ? Chacune a le sien :\n"
                + '\n'.join(f'    {k:<9} → {v.name}' for k, v in DESTINATIONS.items()))
        conf[cle] = val

    # Le fichier doit DIRE ce qu'il est. Sans cela, la confirmation ne
    # pouvait s'accrocher qu'au nom de l'option — et un fichier « maison »
    # rempli avec l'hébergeur passait sans qu'on demande rien.
    role = conf.get('role')
    if role not in ('essai', 'public'):
        sys.exit(f"publier : {chemin.name} doit contenir « role = essai » ou\n"
                 f"  « role = public ». C'est ce qui déclenche la confirmation\n"
                 f"  avant d'écraser un site que le monde voit.")
    if role != attendu:
        sys.exit(
            f"publier : {chemin.name} annonce « role = {role} », alors que la\n"
            f"  destination « {ou} » attend « {attendu} ».\n"
            f"  Deux configurations mélangées ? Vérifiez laquelle est laquelle\n"
            f"  AVANT d'écraser quoi que ce soit — le dépôt efface ce qui n'est\n"
            f"  plus là.")

    # Le port sert à fabriquer la commande ssh de rsync : tout ce qui n'est
    # pas un nombre y glisserait des options (« 22 -o ProxyCommand=… »).
    port = conf.get('port', '22')
    if not str(port).isdigit():
        sys.exit(f"publier : {chemin.name} — « port = {port} » n'est pas un "
                 f"nombre.")
    return conf


def compte_precedent(ou: str):
    """Combien de fichiers le dernier dépôt réussi a envoyés, ou None."""
    if not ETAT_DEPOT.is_file():
        return None
    try:
        return json.loads(ETAT_DEPOT.read_text(encoding='utf-8')).get(ou, {}).get('fichiers')
    except (json.JSONDecodeError, OSError, AttributeError):
        return None


def noter_depot(ou: str, fichiers: int, octets: int):
    etat = {}
    if ETAT_DEPOT.is_file():
        try:
            etat = json.loads(ETAT_DEPOT.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            etat = {}
    if not isinstance(etat, dict):
        etat = {}
    etat[ou] = {'fichiers': fichiers, 'octets': octets,
                'quand': datetime.now().isoformat(timespec='seconds')}
    ETAT_DEPOT.write_text(json.dumps(etat, ensure_ascii=False, indent=2),
                          encoding='utf-8')


def etape(titre, commande, **kw):
    print(f'\n--- {titre} ---')
    # Un délai, même large : sans lui, un rsync qui ne rend pas la main
    # attend indéfiniment, et l'appelant avec.
    kw.setdefault('timeout', 3600)
    try:
        r = subprocess.run(commande, **kw)
    except subprocess.TimeoutExpired:
        sys.exit(f'publier : « {titre} » n’a pas rendu la main au bout '
                 f'd’une heure — interrompu.')
    if r.returncode != 0:
        sys.exit(f'publier : échec à l’étape « {titre} ».')
    return r


def par_rsync(conf, pour_de_vrai):
    if not conf.get('hote') or not conf.get('distant'):
        sys.exit('publier : « hote » et « distant » sont requis pour rsync.')
    commande = [
        'rsync', '-rlptDvz', '--delete',
        '--exclude', '.DS_Store', '--exclude', 'Thumbs.db',
        '-e', f'ssh -p {conf.get("port", "22")}',
        f'{PUBLIC}/', f'{conf["hote"]}:{conf["distant"]}',
    ]
    if not pour_de_vrai:
        commande.insert(1, '--dry-run')
    etape('dépôt par rsync', commande)


def par_ftp(conf, pour_de_vrai):
    """Dépôt FTP par lftp — le seul recours des hébergements mutualisés."""
    if not all(conf.get(c) for c in ('hote', 'login', 'distant')):
        sys.exit('publier : « hote », « login » et « distant » sont requis pour ftp.')
    if not shutil_which('lftp'):
        sys.exit('publier : lftp est absent (sudo pacman -S lftp).')
    # Un dépôt FTP, même à blanc, doit se connecter pour comparer les deux
    # côtés : le mot de passe est donc demandé dans les deux cas. Sans
    # terminal (tâche planifiée, sortie redirigée), getpass lève EOFError —
    # mieux vaut une phrase claire qu'une trace d'exécution.
    if sys.stdin.isatty():
        try:
            mdp = getpass.getpass(
                f'Mot de passe FTP pour {conf["login"]}@{conf["hote"]} : ')
        except (EOFError, KeyboardInterrupt):
            sys.exit('\npublier : mot de passe non saisi — abandon, '
                     'rien n’a été envoyé.')
        # VIDE, LE MASQUAGE DEVIENT UN BROUILLAGE : `remplacer('', …)`
        # insère le masque ENTRE CHAQUE CARACTÈRE, et toute la sortie
        # devient illisible. La branche sans clavier refusait déjà le
        # vide ; celle-ci ne le faisait pas.
        if not mdp:
            sys.exit('publier : mot de passe vide — abandon, '
                     'rien n’a été envoyé.')
    else:
        # Appelé par l'atelier, qui n'a pas de clavier à offrir : le mot de
        # passe arrive par l'ENTRÉE STANDARD. Ni sur la ligne de commande —
        # où « ps » l'afficherait à tout le monde — ni dans un fichier.
        mdp = sys.stdin.readline().rstrip('\n')
        if not mdp:
            sys.exit('publier : aucun mot de passe reçu sur l’entrée '
                     'standard — abandon, rien n’a été envoyé.')
    # LFTP DÉCOUPE SES COMMANDES : un mot de passe à espace, à guillemet
    # ou à barre oblique inverse doit être guillemeté pour arriver entier.
    # Éprouvé contre un vrai dialogue FTP, en relisant la commande PASS
    # reçue : « a b c », « a"b », « a\\b », « p@ss w;rd#1 », « é€ù » et
    # « fin"; rm -rf / » arrivent tous intacts.
    def guillemeter(v: str) -> str:
        return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"'

    miroir = ('mirror -R --delete --verbose'
              + ('' if pour_de_vrai else ' --dry-run')
              + f' {PUBLIC}/ {conf["distant"]}')
    # CHIFFREMENT : trois réglages, et aucun n'est décoratif.
    #   ssl-force        — refuse de parler en clair plutôt que de se
    #                      rabattre dessus en silence ;
    #   ssl-protect-data — chiffre AUSSI le canal de données. Sans lui, le
    #                      contenu des fichiers traverse en clair, seul le
    #                      mot de passe étant protégé ;
    #   verify-certificate — vérifie qu'on parle bien à qui l'on croit.
    #
    # Ce dernier était sur « no ». Il ne l'est plus : on se connecte par le
    # nom de la plateforme (pf-0xx.whm.fr-par.scw.cloud), le seul que le
    # certificat couvre — ni l'adresse IP, ni ftp.dentosophie.com. Si
    # Scaleway déplace l'hébergement, ce nom change et le dépôt échouera
    # franchement : c'est voulu, un échec net vaut mieux qu'un chiffrement
    # que plus personne ne vérifie.
    #
    # ET TROIS RÉGLAGES DE PATIENCE. Par défaut lftp réessaie SANS FIN une
    # connexion refusée : un mot de passe erroné ferait attendre une heure
    # au lieu d'échouer en dix secondes — insupportable depuis l'atelier,
    # qui reste alors figé sans rien dire. « fail-exit » est tout aussi
    # nécessaire : sans lui lftp sort avec un code de succès après un
    # miroir raté, et l'appelant croirait le site déposé.
    # « open » DANS LE SCRIPT, ET NON « -u » SUR LA LIGNE DE COMMANDE.
    # C'était le défaut le plus net de ce fichier — et ses propres
    # commentaires disaient deux fois qu'il ne fallait pas le commettre :
    # « lftp -u login,motdepasse hote » s'affiche dans « ps » pour TOUT
    # utilisateur de la machine, pendant les minutes que dure le
    # transfert. Le script, lui, voyage par l'entrée standard.
    # LES RÉGLAGES D'ABORD, « open » ENSUITE : posés après, ils ne
    # s'appliqueraient pas à la connexion en cours — le chiffrement se
    # réglerait une fois la poignée de main faite, c'est-à-dire trop tard.
    script = ('set ftp:ssl-force true\n'
              'set ftp:ssl-protect-data true\n'
              'set ssl:verify-certificate yes\n'
              'set net:max-retries 2\n'
              'set net:reconnect-interval-base 3\n'
              'set net:timeout 20\n'
              'set cmd:fail-exit true\n'
              f'open -u {guillemeter(conf["login"])},{guillemeter(mdp)} '
              f'{conf["hote"]}\n'
              f'{miroir}\nbye\n')
    # LE MOT DE PASSE NE DOIT PAS S'AFFICHER. lftp répète l'adresse complète
    # — « ftp://login:motdepasse@serveur/… » — à chaque fichier traité. En
    # terminal il s'étalait à l'écran et restait dans l'historique de
    # défilement ; masqué seulement par l'atelier, il fuyait partout ailleurs.
    # On lit donc la sortie ligne à ligne et on le remplace au passage, ce
    # qui préserve l'avancement en direct.
    print(f'\n--- dépôt par FTP ---')
    proc = subprocess.Popen(
        ['lftp'],                       # plus rien d'identifiant dans argv
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        proc.stdin.write(script)
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        # lftp mort avant d'avoir lu : une trace ne dirait rien de plus
        proc.wait()
        sys.exit('publier : lftp s’est arrêté avant de recevoir ses '
                 'ordres — rien n’a été envoyé.')
    for ligne in proc.stdout:
        print(ligne.replace(mdp, '••••••••'), end='')
    if proc.wait() != 0:
        sys.exit('publier : échec à l’étape « dépôt par FTP ».')


def shutil_which(nom):
    import shutil
    return shutil.which(nom)


def main():
    ap = argparse.ArgumentParser(description="Dépose le site chez l'hébergeur.")
    ap.add_argument('--pour-de-vrai', action='store_true',
                    help='envoie réellement (sinon : essai à blanc)')
    ap.add_argument('--sans-regenerer', action='store_true')
    ap.add_argument('--confirme', action='store_true',
                    help='CONTOURNE la phrase à taper : à ne donner que si '
                         'la confirmation a été obtenue ailleurs — c’est ce '
                         'que fait l’atelier, qui la fait taper dans le '
                         'navigateur')
    ap.add_argument('--ou', choices=sorted(DESTINATIONS), default='maison',
                    help="destination : « maison » (serveur d'essai, par "
                         "défaut) ou « en-ligne » (l'hébergeur)")
    args = ap.parse_args()

    if not args.sans_regenerer:
        etape('régénération', [sys.executable, str(RACINE / 'site' / 'generer.py')],
              cwd=str(RACINE))

    print('\n--- vérification ---')
    try:
        r = subprocess.run([sys.executable, str(RACINE / 'outils' / 'verifier.py')],
                           cwd=str(RACINE), timeout=900)
    except subprocess.TimeoutExpired:
        sys.exit('publier : la vérification n’a pas rendu la main (15 min) — '
                 'interrompu, rien n’a été envoyé.')
    if r.returncode != 0:
        print('\npublier : la vérification a relevé des anomalies.')
        if args.pour_de_vrai:
            # Sans clavier, on REFUSE. Répondre « oui » à la place de
            # l'absent serait la pire des réponses : la vérification existe
            # pour arrêter, pas pour informer.
            if not sys.stdin.isatty():
                sys.exit('publier : anomalies relevées et personne pour en '
                         'décider — abandon. Corrigez, ou publiez en terminal.')
            if input('Publier quand même ? [o/N] ').strip().lower() != 'o':
                sys.exit('publier : abandon.')

    if not PUBLIC.is_dir() or not (PUBLIC / 'index.html').exists():
        sys.exit('publier : site/public/ est vide — rien à envoyer.')

    conf = lire_conf(args.ou)
    methode = conf.get('methode', 'rsync').lower()
    poids = sum(f.stat().st_size for f in PUBLIC.rglob('*') if f.is_file())
    nb = sum(1 for f in PUBLIC.rglob('*') if f.is_file())
    print(f'\n  destination : {args.ou.upper()} — {conf.get("hote", "?")}'
          f':{conf.get("distant", "?")}')
    print(f'  à envoyer   : {nb} fichiers, {poids / 1e6:.1f} Mo, par {methode}')

    # UN SITE NE PERD PAS LE TIERS DE SES PAGES PAR ACCIDENT HEUREUX.
    # Le seul contrôle était « index.html existe » : un site tombé de 1 182
    # à 3 fichiers serait parti tel quel, et --delete aurait emporté le
    # reste chez l'hébergeur. On compare donc au dernier dépôt RÉUSSI vers
    # cette destination — les deux n'ont pas le même contenu, d'où un
    # compte par destination.
    avant = compte_precedent(args.ou)
    if avant and nb < avant * (1 - CHUTE_TOLEREE) and args.pour_de_vrai:
        print(f'\n  ATTENTION : le site est passé de {avant} à {nb} fichiers '
              f'depuis le dernier dépôt\n  vers « {args.ou} », soit '
              f'{100 * (1 - nb / avant):.0f} % de moins.')
        if not sys.stdin.isatty():
            sys.exit('publier : chute de volume inexpliquée et personne pour '
                     'en décider — abandon. Publiez en terminal si c’est voulu.')
        if input('  Est-ce voulu ? [o/N] ').strip().lower() != 'o':
            sys.exit('publier : abandon.')

    # Le dépôt efface ce qui n'est plus là (« --delete » / « mirror --delete »).
    # Sur le serveur d'essai c'est sans conséquence ; sur l'hébergeur cela
    # emporte le site que le monde voit, et tout ce qui traînerait à côté.
    # Une frappe distraite ne doit pas suffire.
    if conf.get('role') == 'public' and args.pour_de_vrai and not args.confirme:
        print('\n  ATTENTION : ceci remplace le SITE PUBLIC, et efface de')
        print('  l’hébergeur tout fichier absent de site/public/.')
        if not sys.stdin.isatty():
            sys.exit('publier : pas de clavier pour confirmer. Ajoutez '
                     '--confirme si la confirmation a été donnée ailleurs.')
        if input('  Tapez « je publie en ligne » pour confirmer : ').strip() \
                != 'je publie en ligne':
            sys.exit('publier : abandon.')

    if not args.pour_de_vrai:
        print('  ESSAI À BLANC — rien ne sera modifié en ligne.')
        print('  Ajoutez --pour-de-vrai pour publier.')

    if methode == 'rsync':
        par_rsync(conf, args.pour_de_vrai)
    elif methode == 'ftp':
        par_ftp(conf, args.pour_de_vrai)
    else:
        sys.exit(f'publier : méthode inconnue « {methode} » (rsync ou ftp).')

    if args.pour_de_vrai:
        # Une marque datée du dernier dépôt RÉUSSI. L'atelier s'en sert pour
        # compter ce qui est enregistré mais pas encore publié : sans elle,
        # rien ne distinguait « écrit sur mon disque » de « visible par les
        # autres », et l'on tournait en rond en croyant avoir publié.
        (RACINE / 'site' / '.derniere-publication').write_text(
            datetime.now().isoformat(timespec='seconds'), encoding='utf-8')
        noter_depot(args.ou, nb, poids)

    print('\n  terminé.' if args.pour_de_vrai else '\n  essai à blanc terminé.')


if __name__ == '__main__':
    main()
