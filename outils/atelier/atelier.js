/* =====================================================================
   atelier.js — la logique de l'interface locale
   =====================================================================
   Sans bibliothèque : l'atelier doit démarrer avec un seul « python3 »,
   sans rien installer et sans accès au réseau.

   Refonte du 31/08/2026. Deux idées :
   — le RAIL de gauche ne montre qu'UNE langue à la fois (l'arbre du site
     s'y répétait trois fois), et chaque ligne porte l'état des trois ;
   — la zone de droite montre UN écran à la fois : tableau de bord,
     liste, éditeur, médiathèque, menus, corbeille. Les médias sortent du
     tiroir qui recouvrait la moitié de l'écran.
   ===================================================================== */

'use strict';

const $ = (s) => document.querySelector(s);

const etat = {
  pages: [], langues: [], menus: {}, corbeille: [], medias: null,
  courant: null, modifie: false,
  langue: localStorage.getItem('atelier.langue') || 'fr',
  ecran: 'tableau',
  filtres: { type: '', annee: '', etat: '' },
  media: { choisi: null, selection: new Set(), famille: '', usage: '', annee: '',
           tri: 'recents', vue: 'grille', insertion: null },
  menu: { langue: 'fr', entrees: [], pages: [], medias: [] },
};

const NOMS_LANGUES = { fr: 'Français', it: 'Italiano', en: 'English' };
const NOMS_ECRANS = {
  tableau: 'Tableau de bord', pages: 'Pages', fiches: 'Fiches',
  medias: 'Médias', menus: 'Menus du site', brouillons: 'Brouillons',
  corbeille: 'Corbeille', editeur: '',
};
const FAMILLES = { image: 'Images', pdf: 'PDF', audio: 'Audio', video: 'Vidéos', autre: 'Autres' };

/* --- petits services ------------------------------------------------ */

async function api(chemin, options) {
  const r = await fetch(chemin, options);
  const d = await r.json().catch(() => ({ erreur: 'réponse illisible' }));
  if (!r.ok || d.erreur) throw new Error(d.erreur || `erreur ${r.status}`);
  return d;
}

let minuteurMessage;
function dire(texte, erreur) {
  const m = $('#message');
  m.textContent = texte;
  m.classList.toggle('erreur', !!erreur);
  m.hidden = false;
  clearTimeout(minuteurMessage);
  minuteurMessage = setTimeout(() => { m.hidden = true; }, erreur ? 6000 : 2600);
}

function valeurEntete(entete, cle) {
  const m = entete.match(new RegExp('^' + cle + ':\\s*"?(.*?)"?\\s*$', 'm'));
  return m ? m[1].replace(/\\"/g, '"').replace(/\\\\/g, '\\') : '';
}

/* Comme l'aplatir du serveur : sans accents ni casse, apostrophes,
   guillemets, tirets et espaces ramenés à leur forme clavier. Le filtre
   des titres ne trouvait pas « Témoignage » pour « temoignage », ni
   « l’espérance » pour « l'espérance ». */
function aplatir(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[’‘]/g, "'").replace(/[«»“”„]/g, '"')
    .replace(/[–—]/g, '-').replace(/[   ]/g, ' ')
    .toLowerCase();
}

const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.',
              'août', 'sept.', 'oct.', 'nov.', 'déc.'];

function dateLisible(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  return m ? `${+m[3]} ${MOIS[+m[2] - 1]} ${m[1]}` : '';
}
function dateDHorodatage(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  return `${d.getDate()} ${MOIS[d.getMonth()]} ${d.getFullYear()}`;
}
function poidsLisible(n) {
  // Ko et Mo au sens strict (1000), pas 1024 : c'est ce que dit l'étiquette.
  if (!n) return '—';
  if (n < 1000) return n + ' o';
  if (n < 1e6) return Math.round(n / 1000) + ' Ko';
  return (n / 1e6).toFixed(n < 1e7 ? 1 : 0).replace('.', ',') + ' Mo';
}
function signesLisibles(n) {
  return (Math.round(n / 100) / 10).toString().replace('.', ',') + ' k';
}
function ilYA(iso) {
  if (!iso) return '';
  const jours = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (jours <= 0) return "aujourd'hui";
  if (jours === 1) return 'hier';
  return `il y a ${jours} jours`;
}

/* =====================================================================
   LE RAIL
   ===================================================================== */

/* Sa largeur se règle et se retient : les titres longs — « Témoignages
   après la lecture du livre… » — se coupaient à 300 px. En dessous de
   240 px les pastilles ne tiennent plus à côté du titre ; au-delà de
   620 px c'est l'éditeur qui devient étroit. */
const RAIL_DEFAUT = 300, RAIL_MIN = 240, RAIL_MAX = 620;

function poserLargeurRail(px, retenir) {
  const l = Math.min(RAIL_MAX, Math.max(RAIL_MIN, Math.round(px)));
  document.documentElement.style.setProperty('--rail', l + 'px');
  if (retenir) localStorage.setItem('atelier.rail', l);
  return l;
}

function largeurRailRetenue() {
  const l = parseInt(localStorage.getItem('atelier.rail') || '', 10);
  return Number.isFinite(l) ? l : RAIL_DEFAUT;
}

function brancherPoignee() {
  const poignee = $('#poignee-rail');
  poserLargeurRail(largeurRailRetenue(), false);

  poignee.addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    poignee.setPointerCapture(ev.pointerId);
    document.body.classList.add('redimensionne');
    // le rail commence à x = 0 : la largeur, c'est la position du doigt
    const bouge = (e) => poserLargeurRail(e.clientX, false);
    const fin = (e) => {
      poignee.removeEventListener('pointermove', bouge);
      document.body.classList.remove('redimensionne');
      poserLargeurRail(e.clientX, true);
    };
    poignee.addEventListener('pointermove', bouge);
    poignee.addEventListener('pointerup', fin, { once: true });
    poignee.addEventListener('pointercancel', fin, { once: true });
  });

  poignee.addEventListener('dblclick', () => {
    poserLargeurRail(RAIL_DEFAUT, true);
    dire('Largeur d’origine rétablie.');
  });

  // au clavier : la poignée se met au tabulateur, les flèches l'ajustent
  poignee.addEventListener('keydown', (ev) => {
    const pas = ev.shiftKey ? 48 : 16;
    if (ev.key === 'ArrowLeft') { ev.preventDefault(); poserLargeurRail(largeurActuelle() - pas, true); }
    if (ev.key === 'ArrowRight') { ev.preventDefault(); poserLargeurRail(largeurActuelle() + pas, true); }
  });
}

function largeurActuelle() {
  return $('#rail').getBoundingClientRect().width;
}

function dessinerLangues() {
  const boite = $('#langues');
  boite.textContent = '';
  for (const lg of etat.langues) {
    // le compte est celui de l'arbre : pages et rubriques, pas les 300
    // fiches d'une collection qui vivent DANS une rubrique.
    const n = etat.pages.filter((p) => p.langue === lg
      && (p.type === 'page' || p.type === 'collection')).length;
    const b = document.createElement('button');
    b.setAttribute('role', 'tab');
    b.className = etat.langue === lg ? 'actif' : '';
    b.setAttribute('aria-selected', etat.langue === lg ? 'true' : 'false');
    b.title = NOMS_LANGUES[lg] || lg;
    const nom = document.createElement('span');
    nom.textContent = lg.toUpperCase();
    const nb = document.createElement('span');
    nb.className = 'nb';
    nb.textContent = n;
    b.append(nom, nb);
    b.addEventListener('click', () => changerLangue(lg));
    boite.appendChild(b);
  }
}

function changerLangue(lg) {
  if (etat.langue === lg) return;
  etat.langue = lg;
  localStorage.setItem('atelier.langue', lg);
  dessinerLangues();
  $('#rail-langue').textContent = NOMS_LANGUES[lg] || lg.toUpperCase();
  dessinerArbre();
  if (etat.ecran === 'menus') chargerMenu(lg).catch((e) => dire(e.message, true));
  if (etat.ecran === 'pages' || etat.ecran === 'fiches' || etat.ecran === 'brouillons') {
    dessinerListe(etat.ecran);
  }
  majFil();
}

function dessinerBlocAtelier() {
  const n = (t) => etat.pages.filter((p) => p.type === t).length;
  $('#nb-pages').textContent = n('page');
  $('#nb-fiches').textContent = n('fiche');
  $('#nb-brouillons').textContent = etat.pages.filter((p) => p.statut !== 'publie').length;
  $('#nb-medias').textContent = etat.medias ? etat.medias.total : '';
  const jetees = etat.corbeille || [];
  $('#entree-corbeille').hidden = !jetees.length;
  $('#nb-corbeille').textContent = jetees.length;
  for (const b of document.querySelectorAll('.bloc-atelier .entree')) {
    b.classList.toggle('actif', b.dataset.ecran === etat.ecran);
  }
}

/* --- demander quelque chose, dans le style du site --------------------
   Remplace prompt() et confirm() du navigateur. Les leurs affichaient
   « localhost:8413 indique » au-dessus de nos phrases, dans une fenêtre
   grise qui n'a rien à voir avec l'atelier — et, pour la langue d'une
   jumelle, ils demandaient de TAPER « it » ou « en » au lieu de cliquer.

   demander() rend une promesse : la valeur choisie ou saisie, ou null si
   l'on renonce. Les trois formes :
     demander({titre, texte})                        → true ou null
     demander({titre, texte, champ: 'valeur'})       → texte saisi ou null
     demander({titre, texte, choix: [{valeur, libelle}]}) → valeur ou null   */
function demander({ titre, texte = '', champ = null, choix = null,
                    valider = 'Continuer', annuler = 'Annuler', danger = false,
                    immediat = false }) {
  const f = $('#fenetre-question');
  const bValider = $('#question-valider');
  const bAnnuler = $('#question-annuler');
  $('#question-titre').textContent = titre;
  $('#question-texte').textContent = texte;
  bValider.textContent = valider;
  bAnnuler.textContent = annuler;
  bValider.className = 'bouton ' + (danger ? 'danger' : 'primaire');

  const boiteChamp = $('#question-champ');
  const saisie = $('#question-saisie');
  boiteChamp.hidden = champ === null;
  saisie.value = champ === null ? '' : champ;

  const boiteChoix = $('#question-choix');
  boiteChoix.textContent = '';
  boiteChoix.hidden = !choix;
  let retenu = null;
  if (choix) {
    // un choix ne se tape pas, il se clique. Un seul candidat : on ne
    // pose même pas la question.
    for (const c of choix) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'bouton';
      b.textContent = c.libelle;
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', () => {
        retenu = c.valeur;
        // « immediat » : le bouton EST la réponse. Sans cela il fallait
        // choisir PUIS valider, et le premier clic semblait ne rien faire
        // — Christophe a cru que ça bloquait sur « le modèle local ».
        if (immediat) return bValider.click();
        for (const autre of boiteChoix.children) autre.setAttribute('aria-pressed', 'false');
        b.setAttribute('aria-pressed', 'true');
        bValider.disabled = false;
      });
      boiteChoix.appendChild(b);
    }
    bValider.hidden = immediat;
    bValider.disabled = !immediat;
  } else {
    bValider.hidden = false;
    bValider.disabled = false;
  }

  return new Promise((resoudre) => {
    const fin = (valeur) => {
      bValider.removeEventListener('click', surValider);
      bAnnuler.removeEventListener('click', surAnnuler);
      f.removeEventListener('close', surFermeture);
      if (f.open) f.close();
      resoudre(valeur);
    };
    const surValider = () => fin(choix ? retenu : (champ === null ? true : saisie.value.trim() || null));
    const surAnnuler = () => fin(null);
    const surFermeture = () => fin(null);   // Échap, ou clic hors du cadre
    bValider.addEventListener('click', surValider);
    bAnnuler.addEventListener('click', surAnnuler);
    f.addEventListener('close', surFermeture);
    f.showModal();
    if (champ !== null) { saisie.focus(); saisie.select(); }
    else if (choix) boiteChoix.firstChild?.focus();
    else bValider.focus();
  });
}

/* Le cas courant : une question à laquelle on répond oui ou non. */
async function confirmer(titre, texte, valider = 'Continuer', danger = false) {
  return (await demander({ titre, texte, valider, danger })) === true;
}

/* --- les pastilles F / I / E ---------------------------------------- */
function pastilles(p) {
  const boite = document.createElement('span');
  boite.className = 'pastilles';
  const voulu = p.jumelle_attendue === false;
  for (const lg of etat.langues) {
    const est = (p.etat_langues || {})[lg] || 'absente';
    const b = document.createElement('button');
    b.className = 'past ' + (est === 'humaine' ? 'pleine' : est === 'auto' ? 'auto' : 'absente')
      + (est === 'absente' && voulu ? ' voulue' : '');
    b.textContent = lg[0].toUpperCase();
    b.title = `${NOMS_LANGUES[lg] || lg} — ${
      est === 'humaine' ? 'traduite' : est === 'auto' ? 'traduction automatique'
      : voulu ? 'pas de jumelle attendue pour cette page' : 'version absente'}`;
    b.addEventListener('click', async (ev) => {
      ev.stopPropagation();
      // une absence VOULUE ne se crée pas d'un clic distrait
      if (est === 'absente' && voulu) {
        return dire('Cette page n’attend pas de jumelle — décochez le réglage pour en créer une.');
      }
      const jumelle = (p.jumelles || {})[lg];
      if (jumelle) { changerLangue(lg); ouvrir(jumelle); return; }
      if (await confirmer(
          `Créer la version « ${NOMS_LANGUES[lg] || lg} » ?`,
          `« ${p.titre} » n’existe pas encore dans cette langue. Elle naîtra en `
          + 'brouillon, avec le texte à traduire dedans.', 'Créer la jumelle')) {
        creerJumelle(p.fichier, lg);
      }
    });
    boite.appendChild(b);
  }
  return boite;
}

