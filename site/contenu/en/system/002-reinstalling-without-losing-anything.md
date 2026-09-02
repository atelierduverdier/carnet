---
titre: "Reinstalling without losing anything: the order of operations"
langue: "en"
type: "fiche"
collection: "system"
date: "2026-08-15"
rang: 2
traduction: "reinstaller"
vignette: "captures/chezmoi-gere.png"
statut: "publie"
sommaire: "oui"
extrait: "A reinstall is not prepared on the day you do it. What gets lost is almost never the files: it is the backup repository passphrase, and the “enabled” state of everything you restored."
---

Written after an SSD failure, and reread after the reinstall that followed. This is not an Arch installation guide — there are very good ones — but a list of what **gets lost** when you reinstall, and which is not in the files.

## Do this now, not on the day

Only one thing is genuinely urgent, and it must be done **while the current machine still works**.

**Get the backup repository passphrase out of the desktop keyring.**

If you back up with Borg (or restic, same thing) and the passphrase is stored in KWallet, GNOME Keyring, or your backup tool's own keyring, then it exists **only there**. Dotfile managers do not version keyrings — deliberately, so that secrets never end up in a git repository. That is the right choice, and it is exactly what makes the passphrase invisible on the day you forget it.

Without it, the entire backup history becomes **permanently unreadable**. Borg offers no recovery: it is encryption, doing its job.

Getting it out takes two minutes:

1. open the keyring manager and find the repository's entry;
2. copy the passphrase into a password manager — or onto paper, somewhere safe;
3. **not** into a plaintext file on the machine you are about to wipe.

As long as the passphrase does not change, this is done once and for all.

## The order that works

**1. The system, then the three tools that matter.**

```bash
sudo pacman -Syu
sudo pacman -S git chezmoi borgbackup
```

Nothing else yet: everything else will come from the dotfiles.

**2. The dotfiles.**

```bash
chezmoi init --apply <your-account>/dotfiles
```

One command, and back come the shells, the desktop configuration, the keyboard shortcuts, the terminals, the editors, the applications. This is the gesture that makes a reinstall bearable — provided you versioned the dotfiles *beforehand*, which is the real work and gets done on a quiet day.

**3. The backup repository, with the passphrase you just retrieved.**

Plug the disk back in, reattach the repository in the tool, and **check that the history goes back further than the reinstall**. Do not settle for seeing the list: run one manual backup to confirm that writing works too. A repository you can read is not a repository you can write to.

**4. Re-enable what you restored.**

This is the forgotten box, and it deserves its own section.

## A restored file is not a running service

Dotfiles restore the **files** of systemd user timers and services, since they live in `~/.config/systemd/user/`. They do **not** restore their "enabled" state, which lives in symlinks created by `systemctl enable`.

The result: everything is there, nothing runs, and you only notice when a reminder you were expecting fails to arrive the following week.

```bash
systemctl --user daemon-reload
systemctl --user enable --now my-timer.timer
systemctl --user list-timers --all
```

The last command is the check: every expected timer must appear, with a next-firing time. A timer missing from that list will never fire.

The same principle applies elsewhere. A restored **udev rule** needs a `udevadm control --reload` and the hardware replugged. A **firewall** whose configuration you restored often stays disabled. The general rule: *anything with a switch comes back switched off*.

## Two kinds of application not to restore blindly

**Cloud sync clients.** Configure the local folder **in the application, before the folder exists or is filled**. If you restore the files first and then point the application at them, many clients fail to recognise the content and re-download everything — tens of gigabytes, and sometimes a mess of duplicates.

**Library applications** — book manager, font manager, note vault, 3D model library. Open the application *first* and point it at the intended location. Copying the configuration folder by hand works sometimes, fails silently often, and leaves an index database talking about old paths.

In both cases it is the same principle: **the application must be told the path, not discover it**.

## The final check

Three commands and a look:

```bash
systemctl --user list-timers --all
git -C ~/Projects/something-important status
```

- the expected timers are there and enabled;
- the git repositories are clean and on the right branch;
- the backup history goes back further than the reinstall;
- one manual backup completes.

That last line is the one you skip because you are tired, and it is the only one that proves the whole chain works. The rest proves it looks like it works.

## What I learned the hard way

An archive you **believe** exists does not exist. After the failure I was convinced I had made a backup the day before — there was no trace, no commit, nothing. Conviction does not count; what counts is what the verification command answers.

Since then a small check script goes over the repository and **says** what it finds, rather than letting me assume. It is three lines, and it replaces a belief with a fact.
