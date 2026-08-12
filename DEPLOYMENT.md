# Deploying as a Website (Streamlit Community Cloud)

This turns the dashboard into a URL you just open — no Python commands,
no local setup, ever again after this one-time deployment. Takes about
10 minutes. It's free, and since there's no API key involved, there
are no secrets to configure either.

## Step 1: Put the code on GitHub
Streamlit Cloud deploys directly from a GitHub repo.

1. Go to https://github.com/new and create a repository (e.g.
   `nse-stock-dashboard`). Public or private both work fine — there
   are no credentials embedded in this code.
2. Upload all the files from this folder to that repo. Easiest way if
   you're not familiar with git:
   - On the new repo's GitHub page, click **"uploading an existing file"**
   - Drag in every file from this folder
   - Commit.

   (If you're comfortable with git/terminal instead: `git init`,
   `git add .`, `git commit -m "initial commit"`, then push to the repo
   URL GitHub gives you.)

## Step 2: Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io and sign in with your GitHub account.
2. Click **"New app"**.
3. Pick your `nse-stock-dashboard` repo, branch `main`, and set the main
   file path to `app.py`.
4. Click **Deploy** — no secrets to add, nothing else to configure.
   Streamlit builds the app (installs requirements.txt automatically);
   first deploy takes a couple of minutes.

## Step 3: Use it
You'll get a URL like `https://nse-stock-dashboard-yourname.streamlit.app`.
Bookmark it. Open it from any device — phone, laptop, anywhere — pick
your universe, click "Run today's screen," done. No login flow at all.

## Notes on this hosting setup

- **Free tier limits**: Streamlit Community Cloud free tier apps sleep
  after a period of inactivity and wake up (in ~30 seconds) on the next
  visit — completely normal, no action needed from you.
- **Updating the logic later**: if you ever want to tweak a threshold
  (say, change the RSI cutoff in `config.py`), edit the file on GitHub
  (their web-based editor works fine, no local tools needed) and
  Streamlit Cloud auto-redeploys within a minute of the commit. You'll
  never need to run anything locally.
- **Rate limits**: Yahoo Finance's free endpoint can throttle very
  aggressive polling. The default refresh intervals in the app (1-15
  min) are chosen to stay well within safe limits — avoid setting a
  custom interval lower than that if you modify the code.

## Alternative hosts

This same `app.py` runs unmodified on **Render**, **Railway**, or a
small VPS — anywhere that can run `streamlit run app.py` and expose
port 8501. Streamlit Cloud is simplest because it's purpose-built for
exactly this and free for a single app.
