---
titre: "Mémento des commandes"
langue: "fr"
type: "page"
slug: "commandes"
traduction: "commandes"
sommaire: "cote"
vignette: "captures/glx-symbole.png"
statut: "publie"
extrait: "Les commandes qui ont servi à écrire ce carnet : ce qu'elles font, quand elles servent, et le piège de chacune."
---

Ce ne sont pas *les* commandes Linux : ce sont **celles qui ont servi ici**, dans l'ordre où les problèmes se posent. Chacune tient en trois lignes — ce qu'elle fait, quand on en a besoin, et le piège qui va avec.

## Ce qu'une bibliothèque fournit, et ce qu'elle réclame

```bash
nm -D /usr/lib/libdrm_amdgpu.so.1 | grep monsymbole
nm -Du /usr/lib/libgallium-*.so | grep monsymbole
```

`T` = le symbole est **fourni**. `U` = il est **réclamé**. Une bibliothèque qui réclame ce que personne ne fournit ne se charge pas — et le programme meurt bien plus loin, sur un message qui ne parle pas d'elle.

Le `-D` n'est pas optionnel sur une bibliothèque partagée : sans lui, `nm` répond « aucun symbole ».

```bash
python3 -c "import ctypes; ctypes.CDLL('/usr/lib/malib.so.0')"
```

**Celle-ci nomme le symbole manquant.** C'est souvent la commande qui met fin à une hypothèse : elle dit ce qui manque au lieu de laisser deviner.

```bash
LD_PRELOAD=/usr/lib/a.so:/usr/lib/b.so ./mon-programme
LD_LIBRARY_PATH=/un/dossier/lib glxinfo -B
```

`LD_PRELOAD` force une bibliothèque **avant** toutes les autres — le remède quand un AppImage embarque une version trop vieille. `LD_LIBRARY_PATH` fait l'inverse : il fait voir à un programme les bibliothèques de quelqu'un d'autre, ce qui **reproduit** la panne hors du programme.

## Un processus tourne-t-il vraiment

```bash
pgrep -af '[m]onservice'
```

`-a` affiche la ligne de commande complète : c'est elle qui montre pourquoi la réponse est fausse. Les crochets empêchent le motif de se reconnaître lui-même — [le détail est ici](/fr/depannage/002-pgrep-se-trouve-lui-meme/).

```bash
systemctl --user is-active --quiet mon-service && echo "en marche"
```

**Quand c'est un service, préférez toujours ceci.** Aucun motif, aucune ligne de commande, aucune auto-détection possible : la réponse porte sur l'état réel de l'unité.

## systemd : planifier, vérifier, lire

```bash
systemctl --user daemon-reload
systemctl --user enable --now mon-timer.timer
```

`daemon-reload` après toute écriture de fichier d'unité. `enable --now` arme **et** démarre : sans `--now`, il faudra attendre le prochain démarrage de session.

```bash
systemctl --user list-timers --all
```

Le tableau de bord : prochain déclenchement, précédent, unité associée. **Un timer absent de cette liste ne se déclenchera jamais** — c'est le premier endroit à regarder quand un rappel n'est pas venu.

```bash
journalctl --user -u mon-service.service -n 20
```

La sortie des vingt derniers passages. C'est là que dorment les erreurs qu'on n'a pas vues passer.

```bash
systemd-analyze calendar 'Tue *-*-* 19:00:00'
```

Répond à « ça se déclenche quand, au juste ? » sans attendre. Utile avant d'armer, pas après.

## Les paquets, sous Arch

```bash
grep -n "^IgnorePkg\|^IgnoreGroup" /etc/pacman.conf
```

L'épingle qui retient un paquet à sa version. Elle se perd facilement — un `pacman.conf` remplacé par un `.pacnew`, et elle disparaît sans un mot. À revérifier après chaque `pacdiff`.

```bash
pacman -Qu          # ce qui monterait
pacman -Q freecad   # la version tenue
```

```bash
ls /var/cache/pacman/pkg/ | grep '^freecad-'
```

**Le filet du retour en arrière.** Le cache garde les paquets installés ; si celui de la version en cours n'y est plus, revenir en arrière demande une compilation. À vérifier **avant** d'ôter une épingle, pas après.

`pacman -S unpaquet` sans `-Syu` sur une base de données périmée est une mise à jour partielle : le piège classique. `pacman -Syu unpaquet` fait les deux.

## Où passe la place disque

```bash
df -h /tmp
du -sh /tmp/* | sort -h | tail -12
```

`sort -h` comprend les « M » et les « G » : c'est lui qui met le coupable en dernier. Sans lui, `du` trie par nom et on ne voit rien.

```bash
find /tmp -maxdepth 1 -name 'motif-*' -type d -exec rm -rf {} +
```

`-maxdepth 1` pour ne pas descendre, `-type d` pour ne viser que des dossiers, et `+` plutôt que `\;` pour tout passer en une fois. **Relisez le motif avant d'appuyer** : `rm -rf` ne demande rien.

## Vérifier qu'un site répond

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://exemple.fr/une/page/
```

Le code de retour seul, sans la page. Idéal en boucle sur une liste d'adresses : on voit d'un coup ce qui est en 404.

```bash
getent hosts monsite.exemple.fr
```

Résout un nom comme le fait le système — donc avec ses fichiers `hosts` et son cache, ce qu'un service en ligne ne vous dira pas.

## Images et polices, en ligne de commande

```bash
rsvg-convert -h 128 dessin.svg -o dessin.png
```

Rend un SVG à une **hauteur** donnée, la largeur suivant. Pratique pour préparer une icône ou un logo sans ouvrir d'éditeur.

```bash
xmllint --noout --html page.html
```

Dit si le fichier est bien formé, et rien d'autre. Un SVG invalide ne s'affiche **pas du tout** dans certaines applications, sans le moindre message : ce contrôle coûte une seconde.

```bash
fc-list | grep -i mono
```

Les polices installées, avec leur chemin — celui qu'il faut donner à un script qui dessine du texte.

## Git, quand on partage le dossier

```bash
git status --short
```

**La première commande à taper**, avant toute chose, quand plusieurs sessions travaillent au même endroit. Elle dit ce qui n'est pas à vous.

```bash
git add -A -- ':!un/fichier' ':!un/autre'
```

Verse tout **sauf** ce qui est nommé. C'est ainsi qu'on committe son travail sans emporter celui du voisin.

```bash
git log --oneline -5
git ls-tree --name-only origin/une-branche -- un/dossier/
```

La seconde regarde ce qu'une branche **distante** contient, sans y basculer ni la télécharger — utile pour vérifier qu'une publication est bien partie.