/* --- lignes de l'arbre ----------------------------------------------- */
function ligneDePage(p, avecLangue) {
  const b = document.createElement('button');
  b.className = 'ligne' + (etat.courant === p.fichier ? ' actif' : '');
  b.dataset.fichier = p.fichier;

  const puce = document.createElement('span');
  puce.className = 'puce';
  puce.textContent = '●';
  b.appendChild(puce);

  const texte = document.createElement('span');
  texte.className = 'texte';
  const nom = document.createElement('span');
  nom.className = 'nom';
  nom.textContent = p.titre;
  nom.title = p.titre;      // le titre entier reste lisible au survol
  texte.appendChild(nom);

  const bouts = [];
  if (avecLangue) bouts.push(p.langue.toUpperCase());
  if (p.date) bouts.push(dateLisible(p.date));
  bouts.push(signesLisibles(p.signes));
  const meta = document.createElement('span');
  meta.className = 'meta';
  meta.textContent = bouts.join(' · ');
  texte.appendChild(meta);
  b.appendChild(texte);

  if (p.statut !== 'publie') {
    const e = document.createElement('span');
    e.className = 'etiq brouillon';
    e.textContent = 'brouillon';
    b.appendChild(e);
  }
  b.appendChild(pastilles(p));
  b.addEventListener('click', () => ouvrir(p.fichier));
  return b;
}

function listeDe(pages, avecLangue) {
  const ul = document.createElement('ul');
  for (const p of pages) {
    const li = document.createElement('li');
    li.appendChild(ligneDePage(p, avecLangue));
    ul.appendChild(li);
  }
  return ul;
}

function dossier(titre, contenu, compte) {
  const d = document.createElement('details');
  d.className = 'dossier';
  const s = document.createElement('summary');
  const ch = document.createElement('span');
  ch.className = 'chevron';
  ch.textContent = '▸';
  const nom = document.createElement('span');
  nom.className = 'nom';
  nom.textContent = titre;
  nom.title = titre;
  s.append(ch, nom);
  if (compte) {
    const n = document.createElement('span');
    n.className = 'nb';
    n.textContent = compte;
    s.appendChild(n);
  }
  d.append(s, contenu);
  return d;
}

/* Le menu du site sert de plan : l'atelier range les pages comme le
   visiteur les rencontre. Celles qui ne figurent dans aucun menu ne sont
   pas perdues — elles se retrouvent sous « Hors menu ». */
function brancheDeMenu(entrees, parLien, fichesDe, servies) {
  const morceaux = [];
  for (const e of entrees || []) {
    const page = e.lien ? parLien.get(e.lien) : null;
    const enfants = brancheDeMenu(e.entrees, parLien, fichesDe, servies);
    if (page) {
      servies.add(page.fichier);
      const fiches = page.type === 'collection'
        ? (fichesDe.get(page.fichier.split('/')[1]) || []) : [];
      fiches.forEach((f) => servies.add(f.fichier));
      if (fiches.length || enfants.length) {
        const dedans = document.createElement('div');
        dedans.className = 'dedans';
        dedans.appendChild(listeDe([page, ...fiches]));
        enfants.forEach((c) => dedans.appendChild(c));
        morceaux.push(dossier(page.titre, dedans, fiches.length || null));
      } else {
        morceaux.push(listeDe([page]));
      }
    } else if (enfants.length) {
      const dedans = document.createElement('div');
      dedans.className = 'dedans';
      enfants.forEach((c) => dedans.appendChild(c));
      morceaux.push(dossier(e.titre || '(sans titre)', dedans, null));
    }
  }
  return morceaux;
}

function filtresActifs() {
  return Object.values(etat.filtres).filter(Boolean).length;
}

function passeLesFiltres(p) {
  const f = etat.filtres;
  if (f.type && p.type !== f.type) return false;
  if (f.annee && String(p.date || '').slice(0, 4) !== f.annee) return false;
  if (f.etat === 'brouillon' && p.statut === 'publie') return false;
  // « sans jumelle » cherche un OUBLI : les pages qui n'en attendent pas
  // n'en sont pas un.
  if (f.etat === 'sans-jumelle' && (p.jumelle || p.jumelle_attendue === false)) return false;
  if (f.etat === 'auto' && !p.traduction_automatique) return false;
  return true;
}

function dessinerArbre() {
  const q = aplatir($('#filtre').value.trim());
  const boite = $('#pages');
  boite.textContent = '';

  const dedans = etat.pages.filter((p) => p.langue === etat.langue && passeLesFiltres(p));

  // Quand on cherche ou qu'on filtre, on veut une liste à plat : rien à
  // déplier, tout est visible.
  if (q || filtresActifs()) {
    const vues = dedans.filter((p) => !q
      || aplatir(p.titre).includes(q) || aplatir(p.fichier).includes(q));
    boite.appendChild(listeDe(vues));
    if (!vues.length) {
      const rien = document.createElement('p');
      rien.className = 'astuce';
      rien.style.padding = '.6rem';
      rien.textContent = 'Aucune page ne répond ici.';
      boite.appendChild(rien);
    }
    // sur l'écran des médias, on cherche un FICHIER : inutile d'aller
    // fouiller le texte des pages, la liste « Utilisée dans » le dit mieux.
    if (q.length >= 2 && etat.ecran !== 'medias') {
      chercherDansLeTexte(q, new Set(vues.map((p) => p.fichier)), boite);
    }
    return;
  }

  const publiees = dedans.filter((p) => p.statut === 'publie');
  const parLien = new Map(publiees.map((p) => [p.url, p]));
  const fichesDe = new Map();
  for (const p of publiees.filter((x) => x.type === 'fiche')) {
    const c = p.collection || p.fichier.split('/')[1];
    if (!fichesDe.has(c)) fichesDe.set(c, []);
    fichesDe.get(c).push(p);
  }
  /* Les fiches arrivaient dans l'ordre des NOMS DE FICHIERS : une
     nouvelle, numérotée 201, se retrouvait après les deux cents autres
     alors qu'elle est la première du site. C'est `rang` qui donne
     l'ordre, celui-là même que le générateur suit. */
  for (const [, lot] of fichesDe) lot.sort((a, b) => (a.rang || 0) - (b.rang || 0));

  const servies = new Set();
  // L'accueil n'est dans aucun menu — c'est le logo qui y mène.
  const accueil = publiees.find((p) => p.url === `/${etat.langue}/`);
  if (accueil) { servies.add(accueil.fichier); boite.appendChild(listeDe([accueil])); }

  for (const b of brancheDeMenu(etat.menus[etat.langue], parLien, fichesDe, servies)) {
    boite.appendChild(b);
  }
  const hors = publiees.filter((p) => !servies.has(p.fichier) && p.type !== 'conteneur');
  if (hors.length) {
    const d = document.createElement('div');
    d.className = 'dedans';
    d.appendChild(listeDe(hors));
    boite.appendChild(dossier('Hors menu', d, hors.length));
  }
  const brouillons = dedans.filter((p) => p.statut !== 'publie');
  if (brouillons.length) {
    const d = document.createElement('div');
    d.className = 'dedans';
    d.appendChild(listeDe(brouillons));
    boite.appendChild(dossier('Brouillons', d, brouillons.length));
  }
}

// Le filtre local ne voit que les titres. Le serveur, lui, lit le texte :
// « Krishnamurti » n'est le titre d'aucune page mais revient dans
// plusieurs Réflexions.
async function chercherDansLeTexte(q, dejaVus, boite) {
  let d;
  try { d = await api('/api/chercher?q=' + encodeURIComponent(q)); } catch (e) { return; }
  if (aplatir($('#filtre').value.trim()) !== q) return;   // trop tard

  const neufs = d.resultats.filter((r) => !dejaVus.has(r.fichier)
    && r.fichier.startsWith(etat.langue + '/'));
  const ailleurs = d.resultats.filter((r) => !r.fichier.startsWith(etat.langue + '/')).length;

  if (neufs.length) {
    const tete = document.createElement('p');
    tete.className = 'rubrique';
    tete.style.padding = '.7rem .5rem .3rem';
    tete.textContent = `dans le texte (${neufs.length})`;
    boite.appendChild(tete);
    const ul = document.createElement('ul');
    for (const r of neufs) {
      const p = etat.pages.find((x) => x.fichier === r.fichier);
      if (!p) continue;
      const li = document.createElement('li');
      const b = ligneDePage(p);
      if (r.extrait) {
        const e = b.querySelector('.meta');
        e.textContent = r.extrait;
        e.title = r.extrait;
      }
      li.appendChild(b);
      ul.appendChild(li);
    }
    boite.appendChild(ul);
  }
  if (ailleurs) {
    const p = document.createElement('p');
    p.className = 'astuce';
    p.style.padding = '.5rem';
    p.textContent = `${ailleurs} résultat(s) dans les autres langues — changez de langue en haut.`;
    boite.appendChild(p);
  }
}

/* =====================================================================
   LES ÉCRANS
   ===================================================================== */

function majFil() {
  const fil = $('#fil');
  fil.textContent = '';
  const bouts = ['Atelier', NOMS_LANGUES[etat.langue] || etat.langue];
  if (etat.ecran === 'editeur') {
    const p = etat.pages.find((x) => x.fichier === etat.courant);
    bouts.push(p ? p.titre : 'Page');
  } else {
    bouts.push(NOMS_ECRANS[etat.ecran] || '');
  }
  bouts.forEach((t, i) => {
    if (i) {
      const s = document.createElement('span');
      s.className = 'sep';
      s.textContent = '/';
      fil.appendChild(s);
    }
    const e = document.createElement('span');
    if (i === bouts.length - 1) e.className = 'ici';
    e.textContent = t;
    fil.appendChild(e);
  });
}

function montrerEcran(nom) {
  const cibles = { tableau: 'tableau', pages: 'liste', fiches: 'liste',
                   brouillons: 'liste', medias: 'medias', menus: 'menus',
                   corbeille: 'corbeille', editeur: 'editeur' };
  etat.ecran = nom;
  for (const e of document.querySelectorAll('.ecran')) e.hidden = true;
  $('#ecran-' + cibles[nom]).hidden = false;
  document.body.classList.remove('rail-ouvert');

  $('#filtre').placeholder = nom === 'medias' ? 'Rechercher un fichier…' : 'Filtrer les pages…';
  if (nom === 'tableau') dessinerTableau();
  if (nom === 'pages' || nom === 'fiches' || nom === 'brouillons') dessinerListe(nom);
  if (nom === 'medias') ouvrirMedias();
  if (nom === 'menus') chargerMenu(etat.langue).catch((e) => dire(e.message, true));
  if (nom === 'corbeille') dessinerCorbeille();
  dessinerBlocAtelier();
  majFil();
}

/* --- tableau de bord -------------------------------------------------- */
function dessinerTableau() {
  const n = (t) => etat.pages.filter((p) => p.type === t).length;
  const brouillons = etat.pages.filter((p) => p.statut !== 'publie').length;
  $('#tableau-sous-titre').textContent =
    `${etat.pages.length} page${etat.pages.length > 1 ? 's' : ''} en ${etat.langues.length} langue${etat.langues.length > 1 ? 's' : ''}`
    + (etat.jamais_publie ? ' · jamais publié depuis cet ordinateur'
       : ` · dernière publication ${ilYA(etat.derniere_publication)}`)
    + ((etat.site && etat.site.moteur) ? ` · moteur ${etat.site.moteur}` : '');

  const cartes = [['pages', n('page')], ['rubriques', n('collection')],
                  ['fiches', n('fiche')], ['brouillons', brouillons],
                  ['médias', etat.medias ? etat.medias.total : '…']];
  const boite = $('#cartes');
  boite.textContent = '';
  for (const [nom, v] of cartes) {
    const d = document.createElement('div');
    d.className = 'carte' + (v === 0 ? ' vide' : '');
    const b = document.createElement('b');
    b.textContent = v;
    const s = document.createElement('span');
    s.textContent = nom;
    d.append(b, s);
    boite.appendChild(d);
  }

  // À TRADUIRE : les pages dont une version manque. C'est l'oubli le plus
  // probable d'un site en trois langues — on ajoute d'un côté, l'autre
  // reste en arrière et rien ne le dit.
  const manquantes = etat.pages.filter((p) => p.type !== 'conteneur'
    && p.jumelle_attendue !== false
    && Object.values(p.etat_langues || {}).includes('absente'));
  $('#nb-a-traduire').textContent = manquantes.length || '';
  const zone = $('#a-traduire');
  zone.textContent = '';
  if (!manquantes.length) {
    const p = document.createElement('p');
    p.className = 'rien';
    p.textContent = 'Tout est à jour : chaque page existe dans toutes les langues.';
    zone.appendChild(p);
  }
  // ON PEUT EN JETER PLUSIEURS D'UN COUP. Une traduction dont l'original
  // a été supprimé reste ici, seule et publiée — et il fallait ouvrir
  // chaque page pour la mettre à la corbeille. Christophe en avait deux,
  // il en aurait eu vingt un jour de ménage.
  const choisies = new Set();
  const bJeter = $('#b-jeter-a-traduire');
  const majJeter = () => {
    bJeter.hidden = !choisies.size;
    bJeter.textContent = `Mettre ${choisies.size} page(s) à la corbeille…`;
  };
  majJeter();
  bJeter.onclick = () => jeterDesPages([...choisies]).catch((e) => dire(e.message, true));

  for (const p of manquantes.slice(0, 12)) {
    const r = document.createElement('div');
    r.className = 'rangee';
    const coche = document.createElement('input');
    coche.type = 'checkbox';
    coche.className = 'coche-rangee';
    coche.title = 'Choisir cette page';
    coche.addEventListener('change', () => {
      if (coche.checked) choisies.add(p.fichier); else choisies.delete(p.fichier);
      majJeter();
    });
    r.appendChild(coche);
    // La rangée s'ouvre : sans cela, la page à traduire était nommée mais
    // introuvable — il fallait deviner sa langue et la chercher dans l'arbre.
    const t = document.createElement('button');
    t.className = 'texte lien-rangee';
    t.title = `Ouvrir la version ${NOMS_LANGUES[p.langue] || p.langue}`;
    t.addEventListener('click', () => { changerLangue(p.langue); ouvrir(p.fichier); });
    const nom = document.createElement('span');
    nom.className = 'nom';
    nom.textContent = p.titre;
    const meta = document.createElement('span');
    meta.className = 'meta';
    meta.textContent = etat.langues
      .map((lg) => `${lg.toUpperCase()} ${(p.etat_langues || {})[lg] === 'absente' ? 'absente' : 'à jour'}`)
      .join(' · ') + ' — cliquez pour l’ouvrir';
    t.append(nom, meta);
    const b = document.createElement('button');
    b.className = 'bouton';
    b.textContent = 'Traduire';
    const cible = etat.langues.find((lg) => (p.etat_langues || {})[lg] === 'absente');
    b.addEventListener('click', () => creerJumelle(p.fichier, cible));
    r.append(t, pastilles(p), b);
    zone.appendChild(r);
  }

  const recents = [...etat.pages].sort((a, b) => (b.modifie || 0) - (a.modifie || 0)).slice(0, 8);
  const zr = $('#recents');
  zr.textContent = '';
  for (const p of recents) {
    const r = document.createElement('button');
    r.className = 'rangee cliquable';
    const t = document.createElement('span');
    t.className = 'texte';
    const nom = document.createElement('span');
    nom.className = 'nom';
    nom.textContent = p.titre;
    const meta = document.createElement('span');
    meta.className = 'meta';
    meta.textContent = `${p.langue.toUpperCase()} · ${dateDHorodatage(p.modifie)}`;
    t.append(nom, meta);
    r.appendChild(t);
    r.addEventListener('click', () => { changerLangue(p.langue); ouvrir(p.fichier); });
    zr.appendChild(r);
  }
}

