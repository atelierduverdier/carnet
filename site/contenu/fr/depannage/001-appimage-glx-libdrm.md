---
titre: "Un AppImage meurt au démarrage : « Could not initialize GLX »"
langue: "fr"
type: "fiche"
collection: "depannage"
date: "2026-08-24"
rang: 1
statut: "publie"
sommaire: "oui"
extrait: "Sur Arch avec une carte AMD, les AppImages Qt s'arrêtent net sans fenêtre ni message. La cause n'est pas Qt : c'est une libdrm embarquée trop vieille qui prend le pas sur celle du système."
---

Sur une machine Arch à jour, carte AMD, pilote Mesa : un AppImage Qt — FreeCAD dans mon cas, mais la panne n'a rien de propre à lui — s'arrête au lancement. Pas de fenêtre, pas de boîte de dialogue. Dans le terminal, au mieux :

```text
Could not initialize GLX
Abandon (core dumped)
```

Le processus meurt sur le signal 6. Rien d'autre. Le même AppImage tournait la semaine d'avant.

## Ce que j'ai cru pendant huit jours

Que le problème venait des **bibliothèques Qt et GL gelées dans l'AppImage**, construites en juillet, devenues incompatibles avec le Mesa 26.2 du système. C'est l'explication qui vient naturellement : un AppImage embarque son monde, le système avance, un jour ça craque.

Je l'ai écrite dans un fichier de notes, avec assurance, et elle y est restée huit jours. Elle était fausse. Elle avait surtout le défaut d'être **inactionnable** : si le coupable est « l'AppImage est trop vieille », il n'y a rien à faire qu'attendre la suivante.

Deux pistes classiques ne donnent rien non plus, et il vaut mieux le savoir avant d'y passer une heure :

```bash
LIBGL_DEBUG=verbose MESA_DEBUG=1 ./MonAppli.AppImage
```

Sur cette panne, ces deux variables **n'impriment rien du tout**. Zéro ligne. C'est déroutant — on croit s'être trompé de variable — mais c'est logique : le pilote échoue si tôt que le code qui produit ces traces n'est jamais atteint.

## La vraie cause, en un nom de symbole

L'AppImage embarque `libdrm_amdgpu.so.1` en version **2.4.125** (novembre 2024). Le Mesa du système, lui, réclame le symbole `amdgpu_va_manager_init2`, **apparu en libdrm 2.4.134**.

Or l'AppImage met son propre `usr/lib` en tête du chemin de recherche : **la bibliothèque embarquée gagne**. Le pilote Mesa du système essaie alors de se lier contre une libdrm qui ne connaît pas le symbole. La chaîne se déroule toute seule :

1. `libgallium-26.2.1-arch3.1.so` ne résout pas `amdgpu_va_manager_init2` ;
2. il ne se charge pas — donc **radeonsi disparaît** ;
3. sans pilote, **GLX n'expose plus aucune FBConfig** ;
4. Qt demande un contexte GL, n'en obtient aucun, et abandonne.

Le message « Could not initialize GLX » est donc le quatrième maillon. Il désigne l'endroit où ça s'est vu, pas l'endroit où ça s'est cassé — c'est pour ça qu'on cherche des heures du mauvais côté.

## Le vérifier chez vous, en une minute

Le diagnostic se reproduit **hors de l'application**, ce qui est tout l'intérêt : plus besoin de relancer un logiciel de 800 Mo pour tester une hypothèse.

Montez l'AppImage sans l'exécuter :

```bash
./MonAppli.AppImage --appimage-mount
```

Elle affiche un point de montage (`/tmp/.mount_XXXXXX`) et reste ouverte. Dans **un autre terminal**, forcez son `usr/lib` et regardez ce que voit OpenGL :

```bash
LD_LIBRARY_PATH=/tmp/.mount_XXXXXX/usr/lib glxinfo -B
```

Si radeonsi a disparu, vous verrez `llvmpipe` (le rendu logiciel) ou une erreur, au lieu du nom de votre carte.

La commande suivante **nomme le symbole manquant** — c'est elle qui a mis fin aux huit jours d'hypothèse :

```bash
LD_LIBRARY_PATH=/tmp/.mount_XXXXXX/usr/lib \
  python3 -c "import ctypes; ctypes.CDLL('/usr/lib/libGLX_mesa.so.0')"
```

Le message d'erreur donne le nom exact. Rien à interpréter.

Vous pouvez aussi confirmer les deux côtés sur votre système :

```bash
nm -D --undefined-only /usr/lib/libgallium-*.so | grep amdgpu_va_manager
nm -D /usr/lib/libdrm_amdgpu.so.1 | grep amdgpu_va_manager
```

Le premier doit répondre `U` (le symbole est *réclamé*), le second `T` (il est *fourni*). Si le second ne répond rien, votre libdrm système est elle aussi trop vieille, et c'est une autre histoire.

## Le remède

Une variable. On force les libdrm du système à se charger **avant** celles de l'AppImage :

```bash
LD_PRELOAD=/usr/lib/libdrm_amdgpu.so.1:/usr/lib/libdrm.so.2 ./MonAppli.AppImage
```

**Précharger `libdrm.so.2` seule ne change rien** — je l'ai essayé en premier, par réflexe, parce que c'est elle qu'on nomme quand on dit « libdrm ». Le symbole manquant vit dans `libdrm_amdgpu.so.1`, qui est une bibliothèque *séparée*. Il faut les deux : la seconde parce que la première en dépend, et mélanger une `libdrm_amdgpu` neuve avec une `libdrm` ancienne ne mène nulle part.

Pour ne pas retaper ça à chaque lancement, un petit lanceur dans `~/.local/bin` :

```bash
#!/usr/bin/env bash
set -euo pipefail
export LD_PRELOAD="/usr/lib/libdrm_amdgpu.so.1:/usr/lib/libdrm.so.2${LD_PRELOAD:+:$LD_PRELOAD}"
exec "$HOME/Applications/MonAppli.AppImage" "$@"
```

La forme `${LD_PRELOAD:+:$LD_PRELOAD}` ajoute l'ancienne valeur **seulement si elle existe** : sans elle, un `LD_PRELOAD` vide laisserait un deux-points en trop, que l'éditeur de liens lit comme « précharger le répertoire courant ».

## Ce que la panne apprend

**Un AppImage n'est pas étanche.** On le présente comme « tout est dedans, rien ne peut casser » ; en réalité il partage avec le système tout ce qui touche au matériel — GPU, DRM, pilotes. Cette zone de contact est exactement l'endroit où les versions se croisent, et personne ne la teste.

**Un message d'erreur nomme le symptôme, pas la cause.** Chercher « Could not initialize GLX » ramène des milliers de pages sur Qt, sur X11, sur les pilotes propriétaires. Aucune sur libdrm. C'est en descendant d'un cran à chaque fois — Qt, puis GLX, puis le pilote, puis l'éditeur de liens — qu'on tombe sur le nom.

**Une hypothèse invérifiable est un aveu.** « Les bibliothèques sont trop vieilles » ne se teste pas, ne se réfute pas, et ne se répare pas. Ce genre d'explication devrait déclencher un signal d'alarme au moment où on l'écrit : si elle était vraie, que ferait-on ? Rien. Donc ce n'est pas encore une explication.

À retirer le jour où l'AppImage sera reconstruite avec une libdrm récente. En attendant, le lanceur coûte huit lignes.
