# Simulating the Dashboard Server

A developer guide to running the `igh_deployment` and `igh_rollback` DAGs
end to end on your own machine, against a throwaway SSH host instead of
the real dashboard server.

## Why it exists

Both DAGs publish the gold database by running `scp` and `ssh` against a
remote machine. In the default dev stack `DEPLOY_TARGET_HOST` is `local`,
which makes every deploy and rollback task log a warning and return
without doing anything. The unit tests check the command strings, but
not what they do to a real directory.

The `dashboard-sim` compose profile fills that gap. It starts a small
`alpine` + `openssh` container on the compose network that stands in for
the dashboard server, so the tasks run their real `scp`/`ssh` commands
and you can watch the files change.

Use it whenever you touch:

- `dags/igh_deploy_remote.py` (the swap or rollback command strings)
- `dags/igh_deployment_dag.py` or `dags/igh_rollback_dag.py`
- SSH settings, key handling, or the deploy env vars

It is for development only. The image is never deployed anywhere.

## How it fits together

```
 airflow-worker                        dashboard-sim (/srv/dashboard)
 ──────────────                        ──────────────────────────────
 igh_deployment ("3. IGH Deployment")
   1. scp_gold_db      ──scp──▶  upload star_schema.db.new
   2. swap_remote_db   ──ssh──▶  check .new exists
                                 → hardlink live as .prev
                                 → rename .new to live
 igh_rollback ("4. IGH Rollback")
   rollback_remote_db  ──ssh──▶  check .prev exists
                                 → rename .prev to live
```

Names in quotes are how the DAGs appear in the Airflow UI. The indented
names are the tasks inside each DAG, as shown in the run's grid view and
task logs.

What the container provides (`docker/Dockerfile.dashboard-sim`):

- User `deployer`, key auth only, no password or root login.
- `authorized_keys` copied from `./ssh/id_rsa.pub` at startup, so you can
  regenerate the keypair without rebuilding the image.
- Login shell is busybox `ash`, not bash. A passing run therefore also
  proves the remote commands are portable POSIX shell, which is all the
  real server's login shell is guaranteed to accept.

The service is behind a profile, so a plain `docker compose up -d` never
starts it (`tests/test_compose_profiles.py` keeps it that way).

## Prerequisites

