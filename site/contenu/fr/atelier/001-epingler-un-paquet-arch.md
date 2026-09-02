---
titre: "Épingler un paquet sous Arch, et pourquoi une machine-outil l'exige"
langue: "fr"
type: "fiche"
collection: "atelier"
date: "2026-08-16"
rang: 1
traduction: "epingler-paquet"
vignette: "captures/pacman-epingle.png"
statut: "publie"
sommaire: "oui"
extrait: "Une distribution en flux continu et un logiciel de fabrication ne veulent pas la même chose. IgnorePkg règle le conflit — à condition de savoir ce qu'on achète avec."
---

Arch met tout à jour, tout le temps, et c'est ce qu'on lui demande. Mais un `pacman -Syu` fait un jour passer un logiciel de conception d'une version majeure à la suivante — et le greffon qu'on a écrit pour lui cesse de fonctionner, généralement au pire moment.

Ce n'est pas un désagrément d'informaticien. C'est une pièce de bois déjà bridée sur la table, une session de gravure prévue pour l'après-midi, et un atelier qui ne produit rien jusqu'à ce que le greffon soit porté.

## Le geste

Dans `/etc/pacman.conf`, section `[options]` :

```ini
IgnorePkg = freecad
```

Plusieurs paquets se séparent par des espaces, et le joker est accepté :

```ini
IgnorePkg = freecad linux linux-headers
IgnoreGroup = kde-applications
```

À partir de là, `pacman -Syu` met tout à jour **sauf** ces paquets, et le dit à chaque passage :

```text
avertissement : freecad: ignorer la mise à jour du paquet (1.1.3-1 => 1.2.0-1)
```

Cet avertissement est utile : il rappelle qu'une dette s'accumule. Ne le faites pas taire.

## Vérifier que l'épingle tient

Elle est facile à perdre — un `pacman.conf` remplacé par un `.pacnew` lors d'une mise à jour du gestionnaire de paquets, et l'épingle disparaît sans un mot.

```bash
grep -n "^IgnorePkg\|^IgnoreGroup" /etc/pacman.conf
```

Si la commande ne répond rien, l'épingle n'existe plus. À vérifier après chaque `.pacnew` traité — c'est-à-dire après chaque `pacdiff`.

Et pour savoir ce qui serait monté sans elle :

```bash
pacman -Qu
```

## Ce qu'on achète, et ce qu'on paie

**Ce qu'on achète** : la machine produit demain matin. C'est tout, et ça suffit.

**Ce qu'on paie**, et il faut le savoir avant :

- **une dette qui grossit.** Épingler trois mois est un choix ; épingler deux ans est un problème qu'on s'est fabriqué. La version épinglée finira par ne plus se lier aux bibliothèques du système ;
- **les correctifs de sécurité passent aussi à la trappe.** Pour un logiciel de conception hors ligne, le risque est faible. Pour un navigateur ou un service exposé, épingler est une mauvaise idée — s'il faut vraiment le faire, ce n'est pas la bonne solution au bon problème ;
- **les dépendances, elles, continuent d'avancer.** C'est le vrai piège : le paquet épinglé reste, mais tout ce sur quoi il s'appuie bouge. Un jour la version gelée ne démarre plus, non pas parce qu'elle a changé, mais parce que le sol s'est déplacé sous elle.

## La suite logique : deux versions côte à côte

Épingler n'est supportable que si l'on peut **essayer la nouvelle version sans risquer celle qui travaille**. C'est le vrai remède, et il transforme l'épingle en décision au lieu d'un report.

La plupart des logiciels de fabrication existent en AppImage. Deux précautions suffisent à les faire cohabiter avec le paquet système :

**1. Un dossier de configuration séparé.** Sinon les deux versions écrivent dans le même endroit, et celle de développement migre silencieusement des réglages que l'ancienne ne saura plus relire. Beaucoup d'applications acceptent une variable d'environnement pour cela.

**2. Un lanceur dédié**, dans `~/.local/bin`, qui pose la variable et lance l'AppImage :

```bash
#!/usr/bin/env bash
set -euo pipefail
export MONAPPLI_USER_HOME="$HOME/.local/share/monappli-dev"
mkdir -p "$MONAPPLI_USER_HOME"
exec "$HOME/Applications/MonAppli-weekly.AppImage" "$@"
```

On teste alors le greffon contre la version à venir quand on en a le temps, pas quand `pacman` en décide. Le jour où il passe, on retire l'épingle — et on l'a choisi.

Une précision qui compte si vous faites cela : la version de développement écrit dans **son** dossier, donc **les réglages que vous y changez ne reviennent pas** dans la version qui travaille. C'est le but, mais on l'oublie et on refait deux fois le même réglage en se demandant pourquoi il ne tient pas.

Sur cette machine, l'AppImage de développement demande en plus un `LD_PRELOAD` pour démarrer du tout — c'est une autre histoire, racontée dans [la fiche sur « Could not initialize GLX »](/fr/depannage/001-appimage-glx-libdrm/).

## Quand retirer l'épingle

Quand les trois cases sont cochées, et pas avant :

1. le greffon ou le flux de travail fonctionne sur la nouvelle version, **essayé sur un vrai fichier**, pas sur un cube ;
2. il n'y a pas de pièce en cours sur la machine ;
3. la version qui travaille est encore installable en cas de retour en arrière — le cache de pacman (`/var/cache/pacman/pkg/`) la garde, à condition de ne pas l'avoir vidé.

Cette troisième case est celle qu'on découvre trop tard. Avant d'ôter une épingle :

```bash
ls /var/cache/pacman/pkg/ | grep '^freecad-'
```

Si le paquet de la version en cours n'y est plus, mettez-le de côté ailleurs avant de mettre à jour. Un retour en arrière sans le paquet, c'est une compilation, et une compilation c'est la journée.
