---
titre: "pgrep -f se trouve lui-même (et pkill tue votre script)"
langue: "fr"
type: "fiche"
collection: "depannage"
date: "2026-08-22"
rang: 2
traduction: "pgrep"
vignette: "captures/pgrep-se-trouve.png"
statut: "publie"
sommaire: "oui"
extrait: "Un script qui vérifie si un service tourne le trouve toujours en marche — parce qu'il se voit lui-même. Trois façons de s'en sortir, dont une qui ne suffit pas."
---

Un script de surveillance tout simple :

```bash
if pgrep -f cloudflared > /dev/null; then
    echo "le tunnel tourne"
else
    echo "le tunnel est arrêté ; on le relance"
    cloudflared tunnel run mon-tunnel &
fi
```

Il annonce toujours que le tunnel tourne. Toujours. Même tunnel arrêté, même service masqué, même après un `reboot`.

## Pourquoi

`pgrep -f` cherche le motif dans la **ligne de commande complète** de chaque processus. Or votre script *est* un processus, et sa ligne de commande contient le mot `cloudflared` — puisqu'il est écrit dedans.

Le script se trouve lui-même. Le test est vrai avant même d'avoir regardé quoi que ce soit.

Avec `pkill`, c'est pire : le script **se tue lui-même**, et souvent au milieu d'une boucle, ce qui donne un comportement à moitié exécuté, difficile à relire.

Pour le voir de vos yeux :

```bash
bash -c 'pgrep -af unmotifquinexistepas'
```

Cette commande cherche un motif qui n'existe **nulle part** sur la machine — et pourtant elle affiche une ligne : celle du shell qui la porte, dont la ligne de commande contient le motif. Vérifié à l'instant sur la machine où j'écris.

### Le piège dans le piège : la démonstration qui ne démontre rien

En essayant de reproduire le défaut pour l'illustrer, on tombe sur ceci :

```bash
bash -c 'pgrep -af unmotifabsent'
```

Cette commande ne renvoie **rien**. On en conclut que tout va bien, et on referme.

C'est faux, et pour une raison qui n'a rien à voir avec `pgrep` : quand `bash -c` n'a **qu'une seule commande** à exécuter, il ne crée pas de processus fils — il se **remplace** par elle. Il n'y a donc plus de shell portant le motif, et `pgrep`, qui s'exclut toujours lui-même, ne trouve personne.

Ajoutez la moindre suite et le shell survit — donc se fait trouver :

```bash
bash -c 'pgrep -af unmotifabsent || echo non'
```

Cette fois, une ligne sort : le shell lui-même. Et c'est exactement la forme d'un script de surveillance réel, qui a toujours quelque chose à faire ensuite.

**D'où l'illusion**, et elle est coûteuse : le test rapide semble sain, le vrai script échoue. Ce n'est pas que le défaut soit intermittent — c'est que le test l'avait supprimé en le simplifiant.

## Le remède le plus connu : les crochets

```bash
pgrep -f '[c]loudflared'
```

`[c]loudflared` est une expression régulière qui **correspond à** `cloudflared` mais **ne s'écrit pas** `cloudflared`. La ligne de commande du script contient donc les crochets, pas le mot — et le motif ne se reconnaît plus lui-même.

C'est élégant, ça tient en deux caractères, et c'est ce qu'on trouve partout. Mais ça ne couvre qu'un cas sur deux.

## Le cas que les crochets ne couvrent pas

L'astuce protège **le motif**. Elle ne protège pas le reste de la ligne de commande.

```bash
bash -c "pgrep -f '[c]loudflared' || cloudflared tunnel run mon-tunnel"
```

Ici le mot `cloudflared` apparaît **une seconde fois**, en clair, dans la partie « sinon ». La ligne de commande complète du shell le contient donc, et `pgrep` la trouve — crochets ou pas. Le test redevient toujours vrai.

Le piège est vicieux parce que la protection *a l'air* d'être là. On a écrit les crochets, on se croit couvert, et la panne revient. Je l'ai payé trois fois en deux jours avant de voir ce qui se passait.

**La parade : mettre la recherche dans un appel séparé**, dont la ligne de commande ne mentionne la cible qu'une seule fois — celle avec les crochets.

```bash
if pgrep -f '[c]loudflared' > /dev/null; then
    echo "le tunnel tourne"
else
    demarrer_le_tunnel        # le nom de la cible n'apparaît pas ici
fi
```

Ou, plus simplement : ne jamais écrire le test et la relance sur la **même ligne**.

## Le remède qui vaut mieux que tout ça

Si le processus est un service systemd — et c'est souvent le cas — n'interrogez pas la table des processus. Demandez à systemd :

```bash
systemctl --user is-active --quiet mon-service && echo "en marche"
```

Aucun motif, aucune ligne de commande, aucune auto-détection possible. `is-active` répond sur l'état réel de l'unité, pas sur ce qui ressemble à un nom dans un `ps`.

Pour un processus qui n'est pas un service, un **fichier de verrou** avec le PID dedans est plus sûr qu'un `pgrep`, et se relit dans six mois sans se demander pourquoi il y a des crochets.

## Un dernier réflexe

Quand un `pgrep`/`pkill` se comporte bizarrement, regardez ce qu'il voit **vraiment** — l'option `-a` affiche la ligne de commande complète de chaque correspondance :

```bash
pgrep -af mon-motif
```

Si votre propre script apparaît dans la liste, vous y êtes. C'est un contrôle de deux secondes, et il évite d'accuser le service.