/* --- liste plate ------------------------------------------------------ */
function dessinerListe(mode) {
  const titres = { pages: 'Pages', fiches: 'Fiches', brouillons: 'Brouillons' };
  $('#liste-titre').textContent = titres[mode];
  const q = aplatir($('#filtre').value.trim());
  // LES BROUILLONS NE SONT PAS UNE VUE DE LANGUE. C'est la liste de ce
  // qui reste à finir, et les jumelles fraîchement traduites sont par
  // définition dans une AUTRE langue que celle du rail. Le compteur les
  // comptait toutes, la liste n'en montrait qu'une langue : Christophe
  // lisait « 2 » et voyait « Rien ici ».
  const toutesLangues = mode === 'brouillons';
  let vues = etat.pages.filter((p) => (toutesLangues || p.langue === etat.langue)
                                      && passeLesFiltres(p));
  if (mode === 'pages') vues = vues.filter((p) => p.type === 'page' || p.type === 'collection');
  if (mode === 'fiches') vues = vues.filter((p) => p.type === 'fiche');
  if (mode === 'brouillons') vues = vues.filter((p) => p.statut !== 'publie');
  if (q) vues = vues.filter((p) => aplatir(p.titre).includes(q) || aplatir(p.fichier).includes(q));

  $('#liste-sous-titre').textContent =
    (toutesLangues ? `${vues.length}, toutes langues confondues`
                   : `${vues.length} en ${NOMS_LANGUES[etat.langue] || etat.langue}`)
    + (filtresActifs() ? ` · ${filtresActifs()} filtre(s) actif(s)` : '');
  $('#liste-actions').hidden = !toutesLangues || !vues.length;
  etat.brouillonsVus = toutesLangues ? vues.map((p) => p.fichier) : [];
  const boite = $('#liste-plate');
  boite.textContent = '';
  if (!vues.length) {
    const p = document.createElement('p');
    p.className = 'astuce';
    p.style.padding = '1.2rem';
    p.textContent = 'Rien ici.';
    boite.appendChild(p);
    return;
  }
  for (const p of vues) boite.appendChild(ligneDePage(p, toutesLangues));
}

/* =====================================================================
   ÉDITEUR
   ===================================================================== */

/* Les réglages en clair écrivent dans le MÊME texte que la main : il n'y
   a qu'une source, le YAML. Deux copies auraient divergé au premier
   enregistrement. */
function poserCle(cle, valeur) {
  const ta = $('#entete');
  const motif = new RegExp('^' + cle + ':.*$', 'm');
  if (valeur === '' || valeur === null) {
    ta.value = ta.value.replace(new RegExp('^' + cle + ':.*\\n?', 'm'), '');
  } else {
    /* un nombre s'écrit SANS guillemets : le générateur trie les fiches
       sur `rang`, et un « 7 » entre guillemets restait une chaîne — le
       tri butait sur str contre int et la collection entière échouait. */
    const brut = /^-?\d+$/.test(String(valeur).trim())
      ? String(valeur).trim() : '"' + valeur + '"';
    const ligne = cle + ': ' + brut;
    ta.value = motif.test(ta.value)
      ? ta.value.replace(motif, ligne)
      : ta.value.replace(/\s*$/, '') + '\n' + ligne;
  }
  etat.modifie = true;
}

function relireReglagesClairs() {
  const e = $('#entete').value;
  const statut = valeurEntete(e, 'statut') || 'publie';
  $('#avis-brouillon').hidden = statut === 'publie';
  $('#r-statut').value = statut;
  $('#r-date').value = valeurEntete(e, 'date') || '';
  $('#r-rang').value = valeurEntete(e, 'rang') || '';
  /* Trois états, et il faut les distinguer : « cote » ne se déduit pas
     d'un booléen. Les orthographes admises par le générateur — « cote »,
     « côté », « colonne » — se ramènent toutes au même choix, sinon
     rouvrir une page écrite à la main remettrait la liste sur « aucun »
     et le premier enregistrement effacerait le réglage. */
  $('#r-vignette').value = valeurEntete(e, 'vignette') || '';
  const som = (valeurEntete(e, 'sommaire') || '').trim().toLowerCase();
  $('#r-sommaire').value = ['cote', 'côté', 'colonne'].includes(som) ? 'cote'
                         : ['oui', 'true', 'vrai'].includes(som) ? 'oui' : '';
  $('#r-auto').checked = /^(oui|true|vrai)/i.test(valeurEntete(e, 'traduction_automatique') || '');
  $('#r-sans-jumelle').checked = /^(non|false|no)/i.test(valeurEntete(e, 'jumelle_attendue') || '');
}

async function ouvrir(fichier) {
  if (etat.modifie && !await confirmer('Modifications non enregistrées',
      'Elles seront perdues si vous continuez.', 'Continuer', true)) return;
  const d = await api('/api/lire?f=' + encodeURIComponent(fichier));
  etat.courant = fichier;
  etat.modifie = false;
  $('#corps').value = d.corps;
  $('#entete').value = d.entete;
  $('#titre-courant').textContent = valeurEntete(d.entete, 'titre') || fichier;
  $('#chemin-courant').textContent = fichier;
  const lg = fichier.split('/')[0];
  const pastille = $('#langue-courante');
  pastille.textContent = lg;
  pastille.className = 'etiq langue-' + lg;
  if (lg !== etat.langue) changerLangue(lg);
  relireReglagesClairs();
  const laPage = etat.pages.find((x) => x.fichier === fichier);
  $('#avis-collection').hidden = !laPage || laPage.type !== 'collection';
  // Traduire n'a de sens que sur une page d'ARRIVÉE : une page française
  // n'a rien à traduire depuis, et sans clé d'appariement on ne saurait
  // pas quelle page est son original.
  $('#b-traduire').hidden = (lg === 'fr') || !valeurEntete(d.entete, 'traduction');
  // L'inverse : depuis le français, on fabrique et on traduit les autres.
  $('#b-traduire-tout').hidden = (lg !== 'fr') || etat.langues.length < 2;
  montrerEcran('editeur');
  montrerVue('ecrire');
  dessinerArbre();
}

/* Les traductions MACHINE d'une page, dans les autres langues. Sert à
   les emporter quand on jette l'original, et à les publier quand on le
   publie : les deux gestes suivent la même règle. */
function traductionsMachineDe(fichier) {
  const source = etat.pages.find((p) => p.fichier === fichier);
  if (!source || !source.traduction) return [];
  return etat.pages.filter((p) => p.traduction === source.traduction
                                  && p.fichier !== fichier
                                  && p.traduction_automatique);
}

/* --- jeter plusieurs pages d'un coup ---------------------------------- */
async function jeterDesPages(fichiers) {
  if (!fichiers.length) return;
  if (!await confirmer(`Mettre ${fichiers.length} page(s) à la corbeille ?`,
      'Elles sortiront du site à la prochaine mise en ligne. La corbeille '
      + 'permet de les remettre.', 'Mettre à la corbeille', true)) {
    return dire('Rien n’a été jeté.');
  }
  let faits = 0;
  const refus = [];
  for (const f of fichiers) {
    try {
      await api('/api/supprimer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fichier: f }),
      });
      faits += 1;
    } catch (souci) { refus.push(`${f} : ${souci.message}`); }
  }
  await recharger();
  dire(`${faits} page(s) à la corbeille`
       + (refus.length ? ` — ${refus.length} refus : ${refus[0]}` : '') + '.',
       refus.length > 0);
}

/* --- mettre en ligne tous les brouillons listés ----------------------- */
/* Publier une page demandait de l'ouvrir, d'aller aux Réglages et de
   cliquer « Mettre en ligne » — une fois par page ET par langue. Traduire
   une fiche en fabrique deux d'un coup : le geste se faisait donc trois
   fois pour une idée. Ici, la liste des brouillons se publie en bloc.
   Chaque page est relue et réécrite AVEC SON TEXTE : on ne touche que la
   ligne « statut ». */
/* Passe une page en ligne sans l'ouvrir : on relit le fichier et l'on ne
   réécrit QUE sa ligne « statut ». Le texte n'est pas touché. */
/* Relit l'en-tête d'une page si c'est celle qui est ouverte. Le corps
   n'est pas touché : une saisie en cours ne doit pas disparaître. */
async function rafraichirEntete(fichier) {
  if (etat.courant !== fichier) return;
  try {
    const d = await api('/api/lire?f=' + encodeURIComponent(fichier));
    $('#entete').value = d.entete;
    relireReglagesClairs();
  } catch { /* la page a pu être renommée ou jetée entre-temps */ }
}

async function mettreLaPageEnLigne(fichier) {
  const d = await api('/api/lire?f=' + encodeURIComponent(fichier));
  const entete = d.entete.replace(/^statut:.*$/m, 'statut: "publie"');
  if (entete === d.entete) return false;
  await api('/api/ecrire', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fichier, entete, corps: d.corps }),
  });
  return true;
}

/* LES TRADUCTIONS SUIVENT LEUR ORIGINAL, AU MOMENT OÙ ON LE PUBLIE.
   La règle vivait dans « Traduire partout », qui s'exécute AVANT : une
   fiche neuve est un brouillon, on la traduit, ses jumelles naissent
   brouillons elles aussi — et rien ne les réveillait quand on publiait
   enfin le français. Christophe devait aller les chercher une par une.

   On ne réveille que les traductions MACHINE de cette page-là : une page
   qu'un humain a délibérément laissée en brouillon n'est pas concernée. */
async function publierLesTraductions(fichier) {
  const soeurs = traductionsMachineDe(fichier).filter((p) => p.statut !== 'publie');
  let faits = 0;
  for (const s of soeurs) {
    if (await mettreLaPageEnLigne(s.fichier).catch(() => false)) faits += 1;
  }
  if (faits) await recharger();
  return faits;
}

async function publierLesBrouillons() {
  const fichiers = etat.brouillonsVus || [];
  if (!fichiers.length) return;
  if (!await confirmer(`Mettre ${fichiers.length} page(s) en ligne ?`,
      'Elles cesseront d’être des brouillons et paraîtront à la prochaine '
      + 'fabrication du site. Relisez-les d’abord : une traduction automatique '
      + 'non relue partirait telle quelle.', 'Mettre en ligne')) {
    return dire('Rien n’a été publié.');
  }
  const b = $('#b-publier-brouillons');
  b.disabled = true;
  let faits = 0;
  const refus = [];
  try {
    for (const f of fichiers) {
      try {
        if (!await mettreLaPageEnLigne(f)) throw new Error('pas de ligne « statut »');
        faits += 1;
      } catch (souci) { refus.push(`${f} : ${souci.message}`); }
    }
  } finally {
    b.disabled = false;
    await recharger();
  }
  dire(`${faits} page(s) mise(s) en ligne`
       + (refus.length ? ` — ${refus.length} refus : ${refus[0]}` : '')
       + '. Cliquez « Régénérer » pour les voir.', refus.length > 0);
}

/* --- traduire la page dans TOUTES les autres langues ------------------ */
/* Ce bouton n'invente rien : il enchaîne les deux gestes qui existent déjà,
   « Jumelle » puis « Traduire », pour chaque langue d'arrivée. Les cas
   tordus — rubrique sans jumelle, clé en double, numérotation — restent
   traités par /api/jumelle, qui les connaît. Une langue qui échoue
   n'empêche pas les autres : on va au bout et on rend le compte rendu. */
