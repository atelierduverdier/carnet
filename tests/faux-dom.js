// =========================================================================
// faux-dom.js — de quoi EXÉCUTER site.js hors d'un navigateur
// =========================================================================
// POURQUOI CE FICHIER EXISTE. Le 02/09/2026, une réécriture de
// `sommaireEnColonne()` a emporté la construction de deux tables en
// laissant leurs noms utilisés dix lignes plus bas. En mode strict, cela
// lève une ReferenceError au démarrage : la fonction entière meurt, le
// sommaire se fige, aucun repère n'apparaît. La page se rend normalement,
// le vérificateur ne bronche pas, tous les essais Python passent au vert —
// et le défaut est parti en ligne, dans deux versions.
//
// Un contrôle statique en Python a été tenté puis jeté : sans lexeur
// JavaScript il rendait quatre-vingts faux positifs.
//
// CE QUE CE FICHIER N'EST PAS. Ni un navigateur, ni jsdom. Il monte le
// STRICT nécessaire pour que `sommaireEnColonne()` s'exécute jusqu'au
// bout ; toutes les autres fonctions du script trouvent `null` à leur
// première requête et sortent par leur garde, ce qui est exactement ce
// qu'elles font sur une page qui ne les concerne pas.
//
// Sans dépendance : `vm` est livré avec Node. Rien à installer, rien qui
// se périme. C'est la règle de la maison, et elle vaut aussi pour les
// essais — qui voyagent dans chaque site né du squelette.
//
// UTILISATION : node tests/faux-dom.js <chemin/vers/site.js>
// Sortie : une ligne JSON. `ok:false` porte la faute.
// =========================================================================

'use strict';
const fs = require('fs');
const vm = require('vm');

const chemin = process.argv[2];
if (!chemin) { console.log(JSON.stringify({ ok: false, faute: 'chemin manquant' })); process.exit(0); }

// --- la page d'essai -----------------------------------------------------
// Six chapitres, espacés de 3000 px : l'ordre de grandeur réel d'une page
// longue, où deux titres sont à plusieurs écrans l'un de l'autre.
const ESPACEMENT = 3000;
const CHAPITRES = ['un', 'deux', 'trois', 'quatre', 'cinq', 'six'];

