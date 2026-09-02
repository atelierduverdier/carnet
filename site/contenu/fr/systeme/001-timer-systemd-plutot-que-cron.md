---
titre: "Planifier une tâche : un timer systemd, pas cron"
langue: "fr"
type: "fiche"
collection: "systeme"
date: "2026-08-17"
rang: 1
traduction: "timer-systemd"
vignette: "captures/timer-calendrier.png"
statut: "publie"
sommaire: "oui"
extrait: "Pourquoi une tâche planifiée sur un poste de bureau tient mieux en timer systemd utilisateur qu'en ligne de crontab — et comment en écrire un qui affiche une notification."
---

Sur un serveur qui tourne en continu, cron fait très bien l'affaire. Sur un **poste de bureau**, il a trois défauts qui se paient tôt ou tard, et un timer systemd les corrige tous les trois.

## Les trois raisons

**1. Le poste est éteint la nuit.** Une ligne de crontab prévue à 3 h ne se rattrape pas : la machine était éteinte, l'occasion est passée, on recommence demain. Un timer systemd avec `Persistent=true` **rattrape** le rendez-vous manqué au démarrage suivant. Pour un rappel hebdomadaire, la différence n'est pas cosmétique : c'est la différence entre un rappel qui arrive et un rappel qui n'arrive jamais.

**2. La sortie de cron se perd.** Elle part dans un courrier local que personne ne lit. La sortie d'un service systemd va dans le journal, et se relit avec une commande qu'on connaît déjà.

**3. Cron n'a pas votre session.** Une tâche qui veut afficher une notification sur le bureau a besoin de savoir à quel bus de session parler. En crontab, il faut le deviner et le coder en dur. En timer **utilisateur** (`systemctl --user`), on est déjà dedans.

## Un exemple complet

Un rappel la veille du jour de collecte des ordures — le genre de chose qu'on oublie précisément parce qu'elle revient toutes les semaines.

Trois fichiers. D'abord le script, dans `~/.local/bin/rappel-poubelles` :

```bash
#!/usr/bin/env bash
# Décide s'il y a quelque chose à sortir ce soir, et le dit.
set -euo pipefail

jour=$(date +%u)          # 1 = lundi … 7 = dimanche
[ "$jour" -eq 2 ] || exit 0   # collecte le mercredi : on prévient le mardi

notify-send --icon=user-trash-full \
            --urgency=normal \
            "Poubelles" "Collecte demain matin : sortir le bac."
```

Rendez-le exécutable :

```bash
chmod +x ~/.local/bin/rappel-poubelles
```

Puis le service, `~/.config/systemd/user/rappel-poubelles.service` :

```ini
[Unit]
Description=Rappel de sortie des poubelles

[Service]
Type=oneshot
ExecStart=%h/.local/bin/rappel-poubelles
```

Et le timer, `~/.config/systemd/user/rappel-poubelles.timer` :

```ini
[Unit]
Description=Rappel de sortie des poubelles, tous les soirs

[Timer]
OnCalendar=*-*-* 19:00:00
Persistent=true
AccuracySec=1m

[Install]
WantedBy=timers.target
```

Le service et le timer portent **le même nom** avant l'extension : c'est ainsi que systemd les apparie, sans qu'on ait à le dire.

## Le motif : un timer bête, un script qui décide

Remarquez que le timer se déclenche **tous les soirs**, et que c'est le *script* qui décide s'il y a lieu de parler. On aurait pu écrire `OnCalendar=Tue *-*-* 19:00:00` et supprimer le test.

Le choix n'est pas indifférent. Un timer qui se déclenche tous les jours se **vérifie tous les jours** : si le script est cassé, on le sait sous vingt-quatre heures. Un timer hebdomadaire garde son défaut une semaine — et comme on ne le voit pas passer, on ne sait même pas qu'il aurait dû parler.

La règle générale : **la planification dit *quand regarder*, le script dit *s'il faut agir*.** C'est aussi plus facile à essayer, puisqu'on peut lancer le script à la main n'importe quand.

## L'activer, et vérifier

```bash
systemctl --user daemon-reload
systemctl --user enable --now rappel-poubelles.timer
```

Les deux commandes qui servent ensuite :

```bash
systemctl --user list-timers --all
```

Elle montre, pour chaque timer, le prochain déclenchement, le précédent, et l'unité associée. C'est le tableau de bord — s'il n'y a rien dedans, rien n'est armé.

```bash
journalctl --user -u rappel-poubelles.service -n 20
```

La sortie des vingt derniers passages. C'est là que se lisent les erreurs qu'on n'a pas vues passer.

Pour essayer sans attendre 19 h :

```bash
systemctl --user start rappel-poubelles.service
```

## Deux pièges

**La notification muette.** Si `notify-send` ne fait rien depuis le service alors qu'il marche en terminal, c'est presque toujours l'environnement de session qui manque. En timer *utilisateur* le problème est rare ; s'il survient, `systemctl --user import-environment DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS` au démarrage de session le règle.

**Le fichier restauré n'est pas un timer armé.** Si vous versionnez `~/.config/systemd/user/` (avec chezmoi ou autre), la restauration recopie bien les fichiers — mais **pas l'état « enabled »**, qui vit dans des liens symboliques ailleurs. Après une réinstallation, il faut refaire le `enable --now`. C'est la case qu'on oublie, et on croit le timer perdu alors qu'il est simplement au repos.

## Ne l'activez pas pour quelqu'un d'autre

Une dernière chose, qui n'est pas technique. Un timer est une chose qui **parlera toute seule**, plus tard, sans qu'on s'y attende. Écrire les trois fichiers pour quelqu'un est un service ; les activer à sa place est une décision qui ne vous appartient pas. Laissez la dernière commande à faire.
