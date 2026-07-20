# Updating the Production Dashboard Data

This is the step-by-step guide for refreshing the data shown on the
IGH Dashboard in production. You do **not** need to know anything
about databases, servers, or code to follow it — just be patient and
wait for each job to finish before starting the next.

## What this does

You will log into the **Airflow** website and start the refresh. You
start the **first** job by hand; the **second** job then runs on its
own as soon as the first finishes. The **third** job delivers the
result to the dashboard; depending on how your system is set up, it
either runs on its own or you start it. Together, the jobs
pull the latest data from Dataverse, prepare it, and deliver it to the
dashboard. When the third job finishes, the dashboard will show the new
data automatically — no restart needed.

## Before you start

You will need:

- The **Airflow website URL** and your Airflow username and password.
- The **dashboard URL**, so you can check the result at the end.

If you don't have either, ask the engineering team.

## Step 1 — Log into Airflow

1. Open the Airflow website in your browser.
2. Log in with your username and password.
3. You should now see a list of jobs (called "DAGs" in the UI). The
   three you care about are clearly numbered:
   - **1. IGH Ingestion**
   - **2. IGH Transform**
   - **3. IGH Deployment**

## Step 2 — Run the jobs in order

You always start the **first** job yourself. The **second** job
(**2. IGH Transform**) then runs **automatically** when the first
finishes. The **third** job (**3. IGH Deployment**) may run
automatically too — that depends on how engineering set up your system.
If it doesn't start on its own, you start it. Either way, watch each job
and wait for it to finish before the next begins.

> ⚠️ **Important:** always work in the numbered order, and wait for each
> job to turn fully **dark green** before starting (or moving on to)
> the next. Don't trigger **2. IGH Transform** by hand — it runs on its
> own.

To **start** a job (Ingestion and Deployment):

1. Click the job name to open it.
2. Click the **▶ play / Trigger** button (top-right of the page) and
   confirm.

To **watch** any job (including the one that starts on its own), open it
and check each step (shown as a coloured box):

- **light grey** — waiting to start
- **lime / running** — in progress
- **dark green** — finished successfully ✅
- **red** — failed ❌ (see "If something goes wrong" below)

Wait until **every** step is dark green before moving on.

Work through them in this order:

### Job 1 of 3 — **1. IGH Ingestion**  (you start this)

Pulls the latest data from Dataverse.
Typical run time: a few minutes, but can be longer on the first run
of the day. Wait until the single step is dark green.

> **Note:** when you click Trigger for this job, Airflow shows a
> small form with a single checkbox labeled **Update mode
> (incremental sync)**. **Leave it unchecked** and click the
> submit/trigger button — this gives you a fresh data refresh,
> which is what you want. Only tick it if the engineering team
> specifically asks you to.

When this job finishes, **2. IGH Transform starts on its own within a
minute** — you don't need to do anything. (If it hasn't started after a
couple of minutes, contact engineering — the job may be paused.)

### Job 2 of 3 — **2. IGH Transform**  (starts automatically)

Cleans and prepares the data for the dashboard. You don't trigger this
one — open it and watch. It has **two steps** that run one after the
other. Wait until **both** are dark green before starting Job 3.

### Job 3 of 3 — **3. IGH Deployment**  (you may need to start this)

Delivers the finished data to the dashboard server. Depending on your
setup, it either starts on its own once Transform finishes, or you start
it the same way you started Ingestion. It has two steps; wait until both
are dark green.

> **Note:** if **3. IGH Deployment** has already started or finished on
> its own by the time you reach it, that's expected — your system is set
> up to deploy automatically, so just watch it to the end instead of
> starting it.

## Step 3 — Check the dashboard

1. Open the dashboard URL in a new tab.
2. If it was already open, refresh the page (Ctrl+R / Cmd+R).
3. The new data should appear within a few seconds. No restart is
   needed — the dashboard picks up the new data on its own.

If the numbers don't look updated, wait a minute and refresh once
more. If they're still wrong, contact engineering (see below).

## If something goes wrong

If any step turns **red**, **stop** — do not try to re-run anything
yourself and do not start the next job.

1. Take a screenshot of the red step and of the job page.
2. Send it to the engineering team on the contact channel below.

They will look at the logs, fix the underlying problem, and either
restart the failed step for you or tell you it's safe to re-run.

## Contact

- **Engineering team:** `TODO — add Slack channel / email here`

## Downloading the database files (optional)

If you need to inspect the data yourself, Airflow can hand you a copy of
each stage's database as a file:

1. Log into Airflow (Step 1 above).
2. In the left sidebar, open the **Plugins** menu, then **Downloads**.
3. Click the layer you want — a new browser tab opens and the file
   downloads:
   - **Bronze DB** — raw data, straight from Dataverse.
   - **Silver DB** — cleaned and prepared data.
   - **Gold DB** — the dashboard-ready data (star schema).

You must be logged into Airflow for the download to work. If a layer
hasn't been built yet, you'll get a short "not produced yet" message
instead of a file — run the jobs above first.

---

## For engineers (more detail)

The procedure above is the operator-facing summary. For source and
design context, the following links are pinned to known-good commits:

- Airflow DAG definitions (the three jobs above):
  - [`1. IGH Ingestion` — `dags/igh_ingestion_dag.py`](https://github.com/akvo/igh-airflow/blob/614a543bf0e71298303f4228025410134e20ea92/dags/igh_ingestion_dag.py)
  - [`2. IGH Transform` — `dags/igh_transform_dag.py`](https://github.com/akvo/igh-airflow/blob/614a543bf0e71298303f4228025410134e20ea92/dags/igh_transform_dag.py)
  - [`3. IGH Deployment` — `dags/igh_deployment_dag.py`](https://github.com/akvo/igh-airflow/blob/614a543bf0e71298303f4228025410134e20ea92/dags/igh_deployment_dag.py)
- Why production dashboard hosts rely on this pipeline (rather than
  seeding a bundled database):
  [`igh-dashboard` / `self-hosted/README.md`](https://github.com/akvo/igh-dashboard/blob/6b3a288ec0bc0c47d69ce22c90896ed2fc4579b8/self-hosted/README.md)
- Airflow repo developer guide and production self-hosted setup:
  - [`igh-airflow` / `CLAUDE.md`](https://github.com/akvo/igh-airflow/blob/614a543bf0e71298303f4228025410134e20ea92/CLAUDE.md)
  - [`igh-airflow` / `self-hosted/README.md`](https://github.com/akvo/igh-airflow/blob/614a543bf0e71298303f4228025410134e20ea92/self-hosted/README.md)