async function traduirePartout() {
  const fichier = etat.courant;
  if (!fichier) return;
  if (etat.modifie && !await confirmer('Modifications non enregistrées',
      'Elles seront perdues si vous continuez.', 'Continuer', true)) return;
  const vers = etat.langues.filter((lg) => lg !== fichier.split('/')[0]);
  if (!vers.length) return dire('Il n’y a pas d’autre langue déclarée.');
  const source = etat.pages.find((p) => p.fichier === fichier);
  const moteur = await choisirMoteur(
    `Traduire en ${vers.map((l) => NOMS_LANGUES[l] || l).join(' et ')} ?`);
  if (!moteur) return dire('Traduction abandonnée.');

  const b = $('#b-traduire-tout');
  const avant = b.textContent;
  b.disabled = true;
  const bilan = [];
  try {
    for (const lg of vers) {
      const nom = NOMS_LANGUES[lg] || lg;
      b.textContent = `${nom}…`;
      dire(`${nom} : en cours…`);
      try {
        const jum = await api('/api/jumelle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fichier, langue: lg }),
        });
        const r = await traduireUnFichier(jum.fichier, moteur, nom);
        // LA JUMELLE SUIT SON ORIGINAL. Elle naissait en brouillon — sage
        // tant qu'elle contenait du français, absurde une fois traduite :
        // Christophe ne parle ni anglais ni italien, la « relecture » qui
        // justifiait le brouillon n'aura jamais lieu, et les pages
        // seraient restées invisibles pour toujours. La mention
        // « traduction automatique » reste, elle, et s'affiche au lecteur.
        // Si l'original est DÉJÀ en ligne, sa traduction l'est aussitôt.
        // S'il est encore en brouillon, elle le suivra le jour où on le
        // publiera — c'est publierLesTraductions() qui s'en charge.
        let publiee = false;
        if (r && (source || {}).statut === 'publie') {
          publiee = await mettreLaPageEnLigne(jum.fichier).catch(() => false);
        }
        bilan.push(`${nom} : ${jum.existait ? 'page existante' : 'page créée'}`
                   + (r ? `, traduite${r.reprises ? ` (${r.reprises} repris)` : ''}` : ', NON traduite')
                   + (publiee ? ' et mise en ligne' : ''));
      } catch (souci) {
        bilan.push(`${nom} : ${souci.message}`);
      }
    }
  } finally {
    b.disabled = false;
    b.textContent = avant;
    // « Jumelle » a pu poser la clé « traduction » dans la page ouverte :
    // l'éditeur doit relire son en-tête, sinon le prochain enregistrement
    // réécrirait l'ancien et casserait l'appariement.
    await rafraichirEntete(fichier);
    await recharger();
  }
  dire(bilan.join(' · ') + ' — cliquez « Publier en ligne… » pour les envoyer.',
       bilan.some((x) => /NON traduite|refus|erreur/i.test(x)));
}

/* Traduit un fichier donné, en demandant confirmation si la page porte
   déjà une traduction humaine. Rend le compte rendu, ou null si refusé. */
async function traduireUnFichier(fichier, moteur, nom) {
  const envoyer = (remplacer) => api('/api/traduire', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fichier, moteur, remplacer }),
  });
  try {
    return await envoyer(false);
  } catch (souci) {
    if (!/HUMAINE/.test(souci.message)) throw souci;
    if (!await confirmer(`${nom} : traduction humaine`,
        'Cette page semble avoir été traduite à la main. La traduire par la '
        + 'machine effacera ce travail, que rien ne reconstitue.',
        'Écraser quand même', true)) return null;
    return envoyer(true);
  }
}

/* --- traduire la page courante -------------------------------------- */
/* Le bouton ne s'affiche que sur une page qui a une ORIGINE : traduire le
   français vers le français n'a pas de sens, et une page sans jumelle n'a
   rien à traduire depuis. La page reste en brouillon dans tous les cas. */
async function traduireLaPage() {
  const fichier = etat.courant;
  if (!fichier) return;
  if (etat.modifie && !await confirmer('Modifications non enregistrées',
      'Elles seront perdues si vous continuez.', 'Continuer', true)) return;
  const moteur = await choisirMoteur();
  if (!moteur) return dire('Traduction abandonnée — aucun moteur choisi.');
  const b = $('#b-traduire');
  const avant = b.textContent;
  b.disabled = true;
  b.textContent = 'Traduction…';
  dire('Traduction en cours — une longue page demande plusieurs minutes.');
  try {
    const lg = fichier.split('/')[0];
    const r = await traduireUnFichier(fichier, moteur, NOMS_LANGUES[lg] || lg);
    if (!r) return dire('Traduction abandonnée — rien n’a été écrit.');
    if (etat.courant === fichier) {
      $('#corps').value = r.texte;
      etat.modifie = false;
    }
    dire(`Traduit depuis ${r.depuis}`
         + (r.reprises ? ` — ${r.reprises} passage(s) repris` : '')
         + '. À relire : la page reste en brouillon.');
  } finally {
    b.disabled = false;
    b.textContent = avant;
  }
}

function choisirMoteur(titre = 'Traduire cette page ?') {
  // Sans clé d'API il n'y a qu'un moteur : on ne demande rien.
  if (!etat.iaDistante) return Promise.resolve('local');
  /* Deux moteurs, et le choix se pose à chaque fois : le local ne coûte
     rien et ne sort pas d'ici, mais il faut que le serveur tourne ; le
     distant marche toujours, mais le texte s'en va et l'appel se paie. */
  return demander({
    titre,
    texte: 'Les pages manquantes seront créées en brouillon. Choisissez le moteur — '
           + 'le clic lance la traduction.\n\n'
           + 'Le modèle local ne coûte rien et rien ne sort de la maison, mais il '
           + 'faut avoir lancé « qwen-uncensored ». L’IA externe marche toujours, '
           + 'mais le texte sera envoyé au dehors et l’appel est facturé.',
    choix: [
      { valeur: 'local', libelle: 'Avec le modèle local' },
      { valeur: 'distant', libelle: 'Avec l’IA externe' },
    ],
    immediat: true,
  });
}

async function enregistrer() {
  if (!etat.courant) return;
  await api('/api/ecrire', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fichier: etat.courant, entete: $('#entete').value, corps: $('#corps').value }),
  });
  etat.modifie = false;
  dire('Enregistré.');
  await recharger();
}

async function creerJumelle(fichier, langue) {
  try {
    const d = await api('/api/jumelle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fichier, langue }),
    });
    await rafraichirEntete(fichier);
    await recharger();
    changerLangue(langue);
    await ouvrir(d.fichier);
    dire(d.existait ? 'La jumelle existait déjà : la voici.'
                    : 'Jumelle créée, en brouillon — le texte d’origine y est recopié, '
                      + 'remplacez-le au fil de la traduction.');
  } catch (e) { dire(e.message, true); }
}

function montrerVue(nom) {
  for (const o of document.querySelectorAll('.onglet')) o.classList.toggle('actif', o.dataset.vue === nom);
  for (const v of ['ecrire', 'entete', 'apercu']) $('#vue-' + v).hidden = v !== nom;
  if (nom === 'apercu') apercu();
}

async function apercu() {
  const d = await api('/api/apercu', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ corps: $('#corps').value }),
  });
  $('#apercu').innerHTML = d.html;
}

function inserer(texte) {
  const z = $('#corps');
  const [a, b] = [z.selectionStart, z.selectionEnd];
  z.setRangeText(texte, a, b, 'end');
  z.focus();
  etat.modifie = true;
}
function entourer(marque) {
  const z = $('#corps');
  const [a, b] = [z.selectionStart, z.selectionEnd];
  z.setRangeText(marque + z.value.slice(a, b) + marque, a, b, 'end');
  z.focus();
  etat.modifie = true;
}
/* Entoure la sélection de deux marques DIFFÉRENTES — une balise ouvrante
   et sa fermante. `entourer` ne sait poser que la même des deux côtés. */
function encadrer(avant, apres) {
  const z = $('#corps');
  const [a, b] = [z.selectionStart, z.selectionEnd];
  const dedans = z.value.slice(a, b) || 'le texte';
  z.setRangeText(avant + dedans + apres, a, b, 'end');
  z.focus();
  etat.modifie = true;
}

/* Enveloppe la sélection dans un bloc de la charte. `markdown="1"` est
   indispensable : sans lui, le contenu du div n'est plus interprété comme
   du Markdown et le gras, les listes et les liens sortent en clair. */
function envelopper(classe) {
  const z = $('#corps');
  const [a, b] = [z.selectionStart, z.selectionEnd];
  const dedans = z.value.slice(a, b) || 'Le texte du bloc.';
  const debut = a === 0 || z.value[a - 1] === '\n' ? '' : '\n\n';
  z.setRangeText(`${debut}<div class="${classe}" markdown="1">\n${dedans}\n</div>\n`,
                 a, b, 'end');
  z.focus();
  etat.modifie = true;
}

/* CE QUE FAIT LE BOUTON SE MONTRE, IL NE SE DEVINE PAS. Une petite icône
   ne dit rien d'un « encadré » ni d'une « voix » ; Christophe l'a signalé
   avant même d'avoir essayé. Chaque bouton porte donc son nom, et le
   survol ajoute une carte : à quoi ça sert, et un ÉCHANTILLON RENDU.
   Un échantillon, pas une capture d'écran : une image se démoderait le
   jour où la charte change, celui-ci ne peut pas mentir sur sa forme. */
const EXEMPLES = {
  encadre: '<div class="ex-encadre">Michel Montaud<br>65 Chemin du reposoir<br>26220 Monjoux</div>',
  rappel: '<div class="ex-rappel">Joindre une enveloppe timbrée à votre adresse pour la réponse.</div>',
  praticien: '<p class="ex-praticien">Votre bouche raconte ce que le corps tait.</p>',
  patient: '<p class="ex-patient">Depuis trois ans, je dors mal et je serre les dents.</p>',
  portrait: '<div class="ex-portrait"><span class="ex-photo"></span>Le texte vient se ranger autour de l’image, qui flotte à droite.</div>',
  centree: '<div class="ex-centree"><span class="ex-photo"></span></div>',
};

function poserApercusDOutils() {
  const carte = document.createElement('div');
  carte.id = 'apercu-outil';
  carte.hidden = true;
  document.body.appendChild(carte);
  for (const b of document.querySelectorAll('.outils-texte [data-exemple]')) {
    const montrer = () => {
      carte.innerHTML = `<b>${b.dataset.titre}</b><p>${b.dataset.quoi}</p>`
                        + (EXEMPLES[b.dataset.exemple] || '');
      carte.hidden = false;
      const r = b.getBoundingClientRect();
      carte.style.left = Math.max(8, Math.min(r.left, window.innerWidth - 320)) + 'px';
      carte.style.top = (r.bottom + 8) + 'px';
    };
    const cacher = () => { carte.hidden = true; };
    b.addEventListener('mouseenter', montrer);
    b.addEventListener('focus', montrer);
    b.addEventListener('mouseleave', cacher);
    b.addEventListener('blur', cacher);
    b.addEventListener('click', cacher);
  }
}

function prefixerLigne(prefixe) {
  const z = $('#corps');
  const debut = z.value.lastIndexOf('\n', z.selectionStart - 1) + 1;
  z.setRangeText(prefixe, debut, debut, 'end');
  z.focus();
  etat.modifie = true;
}
function marqueMedia(chemin, image) {
  const nom = chemin.split('/').pop();
  return image ? `\n![${nom}](${chemin})\n` : `\n[${nom}](${chemin})\n`;
}

/* =====================================================================
   HISTORIQUE D'UNE PAGE
   =====================================================================
   La corbeille rattrape une page jetée. Elle ne rattrape RIEN d'un
   paragraphe supprimé puis enregistré — et c'est la faute la plus
   banale. Chaque écriture laisse maintenant une version ; celle-ci se
   relit, et se rétablit. */

async function ouvrirHistorique() {
  if (!etat.courant) return;
  const liste = $('#liste-versions');
  liste.textContent = '';
  $('#histo-texte').hidden = true;
  $('#histo-vide').hidden = false;
  $('#b-retablir').hidden = true;
  etat.versionChoisie = null;
  $('#fenetre-historique').showModal();

  let d;
  try {
    d = await api('/api/historique?f=' + encodeURIComponent(etat.courant));
  } catch (e) { return dire(e.message, true); }

  if (!d.possible) {
    $('#histo-vide').textContent =
      'Ce site n’est pas versionné : l’historique n’existe pas. '
      + '(Un « git init » dans le dossier du site suffit à l’activer.)';
    return;
  }
  if (!d.versions.length) {
    $('#histo-vide').textContent = 'Aucune version enregistrée pour cette page.';
    return;
  }

  d.versions.forEach((v, i) => {
    const li = document.createElement('li');
    const b = document.createElement('button');
    const quand = document.createElement('span');
    quand.className = 'quand';
    const d_ = new Date(v.quand * 1000);
    quand.textContent = `${dateDHorodatage(v.quand)} à ${String(d_.getHours()).padStart(2, '0')}h${String(d_.getMinutes()).padStart(2, '0')}`;
    if (i === 0) {
      const a = document.createElement('span');
      a.className = 'actuelle';
      a.textContent = ' — version actuelle';
      quand.appendChild(a);
    }
    const quoi = document.createElement('span');
    quoi.className = 'quoi';
    quoi.textContent = v.message.replace(/^atelier : /, '');
    quoi.title = v.message;
    b.append(quand, quoi);
    b.addEventListener('click', () => voirVersion(v, b));
    li.appendChild(b);
    liste.appendChild(li);
  });
}

async function voirVersion(v, bouton) {
  for (const x of document.querySelectorAll('#liste-versions button')) {
    x.classList.toggle('actif', x === bouton);
  }
  try {
    const d = await api(`/api/version?f=${encodeURIComponent(etat.courant)}&v=${v.version}`);
    $('#histo-vide').hidden = true;
    const zone = $('#histo-texte');
    zone.hidden = false;
    zone.textContent = d.corps;
    etat.versionChoisie = v.version;
    $('#b-retablir').hidden = false;
  } catch (e) { dire(e.message, true); }
}

