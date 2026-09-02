---
titre: "Command notebook"
langue: "en"
type: "page"
slug: "commands"
traduction: "commandes"
sommaire: "cote"
vignette: "captures/glx-symbole.png"
statut: "publie"
extrait: "The commands that went into writing this notebook: what they do, when they help, and the trap that comes with each."
---

These are not *the* Linux commands: they are **the ones that were needed here**, in the order the problems turn up. Each takes three lines — what it does, when you want it, and the trap attached.

## What a library provides, and what it wants

```bash
nm -D /usr/lib/libdrm_amdgpu.so.1 | grep mysymbol
nm -Du /usr/lib/libgallium-*.so | grep mysymbol
```

`T` = the symbol is **provided**. `U` = it is **wanted**. A library that wants what nobody provides fails to load — and the program dies much later, on a message that says nothing about it.

The `-D` is not optional on a shared library: without it, `nm` answers "no symbols".

```bash
python3 -c "import ctypes; ctypes.CDLL('/usr/lib/mylib.so.0')"
```

**This one names the missing symbol.** It is often the command that ends a hypothesis: it says what is missing instead of leaving you to guess.

```bash
LD_PRELOAD=/usr/lib/a.so:/usr/lib/b.so ./my-program
LD_LIBRARY_PATH=/some/dir/lib glxinfo -B
```

`LD_PRELOAD` forces a library **ahead** of all others — the cure when an AppImage bundles a version that is too old. `LD_LIBRARY_PATH` does the opposite: it shows a program somebody else's libraries, which **reproduces** the fault outside the program.

## Is a process really running

```bash
pgrep -af '[m]yservice'
```

`-a` prints the full command line: that is what shows why the answer is wrong. The brackets stop the pattern from recognising itself — [the detail is here](/en/troubleshooting/002-pgrep-finds-itself/).

```bash
systemctl --user is-active --quiet my-service && echo "running"
```

**When it is a service, always prefer this.** No pattern, no command line, no way to match yourself: the answer is about the unit's real state.

## systemd: schedule, check, read

```bash
systemctl --user daemon-reload
systemctl --user enable --now my-timer.timer
```

`daemon-reload` after writing any unit file. `enable --now` arms **and** starts: without `--now`, you wait for the next session start.

```bash
systemctl --user list-timers --all
```

The dashboard: next firing, previous one, unit attached. **A timer missing from this list will never fire** — the first place to look when a reminder did not arrive.

```bash
journalctl --user -u my-service.service -n 20
```

The output of the last twenty runs. That is where the errors you never saw go past are sleeping.

```bash
systemd-analyze calendar 'Tue *-*-* 19:00:00'
```

Answers "when exactly does this fire?" without waiting. Useful before arming, not after.

## Packages, on Arch

```bash
grep -n "^IgnorePkg\|^IgnoreGroup" /etc/pacman.conf
```

The pin that holds a package at its version. It is easily lost — a `pacman.conf` replaced by a `.pacnew`, and it vanishes without a word. Check again after every `pacdiff`.

```bash
pacman -Qu          # what would go up
pacman -Q freecad   # the version being held
```

```bash
ls /var/cache/pacman/pkg/ | grep '^freecad-'
```

**The safety net for going back.** The cache keeps installed packages; if the one for your current version is gone, rolling back means compiling. Check **before** pulling a pin, not after.

`pacman -S somepackage` without `-Syu` on a stale database is a partial upgrade: the classic trap. `pacman -Syu somepackage` does both.

## Where the disk space went

```bash
df -h /tmp
du -sh /tmp/* | sort -h | tail -12
```

`sort -h` understands "M" and "G": it is what puts the culprit last. Without it, `du` sorts by name and you see nothing.

```bash
find /tmp -maxdepth 1 -name 'pattern-*' -type d -exec rm -rf {} +
```

`-maxdepth 1` so it does not descend, `-type d` so it only targets directories, and `+` rather than `\;` to pass them all at once. **Read the pattern again before pressing return**: `rm -rf` asks nothing.

## Checking that a site answers

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://example.com/a/page/
```

The status code alone, without the page. Ideal in a loop over a list of addresses: you see at once what is a 404.

```bash
getent hosts mysite.example.com
```

Resolves a name the way the system does — so with its `hosts` files and its cache, which an online lookup service will not tell you.

## Images and fonts, from the command line

```bash
rsvg-convert -h 128 drawing.svg -o drawing.png
```

Renders an SVG at a given **height**, the width following. Handy for preparing an icon or a logo without opening an editor.

```bash
xmllint --noout --html page.html
```

Says whether the file is well formed, and nothing else. An invalid SVG renders **not at all** in some applications, without a single message: this check costs one second.

```bash
fc-list | grep -i mono
```

The installed fonts, with their paths — the path you have to hand a script that draws text.

## Git, when the folder is shared

```bash
git status --short
```

**The first command to type**, before anything else, when several sessions work in the same place. It tells you what is not yours.

```bash
git add -A -- ':!some/file' ':!another'
```

Stages everything **except** what is named. That is how you commit your work without carrying off someone else's.

```bash
git log --oneline -5
git ls-tree --name-only origin/some-branch -- some/dir/
```

The second looks at what a **remote** branch contains, without switching to it or downloading it — useful to check that a publication actually went out.