function elt(tag, attrs = {}) {
  const e = {
    tagName: tag.toUpperCase(),
    _attrs: Object.assign({}, attrs),
    id: attrs.id || '',
    className: attrs.class || '',
    style: {},
    children: [],
    textContent: attrs.textContent || '',
    open: 'open' in attrs,
    scrollHeight: 0, clientHeight: 0, scrollWidth: 0, clientWidth: 0,
    tabIndex: -1,
    _haut: attrs._haut || 0,
    getAttribute(n) { return n in this._attrs ? String(this._attrs[n]) : null; },
    setAttribute(n, v) { this._attrs[n] = v; if (n === 'class') this.className = v; },
    removeAttribute(n) { delete this._attrs[n]; },
    hasAttribute(n) { return n in this._attrs; },
    // `parentNode` DOIT suivre : le script remonte l'arbre pour savoir s'il
    // a déjà enveloppé un bloc (`pre.parentNode.classList.contains(...)`).
    // Sans cela il ré-enveloppait sans fin — et l'essai croyait qu'il
    // n'avait rien fait.
    appendChild(c) { this.children.push(c); c.parentNode = this; return c; },
    insertBefore(c) { this.children.push(c); c.parentNode = this; return c; },
    removeChild(c) {
      this.children = this.children.filter(x => x !== c);
      if (c.parentNode === this) c.parentNode = null;
      return c;
    },
    _ecouteurs: null,
    addEventListener(type, f) {
      (this._ecouteurs = this._ecouteurs || {});
      (this._ecouteurs[type] = this._ecouteurs[type] || []).push(f);
    },
    removeEventListener() {},
    declencher(type) {
      ((this._ecouteurs || {})[type] || []).forEach(f => f({ type }));
    },
    scrollIntoView() { this._vu = true; },
    focus() {}, setSelectionRange() {},
    select() { doc._selection = this.value; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getBoundingClientRect() {
      return { top: this._haut - fenetre.scrollY, bottom: this._haut - fenetre.scrollY + 40,
               left: 0, right: 200, width: 200, height: 40, x: 0, y: this._haut - fenetre.scrollY };
    },
    get classList() {
      const self = this;
      return {
        contains: c => self.className.split(/\s+/).includes(c),
        add(c) { if (!this.contains(c)) self.className = (self.className + ' ' + c).trim(); },
        remove(c) { self.className = self.className.split(/\s+/).filter(x => x !== c).join(' '); },
        toggle(c) { this.contains(c) ? this.remove(c) : this.add(c); return this.contains(c); },
      };
    },
  };
  return e;
}

const titres = CHAPITRES.map((n, i) =>
  elt('h2', { id: 'chapitre-' + n, _haut: 1200 + i * ESPACEMENT, textContent: 'Chapitre ' + n }));

const liens = CHAPITRES.map(n =>
  elt('a', { href: '#chapitre-' + n, textContent: 'Chapitre ' + n }));

const details = elt('details', { open: true });
const nav = elt('nav', { class: 'sommaire sommaire-cote' });
nav.children.push(details);
nav.querySelector = s => (s === 'details' ? details : null);
nav.querySelectorAll = s => (s.startsWith('a[href') || s === 'a' ? liens : []);

const parId = {};
titres.forEach(h => { parId[h.id] = h; });

// --- un bloc de code, pour éprouver le bouton « Copier » ----------------
// C'est la fonction que je n'avais jamais pu contrôler : dans le volet
// d'aperçu, l'API du presse-papiers est refusée, et la seule preuve qu'elle
// marchait fut une notification du système. Ici on la tient.
const COMMANDE = 'sudo pacman -Syu\necho ok\n';
const bloc = elt('code', { class: 'language-bash', textContent: COMMANDE });
const pre = elt('pre');
const article = elt('article', { class: 'colonne' });
pre.children.push(bloc); bloc.parentNode = pre;
article.children.push(pre); pre.parentNode = article;
let presse_papiers = null;

const fenetre = {
  scrollY: 0, scrollX: 0, innerWidth: 1440, innerHeight: 900,
  _ecouteurs: {},
  addEventListener(t, f) { (this._ecouteurs[t] = this._ecouteurs[t] || []).push(f); },
  removeEventListener() {},
  dispatchEvent(e) { (this._ecouteurs[e.type] || []).forEach(f => f(e)); return true; },
  scrollTo(x, y) { this.scrollY = y; this.dispatchEvent({ type: 'scroll' }); },
  matchMedia(q) {
    return { media: q, matches: true, addEventListener() {}, addListener() {},
             removeEventListener() {}, removeListener() {} };
  },
  getComputedStyle() { return { getPropertyValue: () => '', position: 'sticky' }; },
  requestAnimationFrame(f) { f(0); return 1; },
  cancelAnimationFrame() {},
  setTimeout(f) { return 0; },          // on ne veut pas des minuteries ici
  clearTimeout() {},
  navigator: { clipboard: null },
  performance: { now: () => 0 },
  Set, Map, Math, JSON, Date, Array, Object, String, Number, Boolean, RegExp, Error,
  decodeURIComponent, encodeURIComponent, parseInt, parseFloat, isNaN,
  console,
};

const doc = {
  documentElement: elt('html'),
  body: elt('body'),
  hidden: false, visibilityState: 'visible',
  getElementById: id => parId[id] || null,
  querySelector: s => (s === '.sommaire-cote' ? nav : null),
  querySelectorAll: s => (s === 'article.colonne pre > code' ? [bloc] : []),
  createElement: t => elt(t),
  addEventListener() {}, removeEventListener() {},
  hasFocus: () => true,
  // Pas d'API moderne (navigator.clipboard vaut null) : le script doit
  // retomber sur l'ancienne méthode. C'est justement ce repli qui a été
  // ajouté après avoir mesuré que `writeText` renonce même sur localhost.
  execCommand: cmd => {
    if (cmd === 'copy') { presse_papiers = doc._selection; return true; }
    return false;
  },
  _selection: null,
};

const bac = Object.assign({}, fenetre, {
  window: fenetre, document: doc, navigator: fenetre.navigator,
  globalThis: null,
});
bac.globalThis = bac;
fenetre.document = doc;

// --- on charge le script -------------------------------------------------
const code = fs.readFileSync(chemin, 'utf8');
const rapport = { ok: true, fichier: chemin };
try {
  vm.createContext(bac);
  vm.runInContext(code, bac, { filename: chemin });
} catch (e) {
  rapport.ok = false;
  rapport.faute = e && e.constructor ? e.constructor.name : 'Erreur';
  rapport.message = String(e && e.message || e);
  console.log(JSON.stringify(rapport));
  process.exit(0);
}

// --- et on l'exerce ------------------------------------------------------
// Le comportement, pas seulement le chargement : c'est tout l'intérêt.
function marque() {
  const a = liens.find(l => l.getAttribute('aria-current'));
  return a ? a.getAttribute('href') : null;
}
const releve = [];
// Au MILIEU de chaque chapitre : le cas que le calcul doit traiter, et
// celui qu'un IntersectionObserver traite mal.
titres.forEach((h, i) => {
  fenetre.scrollTo(0, h._haut + ESPACEMENT / 2 - fenetre.innerHeight * 0.2);
  releve.push({ chapitre: h.id, marque: marque(), juste: marque() === '#' + h.id });
});
// Avant le premier titre : rien ne doit être marqué.
fenetre.scrollTo(0, 0);
rapport.rien_avant_le_premier_titre = marque() === null;

// --- le bouton « Copier » ----------------------------------------------
const enveloppe = pre.parentNode;
const barre = (enveloppe.children || []).find(c => c.className === 'bloc-code-barre');
const bouton = barre && (barre.children || []).find(c => c.className === 'bloc-code-copier');
rapport.bloc_enveloppe = !!enveloppe && enveloppe.className === 'bloc-code';
rapport.langue_affichee = barre ? (barre.children[0] || {}).textContent : null;
rapport.bouton_pose = !!bouton;
rapport.tous_justes = releve.every(r => r.juste);
rapport.releve = releve;

// LE CLIC EST ASYNCHRONE. `copier()` rend une promesse et c'est son `.then`
// qui change le libellé : lu tout de suite, le bouton dit encore
// « Copier ». On laisse donc passer les micro-tâches avant de conclure —
// sinon l'essai rapporte un échec qui n'existe pas, ce qui est pire que pas
// d'essai du tout.
if (bouton) {
  bouton.declencher('click');
  Promise.resolve().then(() => {
    rapport.presse_papiers = presse_papiers;
    rapport.copie_juste = presse_papiers === COMMANDE;
    rapport.libelle_apres_clic = bouton.textContent;
    dire_le_rapport();
  });
} else {
  dire_le_rapport();
}
function dire_le_rapport() {
  if (process.env.SONDE) {
    rapport.sonde = {
      ecouteurs: Object.keys(fenetre._ecouteurs),
      liens_vus: nav.querySelectorAll('a[href^="#"]').length,
      scrollY: fenetre.scrollY,
    };
  }
  console.log(JSON.stringify(rapport));
}
