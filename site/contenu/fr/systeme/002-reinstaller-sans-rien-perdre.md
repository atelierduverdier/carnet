---
titre: "Réinstaller sans rien perdre : l'ordre des gestes"
langue: "fr"
type: "fiche"
collection: "systeme"
date: "2026-08-15"
rang: 2
traduction: "reinstaller"
statut: "publie"
sommaire: "oui"
extrait: "Une réinstallation ne se prépare pas le jour où on la fait. Ce qui se perd n'est presque jamais les fichiers : c'est la phrase de passe du dépôt de sauvegarde, et l'état « activé » de ce qu'on a restauré."
---

Écrit après une panne de SSD, et relu après la réinstallation qui a suivi. Ce n'est pas un guide d'installation d'Arch — il y en a de très bons — mais la liste de ce qui **se perd** quand on réinstalle, et qui n'est pas dans les fichiers.

## À faire maintenant, pas le jour J

Une seule chose est vraiment urgente, et elle doit être faite **pendant que la machine actuelle fonctionne encore**.

**Sortir la phrase de passe du dépôt de sauvegarde du trousseau du bureau.**

Si vous sauvegardez avec Borg (ou restic, c'est pareil) et que la phrase de passe est mémorisée dans KWallet, GNOME Keyring ou le trousseau de votre gestionnaire de sauvegarde, alors elle n'existe **qu'à cet endroit**. Les outils de dotfiles ne versionnent pas les trousseaux — volontairement, pour ne pas mettre de secrets dans un dépôt git. C'est le bon choix, et c'est exactement ce qui rend la phrase de passe invisible le jour où on l'oublie.

Sans elle, l'intégralité de l'historique de sauvegarde devient **définitivement illisible**. Borg ne propose aucune récupération : c'est du chiffrement, il fait son travail.

La sortir prend deux minutes :

1. ouvrir le gestionnaire de trousseau et chercher l'entrée du dépôt ;
2. copier la phrase de passe dans un gestionnaire de mots de passe — ou sur du papier, dans un endroit sûr ;
3. **surtout pas** dans un fichier en clair sur la machine qu'on va effacer.

Tant que la phrase de passe ne change pas, c'est fait une fois pour toutes.

## L'ordre qui marche

**1. Le système, puis les trois outils qui comptent.**

```bash
sudo pacman -Syu
sudo pacman -S git chezmoi borgbackup
```

Rien d'autre pour l'instant : tout le reste va venir des dotfiles.

**2. Les dotfiles.**

```bash
chezmoi init --apply <votre-compte>/dotfiles
```

Une commande, et reviennent d'un coup les shells, la configuration du bureau, les raccourcis clavier, les terminaux, les éditeurs, les applications. C'est le geste qui rend une réinstallation supportable — à condition d'avoir versionné les dotfiles *avant*, ce qui est le vrai travail et se fait un jour de calme.

**3. Le dépôt de sauvegarde, avec la phrase de passe qu'on vient de retrouver.**

Rebrancher le disque, rattacher le dépôt dans l'outil, et **vérifier que l'historique remonte avant la réinstallation**. Ne pas se contenter de voir la liste : lancer une sauvegarde manuelle, une fois, pour confirmer que l'écriture fonctionne aussi. Un dépôt qu'on lit n'est pas un dépôt dans lequel on écrit.

**4. Réactiver ce qui a été restauré.**

C'est la case oubliée, et elle mérite son paragraphe.

## Un fichier restauré n'est pas un service actif

Les dotfiles restaurent les **fichiers** des timers et services systemd utilisateur, puisqu'ils vivent dans `~/.config/systemd/user/`. Ils ne restaurent **pas** leur état « activé », qui tient dans des liens symboliques créés par `systemctl enable`.

Résultat : tout est là, rien ne tourne, et on ne s'en aperçoit qu'en constatant l'absence d'un rappel qu'on attendait la semaine suivante.

```bash
systemctl --user daemon-reload
systemctl --user enable --now mon-timer.timer
systemctl --user list-timers --all
```

La dernière commande est le contrôle : chaque timer attendu doit y figurer, avec une date de prochain déclenchement. Un timer absent de cette liste ne se déclenchera jamais.

Le même principe vaut ailleurs. Une **règle udev** restaurée demande un `udevadm control --reload` et le rebranchement du matériel. Un **pare-feu** dont on a restauré la configuration reste souvent désactivé. La règle générale : *ce qui a un interrupteur revient éteint*.

## Deux catégories d'applications à ne pas restaurer bêtement

**Les clients de synchronisation cloud.** Configurez le dossier local **dans l'application, avant que le dossier existe ou soit rempli**. Si vous restaurez d'abord les fichiers puis pointez l'application dessus, beaucoup de clients ne reconnaissent pas le contenu et retéléchargent tout — plusieurs dizaines de gigaoctets, et parfois une pagaille de doublons.

**Les applications à bibliothèque** — gestionnaire de livres, de polices, de notes, de modèles 3D. Ouvrez l'application *en premier* et pointez-la vers l'emplacement voulu. Recopier le dossier de configuration à la main marche parfois, échoue silencieusement souvent, et laisse une base d'index qui parle d'anciens chemins.

Dans les deux cas, c'est le même principe : **l'application doit apprendre le chemin, pas le découvrir**.

## Le contrôle final

Trois commandes, et un coup d'œil :

```bash
systemctl --user list-timers --all
git -C ~/Projets/un-depot-important status
```

- les timers attendus sont là et « enabled » ;
- les dépôts git sont propres et sur la bonne branche ;
- l'historique de sauvegarde remonte avant la réinstallation ;
- une sauvegarde manuelle passe.

Cette dernière ligne est celle qu'on saute parce qu'on est fatigué, et c'est la seule qui prouve que la chaîne complète fonctionne. Le reste prouve qu'elle a l'air de fonctionner.

## Ce que j'ai appris à la dure

Une archive dont on **croit** qu'elle existe n'existe pas. Après la panne, j'étais persuadé d'avoir fait une sauvegarde la veille — il n'y avait aucune trace, aucun commit, rien. La certitude ne compte pas ; ce qui compte est ce que la commande de vérification répond.

Depuis, un petit script de contrôle passe sur le dépôt et **dit** ce qu'il y trouve, plutôt que de me laisser supposer. C'est trois lignes, et ça remplace une conviction par un fait.