async function retablirVersion() {
  if (!etat.versionChoisie) return;
  if (!confirm('Rétablir cette version de la page ?\n\n'
      + 'Le texte actuel sera remplacé. Rien n’est perdu : ce retour en '
      + 'arrière est lui-même une version, on peut en revenir.')) return;
  try {
    const d = await api('/api/retablir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fichier: etat.courant, version: etat.versionChoisie }),
    });
    $('#entete').value = d.entete;
    $('#corps').value = d.corps;
    etat.modifie = false;
    relireReglagesClairs();
    $('#fenetre-historique').close();
    await recharger();
    dire('Version rétablie — régénérez pour la voir sur le site.');
  } catch (e) { dire(e.message, true); }
}

/* =====================================================================
   MÉDIATHÈQUE
   ===================================================================== */

async function chargerMedias() {
  etat.medias = await api('/api/medias');
  dessinerBlocAtelier();
}

async function ouvrirMedias() {
  if (!etat.medias) {
    $('#grille-medias').textContent = 'Lecture des fichiers…';
    await chargerMedias().catch((e) => dire(e.message, true));
  }
  dessinerFiltresMedias();
  dessinerGrille();
  dessinerDetail();
}

function mediasVisibles() {
  const d = etat.medias;
  if (!d) return [];
  const f = etat.media;
  const q = aplatir($('#filtre').value.trim());
  let lot = d.medias.filter((m) => {
    if (f.usage === 'introuvables') return !m.existe;
    if (!m.existe) return false;                    // sinon ils polluent tout
    if (f.famille && m.famille !== f.famille) return false;
    if (f.usage === 'utilisees' && m.orphelin) return false;
    if (f.usage === 'orphelines' && !m.orphelin) return false;
    if (f.annee && m.annee !== f.annee) return false;
    return true;
  });
  if (q) lot = lot.filter((m) => aplatir(m.nom).includes(q) || aplatir(m.chemin).includes(q));
  const tris = {
    recents: (a, b) => b.ajoute - a.ajoute,
    anciens: (a, b) => a.ajoute - b.ajoute,
    nom: (a, b) => a.nom.localeCompare(b.nom, 'fr'),
    poids: (a, b) => b.poids - a.poids,
    usages: (a, b) => b.usages.length - a.usages.length,
  };
  return lot.sort(tris[f.tri] || tris.recents);
}

function dessinerFiltresMedias() {
  const d = etat.medias;
  const boite = $('#medias-filtres');
  boite.textContent = '';
  if (!d) return;

  const groupe = (titre, lignes) => {
    const t = document.createElement('p');
    t.className = 'rubrique';
    t.textContent = titre;
    boite.appendChild(t);
    for (const [cle, valeur, nom, nb, alerte] of lignes) {
      const b = document.createElement('button');
      b.className = (etat.media[cle] === valeur ? 'actif' : '') + (alerte ? ' alerte' : '');
      const n = document.createElement('span');
      n.className = 'nom';
      n.textContent = nom;
      const c = document.createElement('span');
      c.className = 'nb';
      c.textContent = nb;
      b.append(n, c);
      b.addEventListener('click', () => {
        etat.media[cle] = etat.media[cle] === valeur ? '' : valeur;
        dessinerFiltresMedias();
        dessinerGrille();
      });
      boite.appendChild(b);
    }
  };

  groupe('Type', [['famille', '', 'Tout', d.total, false],
    ...Object.entries(FAMILLES)
      .filter(([f]) => d.familles[f])
      .map(([f, nom]) => ['famille', f, nom, d.familles[f], false])]);

  // Le ménage à faire se voit en orange : 86 fichiers sur 133 ne servent
  // plus à rien — c'est le filtre le plus utile de la médiathèque.
  groupe('Usage', [
    ['usage', 'utilisees', 'Utilisées', d.utilisees, false],
    ['usage', 'orphelines', 'Orphelines', d.orphelines, true],
    ['usage', 'introuvables', 'Fichiers introuvables', d.introuvables, true],
  ]);

  // Nos dossiers réels sont des année/mois hérités de WordPress, pas des
  // thèmes : le filtre suit le rangement qui existe.
  const annees = Object.entries(d.annees).sort((a, b) => b[0].localeCompare(a[0]));
  if (annees.length) groupe('Année', annees.map(([a, n]) => ['annee', a, a, n, false]));

  const depot = document.createElement('div');
  depot.className = 'depot';
  depot.id = 'depot';
  depot.textContent = 'Glissez des fichiers ici pour les déposer';
  boite.appendChild(depot);
  brancherDepot(depot);
}

function vignette(m) {
  const b = document.createElement('button');
  b.className = 'vignette' + (etat.media.choisi === m.chemin ? ' choisie' : '')
    + (etat.media.selection.has(m.chemin) ? ' cochee' : '');

  const cadre = document.createElement('div');
  cadre.className = 'cadre' + (m.existe ? '' : ' manquant');
  if (!m.existe) {
    cadre.textContent = 'fichier introuvable';
  } else if (m.famille === 'image') {
    const i = new Image();
    i.src = m.chemin;
    i.loading = 'lazy';
    i.alt = '';
    cadre.appendChild(i);
  } else {
    const d = document.createElement('div');
    d.className = 'doc';
    d.textContent = m.famille === 'pdf' ? '📄' : m.famille === 'audio' ? '♪' : '▦';
    cadre.appendChild(d);
  }
  const badge = document.createElement('span');
  badge.className = 'badge';
  badge.textContent = m.type;
  cadre.appendChild(badge);
  // La case coche SANS ouvrir le détail : c'est elle qui sert à faire le
  // ménage en lot, la vignette elle-même sert à regarder le fichier.
  const coche = document.createElement('span');
  coche.className = 'coche';
  coche.textContent = '✓';
  coche.title = 'Sélectionner ce fichier';
  coche.addEventListener('click', (ev) => {
    ev.stopPropagation();
    if (etat.media.selection.has(m.chemin)) etat.media.selection.delete(m.chemin);
    else etat.media.selection.add(m.chemin);
    dessinerGrille();
  });
  cadre.appendChild(coche);
  b.appendChild(cadre);

  const corps = document.createElement('span');
  corps.className = 'corps-vignette';
  const nom = document.createElement('span');
  nom.className = 'nom';
  nom.textContent = m.nom;
  nom.title = m.chemin;
  const infos = document.createElement('span');
  infos.className = 'infos';
  const mesure = document.createElement('span');
  mesure.className = 'mesure';
  mesure.textContent = [m.dimensions ? m.dimensions.join('×') : '—',
                        m.existe ? poidsLisible(m.poids) : '—'].join(' · ');
  const usage = document.createElement('span');
  usage.className = 'usage' + (m.orphelin ? ' orpheline' : '');
  usage.textContent = m.orphelin ? 'orpheline'
    : `${m.usages.length} page${m.usages.length > 1 ? 's' : ''}`;
  infos.append(mesure, usage);
  corps.append(nom, infos);
  b.appendChild(corps);

  b.addEventListener('click', () => {
    etat.media.choisi = m.chemin;
    dessinerGrille();
    dessinerDetail();
    document.body.classList.add('detail-ouvert');
    // Le bandeau le promet : en mode insertion, le fichier cliqué part
    // dans la page, et l'on revient à ce qu'on était en train d'écrire.
    if (etat.media.insertion && m.existe) insererMedia(m);
  });
  return b;
}

function dessinerGrille() {
  const d = etat.medias;
  const grille = $('#grille-medias');
  grille.textContent = '';
  grille.className = 'medias-grille' + (etat.media.vue === 'liste' ? ' liste' : '');
  if (!d) return;

  const lot = mediasVisibles();
  $('#medias-meta').textContent =
    `${d.total} fichiers · ${poidsLisible(d.poids)} · ${d.orphelines} orphelines`
    + (lot.length !== d.total ? ` — ${lot.length} affichés` : '');
  majBarreSelection();
  if (!lot.length) {
    const p = document.createElement('p');
    p.className = 'astuce';
    p.textContent = 'Aucun fichier ne répond à ces filtres.';
    grille.appendChild(p);
    return;
  }
  for (const m of lot) grille.appendChild(vignette(m));
}

function majBarreSelection() {
  // EN MODE INSERTION, LA SÉLECTION SERT À INSÉRER, PAS À JETER.
  // Deux gestes cohabitaient sur la même vignette : cliquer l'image
  // insérait, cocher sa case sélectionnait pour la corbeille. Christophe
  // a coché, puis cherché en vain le bouton pour valider — le seul offert
  // était rouge et jetait le fichier. On montre donc l'action du mode.
  const enInsertion = !!etat.media.insertion;
  $('#b-inserer-selection').hidden = !enInsertion;
  $('#b-jeter-selection').hidden = enInsertion;
  const n = etat.media.selection.size;
  $('#barre-selection').hidden = !n;
  if (n) {
    const poids = [...etat.media.selection]
      .map((c) => (etat.medias.medias.find((m) => m.chemin === c) || {}).poids || 0)
      .reduce((a, b) => a + b, 0);
    $('#selection-compte').textContent =
      `${n} fichier${n > 1 ? 's' : ''} sélectionné${n > 1 ? 's' : ''} · ${poidsLisible(poids)}`;
  }
}

/* Le ménage en lot. Trois garde-fous, aucun n'est décoratif :
   — rien n'est détruit, tout va dans la corbeille des médias, d'où l'on
     peut remettre chaque fichier à sa place ;
   — le serveur REFUSE un fichier encore cité par une page ou un menu, et
     le dit ; le compte des refus est rendu à la fin ;
   — l'adresse d'un PDF a pu être partagée par courriel ou sur Facebook :
     aucune page du site n'y mène plus, mais un lien du dehors, si. La
     demande de confirmation le rappelle quand il y a des PDF dans le lot. */
async function jeterSelection() {
  const chemins = [...etat.media.selection];
  if (!chemins.length) return;
  const fiches = chemins.map((c) => etat.medias.medias.find((m) => m.chemin === c)).filter(Boolean);
  const pdf = fiches.filter((m) => m.famille === 'pdf').length;
  const utilises = fiches.filter((m) => !m.orphelin).length;

  let question = `Mettre ${chemins.length} fichier(s) à la corbeille ?\n\n`
    + 'Ils quitteront le site au prochain dépôt. La corbeille permet de les '
    + 'remettre tant qu’elle n’est pas vidée.';
  if (utilises) question += `\n\n${utilises} fichier(s) sont encore utilisés par des `
    + 'pages : ceux-là seront refusés, les autres partiront.';
  if (pdf) question += `\n\nAttention : ${pdf} PDF dans le lot. Aucune page du site n’y `
    + 'mène plus, mais leur adresse a pu être partagée par courriel ou sur les '
    + 'réseaux — ces liens-là cesseront de répondre.';
  if (!await confirmer('Mettre à la corbeille', question, 'Mettre à la corbeille', true)) return;

  let faits = 0;
  const refus = [];
  for (const chemin of chemins) {
    $('#selection-compte').textContent = `Suppression… ${faits + refus.length + 1} / ${chemins.length}`;
    try {
      await api('/api/supprimer-media', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chemin }),
      });
      faits += 1;
    } catch (e) {
      refus.push(chemin.split('/').pop());
    }
  }
  etat.media.selection.clear();
  etat.media.choisi = null;
  await chargerMedias();
  await recharger();
  dessinerFiltresMedias();
  dessinerGrille();
  dessinerDetail();
  dire(refus.length
    ? `${faits} fichier(s) à la corbeille — ${refus.length} refusé(s), encore utilisés : `
      + refus.slice(0, 3).join(', ') + (refus.length > 3 ? '…' : '')
    : `${faits} fichier(s) mis à la corbeille.`, !!refus.length);
}

function champAlt(m, lg) {
  const ligne = document.createElement('div');
  const auto = (m.alt_auto || []).includes(lg);
  const texte = m.alt[lg] || '';
  ligne.className = 'champ-alt' + (auto ? ' est-auto' : '') + (texte ? '' : ' est-vide');

  const past = document.createElement('span');
  past.className = 'past ' + (texte ? (auto ? 'auto' : 'pleine') : 'absente');
  past.textContent = lg[0].toUpperCase();
  past.title = NOMS_LANGUES[lg] || lg;

  const ta = document.createElement('textarea');
  ta.rows = 2;
  ta.value = texte;
  ta.placeholder = 'à renseigner';
  ta.setAttribute('aria-label', 'Texte alternatif ' + (NOMS_LANGUES[lg] || lg));
  ta.addEventListener('change', async () => {
    try {
      await api('/api/media-texte', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chemin: m.chemin, langue: lg, texte: ta.value, auto }),
      });
      m.alt[lg] = ta.value.trim();
      dire('Texte alternatif enregistré.');
      dessinerDetail();
    } catch (e) { dire(e.message, true); }
  });
  ligne.append(past, ta);
  return ligne;
}

