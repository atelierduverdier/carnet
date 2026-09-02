# CLAUDE.md

Ce qui doit être vrai à chaque session sur ce dépôt. Lire `LISEZMOI.md` d'abord.

## Ce que c'est

**Le Carnet du Verdier** — les pense-bêtes Linux de l'atelier, en public sur
`carnet.atelierduverdier.fr` (voir `CNAME`), servi par GitHub Pages.

Fabriqué avec le **squelette de site**, dont ce dépôt contient une **copie du
moteur**, pas un lien. Le squelette vit dans
`~/Projets/logiciels/squelette-site`.

## Non négociable

### 1. Tout est en français

Commentaires, docstrings, textes d'interface, **et messages de commit**.

### 2. C'est un site PUBLIC, et publier le met en ligne

Il n'y a pas de préproduction. Relire avant de publier, et vérifier dans un
navigateur — pas seulement le HTML.

### 3. Rien de privé ne part en ligne

Ce carnet raconte une machine réelle. Il ne doit **jamais** porter : une
adresse IP du réseau local, un nom de machine, un chemin vers un coffre ou une
sauvegarde, un nom de dépôt privé, une clé. Les fiches existantes remplacent
tout cela par des exemples (`<votre-compte>/dotfiles`, `MonAppli.AppImage`) —
garder cette discipline, y compris quand la valeur réelle rendrait la fiche
« plus concrète ». Ce qui compte est la méthode.

### 4. Une fiche qu'on n'a pas essayée n'entre pas

C'est la promesse de la page « À propos », et c'est ce qui distingue ce carnet
des milliers de pages qui recopient une réponse trouvée ailleurs. Si une piste
n'a pas été vérifiée sur la machine, elle est **écrite comme telle**, noir sur
blanc. Vérifier avant d'écrire : les versions de paquets, les noms de symboles,
les chemins de bibliothèques se contrôlent en une commande.

Exemple de ce que ça veut dire : la fiche sur le « Could not initialize GLX »
affirme que `libgallium` réclame `amdgpu_va_manager_init2` et que seule libdrm
≥ 2.4.134 le fournit. Les deux moitiés ont été lues avec `nm -D` avant d'être
écrites.

### 5. Le `CNAME` fait vivre le domaine

Le supprimer ou le modifier casse `carnet.atelierduverdier.fr`. Il n'a rien à
faire dans un `.gitignore` ni dans un nettoyage de fichiers « inutiles ».

## La forme d'une fiche

Symptôme → **ce que j'ai cru** → cause → remède. Le deuxième temps n'est pas
décoratif : c'est ce qui manque dans les pages qu'on trouve en cherchant une
panne, et c'est lui qui fait gagner du temps au lecteur engagé dans la même
fausse piste. Ne pas le raboter pour « aller à l'essentiel ».

`sommaire: "oui"` dans l'en-tête pose un plan, à partir de trois sections.

## Écrire un paragraphe sur UNE ligne

Le moteur active `nl2br` : un simple retour à la ligne devient un `<br>`. Un
paragraphe coupé sur deux lignes dans le fichier sort donc coupé dans la page.
C'est voulu côté moteur (il vient d'un import WordPress) et il faut faire avec
ici : **un paragraphe, une ligne**. Les listes, elles, se coupent normalement.

## Les blocs de code se jouent en deux endroits

Le moteur pose `<pre><code class="language-xxx">` ; **tout le reste est du
thème**. Ce qui est branché : défilement horizontal (une ligne de commande ne
se coupe pas), barre avec le langage et le bouton **Copier**, et retour à la
ligne à l'impression.

Le bouton essaie `navigator.clipboard` **puis** `document.execCommand('copy')`.
Le repli n'est pas de la ceinture-bretelles : mesuré le 02/09/2026, page servie
depuis localhost, clic réel, document focalisé — `writeText` rejette quand
même. Sans le repli, le bouton affichait « Échec ».

## Le thème

`themes/carnet/`, qui **hérite** de `verdure`. Il n'apporte que sa feuille de
style ; gabarits, script, polices et images viennent du parent, sauf les trois
images qu'il livre (`logo.png` — le chapeau —, les deux favicons).

Deux choses à savoir avant d'y toucher :

- **les couleurs viennent de `kit/verdier.css`** du dépôt
  `atelierduverdier/site`, où elles ont été mesurées. Ne pas en inventer :
  corriger là-bas, reporter ici ;
- **le mode sombre oblige à reprendre six fonds** que Verdure écrit en dur
  (bandeau, sous-menus, rappel, encadré, pied, filet du pied). Ils passent par
  des variables déclarées dans les DEUX livrées. Le plus coûteux a été
  `.entete` : sur fond noir le bandeau restait blanc avec un nom de site clair
  par-dessus, donc invisible — **trouvé à l'écran, pas dans la feuille**. Si
  une zone claire réapparaît en mode sombre, chercher une couleur en dur dans
  `themes/verdure/site.css`, pas ailleurs.

Pas de bouton clair/sombre : il faudrait recopier `base.html` dans le thème, et
cette copie ne recevrait plus jamais un correctif du parent. Le site suit
`prefers-color-scheme`.

## Le moteur ne se met pas à jour tout seul

```bash
python3 outils/mettre-a-jour.py --depuis ~/Projets/logiciels/squelette-site
python3 outils/mettre-a-jour.py --depuis ~/Projets/logiciels/squelette-site --pour-de-vrai --sans-essais
```

À blanc d'abord. L'outil remplace le moteur et **ne touche jamais `themes/`** :
il se contente de nommer les fichiers de thème qui ont divergé. Les porter **à
la main**, fichier par fichier — c'est le seul chemin, et l'oublier laisse le
site avec un défaut déjà corrigé ailleurs.

`--sans-essais` n'est pas du confort : sans lui l'outil relance
`tests/lancer.py` dans le site, ce qui prend une bonne minute.

**Un correctif qui compte remonte au squelette**, pas seulement ici. Quatre
défauts trouvés en montant ce site y sont remontés (1.9.0 à 1.9.5) : les blocs
de code lus comme du code en ligne, le sommaire jeté par `fiche.html`,
`mettre-a-jour.py` aveugle aux thèmes, et une image de fond réclamée par la
feuille mais absente du thème.

## Après toute modification

```bash
python3 site/generer.py && python3 outils/verifier.py
python3 tests/lancer.py
```

Le vérificateur doit dire « rien à signaler ». Le filet monte un site jetable
dans `/tmp` : il ne touche jamais celui-ci.

Puis, parce qu'un site se juge à ce qu'il affiche : **ouvrir la page**, dans
les deux livrées. Les deux défauts les plus coûteux de ce dépôt — le bandeau
invisible en sombre, le bouton Copier muet — n'étaient visibles ni dans le
Markdown, ni dans le CSS, ni dans la sortie du vérificateur.
