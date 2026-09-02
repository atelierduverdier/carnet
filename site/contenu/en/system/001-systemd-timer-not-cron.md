---
titre: "Scheduling a task: a systemd timer, not cron"
langue: "en"
type: "fiche"
collection: "system"
date: "2026-08-17"
rang: 1
traduction: "timer-systemd"
vignette: "captures/timer-calendrier.png"
statut: "publie"
sommaire: "oui"
extrait: "Why a scheduled task on a desktop machine belongs in a systemd user timer rather than a crontab line — and how to write one that shows a notification."
---

On a server that runs around the clock, cron does the job perfectly well. On a **desktop machine** it has three defects that you pay for sooner or later, and a systemd timer fixes all three.

## The three reasons

**1. The machine is off at night.** A crontab line set for 3 a.m. does not catch up: the machine was off, the slot is gone, try again tomorrow. A systemd timer with `Persistent=true` **catches up** the missed appointment at the next boot. For a weekly reminder the difference is not cosmetic: it is the difference between a reminder that arrives and one that never does.

**2. Cron's output goes nowhere.** It lands in a local mail nobody reads. A systemd service's output goes to the journal, and reads back with a command you already know.

**3. Cron does not have your session.** A task that wants to show a desktop notification needs to know which session bus to talk to. In a crontab you have to guess it and hard-code it. In a **user** timer (`systemctl --user`), you are already inside it.

## A complete example

A reminder the evening before bin collection — exactly the kind of thing you forget *because* it comes round every week.

Three files. First the script, in `~/.local/bin/bin-reminder`:

```bash
#!/usr/bin/env bash
# Decides whether anything needs putting out tonight, and says so.
set -euo pipefail

day=$(date +%u)             # 1 = Monday … 7 = Sunday
[ "$day" -eq 2 ] || exit 0  # collection on Wednesday: we warn on Tuesday

notify-send --icon=user-trash-full \
            --urgency=normal \
            "Bins" "Collection tomorrow morning: put the bin out."
```

Make it executable:

```bash
chmod +x ~/.local/bin/bin-reminder
```

Then the service, `~/.config/systemd/user/bin-reminder.service`:

```ini
[Unit]
Description=Bin collection reminder

[Service]
Type=oneshot
ExecStart=%h/.local/bin/bin-reminder
```

And the timer, `~/.config/systemd/user/bin-reminder.timer`:

```ini
[Unit]
Description=Bin collection reminder, every evening

[Timer]
OnCalendar=*-*-* 19:00:00
Persistent=true
AccuracySec=1m

[Install]
WantedBy=timers.target
```

The service and the timer share **the same name** before the extension: that is how systemd pairs them, without you having to say so.

## The pattern: a dumb timer, a script that decides

Notice that the timer fires **every evening**, and that it is the *script* that decides whether there is anything to say. We could have written `OnCalendar=Tue *-*-* 19:00:00` and dropped the test.

The choice is not neutral. A timer that fires daily is **checked daily**: if the script is broken, you know within twenty-four hours. A weekly timer keeps its defect for a week — and since you never see it go past, you do not even know it should have spoken.

The general rule: **the schedule says *when to look*, the script says *whether to act*.** It is also easier to try out, since you can run the script by hand at any time.

## Enabling it, and checking

```bash
systemctl --user daemon-reload
systemctl --user enable --now bin-reminder.timer
```

The two commands you will use afterwards:

```bash
systemctl --user list-timers --all
```

It shows, for each timer, the next firing, the previous one, and the unit attached. That is the dashboard — if it is empty, nothing is armed.

```bash
journalctl --user -u bin-reminder.service -n 20
```

The output of the last twenty runs. That is where the errors you never saw go past are waiting.

To try it without waiting for 7 p.m.:

```bash
systemctl --user start bin-reminder.service
```

## Two traps

**The silent notification.** If `notify-send` does nothing from the service while working fine in a terminal, it is almost always the session environment that is missing. In a *user* timer the problem is rare; if it happens, `systemctl --user import-environment DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS` at session start settles it.

**A restored file is not an armed timer.** If you version `~/.config/systemd/user/` (with chezmoi or anything else), restoring copies the files back — but **not** the "enabled" state, which lives in symlinks elsewhere. After a reinstall you have to redo the `enable --now`. That is the box everyone forgets, and you conclude the timer is lost when it is merely asleep.

## Do not enable it on someone else's behalf

One last thing, which is not technical. A timer is something that **will speak on its own**, later, when nobody expects it. Writing the three files for someone is a favour; enabling them in their place is a decision that is not yours to make. Leave them the last command.