function dessinerDetail() {
  const boite = $('#medias-detail');
  boite.textContent = '';
  const m = (etat.medias && etat.medias.medias.find((x) => x.chemin === etat.media.choisi)) || null;
  if (!m) {
    const p = document.createElement('p');
    p.className = 'detail-vide';
    p.textContent = 'Choisissez un fichier pour voir son détail, son texte alternatif et les pages qui l’utilisent.';
    boite.appendChild(p);
    return;
  }

  // sur écran étroit le volet couvre la grille : il lui faut une sortie
  const fermer = document.createElement('button');
  fermer.className = 'fermer-detail';
  fermer.textContent = '✕ Fermer le détail';
  fermer.addEventListener('click', () => document.body.classList.remove('detail-ouvert'));
  boite.appendChild(fermer);

  const defile = document.createElement('div');
  defile.className = 'detail-defile';

  if (m.existe && m.famille === 'image') {
    const i = new Image();
    i.className = 'detail-apercu';
    i.src = m.chemin;
    i.alt = '';
    defile.appendChild(i);
  }
  const nom = document.createElement('h2');
  nom.className = 'detail-nom';
  nom.textContent = m.nom;
  const meta = document.createElement('p');
  meta.className = 'detail-meta';
  meta.textContent = [m.type, m.dimensions ? m.dimensions.join('×') : null,
                      m.existe ? poidsLisible(m.poids) : 'absent du disque'].filter(Boolean).join(' · ')
    + (m.ajoute ? `\najouté le ${dateDHorodatage(m.ajoute)}` : '');
  defile.append(nom, meta);

  if (m.existe) {
    const actions = document.createElement('div');
    actions.className = 'detail-actions';
    const bRenommer = document.createElement('button');
    bRenommer.className = 'bouton';
    bRenommer.textContent = 'Renommer';
    bRenommer.addEventListener('click', () => renommerMedia(m));
    const bRemplacer = document.createElement('label');
    bRemplacer.className = 'bouton';
    bRemplacer.textContent = 'Remplacer';
    const champ = document.createElement('input');
    champ.type = 'file';
    champ.hidden = true;
    champ.addEventListener('change', () => remplacerMedia(m, champ.files[0]));
    bRemplacer.appendChild(champ);
    const bSupprimer = document.createElement('button');
    bSupprimer.className = 'bouton discret';
    bSupprimer.textContent = 'Supprimer';
    bSupprimer.addEventListener('click', () => supprimerMedia(m));
    actions.append(bRenommer, bRemplacer, bSupprimer);
    defile.appendChild(actions);

    const t = document.createElement('p');
    t.className = 'rubrique';
    t.textContent = 'Texte alternatif';
    defile.appendChild(t);
    for (const lg of etat.langues) defile.appendChild(champAlt(m, lg));
  }

  const tu = document.createElement('p');
  tu.className = 'rubrique';
  tu.style.marginTop = '1rem';
  tu.textContent = m.usages.length
    ? `Utilisée dans ${m.usages.length} page${m.usages.length > 1 ? 's' : ''}`
    : 'Aucune page ne l’utilise';
  defile.appendChild(tu);

  const ul = document.createElement('ul');
  ul.className = 'detail-usages';
  for (const u of m.usages) {
    const li = document.createElement('li');
    const b = document.createElement('button');
    const titre = document.createElement('span');
    titre.className = 'titre';
    titre.textContent = u.titre;
    // ici la pastille dit seulement DANS QUELLE LANGUE est la page : elle
    // reste pleine pour les trois, sans quoi l'orange voudrait dire deux
    // choses différentes sur le même écran (auto, et italien).
    const past = document.createElement('span');
    past.className = 'past pleine';
    past.textContent = (u.langue || '?')[0].toUpperCase();
    b.append(titre, past);
    b.addEventListener('click', () => {
      if (u.fichier.endsWith('.yaml')) return dire('C’est un menu : ouvrez « Menus du site ».');
      changerLangue(u.langue);
      ouvrir(u.fichier);
    });
    li.appendChild(b);
    ul.appendChild(li);
  }
  defile.appendChild(ul);
  boite.appendChild(defile);

  if (etat.media.insertion && m.existe) {
    const pied = document.createElement('div');
    pied.className = 'detail-pied';
    const b = document.createElement('button');
    b.className = 'bouton primaire';
    b.textContent = 'Insérer dans la page';
    b.addEventListener('click', () => insererMedia(m));
    pied.appendChild(b);
    boite.appendChild(pied);
  }
}

function insererMedia(m) {
  const cible = etat.media.insertion;
  if (!cible) return;
  /* Le même clic sert deux buts : insérer dans le texte, ou choisir la
     vignette de la tuile. Un seul mode d'insertion, deux destinations —
     plutôt qu'un second écran de sélection qui ferait double emploi. */
  if (cible.but === 'vignette') {
    if (m.famille !== 'image') return dire('Une vignette doit être une image.', true);
    poserCle('vignette', m.chemin);
    relireReglagesClairs();
    quitterInsertion();
    montrerEcran('editeur');
    montrerVue('entete');
    return dire('Vignette choisie — pensez à enregistrer.');
  }
  inserer(marqueMedia(m.chemin, m.famille === 'image'));
  quitterInsertion();
  montrerEcran('editeur');
  dire('Inséré dans la page.');
}

/* Insère tout ce qui est coché, dans l'ordre de la grille. Un seul
   fichier est le cas courant, mais rien n'oblige à s'y tenir. */
function insererLaSelection() {
  if (!etat.media.insertion) return;
  const choisis = ((etat.medias || {}).medias || []).filter(
    (m) => etat.media.selection.has(m.chemin) && m.existe);
  if (!choisis.length) return dire('Cochez d’abord un fichier.', true);
  if (etat.media.insertion.but === 'vignette') {
    /* Une tuile n'a qu'une bande : on prend la première image cochée et on
       le DIT, plutôt que d'en poser une au hasard sans prévenir. */
    const img = choisis.find((m) => m.famille === 'image');
    if (!img) return dire('Une vignette doit être une image.', true);
    poserCle('vignette', img.chemin);
    relireReglagesClairs();
    etat.media.selection.clear();
    quitterInsertion();
    montrerEcran('editeur');
    montrerVue('entete');
    return dire(choisis.length > 1
      ? 'Vignette choisie : la première image cochée. Pensez à enregistrer.'
      : 'Vignette choisie — pensez à enregistrer.');
  }
  for (const m of choisis) inserer(marqueMedia(m.chemin, m.famille === 'image'));
  etat.media.selection.clear();
  quitterInsertion();
  montrerEcran('editeur');
  dire(choisis.length === 1 ? 'Inséré dans la page.'
                            : `${choisis.length} fichiers insérés dans la page.`);
}

function quitterInsertion() {
  etat.media.insertion = null;
  $('#bandeau-insertion').hidden = true;
}

async function renommerMedia(m) {
  const bout = m.nom.replace(/\.[^.]+$/, '');
  const neuf = await demander({
    titre: 'Renommer le fichier',
    texte: 'Sans l’extension. L’ancienne adresse cessera de répondre ; les liens '
           + 'du site seront recousus, mais pas ceux venus du dehors.',
    champ: bout,
    valider: 'Renommer',
  });
  if (!neuf || neuf === bout) return;
  try {
    const d = await api('/api/renommer-media', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chemin: m.chemin, nom: neuf }),
    });
    etat.media.choisi = d.chemin;
    await chargerMedias();
    dessinerGrille();
    dessinerDetail();
    dire(d.liens_recousus ? `Renommé, ${d.liens_recousus} lien(s) recousu(s).` : 'Renommé.');
  } catch (e) { dire(e.message, true); }
}

async function remplacerMedia(m, fichier) {
  if (!fichier) return;
  if (!await confirmer(`Remplacer « ${m.nom} » ?`,
      `Par « ${fichier.name} ». L’adresse ne change pas : toutes les pages qui `
      + 'l’affichent montreront le nouveau fichier.', 'Remplacer', true)) return;
  try {
    await api('/api/televerser', {
      method: 'POST',
      headers: { 'X-Nom-Fichier': encodeURIComponent(fichier.name),
                 'X-Remplacer': encodeURIComponent(m.chemin) },
      body: fichier,
    });
    await chargerMedias();
    dessinerGrille();
    dessinerDetail();
    dire('Fichier remplacé — cliquez « Régénérer » pour le voir sur le site.');
  } catch (e) { dire(e.message, true); }
}

async function supprimerMedia(m) {
  if (!await confirmer(`Mettre « ${m.nom} » à la corbeille ?`,
      'Il ne sera plus proposé ici, et disparaîtra du site au prochain dépôt. '
      + 'La corbeille permet de le remettre.', 'Mettre à la corbeille', true)) return;
  try {
    await api('/api/supprimer-media', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chemin: m.chemin }),
    });
    etat.media.choisi = null;
    await chargerMedias();
    await recharger();
    dessinerFiltresMedias();
    dessinerGrille();
    dessinerDetail();
    dire('Fichier mis à la corbeille.');
  } catch (e) { dire(e.message, true); }
}

async function televerser(fichiers) {
  const derniers = [];
  for (const f of fichiers) {
    try {
      derniers.push(await api('/api/televerser', {
        method: 'POST',
        headers: { 'X-Nom-Fichier': encodeURIComponent(f.name) },
        body: f,
      }));
    } catch (e) { dire(`${f.name} : ${e.message}`, true); }
  }
  if (derniers.length) {
    await chargerMedias();
    await recharger();
    if (etat.ecran === 'medias') { dessinerFiltresMedias(); dessinerGrille(); }
    // dire ce qui a été fait de la photo : une réduction silencieuse
    // laisserait croire que le fichier d'origine est parti en ligne.
    const r = derniers.filter((d) => d.reduite);
    dire(r.length
      ? `${derniers.length} fichier(s) déposé(s) — ${r.length} photo(s) ramenée(s) à `
        + `${r[0].reduite.apres} (${Math.round(r[0].reduite.octets_avant / 1024)} ko → `
        + `${Math.round(r[0].reduite.octets_apres / 1024)} ko).`
      : `${derniers.length} fichier(s) déposé(s).`);
  }
  return derniers;
}

function brancherDepot(zone) {
  ['dragenter', 'dragover'].forEach((n) => zone.addEventListener(n, (e) => {
    e.preventDefault();
    zone.classList.add('survol');
  }));
  ['dragleave', 'drop'].forEach((n) => zone.addEventListener(n, (e) => {
    e.preventDefault();
    zone.classList.remove('survol');
  }));
  zone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files.length) televerser(e.dataTransfer.files);
  });
}

/* =====================================================================
   MENUS
   ===================================================================== */
/* Le menu est la seule chose du site qu'aucune page ne rattrape : une
   rubrique perdue rend ses pages introuvables alors qu'elles existent
   toujours. D'où le travail sur une COPIE en mémoire, et l'écriture
   seulement quand on appuie sur Enregistrer. */

async function chargerMenu(langue) {
  const d = await api('/api/menu?langue=' + encodeURIComponent(langue));
  etat.menu = { langue, entrees: d.entrees, pages: d.pages, medias: d.medias };
  dessinerMenu();
}

function dessinerMenu() {
  const ol = $('#liste-menu');
  ol.textContent = '';
  const n = etat.menu.entrees.length;
  etat.menu.entrees.forEach((e, i) => {
    const suivante = etat.menu.entrees[i + 1];
    const rubrique = !!suivante && suivante.profondeur > e.profondeur;

    const li = document.createElement('li');
    li.dataset.profondeur = e.profondeur;
    if (rubrique) li.classList.add('rubrique-menu');

    const marque = document.createElement('span');
    marque.className = 'marque-menu';
    marque.textContent = rubrique ? '▸' : '•';
    marque.title = rubrique ? 'rubrique' : 'lien';

    const titre = document.createElement('span');
    titre.className = 'titre';
    const it = document.createElement('input');
    it.value = e.titre;
    it.setAttribute('aria-label', 'Intitulé');
    it.addEventListener('input', () => { e.titre = it.value; });
    titre.appendChild(it);

    const lien = document.createElement('span');
    lien.className = 'lien-champ';
    const il = document.createElement('input');
    il.value = e.lien || '';
    il.setAttribute('list', 'adresses-connues');
    il.placeholder = rubrique ? '— rubrique, pas de lien —' : 'adresse';
    il.disabled = rubrique;
    il.addEventListener('input', () => { e.lien = il.value; });
    lien.appendChild(il);

    const bouton = (texte, titre_, action, classe) => {
      const b = document.createElement('button');
      b.textContent = texte;
      b.title = titre_;
      if (classe) b.className = classe;
      b.addEventListener('click', () => { action(); dessinerMenu(); });
      return b;
    };
    const permute = (a, b) => {
      const t = etat.menu.entrees[a];
      etat.menu.entrees[a] = etat.menu.entrees[b];
      etat.menu.entrees[b] = t;
    };
    li.append(marque, titre, lien,
      bouton('↑', 'Monter', () => { if (i > 0) permute(i, i - 1); }),
      bouton('↓', 'Descendre', () => { if (i < n - 1) permute(i, i + 1); }),
      bouton('←', 'Sortir de la rubrique', () => { if (e.profondeur > 0) e.profondeur--; }),
      bouton('→', 'Ranger sous celle du dessus', () => {
        const max = i === 0 ? 0 : etat.menu.entrees[i - 1].profondeur + 1;
        if (e.profondeur < Math.min(2, max)) e.profondeur++;
      }),
      bouton('✕', 'Ôter cette entrée', async () => {
        if (await confirmer('Ôter du menu ?', '« ' + e.titre + ' » ne figurera '
            + 'plus dans le menu du site.', 'Ôter', true)) etat.menu.entrees.splice(i, 1);
      }, 'oter'));
    ol.appendChild(li);
  });

  let dl = document.getElementById('adresses-connues');
  if (!dl) {
    dl = document.createElement('datalist');
    dl.id = 'adresses-connues';
    document.body.appendChild(dl);
  }
  dl.textContent = '';
  for (const p of etat.menu.pages) dl.appendChild(new Option(p.titre, p.url));
  for (const m of etat.menu.medias) dl.appendChild(new Option(m, m));
}

/* =====================================================================
   CORBEILLE
   ===================================================================== */

