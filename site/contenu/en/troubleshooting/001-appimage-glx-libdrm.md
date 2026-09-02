---
titre: "An AppImage dies at startup: “Could not initialize GLX”"
langue: "en"
type: "fiche"
collection: "troubleshooting"
date: "2026-08-24"
rang: 1
traduction: "glx-libdrm"
statut: "publie"
sommaire: "oui"
extrait: "On Arch with an AMD card, Qt AppImages stop dead with no window and no message. The cause is not Qt: it is a bundled libdrm, too old, winning over the system one."
---

On an up-to-date Arch machine, AMD card, Mesa driver: a Qt AppImage — FreeCAD in my case, though nothing about this is specific to it — stops at launch. No window, no dialog. In the terminal, at best:

```text
Could not initialize GLX
Aborted (core dumped)
```

The process dies on signal 6. Nothing else. The same AppImage ran the week before.

## What I believed for eight days

That the problem came from the **Qt and GL libraries frozen inside the AppImage**, built in July, now incompatible with the system's Mesa 26.2. It is the explanation that comes naturally: an AppImage carries its own world, the system moves on, one day it snaps.

I wrote it in a notes file, with confidence, and there it stayed for eight days. It was wrong. Above all it had the defect of being **unactionable**: if the culprit is "the AppImage is too old", there is nothing to do but wait for the next one.

Two standard leads give nothing either, and it is worth knowing before spending an hour on them:

```bash
LIBGL_DEBUG=verbose MESA_DEBUG=1 ./MyApp.AppImage
```

On this fault, those two variables print **nothing at all**. Not one line. It is disorienting — you assume you got the variable name wrong — but it is logical: the driver fails so early that the code producing those traces is never reached.

## The real cause, in the name of one symbol

The AppImage bundles `libdrm_amdgpu.so.1` version **2.4.125** (November 2024). The system's Mesa, meanwhile, needs the symbol `amdgpu_va_manager_init2`, which **appeared in libdrm 2.4.134**.

And the AppImage puts its own `usr/lib` at the head of the search path: **the bundled library wins**. The system Mesa driver then tries to link against a libdrm that does not know the symbol. The chain unrolls on its own:

1. `libgallium-26.2.1-arch3.1.so` fails to resolve `amdgpu_va_manager_init2`;
2. it does not load — so **radeonsi disappears**;
3. with no driver, **GLX exposes no FBConfig at all**;
4. Qt asks for a GL context, gets none, and gives up.

So "Could not initialize GLX" is the fourth link. It names where the failure became visible, not where it broke — which is exactly why you spend hours looking on the wrong side.

## Checking it yourself, in a minute

The diagnosis reproduces **outside the application**, which is the whole point: no more relaunching an 800 MB program to test a hypothesis.

Mount the AppImage without running it:

```bash
./MyApp.AppImage --appimage-mount
```

It prints a mount point (`/tmp/.mount_XXXXXX`) and stays open. In **another terminal**, force its `usr/lib` and look at what OpenGL sees:

```bash
LD_LIBRARY_PATH=/tmp/.mount_XXXXXX/usr/lib glxinfo -B
```

If radeonsi is gone, you will see `llvmpipe` (software rendering) or an error, instead of your card's name.

The next command **names the missing symbol** — this is the one that ended the eight days of hypothesis:

```bash
LD_LIBRARY_PATH=/tmp/.mount_XXXXXX/usr/lib \
  python3 -c "import ctypes; ctypes.CDLL('/usr/lib/libGLX_mesa.so.0')"
```

The error message gives the exact name. Nothing to interpret.

You can also confirm both sides on your own system:

```bash
nm -D --undefined-only /usr/lib/libgallium-*.so | grep amdgpu_va_manager
nm -D /usr/lib/libdrm_amdgpu.so.1 | grep amdgpu_va_manager
```

The first should answer `U` (the symbol is *wanted*), the second `T` (it is *provided*). If the second answers nothing, your system libdrm is too old as well, and that is a different story.

## The cure

One variable. Force the system libdrm libraries to load **before** the AppImage's:

```bash
LD_PRELOAD=/usr/lib/libdrm_amdgpu.so.1:/usr/lib/libdrm.so.2 ./MyApp.AppImage
```

**Preloading `libdrm.so.2` alone changes nothing** — I tried that first, by reflex, because it is the one you name when you say "libdrm". The missing symbol lives in `libdrm_amdgpu.so.1`, which is a *separate* library. You need both: the second because the first depends on it, and mixing a new `libdrm_amdgpu` with an old `libdrm` goes nowhere.

To avoid retyping this every time, a small launcher in `~/.local/bin`:

```bash
#!/usr/bin/env bash
set -euo pipefail
export LD_PRELOAD="/usr/lib/libdrm_amdgpu.so.1:/usr/lib/libdrm.so.2${LD_PRELOAD:+:$LD_PRELOAD}"
exec "$HOME/Applications/MyApp.AppImage" "$@"
```

The `${LD_PRELOAD:+:$LD_PRELOAD}` form appends the previous value **only if there is one**: without it, an empty `LD_PRELOAD` would leave a stray colon, which the linker reads as "preload the current directory".

## What the fault teaches

**An AppImage is not sealed.** It is sold as "everything is inside, nothing can break"; in reality it shares with the system everything that touches hardware — GPU, DRM, drivers. That contact surface is exactly where versions cross, and nobody tests it.

**An error message names the symptom, not the cause.** Searching for "Could not initialize GLX" returns thousands of pages about Qt, about X11, about proprietary drivers. None about libdrm. You only reach the name by going down one level at a time — Qt, then GLX, then the driver, then the dynamic linker.

**An unfalsifiable hypothesis is a confession.** "The libraries are too old" cannot be tested, cannot be refuted, and cannot be repaired. That kind of explanation should set off an alarm the moment you write it: if it were true, what would you do? Nothing. So it is not an explanation yet.

To be removed the day the AppImage is rebuilt against a recent libdrm. Until then, the launcher costs eight lines.
