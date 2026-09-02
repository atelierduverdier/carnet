/* =====================================================================
   site.js — les comportements du site
   =====================================================================
   1. le menu qui se déplie sur téléphone ;
   2. la recherche, qui lit un index JSON engendré par site/generer.py ;
   3. la loupe sur les images, le fil de lecture, les apparitions ;
   4. les blocs de code, qu'on coiffe d'un bouton « Copier » ;
   5. le sommaire en colonne, et le chapitre où l'on en est.

   Rien d'autre : pas de bibliothèque, pas d'appel extérieur. Le site
   reste entièrement lisible si ce fichier ne charge pas.
   ===================================================================== */

(function () {
  'use strict';

  /* --- menu repliable ------------------------------------------------ */
  var bouton = document.querySelector('.bouton-menu');
  var menu = document.getElementById('menu-principal');
  if (bouton && menu) {
    bouton.addEventListener('click', function () {
      var ouvert = menu.classList.toggle('ouvert');
      bouton.setAttribute('aria-expanded', ouvert ? 'true' : 'false');
    });
  }

  /* --- sous-menus repliables au doigt --------------------------------
     Dépliés d'un bloc, les 32 liens du menu font 2074 px à parcourir sur
     un téléphone. Chaque rubrique se replie donc et s'ouvre au toucher.

     La classe `repliable` est posée ICI, par le script : sans lui, le CSS
     ne replie rien et le menu reste entièrement déplié, donc utilisable.
     C'est la seule façon de ne pas laisser un menu fermé sans moyen de
     l'ouvrir si le JavaScript ne charge pas. */
  var rubriques = document.querySelectorAll('.nav li > .intitule');
  Array.prototype.forEach.call(rubriques, function (titre) {
    var li = titre.parentElement;
    if (!li.querySelector(':scope > ul')) return;
    li.classList.add('repliable');
    titre.setAttribute('aria-expanded', 'false');
  });

  // la rubrique de la page courante s'ouvre d'emblée : on doit voir où l'on est
  var courant = document.querySelector('.nav a[aria-current="page"]');
  for (var p = courant && courant.parentElement.closest('li.repliable'); p;
       p = p.parentElement.closest('li.repliable')) {
    p.classList.add('deplie');
    p.querySelector(':scope > .intitule').setAttribute('aria-expanded', 'true');
  }

  var auDoigt = window.matchMedia('(max-width: 73.99rem)');

  function basculer(titre) {
    var li = titre.parentElement;
    var ouvert = li.classList.toggle('deplie');
    titre.setAttribute('aria-expanded', ouvert ? 'true' : 'false');
  }

  document.addEventListener('click', function (ev) {
    var titre = ev.target.closest('.nav li.repliable > .intitule');
    if (titre && auDoigt.matches) basculer(titre);
  });

  // au clavier : l'intitulé porte déjà un tabindex, il doit répondre
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Enter' && ev.key !== ' ') return;
    var titre = ev.target.closest && ev.target.closest('.nav li.repliable > .intitule');
    if (titre && auDoigt.matches) { ev.preventDefault(); basculer(titre); }
  });

  /* --- la bande du haut s'efface en descendant (petit écran) ---------
     Sur téléphone la bande fixe occupe 157 px, soit 19 % de l'écran, en
     permanence — cher sur des pages de plusieurs centaines de milliers
     de signes. Elle se replie donc quand on descend et revient dès qu'on
     remonte. Sur écran large elle ne bouge pas : 114 px sur 860, le jeu
     n'en vaut pas la chandelle.

     Pas de `requestAnimationFrame` ici : il ne se déclenche pas dans un
     onglet que le navigateur ne compose pas, et la bande resterait alors
     repliée pour de bon. Le travail fait à chaque défilement se réduit à
     trois lectures. */
  var bandeau = document.querySelector('.bandeau');
  if (bandeau) {
    var petitEcran = window.matchMedia('(max-width: 46rem)');
    var dernierY = window.scrollY;

    window.addEventListener('scroll', function () {
      var y = window.scrollY;
      var pas = y - dernierY;
      if (Math.abs(pas) < 6) return;              // le tremblement du doigt
      dernierY = y;

      if (!petitEcran.matches) { bandeau.classList.remove('repliee'); return; }
      // on ne la replie pas sous les doigts de qui s'en sert
      if (menu && menu.classList.contains('ouvert')) return;
      if (bandeau.contains(document.activeElement)) return;

      bandeau.classList.toggle('repliee', pas > 0 && y > bandeau.offsetHeight);
    }, { passive: true });

    // en passant sur grand écran, la bande doit reparaître
    petitEcran.addEventListener('change', function () {
      bandeau.classList.remove('repliee');
    });
  }

  /* --- agrandissement des images -------------------------------------
     Les couvertures sont des liens vers le fichier image. Sans JS, le
     clic l'ouvre nue dans l'onglet — le site reste utilisable. Avec JS,
     on l'affiche par-dessus la page, et on revient d'une touche Échap.
     -------------------------------------------------------------------- */
  var IMAGE = /\.(jpe?g|png|gif|webp|avif)$/i;
  var voile = null, declencheur = null;

  function fermer() {
    if (!voile) return;
    document.documentElement.classList.remove('sans-defilement');
    voile.setAttribute('hidden', '');
    if (declencheur) { declencheur.focus(); declencheur = null; }
  }

  function batir() {
    voile = document.createElement('div');
    voile.className = 'loupe';
    voile.setAttribute('role', 'dialog');
    voile.setAttribute('aria-modal', 'true');
    voile.setAttribute('hidden', '');
    voile.innerHTML =
      '<button type="button" class="loupe-fermer" aria-label="Fermer">×</button>' +
      '<figure><img alt=""><figcaption></figcaption></figure>';
    voile.addEventListener('click', function (ev) {
      // seul le fond ferme : un clic SUR l'image ne doit pas la faire fuir
      if (ev.target === voile || ev.target.closest('.loupe-fermer')) fermer();
    });
    document.body.appendChild(voile);
    return voile;
  }

  document.addEventListener('click', function (ev) {
    var a = ev.target.closest('main a[href]');
    if (!a || !IMAGE.test(a.getAttribute('href'))) return;
    if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button !== 0) return;  // ouvrir dans un onglet
    ev.preventDefault();

    var v = voile || batir();
    var img = v.querySelector('img');
    var source = a.querySelector('img');
    var legende = source ? (source.getAttribute('alt') || '') : '';
    img.src = a.getAttribute('href');
    img.alt = legende;
    v.querySelector('figcaption').textContent = legende;

    declencheur = a;
    v.removeAttribute('hidden');
    document.documentElement.classList.add('sans-defilement');
    // L'apparition est une animation CSS, jouée du seul fait que l'élément
    // cesse d'être `hidden`. Un `requestAnimationFrame` était plus élégant
    // mais ne se déclenche pas dans un onglet que le navigateur ne compose
    // pas : la loupe restait alors à opacité 0 tout en bloquant la page.
    v.querySelector('.loupe-fermer').focus();
  });

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && voile && !voile.hasAttribute('hidden')) fermer();
  });

  /* --- recherche ------------------------------------------------------ */
  /* Enfermée dans une fonction, et ce n'est pas une question de style.

     Sa garde `if (!champ || !liste) return;` était écrite au PREMIER
     NIVEAU de cette fonction anonyme : elle ne sortait donc pas de la
     recherche, elle TERMINAIT LE SCRIPT ENTIER. Sur une page sans champ
     de recherche, tout ce qui suit — la loupe, les apparitions, le fil
     de lecture, les boutons « Copier », le sommaire en colonne — ne
     s'exécutait jamais, et rien ne le disait.

     Le champ vient du gabarit de base, donc il est là sur toutes les
     pages du site livré : le défaut ne s'est jamais VU. Il attendait
     qu'un thème retire la recherche, ou qu'une page se rende sans
     bandeau. Trouvé le 02/09/2026 en exécutant le script hors du
     navigateur — le premier essai monté pour ça l'a sorti du premier
     coup, avant même de contrôler ce qu'il venait contrôler.

     Toutes les autres parties de ce fichier sont déjà des fonctions.
     Celle-ci était la dernière à ne pas l'être. */
  function recherche() {
    var champ = document.getElementById('champ-recherche');
    var liste = document.getElementById('resultats-recherche');
    if (!champ || !liste) return;

    var index = null, enCours = false;

    /* Comparer sans accents ni casse : « éveil » doit répondre à « eveil ».
       Les apostrophes, guillemets, tirets et espaces sont aussi ramenés à
       leur forme clavier : le site mélange « l’espérance » (typographique,
       venu de WordPress) et « l'espérance » (droite, tapée dans l'atelier),
       et la même phrase se trouvait ou non selon l'apostrophe. Chaque
       remplacement garde LA MÊME LONGUEUR : surligner() découpe le texte
       affiché avec les indices trouvés dans le texte aplati. */
    function aplatir(s) {
      return s.normalize('NFD').replace(/[̀-ͯ]/g, '')
        .replace(/[’‘]/g, "'").replace(/[«»“”„]/g, '"')
        .replace(/[–—]/g, '-').replace(/[\u00A0\u202F\u2009\n\r\t]/g, ' ')
        .toLowerCase();
    }

    function charger() {
      if (index || enCours) return Promise.resolve();
      enCours = true;
      return fetch(champ.dataset.index)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          index = d.map(function (e) {
            return { t: e.t, u: e.u, e: e.e, c: e.c, _t: aplatir(e.t), _e: aplatir(e.e || '') };
          });
        })
        .catch(function () { index = []; })
        .finally(function () { enCours = false; });
    }

    function surligner(texte, terme) {
      var i = aplatir(texte).indexOf(terme);
      if (i < 0) return document.createTextNode(texte);
      var frag = document.createDocumentFragment();
      frag.appendChild(document.createTextNode(texte.slice(0, i)));
      var m = document.createElement('mark');
      m.textContent = texte.slice(i, i + terme.length);
      frag.appendChild(m);
      frag.appendChild(document.createTextNode(texte.slice(i + terme.length)));
      return frag;
    }

    /* [début, fin] de la première suite des mots — dans l'ordre et presque
       collés (12 caractères d'écart au plus) — ou null. « Seul les » doit
       trouver « Seuls les personnes » : la phrase exacte échoue pour une
       lettre, mais les mots sont là, dans l'ordre, à deux caractères près.
       Exiger l'ordre ET la quasi-adjacence est ce qui évite le bruit — un
       simple voisinage ramenait 32 pages, « seul » vivant dans
       « seulement » et « les » traînant partout. */
    function suiteDeMots(texte, mots) {
      var i = texte.indexOf(mots[0]);
      while (i >= 0) {
        var pos = i + mots[0].length, ok = true;
        for (var k = 1; k < mots.length; k++) {
          var j = texte.indexOf(mots[k], pos);
          if (j < 0 || j > pos + 12) { ok = false; break; }
          pos = j + mots[k].length;
        }
        if (ok) return [i, pos];
        i = texte.indexOf(mots[0], i + 1);
      }
      return null;
    }

    function chercher() {
      var q = aplatir(champ.value.trim()).replace(/\s+/g, ' ');
      liste.textContent = '';
      if (q.length < 2 || !index) return;

      var mots = q.split(' ').filter(function (m) { return m.length >= 2; });

      var titres = [], corps = [], approchees = [];
      for (var i = 0; i < index.length
           && titres.length + corps.length + approchees.length < 60; i++) {
        var e = index[i];
        if (e._t.indexOf(q) >= 0) titres.push(e);
        else if (e._e.indexOf(q) >= 0) corps.push(e);
        else if (mots.length > 1 && suiteDeMots(e._e, mots)) approchees.push(e);
      }
      // la phrase exacte d'abord, la suite approchée ensuite
      var trouves = titres.concat(corps, approchees).slice(0, 12);

      if (!trouves.length) {
        var vide = document.createElement('li');
        vide.className = 'ou';
        vide.style.padding = '.6em .7em';
        vide.textContent = champ.dataset.rien || 'Aucun résultat';
        liste.appendChild(vide);
        return;
      }

      trouves.forEach(function (e) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = e.u;
        a.appendChild(surligner(e.t, q));
        if (e.c) {
          var ou = document.createElement('span');
          ou.className = 'ou';
          ou.textContent = e.c;
          a.appendChild(ou);
        }
        /* Trouvé dans le texte : montrer le bout de phrase autour du terme.
           Sans lui, chercher une phrase renvoyait cinq « Témoignage du … »
           identiques, sans rien pour choisir. Pour une suite approchée, la
           tranche réellement trouvée (« Seuls les ») sert de terme : c'est
           elle qui est surlignée, pas la saisie qui a échoué. */
        var terme = q, j = e._e.indexOf(q);
        if (j < 0 && mots.length > 1) {
          var bornes = suiteDeMots(e._e, mots);
          if (bornes) { j = bornes[0]; terme = e._e.slice(bornes[0], bornes[1]); }
        }
        if (j >= 0 && e._t.indexOf(q) < 0) {
          var d = Math.max(0, j - 45);
          var morceau = (d ? '…' : '') + e.e.slice(d, j + terme.length + 70) + '…';
          var ex = document.createElement('span');
          ex.className = 'extrait';
          ex.appendChild(surligner(morceau, terme));
          a.appendChild(ex);
        }
        li.appendChild(a);
        liste.appendChild(li);
      });
    }

    champ.addEventListener('focus', charger);
    var minuteur;
    champ.addEventListener('input', function () {
      clearTimeout(minuteur);
      minuteur = setTimeout(function () { charger().then(chercher); }, 120);
    });
    champ.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { champ.value = ''; liste.textContent = ''; champ.blur(); }
      if (ev.key === 'ArrowDown') {
        var p = liste.querySelector('a');
        if (p) { ev.preventDefault(); p.focus(); }
      }
    });
    liste.addEventListener('keydown', function (ev) {
      var liens = Array.prototype.slice.call(liste.querySelectorAll('a'));
      var i = liens.indexOf(document.activeElement);
      if (ev.key === 'ArrowDown' && i < liens.length - 1) { ev.preventDefault(); liens[i + 1].focus(); }
      if (ev.key === 'ArrowUp') { ev.preventDefault(); (i > 0 ? liens[i - 1] : champ).focus(); }
      if (ev.key === 'Escape') { liste.textContent = ''; champ.focus(); }
    });
    document.addEventListener('click', function (ev) {
      if (!ev.target.closest('.recherche')) liste.textContent = '';
    });
  }
  recherche();

  /* --- déroulants qui sortiraient de l'écran --------------------------
     Un déroulant s'ouvre sous sa rubrique, aligné à gauche sur elle, et
     mesure au moins 15 rem. Une rubrique posée à droite de l'écran le
     fait donc dépasser : à 1024 px, en italien, « Testimonianze » se
     trouve à 788 px et son panneau finissait à 1028 pour une fenêtre de
     1005 — la page gagnait une barre de défilement horizontale.

     Le français n'en souffrait pas, ses intitulés tombant ailleurs :
     c'est la LARGEUR DES MOTS qui décide, donc rien qu'une feuille de
     style puisse prévoir. On mesure et on bascule vers la gauche.

     `visibility: hidden` conserve la mise en page : le panneau se mesure
     sans être montré. */
  var barreMenu = document.querySelector('.nav > .enveloppe > ul');
  if (barreMenu) {
    var replacerDeroulants = function () {
      var large = document.documentElement.clientWidth;
      Array.prototype.forEach.call(barreMenu.children, function (li) {
        var sm = li.querySelector(':scope > ul');
        if (!sm) return;
        li.classList.remove('vers-la-gauche');
        var b = li.getBoundingClientRect();
        if (b.left + sm.offsetWidth > large - 8) li.classList.add('vers-la-gauche');
      });
    };
    /* Mesurer une fois ne suffit pas : au moment où le script s'exécute
       les polices ne sont pas encore là, les intitulés n'ont pas leur
       largeur définitive, et la barre n'a pas encore décidé si elle
       passe sur deux rangées. On remesure quand la page est complète et
       quand les polices arrivent — c'est justement ce décalage qui
       laissait « Testimonianze » déborder de 23 px. */
    replacerDeroulants();
    window.addEventListener('load', replacerDeroulants);
    window.addEventListener('resize', replacerDeroulants);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(replacerDeroulants);
    }
  }

  /* ---- l'image d'ouverture dérive plus lentement que la page ----------
     Ce décalage est ce qui donne la profondeur : l'œil lit un plan
     lointain. Trois précautions le rendent inoffensif.

     On respecte « prefers-reduced-motion », et l'on ne s'accroche même pas
     au défilement dans ce cas : ni calcul, ni écouteur.

     On passe par requestAnimationFrame. Sans lui, l'événement de
     défilement se déclenche des dizaines de fois par image et l'on écrit
     dans le style à chaque fois : le navigateur recalcule la mise en page
     autant de fois, et le défilement devient saccadé sur un téléphone.

     Et l'on s'arrête dès que l'image a quitté l'écran — continuer à
     calculer pour ce que personne ne voit ne sert personne. */
  function derivePhotoOuverture() {
    var cadre = document.querySelector('.hero');
    var image = cadre && cadre.querySelector('img');
    if (!image) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    /* Troisième version. La 1re attendait que le cadre sorte de l'écran
       pour commencer — invisible par construction. La 2e translatait dès
       le premier pixel, 14 px à 300 px de défilement — invisible par
       amplitude : l'œil ne détache pas un glissement de 5 % du mouvement
       de la page. D'où le ZOOM, que l'œil perçoit immédiatement, doublé
       d'un glissement qui reste sous la réserve que le zoom crée :
       glissement 0.07 < 0.18/2 = réserve, jamais de bord vide. */
    var ZOOM = 0.18;              /* grossissement à la sortie du cadre */
    var GLISSE = 0.07;            /* translation, en fraction de la hauteur */
    var enAttente = false;
    /* La position du cadre dans le DOCUMENT, prise une fois : c'est elle
       qui permet de partir de zéro dès que la page bouge. */
    var origine = cadre.getBoundingClientRect().top + window.scrollY;

    function poser() {
      enAttente = false;
      var r = cadre.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight) return;
      /* 0 page en haut, 1 quand le cadre a entièrement quitté l'écran. */
      var course = origine + r.height;
      var avance = Math.min(1, Math.max(0, window.scrollY / (course || 1)));
      image.style.setProperty('--derive-z', (1 + avance * ZOOM).toFixed(4));
      image.style.setProperty('--derive-y',
                              (avance * GLISSE * r.height).toFixed(1) + 'px');
    }

    window.addEventListener('scroll', function () {
      if (!enAttente) { enAttente = true; requestAnimationFrame(poser); }
    }, { passive: true });
    window.addEventListener('resize', function () {
      origine = cadre.getBoundingClientRect().top + window.scrollY;
      poser();
    }, { passive: true });
    poser();
  }
  derivePhotoOuverture();

  /* ---- l'ombre de la bande, et l'entrée des cartes --------------------
     Deux effets, une même règle : le script AJOUTE — jamais il ne
     retranche. Sans lui, la bande n'a pas d'ombre et les cartes sont
     simplement là : le site complet, moins la politesse.

     PAS d'IntersectionObserver, et c'est un choix payé : à l'essai,
     l'observateur n'a pas tiré et les 24 cartes de la page restaient
     invisibles — le contenu emporté par l'ornement. La révélation passe
     donc par le même contrôle au défilement que la dérive de la photo :
     déterministe, testable, et le pire cas d'une panne est une carte SANS
     effet, jamais une carte absente. */
  function profondeurEtApparitions() {
    var bande = document.querySelector('.bandeau');
    if (bande) {
      var poserOmbre = function () {
        bande.classList.toggle('detachee', window.scrollY > 4);
      };
      window.addEventListener('scroll', poserOmbre, { passive: true });
      poserOmbre();
    }

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    /* Une carte déjà visible au chargement n'est PAS masquée puis
       révélée : le lecteur arrivé par une ancre verrait la page
       clignoter. Seules celles sous la ligne de flottaison entrent
       dans la liste d'attente. */
    var enAttente = [];
    document.querySelectorAll('.fiches > li').forEach(function (carte) {
      if (carte.getBoundingClientRect().top < window.innerHeight * .92) return;
      carte.classList.add('a-apparaitre');
      enAttente.push(carte);
    });
    if (!enAttente.length) return;

    var demande = false;
    function reveler() {
      demande = false;
      var seuil = window.innerHeight * .96;
      var rang = 0;
      /* On parcourt à rebours pour retirer sans décaler. Les cartes d'une
         même fournée se décalent de 70 ms : c'est le décalage qui fait la
         mise en place, pas le fondu seul. */
      for (var i = 0; i < enAttente.length; ) {
        var carte = enAttente[i];
        if (carte.getBoundingClientRect().top < seuil) {
          carte.style.setProperty('--cadence', (rang * 70) + 'ms');
          rang += 1;
          carte.classList.add('apparu');
          enAttente.splice(i, 1);
        } else {
          i += 1;
        }
      }
      if (!enAttente.length) {
        window.removeEventListener('scroll', surDefilement);
      }
    }
    function surDefilement() {
      if (!demande) { demande = true; requestAnimationFrame(reveler); }
    }
    window.addEventListener('scroll', surDefilement, { passive: true });
    window.addEventListener('resize', surDefilement, { passive: true });
    reveler();
  }
  profondeurEtApparitions();

  /* ---- le fil de lecture ----------------------------------------------
     Seulement quand la page est vraiment longue : en dessous de deux
     écrans et demi de défilement, le trait dirait « vous avancez » sur un
     trajet qu'un pouce couvre en un geste. Même mécanique au défilement
     que le reste — et pas de garde « reduced motion » : le trait suit la
     main, il ne bouge jamais seul. */
  function filDeLecture() {
    var bande = document.querySelector('.bandeau');
    var article = document.querySelector('article.colonne');
    if (!bande || !article) return;

    var course = document.documentElement.scrollHeight - window.innerHeight;
    if (course < window.innerHeight * 2.5) return;

    var fil = document.createElement('div');
    fil.className = 'fil-lecture';
    fil.setAttribute('aria-hidden', 'true');
    bande.appendChild(fil);

    var demande = false;
    function poser() {
      demande = false;
      var c = document.documentElement.scrollHeight - window.innerHeight;
      var avance = c > 0 ? Math.min(1, window.scrollY / c) : 0;
      fil.style.transform = 'scaleX(' + avance.toFixed(4) + ')';
    }
    window.addEventListener('scroll', function () {
      if (!demande) { demande = true; requestAnimationFrame(poser); }
    }, { passive: true });
    window.addEventListener('resize', poser, { passive: true });
    poser();
  }
  filDeLecture();

  /* --- les blocs de code se laissent copier ---------------------------
     `fenced_code` pose <pre><code class="language-bash">. On enveloppe
     chaque bloc et on le coiffe d'une barre : le langage à gauche, le
     bouton à droite.

     POURQUOI UN BOUTON. Une commande est faite pour être collée dans un
     terminal. La sélectionner à la souris dans un bloc qui défile, c'est
     l'occasion exacte d'emporter un espace de trop ou d'oublier le
     dernier caractère — et une commande fausse d'un signe ne dit pas
     qu'elle est fausse, elle fait autre chose.

     DEUX MÉCANISMES, ET IL EN FAUT DEUX. L'API `navigator.clipboard`
     exige une ORIGINE SÛRE (https ou localhost) — et cela ne suffit même
     pas : elle est aussi refusée quand le document n'a pas le focus, et
     dans les cadres où la politique de permissions ne l'accorde pas.
     Mesuré : bouton cliqué pour de vrai, document focalisé, page servie
     depuis localhost — `writeText` rejette quand même, et le bouton
     affichait « Échec » sans autre recours.

     D'où le repli sur `document.execCommand('copy')`, l'ancienne
     méthode : un champ de texte temporaire, une sélection, une commande
     d'édition. Elle est marquée obsolète et implémentée partout, sans
     permission ni origine sûre. Elle passe là où l'API moderne renonce.

     Si les DEUX manquent, le bouton n'est pas posé du tout — plutôt
     qu'un bouton mort. Le bloc reste lu, lisible et sélectionnable à la
     main : c'était déjà le cas avant ce script. */

  /* Le repli. Trois pièges tiennent dans ces dix lignes :
     - le champ ne doit être ni `display:none` ni `visibility:hidden` —
       un champ invisible ne se sélectionne pas, et la copie échoue sans
       rien dire. On le sort de l'écran, ce qui n'est pas pareil ;
     - `setSelectionRange` en plus de `select()`, faute de quoi iOS ne
       sélectionne rien ;
     - `position: fixed` plutôt qu'`absolute` : sinon l'ajout du champ
       fait défiler la page jusqu'à lui, et le lecteur perd sa place. */
  function copierALAncienne(texte) {
    var zone = document.createElement('textarea');
    zone.value = texte;
    zone.setAttribute('readonly', '');
    zone.setAttribute('aria-hidden', 'true');
    zone.style.position = 'fixed';
    zone.style.top = '0';
    zone.style.left = '-9999px';
    document.body.appendChild(zone);
    zone.select();
    try { zone.setSelectionRange(0, zone.value.length); } catch (e) { /* vieux moteurs */ }
    var fait = false;
    try { fait = document.execCommand('copy'); } catch (e) { fait = false; }
    document.body.removeChild(zone);
    return fait;
  }

  /* L'API d'abord, le repli si elle renonce. Rend une promesse dans les
     deux cas, pour que l'appelant n'ait qu'un seul chemin. */
  function copier(texte) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(texte).catch(function () {
        return copierALAncienne(texte) ? undefined : Promise.reject();
      });
    }
    return copierALAncienne(texte) ? Promise.resolve() : Promise.reject();
  }
  function blocsDeCode() {
    var blocs = document.querySelectorAll('article.colonne pre > code');
    if (!blocs.length) return;

    var copiable = !!(navigator.clipboard && navigator.clipboard.writeText)
                || typeof document.execCommand === 'function';

    Array.prototype.forEach.call(blocs, function (code) {
      var pre = code.parentNode;
      if (!pre.parentNode || pre.parentNode.classList.contains('bloc-code')) return;

      /* Le nom du langage vient de la classe posée par le générateur.
         Un bloc sans langage — trois accents graves nus — n'en affiche
         pas : inventer « text » n'apprendrait rien à personne. */
      var langue = '';
      var m = /(?:^|\s)language-([\w+#-]+)/.exec(code.className || '');
      if (m) langue = m[1];

      if (!langue && !copiable) return;   // rien à ajouter : on laisse le <pre>

      var enveloppe = document.createElement('div');
      enveloppe.className = 'bloc-code';
      pre.parentNode.insertBefore(enveloppe, pre);

      var barre = document.createElement('div');
      barre.className = 'bloc-code-barre';

      var nom = document.createElement('span');
      nom.className = 'bloc-code-langue';
      nom.textContent = langue;
      barre.appendChild(nom);

      if (copiable) {
        var bouton = document.createElement('button');
        bouton.type = 'button';
        bouton.className = 'bloc-code-copier';
        bouton.textContent = 'Copier';
        /* Le libellé change au clic. Sans `aria-live`, un lecteur d'écran
           ne dirait rien : l'utilisateur ne saurait pas si ça a marché. */
        bouton.setAttribute('aria-live', 'polite');
        bouton.addEventListener('click', function () {
          copier(code.textContent).then(function () { dire('Copié'); },
                                        function () { dire('Échec'); });
        });
        var rendezvous = null;
        function dire(quoi) {
          bouton.textContent = quoi;
          bouton.setAttribute('data-fait', 'oui');
          clearTimeout(rendezvous);
          rendezvous = setTimeout(function () {
            bouton.textContent = 'Copier';
            bouton.removeAttribute('data-fait');
          }, 1600);
        }
        barre.appendChild(bouton);
      }

      enveloppe.appendChild(barre);
      enveloppe.appendChild(pre);

      /* Un bloc qui défile doit être atteignable au clavier, sinon ce
         qui dépasse à droite est inaccessible sans souris. On ne le pose
         QUE s'il défile vraiment : un tabstop de plus sur chaque bloc
         court alourdirait la page pour rien. */
      if (pre.scrollWidth > pre.clientWidth) {
        pre.tabIndex = 0;
        pre.setAttribute('role', 'region');
        pre.setAttribute('aria-label', 'Bloc de code' + (langue ? ' ' + langue : ''));
      }
    });
  }
  blocsDeCode();

  /* --- le sommaire en colonne, et « vous êtes ici » --------------------
     `sommaire: "cote"` engendre <nav class="sommaire sommaire-cote">
     contenant un <details open>. Deux choses ici, et la seconde est celle
     qui compte.

     1. LE TIROIR SUIT LA LARGEUR. Au-dessus de 76 rem il y a la place
        d'une colonne : le sommaire reste déplié et collant. En dessous,
        on le referme — 27 entrées font 877 px, soit l'écran entier d'un
        téléphone avant la première phrase. L'attribut `open` est écrit
        dans le HTML : sans ce script, le sommaire est déplié partout,
        donc entièrement lisible. Le confort ne conditionne pas le contenu.

     2. LE CHAPITRE EN COURS. Vingt-sept liens identiques disent où l'on
        peut aller, pas où l'on est — et sur une page de 158 écrans (celle
        qui a motivé tout ceci), savoir où l'on est vaut au moins autant.
        On marque l'entrée courante avec `aria-current`, pas avec une
        classe : l'information est alors DANS le HTML, donc annoncée par
        un lecteur d'écran, et pas seulement peinte. */
  function sommaireEnColonne() {
    var nav = document.querySelector('.sommaire-cote');
    if (!nav) return;
    var tiroir = nav.querySelector('details');
    var liens = [].slice.call(nav.querySelectorAll('a[href^="#"]'));
    if (!liens.length) return;

    /* --- 1. le tiroir --- */
    if (tiroir) {
      var large = window.matchMedia('(min-width: 76rem)');
      function accorder(mq) { tiroir.open = mq.matches; }
      accorder(large);
      /* `addEventListener` sur une MediaQueryList date de Safari 14 ;
         `addListener`, déprécié, est le repli des moteurs plus anciens. */
      if (large.addEventListener) large.addEventListener('change', accorder);
      else if (large.addListener) large.addListener(accorder);
    }

    /* --- 2. le chapitre en cours ---
       On tient une table des hauteurs de titre, et on cherche le dernier
       titre passé au-dessus de la « ligne de lecture », posée au premier
       cinquième de l'écran : c'est là que l'œil lit, et un titre encore au
       bas de l'écran n'est pas celui qu'on est en train de lire.

       POURQUOI PAS UN IntersectionObserver, qui semble fait pour ça : il
       ne signale que les ENTRÉES et les SORTIES du cadre. Entre deux
       titres distants de 7 écrans — la mesure réelle de la page qui a
       motivé cette fonction — il ne se passe rien, et il faut de toute
       façon retomber sur un calcul de position pour savoir dans quel
       chapitre on se trouve. Autant ne faire que ce calcul : une seule
       logique au lieu de deux, et on peut la vérifier à la règle.

       Les hauteurs sont mesurées UNE FOIS, pas à chaque image : lire 27
       rectangles à chaque défilement force le navigateur à recalculer la
       mise en page soixante fois par seconde. On remesure quand la page
       change de forme — redimensionnement, et chargement complet, les
       images pouvant encore déplacer ce qui les suit. */
    /* La table qui relie un titre de la page à son entrée du sommaire.
       ELLE AVAIT DISPARU. Une réécriture de ce bloc a emporté sa
       construction en laissant les deux noms utilisés plus bas : en mode
       strict, `mesurer()` levait une ReferenceError au démarrage et la
       fonction entière mourait — sommaire figé, aucun repère, aucune
       erreur visible dans la page. Le filet Python ne pouvait pas le
       voir : il ne contrôle que le HTML offert au script. */
    var parAncre = {};
    var titres = [];
    liens.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute('href').slice(1));
      var cible = document.getElementById(id);
      if (!cible) return;          // un titre a pu être renommé depuis
      parAncre[id] = a;
      titres.push(cible);
    });
    if (!titres.length) return;

    var reperes = [];
    function mesurer() {
      reperes = titres.map(function (h) {
        return { haut: h.getBoundingClientRect().top + window.scrollY,
                 lien: parAncre[h.id] };
      });
    }

    var courant = null;
    function marquer(a) {
      if (a === courant) return;
      if (courant) courant.removeAttribute('aria-current');
      courant = a || null;
      if (!courant) return;
      courant.setAttribute('aria-current', 'true');
      /* La liste peut défiler dans sa colonne : on y ramène l'entrée
         courante quand elle en sort. `nearest` — jamais `center` :
         centrer ferait sauter la liste à chaque titre franchi, un
         mouvement que personne n'a demandé pendant qu'on lit. */
      if (nav.scrollHeight > nav.clientHeight) {
        var r = courant.getBoundingClientRect(), n = nav.getBoundingClientRect();
        if (r.top < n.top || r.bottom > n.bottom) {
          courant.scrollIntoView({ block: 'nearest' });
        }
      }
    }

    function situer() {
      var ligne = window.scrollY + window.innerHeight * 0.2;
      var trouve = null;
      for (var i = 0; i < reperes.length; i++) {
        if (reperes[i].haut > ligne) break;
        trouve = reperes[i].lien;
      }
      marquer(trouve);
    }

    var demande = false;
    function auDefilement() {
      if (demande) return;
      demande = true;
      requestAnimationFrame(function () { demande = false; situer(); });
    }

    mesurer();
    situer();
    window.addEventListener('scroll', auDefilement, { passive: true });
    window.addEventListener('resize', function () { mesurer(); situer(); },
                            { passive: true });
    window.addEventListener('load', function () { mesurer(); situer(); });
  }
  sommaireEnColonne();
})();
