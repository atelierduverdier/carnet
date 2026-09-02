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
    appendChild(c) { this.children.push(c); return c; },
    insertBefore(c) { this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); return c; },
    addEventListener() {}, removeEventListener() {},
    scrollIntoView() { this._vu = true; },
    focus() {}, select() {}, setSelectionRange() {},
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
  querySelectorAll: () => [],
  createElement: t => elt(t),
  addEventListener() {}, removeEventListener() {},
  hasFocus: () => true,
  execCommand: () => false,
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
rapport.tous_justes = releve.every(r => r.juste);
rapport.releve = releve;
if (process.env.SONDE) {
  rapport.sonde = {
    ecouteurs: Object.keys(fenetre._ecouteurs),
    liens_vus: nav.querySelectorAll('a[href^="#"]').length,
    href0: liens[0].getAttribute('href'),
    cible0: !!doc.getElementById('chapitre-un'),
    attrs0: liens[0]._attrs,
    scrollY: fenetre.scrollY,
  };
}
console.log(JSON.stringify(rapport));
