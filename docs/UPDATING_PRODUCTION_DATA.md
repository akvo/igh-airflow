# Updating the Production Dashboard Data

This is the step-by-step guide for refreshing the data shown on the
IGH Dashboard in production. You do **not** need to know anything
about databases, servers, or code to follow it — just be patient and
wait for each job to finish before starting the next.

## What this does

You will log into the **Airflow** website and start three jobs, one
after another. Together, the jobs pull the latest data from
Dataverse, prepare it, and deliver it to the dashboard. When the
third job finishes, the dashboard will show the new data
automatically — no restart needed.

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

## Step 2 — Run the three jobs in order

> ⚠️ **Important:** run them **one at a time**, in the numbered order
> shown. Do not start the next job until the previous one has
> finished successfully. If you start them out of order, the
> dashboard will not update correctly.

For each job, follow the same pattern:

1. Click the job name to open it.
2. Click the **▶ play / Trigger** button (top-right of the page) and
   confirm.
3. Watch the job run. Each step (shown as a coloured box) will be:
   - **light grey** — waiting to start
   - **lime / running** — in progress
   - **dark green** — finished successfully ✅
   - **red** — failed ❌ (see "If something goes wrong" below)
4. Wait until **every** step is dark green before moving on.

Run them in this order:

### Job 1 of 3 — **1. IGH Ingestion**

Pulls the latest data from Dataverse.
Typical run time: a few minutes, but can be longer on the first run
of the day. Wait until the single step is dark green.

> **Note:** when you click Trigger for this job, Airflow shows a
> small form with a single checkbox labeled **Update mode
> (incremental sync)**. **Leave it unchecked** and click the
> submit/trigger button — this gives you a fresh data refresh,
> which is what you want. Only tick it if the engineering team
> specifically asks you to.

### Job 2 of 3 — **2. IGH Transform**

Cleans and prepares the data for the dashboard. This job has **two
steps** that run one after the other. Wait until **both** are dark
green.

### Job 3 of 3 — **3. IGH Deployment**

Delivers the finished data to the dashboard server. This job also
has two steps. Wait until both are dark green.

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