function dessinerCorbeille() {
  const ul = $('#liste-corbeille');
  ul.textContent = '';
  const jetees = etat.corbeille || [];
  if (!jetees.length) {
    const li = document.createElement('li');
    li.textContent = 'La corbeille est vide.';
    ul.appendChild(li);
    return;
  }
  for (const x of jetees) {
    const li = document.createElement('li');
    const t = document.createElement('span');
    t.textContent = x.titre;
    if (x.media) {
      const e = document.createElement('span');
      e.className = 'etiq';
      e.textContent = 'média';
      e.style.marginLeft = '.4em';
      t.appendChild(e);
    }
    const c = document.createElement('span');
    c.className = 'chemin';
    c.textContent = x.fichier;
    const b = document.createElement('button');
    b.className = 'bouton discret';
    b.textContent = 'Remettre';
    b.addEventListener('click', async () => {
      try {
        // une page et un média ne se remettent pas au même endroit
        await api(x.media ? '/api/restaurer-media' : '/api/restaurer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fichier: x.fichier }),
        });
        if (x.media) await chargerMedias();
        await recharger();
        dessinerCorbeille();
        dire('Remis en place.');
      } catch (e) { dire(e.message, true); }
    });
    li.append(t, c, b);
    ul.appendChild(li);
  }
}

/* =====================================================================
   CHARGEMENT ET DÉMARRAGE
   ===================================================================== */

