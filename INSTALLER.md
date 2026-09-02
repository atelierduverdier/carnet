# Installer l'atelier sur un autre ordinateur

*(Ce fichier vient du site dentosophie.com, qui tourne sur ce squelette ;
il vaut tel quel pour tout site fait avec.)*

Le site et son atelier tournent sur **Linux, macOS et Windows** : tout est en
Python et rien n'y suppose un système particulier. Voici ce qu'il faut mettre
en place, et ce qui coince selon la machine.

## Ce qu'il faut

| | |
|---|---|
| **Python 3.8 ou plus** | macOS en fournit un depuis Monterey, Linux toujours ; sous Windows, l'installer depuis python.org en cochant « Add to PATH » |
| **Cinq bibliothèques** | voir ci-dessous |
| **rsync** (facultatif) | seulement pour publier par SSH — présent sur macOS et Linux, absent de Windows |
| **Un navigateur Chrome/Brave** (facultatif) | seulement pour réimprimer le bon de commande en PDF |

## Les bibliothèques

```bash
python3 -m pip install --user pyyaml markdown jinja2 markupsafe pillow
```

À quoi chacune sert, pour savoir laquelle manque quand quelque chose casse :

| bibliothèque | sans elle |
|---|---|
| `pyyaml` | l'atelier ne démarre pas — il lit les en-têtes des pages |
| `markdown` | le site ne s'engendre pas |
| `jinja2`, `markupsafe` | les gabarits ne s'appliquent pas |
| `pillow` | les photos déposées ne sont plus réduites à 1 600 px |

`html2text` n'est utile qu'à `outils/importer.py`, qui relit l'export
WordPress. Une personne qui reprend le site n'en a pas besoin.

## Démarrer

```bash
cd <le dossier du site>
python3 outils/atelier.py
```

L'atelier s'ouvre dans le navigateur sur <http://localhost:8413>. Il sert aussi
l'aperçu : rien d'autre à lancer.

## Ce qui diffère selon la machine

**macOS.** Tout fonctionne, vérifié fichier par fichier — rien dans le code ne
suppose Linux, aucun nom de fichier du dépôt ne se heurte à un disque
insensible à la casse, et `rsync` n'emploie que des options que celui d'Apple
connaît (il écarte même les `.DS_Store`). Trois points tout de même :

- `python3` n'existe qu'une fois les **outils en ligne de commande** installés ;
  la première invocation propose de le faire, sinon `xcode-select --install` ;
- le Python d'Apple n'a pas toujours `pip` : si la commande échoue, installer
  Python depuis python.org, ou `brew install python` ;
- publier **par FTP** demande `lftp`, absent de macOS : `brew install lftp`. La
  publication par SSH (rsync), elle, marche telle quelle.

Les navigateurs n'étant pas dans le PATH, `refaire_bon_de_commande.py` les
cherche aussi dans `/Applications`. Et le raccourci de la recherche est ⌘K,
l'atelier l'affiche ainsi de lui-même.

**Windows.** Pas de `rsync` : la publication par SSH ne marchera pas telle
quelle. Deux voies — passer par la méthode `ftp` de `outils/publier.py`, qui
demande `lftp`, ou déposer `site/public/` à la main chez l'hébergeur.

**Linux.** Rien de particulier.

## Ce qu'il faut EXPLIQUER à la personne

L'installation n'est pas le difficile. Le difficile est la chaîne en trois
temps, et elle ne se devine pas :

1. **Enregistrer chez moi** écrit le fichier sur son disque — rien ne change en
   ligne ;
2. **Vérifier chez moi** refabrique les pages, pour les relire ;
3. **Publier en ligne…** les envoie chez l'hébergeur — le seul moment où ce que
   voient les visiteurs change.

Le bouton de publication porte le compte de ce qui attend. Et une fiche
**naît en brouillon** : tant qu'elle l'est, elle n'apparaît nulle part.

## Ce qui NE se transmet pas

`outils/publier.conf` contient les identifiants d'hébergement et ne quitte
jamais la machine — il est ignoré par git. La personne devra créer le sien à
partir de `outils/publier.conf.exemple`.
