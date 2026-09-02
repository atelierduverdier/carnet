---
titre: "Pinning a package on Arch, and why a machine tool demands it"
langue: "en"
type: "fiche"
collection: "workshop"
date: "2026-08-16"
rang: 1
traduction: "epingler-paquet"
vignette: "captures/pacman-epingle.png"
statut: "publie"
sommaire: "oui"
extrait: "A rolling distribution and a fabrication program do not want the same thing. IgnorePkg settles the conflict — provided you know what you are buying with it."
---

Arch updates everything, all the time, and that is what we ask of it. But one day a `pacman -Syu` moves a CAD program from one major version to the next — and the add-on you wrote for it stops working, generally at the worst moment.

This is not an inconvenience for a computer person. It is a piece of wood already clamped on the table, an engraving session planned for the afternoon, and a workshop producing nothing until the add-on has been ported.

## The move

In `/etc/pacman.conf`, under `[options]`:

```ini
IgnorePkg = freecad
```

Several packages are separated by spaces, and wildcards are accepted:

```ini
IgnorePkg = freecad linux linux-headers
IgnoreGroup = kde-applications
```

From then on, `pacman -Syu` updates everything **except** those packages, and says so on every pass:

```text
warning: freecad: ignoring package upgrade (1.1.3-1 => 1.2.0-1)
```

That warning is useful: it reminds you a debt is accumulating. Do not silence it.

## Checking the pin holds

It is easy to lose — a `pacman.conf` replaced by a `.pacnew` during a package-manager update, and the pin vanishes without a word.

```bash
grep -n "^IgnorePkg\|^IgnoreGroup" /etc/pacman.conf
```

If the command answers nothing, the pin is gone. Check after every `.pacnew` you process — that is, after every `pacdiff`.

And to see what would have gone up without it:

```bash
pacman -Qu
```

## What you buy, and what you pay

**What you buy**: the machine produces tomorrow morning. That is all, and it is enough.

**What you pay**, and you should know before:

- **a debt that grows.** Pinning for three months is a choice; pinning for two years is a problem you built yourself. The pinned version will eventually fail to link against the system's libraries;
- **security fixes are skipped too.** For an offline CAD program the risk is low. For a browser or an exposed service, pinning is a bad idea — and if you really must, it is the wrong solution to the right problem;
- **the dependencies keep moving.** That is the real trap: the pinned package stays, but everything it rests on shifts. One day the frozen version stops starting, not because it changed, but because the ground moved under it.

## The logical sequel: two versions side by side

Pinning is only bearable if you can **try the new version without risking the one that works**. That is the real cure, and it turns the pin into a decision instead of a postponement.

Most fabrication programs also exist as an AppImage. Two precautions are enough to make one coexist with the system package:

**1. A separate configuration directory.** Otherwise both versions write to the same place, and the development one silently migrates settings the old one can no longer read. Many applications accept an environment variable for this.

**2. A dedicated launcher**, in `~/.local/bin`, that sets the variable and starts the AppImage:

```bash
#!/usr/bin/env bash
set -euo pipefail
export MYAPP_USER_HOME="$HOME/.local/share/myapp-dev"
mkdir -p "$MYAPP_USER_HOME"
exec "$HOME/Applications/MyApp-weekly.AppImage" "$@"
```

You then test the add-on against the coming version when you have the time, not when `pacman` decides. The day it passes, you drop the pin — and you chose to.

One detail that matters if you do this: the development version writes to **its** directory, so **settings you change there do not come back** to the version that works. That is the point, but you forget it and redo the same setting twice wondering why it will not stick.

On this machine, the development AppImage additionally needs an `LD_PRELOAD` to start at all — that is another story, told in [the note on “Could not initialize GLX”](/en/troubleshooting/001-appimage-glx-libdrm/).

## When to remove the pin

When the three boxes are ticked, and not before:

1. the add-on or workflow works on the new version, **tried on a real file**, not on a cube;
2. there is no work in progress on the machine;
3. the working version can still be installed if you need to go back — pacman's cache (`/var/cache/pacman/pkg/`) keeps it, provided you have not emptied it.

That third box is the one you discover too late. Before pulling a pin:

```bash
ls /var/cache/pacman/pkg/ | grep '^freecad-'
```

If the package for the current version is gone, set it aside somewhere else before updating. Rolling back without the package means compiling, and compiling means the whole day.