async function recharger() {
  const d = await api('/api/liste');
  etat.pages = d.pages;
  etat.langues = d.langues;
  etat.iaDistante = !!d.ia_distante;
  $('#code-perime').hidden = !d.code_perime;
  etat.menus = d.menus || {};
  etat.en_attente = d.en_attente || 0;
  etat.jamais_publie = !!d.jamais_publie;
  etat.derniere_publication = d.derniere_publication || '';
  if (!etat.langues.includes(etat.langue)) etat.langue = etat.langues[0];

  /* Le nom du site vient de config.yaml, jamais du code. Trois libellés
     l'affichaient en dur — et le pire était celui de la fenêtre de
     publication : « le site public — dentosophie.com » aurait menti au
     moment le plus dangereux le jour où l'atelier sert un autre site. */
  etat.site = d.site || {};
  const marque = etat.site.titre || 'Le site';
  $('#marque').textContent = marque;
  document.title = `L'atelier — ${marque}`;
  const dom = (etat.site.domaine || '').replace(/^https?:\/\//, '').replace(/\/$/, '');
  $('#nom-domaine').textContent = dom
    ? `${dom}, celui que tout le monde voit`
    : 'celui que tout le monde voit';

  /* « Enregistrer » écrit sur le disque ; « Publier » seul change ce que
     voient les autres. Les deux mots se ressemblaient trop : on
     enregistrait vingt fois en croyant publier. Le bouton porte donc le
     COMPTE de ce qui attend. */
  const bp = $('#b-mettre-en-ligne');
  bp.textContent = etat.en_attente
    ? `Publier en ligne (${etat.en_attente})…` : 'Publier en ligne…';
  bp.title = etat.jamais_publie
    ? 'Le site n’a jamais été publié depuis cet ordinateur.'
    : (etat.en_attente
        ? `${etat.en_attente} page(s) enregistrée(s) depuis la dernière publication `
          + `(${etat.derniere_publication}). Elles ne sont pas encore visibles.`
        : `Tout est publié — dernière fois le ${etat.derniere_publication}.`);

  const nl = $('#nouveau-langue');
  if (!nl.options.length) for (const l of etat.langues) nl.add(new Option(l, l));
  const sa = $('#filtre-annee');
  if (sa.options.length <= 1) {
    // Les années viennent des DATES existantes, pas d'un intervalle deviné.
    const annees = [...new Set(etat.pages.map((p) => String(p.date || '').slice(0, 4))
                                         .filter((a) => /^\d{4}$/.test(a)))].sort().reverse();
    for (const a of annees) sa.add(new Option(a, a));
  }

  etat.corbeille = await api('/api/corbeille').then((c) => c.corbeille).catch(() => []);
  dessinerLangues();
  $('#rail-langue').textContent = NOMS_LANGUES[etat.langue] || etat.langue.toUpperCase();
  dessinerBlocAtelier();
  dessinerArbre();
  if (etat.ecran === 'tableau') dessinerTableau();
}

function majCollectionsNouvelle() {
  /* « Ranger dans » ne propose QUE les rubriques de la langue choisie.
     La liste complète mélangeait les trois langues, anglais en tête — et
     cinq rubriques anglaises portent le MÊME nom de dossier que les
     françaises : la fiche pouvait naître dans la mauvaise langue. */
  const lg = $('#nouveau-langue').value;
  const nc = $('#nouveau-collection');
  while (nc.options.length > 1) nc.remove(1);
  for (const p of etat.pages.filter((x) => x.type === 'collection' && x.langue === lg)) {
    nc.add(new Option(p.titre, p.fichier.split('/')[1]));
  }
  $('#choix-place').hidden = !nc.value;
}

document.addEventListener('DOMContentLoaded', async () => {
  brancherPoignee();
  /* Sur un Mac, le raccourci est ⌘K et non Ctrl K — le gestionnaire
     accepte déjà les deux, seul l'indice affiché mentait. */
  if (/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) {
    const indice = document.querySelector('.rail-recherche kbd');
    if (indice) indice.textContent = '\u2318 K';
  }
  await recharger();
  await chargerMedias().catch(() => {});
  montrerEcran('tableau');

  /* --- rail --- */
  for (const b of document.querySelectorAll('.bloc-atelier .entree')) {
    b.addEventListener('click', () => montrerEcran(b.dataset.ecran));
  }
  $('#b-rail').addEventListener('click', () =>
    document.body.classList.toggle('rail-ouvert'));
  $('#filtre').addEventListener('input', () => {
    // l'arbre suit toujours : sinon, en revenant des médias, il resterait
    // filtré sur une recherche de fichier qu'on ne voit plus.
    dessinerArbre();
    if (etat.ecran === 'medias') dessinerGrille();
    if (etat.ecran === 'pages' || etat.ecran === 'fiches' || etat.ecran === 'brouillons') {
      dessinerListe(etat.ecran);
    }
  });
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); $('#filtre').focus(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      enregistrer().catch((x) => dire(x.message, true));
    }
  });

  /* --- filtres --- */
  const pop = $('#popover-filtres');
  const majFiltres = () => {
    const n = filtresActifs();
    $('#nb-filtres').textContent = n;
    $('#nb-filtres').hidden = !n;
    dessinerArbre();
    if (etat.ecran === 'pages' || etat.ecran === 'fiches' || etat.ecran === 'brouillons') {
      dessinerListe(etat.ecran);
    }
  };
  $('#b-filtres').addEventListener('click', () => { pop.hidden = !pop.hidden; });
  $('#b-filtres-fermer').addEventListener('click', () => { pop.hidden = true; });
  $('#filtre-type').addEventListener('change', (e) => { etat.filtres.type = e.target.value; majFiltres(); });
  $('#filtre-annee').addEventListener('change', (e) => { etat.filtres.annee = e.target.value; majFiltres(); });
  $('#filtre-etat').addEventListener('change', (e) => { etat.filtres.etat = e.target.value; majFiltres(); });
  $('#b-filtres-effacer').addEventListener('click', () => {
    etat.filtres = { type: '', annee: '', etat: '' };
    $('#filtre-type').value = ''; $('#filtre-annee').value = ''; $('#filtre-etat').value = '';
    majFiltres();
  });
  document.addEventListener('click', (e) => {
    if (!pop.hidden && !e.target.closest('.enveloppe-filtres')) pop.hidden = true;
  });

  /* --- éditeur --- */
  $('#corps').addEventListener('input', () => { etat.modifie = true; });
  $('#entete').addEventListener('input', () => { etat.modifie = true; relireReglagesClairs(); });
  for (const o of document.querySelectorAll('.onglet')) {
    o.addEventListener('click', () => montrerVue(o.dataset.vue));
  }
  for (const b of document.querySelectorAll('[data-autour]')) {
    b.addEventListener('click', () => entourer(b.dataset.autour));
  }
  for (const b of document.querySelectorAll('[data-ligne]')) {
    b.addEventListener('click', () => prefixerLigne(b.dataset.ligne));
  }
  for (const b of document.querySelectorAll('[data-inserer]')) {
    b.addEventListener('click', () => inserer(b.dataset.inserer));
  }
  for (const b of document.querySelectorAll('[data-avant]')) {
    b.addEventListener('click', () => encadrer(b.dataset.avant, b.dataset.apres));
  }
  for (const b of document.querySelectorAll('[data-bloc]')) {
    b.addEventListener('click', () => envelopper(b.dataset.bloc));
  }
  poserApercusDOutils();
  $('#b-enregistrer').addEventListener('click', () => enregistrer().catch((e) => dire(e.message, true)));
  $('#b-traduire').addEventListener('click', () => traduireLaPage().catch((e) => dire(e.message, true)));
  $('#b-traduire-tout').addEventListener('click', () => traduirePartout().catch((e) => dire(e.message, true)));
  $('#b-publier-brouillons').addEventListener('click', () => publierLesBrouillons().catch((e) => dire(e.message, true)));

  $('#r-statut').addEventListener('change', (e) => {
    poserCle('statut', e.target.value);
    $('#avis-brouillon').hidden = e.target.value === 'publie';
  });
  $('#b-publier-page').addEventListener('click', async () => {
    poserCle('statut', 'publie');
    relireReglagesClairs();
    try {
      await enregistrer();
      const suivi = await publierLesTraductions(etat.courant);
      dire('Page mise en ligne'
           + (suivi ? `, avec ses ${suivi} traduction(s)` : '')
           + ' — cliquez « Régénérer » pour la voir.');
    } catch (e) { dire(e.message, true); }
  });
  $('#r-date').addEventListener('change', (e) => poserCle('date', e.target.value));
  $('#r-rang').addEventListener('change', (e) => poserCle('rang', e.target.value));
  /* « aucun » RETIRE la clé plutôt que d'écrire « non » : une clé absente
     et une clé à « non » disent la même chose, et le générateur refuse
     toute valeur qu'il ne connaît pas — mieux vaut ne rien écrire. */
  $('#r-sommaire').addEventListener('change', (e) => poserCle('sommaire', e.target.value));
  $('#b-vignette-choisir').addEventListener('click', () => {
    if (!etat.courant) return dire('Ouvrez d’abord une page.', true);
    const p = etat.pages.find((x) => x.fichier === etat.courant);
    etat.media.insertion = { fichier: etat.courant, titre: p ? p.titre : etat.courant,
                             but: 'vignette' };
    $('#insertion-quoi').textContent =
      'Choix d’une vignette — l’image cliquée coiffera la tuile de';
    $('#insertion-page').textContent = etat.media.insertion.titre;
    $('#bandeau-insertion').hidden = false;
    majBarreSelection();
    montrerEcran('medias');
  });
  $('#b-vignette-retirer').addEventListener('click', () => {
    poserCle('vignette', '');
    relireReglagesClairs();
    dire('Vignette retirée — pensez à enregistrer.');
  });
  /* Cocher écrit la ligne, décocher la RETIRE — plutôt que d'écrire
     « non » : une clé absente et une clé à « non » disent la même chose. */
  $('#r-auto').addEventListener('change', (e) =>
    poserCle('traduction_automatique', e.target.checked ? 'oui' : ''));
  $('#r-sans-jumelle').addEventListener('change', (e) =>
    poserCle('jumelle_attendue', e.target.checked ? 'non' : ''));

  $('#b-voir').addEventListener('click', async () => {
    const p = etat.pages.find((x) => x.fichier === etat.courant);
    if (!p) return;
    /* « Voir » ouvre la page ENGENDRÉE, pas ce qu'on vient d'écrire. Sans
       cet avertissement on relisait l'ancienne version en croyant avoir
       raté sa correction. */
    if (etat.modifie && await confirmer('Modifications non enregistrées',
        '« Voir » montre la page telle qu’elle a été engendrée : vos changements '
        + 'n’y seront pas.', 'Enregistrer d’abord')) {
      await enregistrer().catch((e) => dire(e.message, true));
    }
    if (!p.engendree) {
      if (!await confirmer('Page jamais engendrée',
          '« Voir » ne trouverait rien. Régénérer le site maintenant ?',
          'Régénérer')) return;
      await regenerer();
    } else if (!p.a_jour) {
      if (await confirmer('Page changée depuis la dernière fabrication',
          '« Voir » montrerait l’ancienne version.', 'Régénérer d’abord')) {
        await regenerer();
      }
    }
    /* L'adresse vient du serveur (p.url) : il la calcule exactement comme
       le générateur. La refabriquer depuis le nom du fichier cassait les
       trois pages d'accueil, servies à /fr/ et non à /fr/introduction/. */
    window.open('/apercu' + p.url, '_blank', 'noopener');
  });

  $('#b-supprimer').addEventListener('click', async () => {
    if (!etat.courant) return;
    // SUPPRIMER L'ORIGINAL LAISSAIT SES TRADUCTIONS SEULES. Christophe a
    // jeté la page française de « Test 8 » : les versions italienne et
    // anglaise sont restées, publiées, sans original — le site italien
    // portait un témoignage que le français n'avait pas. C'est la
    // symétrie de « publier une page publie ses traductions ».
    // On ne propose que les traductions MACHINE : une page traduite par
    // quelqu'un ne se jette pas dans la foulée d'une autre.
    const soeurs = traductionsMachineDe(etat.courant);
    const langues = soeurs.map((p) => NOMS_LANGUES[p.langue] || p.langue).join(', ');
    let texte = 'Elle sortira du site au prochain dépôt. La corbeille permet de la remettre.';
    if (soeurs.length === 1) {
      texte += '\n\nSa traduction automatique (' + langues + ') partira avec elle : '
               + 'sans original, elle resterait seule en ligne.';
    } else if (soeurs.length) {
      texte += '\n\nSes ' + soeurs.length + ' traductions automatiques (' + langues
               + ') partiront avec elle : sans original, elles resteraient seules '
               + 'en ligne.';
    }
    if (!await confirmer('Mettre cette page à la corbeille ?', texte,
        'Mettre à la corbeille', true)) return;
    try {
      for (const s of soeurs) {
        await api('/api/supprimer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fichier: s.fichier }),
        }).catch(() => {});
      }
      await api('/api/supprimer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fichier: etat.courant }),
      });
      etat.courant = null;
      etat.modifie = false;
      await recharger();
      montrerEcran('tableau');
      dire(soeurs.length === 1
        ? 'Page et sa traduction déplacées dans la corbeille.'
        : soeurs.length
          ? `Page et ses ${soeurs.length} traductions déplacées dans la corbeille.`
          : 'Déplacée dans site/contenu/.corbeille/');
    } catch (e) { dire(e.message, true); }
  });

  $('#b-renommer').addEventListener('click', async () => {
    if (!etat.courant) return;
    const p = etat.pages.find((x) => x.fichier === etat.courant);
    const actuelle = p ? p.url : '';
    const bout = actuelle.replace(/\/$/, '').split('/').pop();
    const neuf = await demander({
      titre: 'Nouvelle adresse de la page',
      texte: 'L’ancienne (' + actuelle + ') cessera de répondre ; les liens du '
             + 'site seront recousus, mais pas ceux venus du dehors.',
      champ: bout,
      valider: 'Changer l’adresse',
    });
    if (!neuf || neuf === bout) return;
    try {
      const d = await api('/api/renommer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fichier: etat.courant, slug: neuf }),
      });
      await recharger();
      await ouvrir(d.fichier);
      dire(d.liens_recousus
        ? 'Adresse changée, ' + d.liens_recousus + ' lien(s) recousu(s).'
        : 'Adresse changée.');
    } catch (e) { dire(e.message, true); }
  });

  $('#b-historique').addEventListener('click', () =>
    ouvrirHistorique().catch((e) => dire(e.message, true)));
  $('#b-fermer-historique').addEventListener('click', () => $('#fenetre-historique').close());
  $('#b-retablir').addEventListener('click', () => retablirVersion());

  $('#b-jumelle').addEventListener('click', async () => {
    if (!etat.courant) return;
    const ici = etat.courant.split('/')[0];
    const autres = etat.langues.filter((l) => l !== ici);
    if (!autres.length) return dire('Il n’y a qu’une langue.', true);
    const vers = autres.length === 1 ? autres[0] : await demander({
      titre: 'Créer la page jumelle',
      texte: 'Elle naîtra en brouillon, avec le texte français dedans, à remplacer '
             + 'au fil de la lecture.',
      choix: autres.map((l) => ({ valeur: l, libelle: NOMS_LANGUES[l] || l })),
      valider: 'Créer la jumelle',
    });
    if (vers) creerJumelle(etat.courant, vers);
  });

  /* --- médias --- */
  $('#b-inserer-media').addEventListener('click', () => {
    if (!etat.courant) return dire('Ouvrez d’abord une page.', true);
    const p = etat.pages.find((x) => x.fichier === etat.courant);
    etat.media.insertion = { fichier: etat.courant, titre: p ? p.titre : etat.courant,
                             but: 'texte' };
    $('#insertion-quoi').textContent =
      'Mode insertion — le fichier cliqué sera inséré dans';
    $('#insertion-page').textContent = etat.media.insertion.titre;
    $('#bandeau-insertion').hidden = false;
    majBarreSelection();
    montrerEcran('medias');
  });
  $('#b-quitter-insertion').addEventListener('click', () => {
    quitterInsertion();
    montrerEcran('editeur');
  });
  $('#fichier').addEventListener('change', (e) => televerser(e.target.files));
  $('#medias-tri').addEventListener('change', (e) => { etat.media.tri = e.target.value; dessinerGrille(); });
  $('#b-vue-grille').addEventListener('click', () => {
    etat.media.vue = 'grille';
    $('#b-vue-grille').classList.add('actif');
    $('#b-vue-liste').classList.remove('actif');
    dessinerGrille();
  });
  $('#b-vue-liste').addEventListener('click', () => {
    etat.media.vue = 'liste';
    $('#b-vue-liste').classList.add('actif');
    $('#b-vue-grille').classList.remove('actif');
    dessinerGrille();
  });
  brancherDepot($('#grille-medias'));
  $('#b-tout-selectionner').addEventListener('click', () => {
    // « tout » = tout ce que les filtres montrent en ce moment. Coché
    // depuis « Orphelines », c'est exactement le lot à faire disparaître.
    for (const m of mediasVisibles()) etat.media.selection.add(m.chemin);
    dessinerGrille();
  });
  $('#b-inserer-selection').addEventListener('click', () => insererLaSelection());
  $('#b-rien-selectionner').addEventListener('click', () => {
    etat.media.selection.clear();
    dessinerGrille();
  });
  $('#b-jeter-selection').addEventListener('click', () =>
    jeterSelection().catch((e) => dire(e.message, true)));

  /* glisser-déposer dans le texte */
  const zone = $('#vue-ecrire');
  ['dragenter', 'dragover'].forEach((n) => zone.addEventListener(n, (e) => {
    e.preventDefault();
    zone.classList.add('survol');
  }));
  ['dragleave', 'drop'].forEach((n) => zone.addEventListener(n, (e) => {
    e.preventDefault();
    if (n === 'dragleave' && zone.contains(e.relatedTarget)) return;
    zone.classList.remove('survol');
  }));
  zone.addEventListener('drop', async (e) => {
    if (!e.dataTransfer.files.length) return;
    if (!etat.courant) return dire('Ouvrez d’abord une page.', true);
    const deposes = await televerser(e.dataTransfer.files);
    for (const d of deposes) inserer(marqueMedia(d.chemin, d.image));
  });

  /* --- nouvelle page --- */
  const fn = $('#fenetre-nouveau');
  $('#b-nouveau').addEventListener('click', () => {
    $('#nouveau-langue').value = etat.langue;
    majCollectionsNouvelle();
    fn.showModal();
  });
  $('#nouveau-langue').addEventListener('change', majCollectionsNouvelle);
  $('#nouveau-collection').addEventListener('change', (e) => {
    $('#choix-place').hidden = !e.target.value;
  });
  fn.addEventListener('close', async () => {
    if (fn.returnValue !== 'creer') return;
    const f = fn.querySelector('form');
    try {
      const d = await api('/api/creer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          titre: f.titre.value, langue: f.langue.value, collection: f.collection.value,
          place: f.place ? f.place.value : 'tete',
        }),
      });
      const collection = f.collection.value;
      f.reset();
      await recharger();
      await ouvrir(d.fichier);
      dire(collection ? 'Fiche créée en tête de rubrique, en brouillon.'
                      : 'Page créée — elle est en brouillon.');
    } catch (e) { dire(e.message, true); }
  });

  /* --- menus --- */
  $('#b-menu-ajouter').addEventListener('click', () => {
    etat.menu.entrees.push({ titre: 'Nouvelle entrée', lien: '', profondeur: 0 });
    dessinerMenu();
  });
  $('#b-menu-enregistrer').addEventListener('click', async () => {
    try {
      const d = await api('/api/menu', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ langue: etat.menu.langue, entrees: etat.menu.entrees }),
      });
      etat.menu.entrees = d.entrees;
      dessinerMenu();
      await recharger();
      dire('Menu enregistré — cliquez « Régénérer » pour le voir sur le site.');
    } catch (e) { dire(e.message, true); }
  });

  /* --- corbeille --- */
  $('#b-vider').addEventListener('click', async () => {
    if (!await confirmer('Vider la corbeille ?',
        'Tout ce qu’elle contient sera détruit pour de bon. Rien ne se rattrape après.',
        'Détruire pour de bon', true)) return;
    try {
      const d = await api('/api/vider-corbeille', { method: 'POST' });
      await chargerMedias().catch(() => {});
      await recharger();
      dessinerCorbeille();
      dire(d.detruits.length
        ? d.detruits.length + ' élément(s) détruits pour de bon.'
        : 'La corbeille était déjà vide.');
    } catch (e) { dire(e.message, true); }
  });

  /* --- régénérer --- */
  const fp = $('#fenetre-publier');
  async function regenerer() {
    $('#journal-publier').textContent = 'Régénération en cours…';
    fp.showModal();
    try {
      const d = await api('/api/generer', { method: 'POST' });
      $('#journal-publier').textContent = d.sortie + '\n' + d.verification;
      await recharger();
    } catch (e) {
      $('#journal-publier').textContent = 'Échec : ' + e.message;
    }
  }
  window.regenerer = regenerer;
  $('#b-fermer-publier').addEventListener('click', () => fp.close());
  $('#b-publier').addEventListener('click', async () => {
    if (etat.modifie && await confirmer('Page non enregistrée',
        'Enregistrer la page ouverte avant de régénérer ?', 'Enregistrer')) {
      await enregistrer().catch(() => {});
    }
    regenerer();
  });

  /* --- mettre en ligne : essai à blanc d'abord, dépôt réel sur demande --- */
  const fl = $('#fenetre-ligne');
  $('#b-fermer-ligne').addEventListener('click', () => fl.close());
  const destination = () =>
    (document.querySelector('input[name=destination]:checked') || {}).value || 'maison';

  /* Changer de destination remet tout à zéro : un essai à blanc fait pour
     la maison ne dit RIEN de ce qui partirait en ligne — les deux serveurs
     n'ont pas le même contenu. */
  function majDestination() {
    const enLigne = destination() === 'en-ligne';
    $('#bloc-public').hidden = !enLigne;
    $('#b-deposer').hidden = true;
    $('#journal-ligne').textContent = '';
    $('#ligne-ou').textContent = '';
  }
  document.querySelectorAll('input[name=destination]')
    .forEach((r) => r.addEventListener('change', majDestination));

  async function mettreEnLigne(pourDeVrai) {
    const ou = destination();
    const enLigne = ou === 'en-ligne';
    $('#b-deposer').hidden = true;
    $('#journal-ligne').textContent = pourDeVrai
      ? 'Dépôt en cours — ne fermez pas cette fenêtre…'
      : 'Essai à blanc : régénération, vérification, puis liste de ce qui PARTIRAIT…';
    try {
      const d = await api('/api/publier', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pour_de_vrai: !!pourDeVrai, ou,
          confirmation: enLigne ? $('#confirmation-ligne').value : '',
          mot_de_passe: enLigne ? $('#mdp-ligne').value : '',
        }),
      });
      $('#ligne-ou').textContent =
        (d.public ? 'SITE PUBLIC : ' : 'Serveur d’essai : ') + d.destination + ' (' + d.methode + ')';
      /* UN ESSAI RATÉ RESSEMBLE À UN ESSAI RÉUSSI. Quand lftp n'arrive pas
         à lire l'autre côté, il croit le serveur VIDE et annonce la
         création des 887 fichiers : une liste parfaitement vraisemblable,
         où ne figure évidemment rien de ce qui serait effacé. */
      $('#journal-ligne').textContent =
        (d.ok ? '' : '⚠ CET ESSAI A ÉCHOUÉ. La liste ci-dessous ne veut rien '
                   + 'dire : faute d’avoir pu lire le serveur, l’outil le croit '
                   + 'vide et annonce l’envoi de tout le site. Corrigez la cause '
                   + '(mot de passe ?) et recommencez.\n\n')
        + d.sortie;
      if (!pourDeVrai && d.ok) $('#b-deposer').hidden = false;
      if (pourDeVrai && d.ok) {
        /* Le mot de passe ne reste pas dans le champ : l'atelier passe
           souvent des heures ouvert dans un onglet oublié. */
        $('#mdp-ligne').value = '';
        $('#confirmation-ligne').value = '';
        $('#b-deposer').hidden = true;
        await recharger();
        dire(d.public ? 'Site public remplacé.' : 'Déposé sur le serveur d’essai.');
      }
    } catch (e) {
      $('#journal-ligne').textContent = 'Échec : ' + e.message;
    }
  }

  $('#b-mettre-en-ligne').addEventListener('click', async () => {
    if (etat.modifie && await confirmer('Page non enregistrée',
        'Enregistrer la page ouverte avant de publier ?', 'Enregistrer')) {
      await enregistrer().catch(() => {});
    }
    majDestination();
    fl.showModal();
    /* Vers la maison, l'essai part tout seul. Vers l'hébergeur il attend le
       mot de passe : lancer et échouer aussitôt n'apprendrait rien. */
    if (destination() !== 'en-ligne') mettreEnLigne(false);
  });
  $('#b-essai').addEventListener('click', () => {
    /* En FTP, l'essai à blanc se connecte pour comparer les deux côtés :
       sans mot de passe il n'y a pas d'essai, seulement un échec. */
    if (destination() === 'en-ligne' && !$('#mdp-ligne').value) {
      $('#journal-ligne').textContent =
        'Le mot de passe FTP est nécessaire même pour l’essai à blanc : '
        + 'il faut se connecter pour savoir ce qui partirait.';
      $('#mdp-ligne').focus();
      return;
    }
    mettreEnLigne(false);
  });
  $('#b-deposer').addEventListener('click', async () => {
    if (destination() === 'en-ligne') {
      if ($('#confirmation-ligne').value.trim() !== 'je publie en ligne') {
        $('#journal-ligne').textContent = 'Recopiez exactement « je publie en ligne » pour continuer.';
        $('#confirmation-ligne').focus();
        return;
      }
      if (!$('#mdp-ligne').value) {
        $('#journal-ligne').textContent = 'Le mot de passe FTP est nécessaire.';
        $('#mdp-ligne').focus();
        return;
      }
    } else if (!await confirmer('Écraser le serveur d’essai ?',
        'Il recevra exactement ce que vous voyez ici.', 'Écraser', true)) {
      return;
    }
    mettreEnLigne(true);
  });

  window.addEventListener('beforeunload', (e) => {
    if (etat.modifie) { e.preventDefault(); e.returnValue = ''; }
  });
});