- The normal local stack works (see the [README](../README.md#local-development)).
- `AIRFLOW_UID` in `.env` matches your own user ID (`id -u`). The Airflow
  containers read `./ssh/id_rsa` as that user; if it does not match the
  file's owner, `ssh` rejects the key.
- `ssh-keygen` installed on your host.

## Setup

Run everything from the project root.

### 1. Generate a throwaway keypair

Do this **before** starting the stack. If `./ssh` does not exist when
compose starts, Docker creates it owned by root and `ssh-keygen` then
fails to write into it. If that already happened, stop the stack and
`sudo rm -r ssh` first.

```bash
mkdir -p ssh && ssh-keygen -t ed25519 -f ssh/id_rsa -N "" -q && chmod 600 ssh/id_rsa
```

The file is called `id_rsa` even though it is an ed25519 key, because
that is the default `DEPLOY_SSH_KEY_PATH`. `ssh/` is git-ignored. Never
put a real key here.

### 2. Provide a gold database

Use a real `star_schema.db` if you have one. Otherwise a stand-in is
fine, because the swap and rollback only move files and never read them:

```bash
mkdir -p data/gold
uv run python -c "import sqlite3; sqlite3.connect('data/gold/star_schema.db').execute('create table t(x)')"
```

### 3. Start the stack with the simulator

```bash
DEPLOY_TARGET_HOST=dashboard-sim \
DEPLOY_TARGET_USER=deployer \
DEPLOY_TARGET_PATH=/srv/dashboard \
  docker compose --profile dashboard-sim up -d
```

These three variables only apply to this one command. A later
`docker compose up -d` without them recreates the Airflow containers in
`local` mode again. If you will be working with the simulator for a
while, put them in `.env` instead, and remove them when you are done.

### 4. Unpause the DAGs

New DAGs start paused. A paused DAG accepts a trigger, but the run stays
queued.

```bash
docker compose exec airflow-apiserver airflow dags unpause igh_deployment
docker compose exec airflow-apiserver airflow dags unpause igh_rollback
```

## Walkthrough

Trigger the DAGs from the Airflow UI (http://localhost:8080) or the CLI:

```bash
docker compose exec airflow-apiserver airflow dags trigger igh_deployment
docker compose exec airflow-apiserver airflow dags trigger igh_rollback
```

After each step, look at the simulated deploy directory. `-i` shows
inode numbers, which is how you confirm `.prev` is a hardlink to the old
live file and not a copy. `md5sum` tells the versions apart:

```bash
docker compose exec dashboard-sim sh -c 'cd /srv/dashboard && ls -li star_schema.db* && md5sum star_schema.db*'
```

To see files appear and move as the tasks run, keep a live view open in
a second terminal (Ctrl+C to quit):

```bash
docker compose exec dashboard-sim sh -c 'cd /srv/dashboard && watch -n 1 ls -lhi'
```

To produce a "new version" between deploys, change the local gold DB,
for example:

```bash
uv run python -c "import sqlite3; c = sqlite3.connect('data/gold/star_schema.db'); c.execute('create table if not exists t2(x)'); c.commit()"
```

Go through these steps in order:

| # | Action | Expected result |
|---|--------|-----------------|
| 1 | Trigger `igh_deployment` (first time) | Only `star_schema.db`, no `.prev`. Swap log says `no previous version existed to retain (first deploy)` |
| 2 | Change the gold DB, trigger `igh_deployment` again | Live is the new version. `.prev` holds the old one **at the inode the live file had before**. Log says `previous version kept as star_schema.db.prev` |
| 3 | Trigger `igh_rollback` | Live is the old version again. `.prev` is gone |
| 4 | Trigger `igh_rollback` a second time | Task is **skipped**, not failed. Log says `NO ROLLBACK PERFORMED`. Directory unchanged. The DAG run itself shows success, so check the task, not the run |
| 5 | In the UI, open the latest **3. IGH Deployment** run and clear only its `swap_remote_db` task | Task **fails** with `no star_schema.db.new to deploy`. **Live DB still intact** |
| 6 | Trigger `igh_deployment` without changing the gold DB (roll forward) | Live is the step 2 version again (same `md5sum`). `.prev` holds the step 1 version |

Step 5 is the important one. Re-run it after any change to the swap
command. It covers an operator re-running the swap after a successful
deploy has already consumed `.new`. A command that set the live file
aside before checking for `.new` would leave the dashboard with no
database at all in that case.

In step 5 the task fails straight away, but it then waits five minutes in
`up_for_retry` before turning red (`igh_deployment` has `retries: 1` with
a 5-minute delay). Read the task log instead of waiting. Clearing the
task also puts its run back into running state, and only one deploy runs
at a time, so a step 6 deploy stays queued until step 5 turns red.

### Rolling forward after a rollback

> **Rolling forward is a single `igh_deployment` run.** There is no need to
> re-run ingestion or transform.

A rollback only changes files on the dashboard server. The gold DB that
Airflow built (`data/gold/star_schema.db`) is left untouched. Triggering
**3. IGH Deployment** again uploads that same file and publishes it, which
restores the version you rolled back from.

The server does not keep the rolled-back-from version. Airflow's copy is
the only one left, so this works only as long as no `igh_transform` run has
rebuilt the gold DB since. Otherwise the deploy publishes the newer build.

Step 6 of the walkthrough checks this.

## Resetting and teardown

The deploy directory lives only inside the container. To start again
from an empty directory, recreate the container. This does not rebuild
the image, so the host keys stay the same:

```bash
docker compose --profile dashboard-sim up -d --force-recreate dashboard-sim
```

To stop everything, including the simulator:

```bash
docker compose --profile dashboard-sim down
```

Then start normally (`docker compose up -d`, with the deploy variables
removed from `.env` if you added them) to go back to `local` mode.

### After rebuilding the simulator image

Rebuilding `dashboard-sim` (for example after `Dockerfile.dashboard-sim`
changes) generates new SSH host keys. The tasks use
`StrictHostKeyChecking=accept-new`, which accepts an unknown host but
refuses a changed one, so they fail with `Host key verification failed`.
Recreate the worker to drop its cached entry:

```bash
docker compose up -d --force-recreate airflow-worker
```
