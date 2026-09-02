---
titre: "pgrep -f finds itself (and pkill kills your script)"
langue: "en"
type: "fiche"
collection: "troubleshooting"
date: "2026-08-22"
rang: 2
traduction: "pgrep"
statut: "publie"
sommaire: "oui"
extrait: "A script that checks whether a service is running always finds it running — because it sees itself. Three ways out, one of which is not enough."
---

A perfectly ordinary watchdog script:

```bash
if pgrep -f cloudflared > /dev/null; then
    echo "the tunnel is up"
else
    echo "the tunnel is down; restarting"
    cloudflared tunnel run my-tunnel &
fi
```

It always reports the tunnel as up. Always. Tunnel stopped, service masked, freshly rebooted — always.

## Why

`pgrep -f` matches the pattern against each process's **full command line**. Your script *is* a process, and its command line contains the word `cloudflared` — because it is written inside it.

The script finds itself. The test is true before it has looked at anything.

With `pkill` it is worse: the script **kills itself**, often mid-loop, which leaves half-executed behaviour that is hard to read back.

To see it for yourself:

```bash
bash -c 'pgrep -af somepatternthatdoesnotexist'
```

That command searches for a pattern that exists **nowhere** on the machine — and still prints a line: the shell carrying it, whose command line contains the pattern. Verified on the machine I am writing this on.

## The well-known cure: brackets

```bash
pgrep -f '[c]loudflared'
```

`[c]loudflared` is a regular expression that **matches** `cloudflared` but is **not spelled** `cloudflared`. The script's command line therefore contains the brackets, not the word — and the pattern no longer recognises itself.

It is elegant, it costs two characters, and it is what you find everywhere. But it only covers one case out of two.

## The case brackets do not cover

The trick protects **the pattern**. It does not protect the rest of the command line.

```bash
bash -c "pgrep -f '[c]loudflared' || cloudflared tunnel run my-tunnel"
```

Here the word `cloudflared` appears **a second time**, in the clear, in the "otherwise" branch. The shell's full command line therefore contains it, and `pgrep` finds it — brackets or no brackets. The test is permanently true again.

The trap is nasty because the protection *looks* like it is there. You wrote the brackets, you assume you are covered, and the fault comes back. I paid for it three times in two days before seeing what was happening.

**The fix: put the search in a separate call**, whose command line mentions the target only once — the bracketed one.

```bash
if pgrep -f '[c]loudflared' > /dev/null; then
    echo "the tunnel is up"
else
    start_the_tunnel        # the target's name does not appear here
fi
```

Or more simply: never write the test and the restart on the **same line**.

## The cure that beats all of that

If the process is a systemd service — and it often is — do not interrogate the process table. Ask systemd:

```bash
systemctl --user is-active --quiet my-service && echo "running"
```

No pattern, no command line, no way to match yourself. `is-active` answers on the unit's real state, not on something that looks like a name in a `ps` listing.

For a process that is not a service, a **lock file** holding the PID is safer than a `pgrep`, and reads back six months later without wondering why there are brackets in it.

## One last reflex

When a `pgrep`/`pkill` behaves oddly, look at what it **actually** sees — the `-a` option prints the full command line of every match:

```bash
pgrep -af my-pattern
```

If your own script shows up in the list, that is your answer. It is a two-second check, and it saves you from blaming the service.
