# Le Carnet du Verdier

Les pense-bêtes Linux de l'atelier, en public :
**<https://carnet.atelierduverdier.fr>**.

Pannes résolues, réglages système, et Linux du côté des machines — CNC,
FreeCAD, impression 3D. Ce qui est écrit ici a tourné sur une vraie machine ;
le reste n'y est pas.

**Bilingue français / anglais**, jumelé page à page. Fait avec le
[squelette de site](https://github.com/atelierduverdier/squelette-site),
moteur **1.14.0**. Un site de l'[Atelier du Verdier](https://atelierduverdier.fr).

## ⚠ Le site est MASQUÉ AUX MOTEURS

`moteurs: "non"` dans `site/config.yaml`. Le carnet est en ligne mais ne veut
pas encore être trouvé, le temps d'être rempli : `robots.txt` refuse tout,
chaque page porte `noindex, nofollow`, le plan du site n'est pas écrit. Le
générateur le rappelle à chaque passage.

**Le retirer est un geste, pas un oubli.** Quand le carnet sera prêt :

1. supprimer la ligne `moteurs: "non"` de `site/config.yaml` ;
2. `python3 outils/publier-pages.py` ;
3. publier la carte du portail et le lien, préparés sur la branche
   `carnet-a-annoncer` des dépôts `site` et `liens`.

## Écrire

```bash
python3 outils/atelier.py
```

L'atelier s'ouvre sur <http://localhost:8413> et sert aussi l'aperçu : rien
d'autre à lancer. On y écrit en Markdown, on dépose des images, on règle le
menu.

**Les trois gestes, dans cet ordre.** *Enregistrer* écrit le fichier.
*Régénérer* fabrique les pages. *Publier* les envoie. Sauter une étape ne
produit aucune erreur — seulement l'impression que rien ne marche.

Une fiche **naît en brouillon**, et un brouillon n'apparaît nulle part.

## La forme d'une fiche

Chaque fiche suit le même plan, parce que c'est celui qu'on veut quand on
arrive en panne à 23 h : **le symptôme** tel qu'il s'affiche, **ce que j'ai
cru** et pourquoi c'était faux, **la cause** avec de quoi la vérifier en une
commande, **le remède** en dernier.

La partie « ce que j'ai cru » n'est pas de la modestie : c'est ce qui manque
partout ailleurs, et c'est elle qui fait gagner du temps au lecteur qui est en
train de suivre la même fausse piste.

## Trois rubriques, deux langues

| français | anglais | ce qu'on y met |
|---|---|---|
| `fr/depannage/` | `en/troubleshooting/` | **Pannes** — ça ne marche pas, et voilà pourquoi |
| `fr/systeme/` | `en/system/` | **Système** — installer, régler, entretenir |
| `fr/atelier/` | `en/workshop/` | **À l'établi** — CNC, FreeCAD, impression 3D |

Le jumelage se fait sur la clé **`traduction:`** de l'en-tête : les deux
versions d'une même page portent la MÊME valeur (`glx-libdrm`, `pgrep`…). Les
slugs, eux, sont dans la langue de la page — c'est l'adresse que lit un moteur
et un humain.

Une page sans jumelle voit sa langue **grisée** dans le sélecteur, plutôt que
de renvoyer le lecteur à l'accueil sans prévenir. Écrire une fiche en français
seulement est donc parfaitement admis.

Le français fait foi : l'anglais en est la traduction, et la page d'accueil
anglaise le dit.

## Les blocs de code

Trois accents graves et le nom du langage :

    ```bash
    sudo pacman -Syu
    ```

Le bloc sort dans une boîte qui défile horizontalement — une ligne de commande
ne se coupe pas —, coiffée du nom du langage et d'un bouton **Copier**.

C'est le moteur qui pose la balise et le thème qui l'habille. Les deux ont dû
être corrigés pour ce site : le squelette lisait les trois accents graves comme
du code *en ligne*, et le bouton ne copiait rien sans son repli sur
`document.execCommand`. Corrections remontées au squelette en 1.9.0 et 1.9.3.

## Le thème

`themes/carnet/` — la charte de l'atelier (orange `#ff8a00`, ardoise `#2f3540`,
le chapeau melon) posée sur Verdure, dont il hérite. Il n'apporte que sa feuille
de style : gabarits, script et polices viennent du parent.

Ce qu'il ajoute et que Verdure n'a pas : **un mode sombre**. Le lecteur lit des
commandes, souvent la nuit, souvent à côté d'un terminal — lui envoyer une page
blanche en pleine figure est un choix, et le mauvais. Le site suit
`prefers-color-scheme`, le réglage déjà fait dans le système. Pas de bouton
pour basculer : il faudrait recopier le gabarit `base.html` dans ce thème, et
cette copie ne recevrait plus jamais un correctif du parent.

Les valeurs des couleurs viennent de `kit/verdier.css` du dépôt
[`atelierduverdier/site`](https://github.com/atelierduverdier/site), où elles
ont été **mesurées**. Si une couleur de la charte change là-bas, elle se
reporte ici — et nulle part ailleurs dans ce dépôt.

## Vérifier avant de publier

```bash
python3 site/generer.py && python3 outils/verifier.py
```

Le vérificateur distingue ce qui **bloque** — un lien mort, une image absente,
une déclinaison de `srcset` qui ne mène nulle part, deux pages au même
`<title>` — de ce qui se **dit** seulement. Un code de retour 1 fait demander
confirmation à la publication.

Et le filet du moteur, qui ne touche jamais ce site (il monte un site jetable
dans `/tmp`) :

```bash
python3 tests/lancer.py
```

## Mettre le moteur à jour

Ce site contient une **copie** du moteur, pas un lien. Une correction faite
dans le squelette ne l'atteint pas toute seule :

```bash
python3 outils/mettre-a-jour.py --depuis ~/Projets/logiciels/squelette-site
python3 outils/mettre-a-jour.py --depuis ~/Projets/logiciels/squelette-site --pour-de-vrai
```

À blanc d'abord, comme la publication. L'outil remplace le moteur et **ne
touche jamais `themes/`** — l'habillage appartient au site. Il se contente de
**nommer** les fichiers de thème qui ont divergé ; c'est à vous de porter le
correctif à la main, fichier par fichier.

## Publier

Le site est servi par **GitHub Pages**, comme les autres sites de l'atelier.
Le fichier `CNAME` à la racine du dossier publié fait vivre le sous-domaine :
le supprimer casse `carnet.atelierduverdier.fr`.
