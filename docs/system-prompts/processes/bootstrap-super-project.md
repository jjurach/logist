# bootstrap-super-project.md

**Purpose:** Rehydrate the hentown top-level project after a fresh GitHub checkout.
Checks that all required tools are installed, sets up the Python environment,
and starts the shared Dolt server so all submodule `bd` commands work.

**When to run:** After `git clone`, after a machine rebuild, or whenever `bd list`
returns "Dolt server not running" from the hentown root.

**Run from:** `~/hentown` (the hentown repository root)

---

## Quick Reference

```bash
# One-liner to run the full bootstrap:
cd ~/hentown && bash docs/system-prompts/processes/bootstrap-super-project.sh
```

Or follow the phases below manually.

---

## Phase 1: Required Tools Check

Verify the following binaries are on `PATH` or at the expected local paths.
If any are missing, install before continuing — do not proceed with a partial setup.

```bash
# bd CLI (beads issue tracker)
tools/go/bin/bd --version
# Expected: bd version 0.56.x or higher

# dolt (Dolt database server — required by bd)
tools/go/bin/dolt version
# Expected: dolt version 1.x

# Python 3.10+
python3 --version
# Expected: Python 3.10 or higher

# git
git --version
```

If `bd` or `dolt` are missing, they are built from source in `tools/go/`:

```bash
# Build bd (beads CLI)
cd tools/go/src/beads && go build -o ../../bin/bd ./cmd/bd

# Build dolt
cd tools/go/src/dolt/go && go install ./cmd/dolt
# binary lands at ~/go/bin/dolt — copy to tools/go/bin/
cp ~/go/bin/dolt tools/go/bin/dolt
```

---

## Phase 2: Python Virtual Environment

```bash
cd ~/hentown

# Create venv if it does not exist
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "Created .venv"
fi

# Activate
source .venv/bin/activate

# Install tools/requirements.txt
pip install -r tools/requirements.txt
echo "Python environment ready"
```

Verify:

```bash
python3 -c "import boto3, rich; print('deps ok')"
```

---

## Phase 3: Git Submodules

Ensure all submodules are checked out:

```bash
git submodule update --init --recursive
```

Expected: all `modules/*` directories are populated.

---

## Phase 4: Start the Shared Dolt Server

The hentown root owns the single Dolt server that all submodules connect to.

```bash
cd ~/hentown

# Add bd and dolt to PATH for this session
export PATH="$PWD/tools/go/bin:$PATH"

# Start the server (no-op if already running)
bd dolt start

# Verify it's up on port 3307
bd dolt status
# Expected: Dolt server: running, Port: 3307, Data: .beads/dolt
```

If `bd dolt start` fails:

```bash
# Check logs
cat .beads/dolt-server.log | tail -20

# Check if port 3307 is already occupied by a different process
lsof -i :3307

# If stale PID file:
rm -f .beads/dolt-server.pid .beads/dolt-server.port
bd dolt start
```

---

## Phase 5: Verify Beads Databases

After the server starts, confirm all project databases are accessible:

```bash
cd ~/hentown

# Top-level project
bd list 2>&1 | head -3

# Spot-check a submodule
cd modules/hatchery && bd list 2>&1 | head -3 && cd ~/hentown
```

If a submodule returns "database not found", the database needs rehydration:

```bash
cd modules/<name>
bd init --from-jsonl --force --server-port 3307
cd ~/hentown
```

---

## Phase 6: Environment Convenience (Optional)

Add to your shell profile (`~/.zshrc` or `~/.bashrc`) to avoid repeating `PATH` setup:

```bash
# hentown tools
export PATH="$HOME/hentown/tools/go/bin:$PATH"
```

And add a shell function to start the server from anywhere:

```bash
hentown-start() {
  cd ~/hentown && bd dolt start && cd -
}
```

---

## Submodule Agent Note

Agents working inside a submodule (`modules/*`) **must not start Dolt themselves**.
The shared server must already be running (started by the top-level bootstrap above).

**Submodule pre-flight check** (add to agent session start):

```bash
if ! nc -z 127.0.0.1 3307 2>/dev/null; then
  echo "ERROR: Dolt server not running."
  echo "Bootstrap from hentown root: cd ~/hentown && bd dolt start"
  exit 1
fi
```

---

## Full Database Map

| Project | Database | Issues (approx) |
|---|---|---|
| hentown (root) | `beads_hentown` | 84 |
| modules/hatchery | `beads_hatchery` | 66 |
| modules/pitchjudge | `beads_pitchjudge` | 61 |
| modules/chatterbox | `beads_chatterbox` | 43 |
| modules/pigeon | `beads_pigeon` | 21 |
| modules/mellona | `beads_mellona` | 13 |
| modules/second_voice | `beads_second_voice` | 6 |

All databases live in `~/hentown/.beads/dolt/` on the shared server at `127.0.0.1:3307`.

---

**Last Updated:** 2026-02-28
**Maintained by:** hentown project
