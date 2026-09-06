# Publish Playing in New York on GitHub

This folder contains the complete website, current listings, locally cached film images, Courier Prime font, scraper source, and GitHub Actions workflow. There is no frontend build step.

## 1. Create and push the repository

Create an empty GitHub repository named playing-in-new-york. Do not initialize it with a README. Unzip this archive, open a terminal inside the extracted playing-in-new-york folder, and run the following, replacing YOUR-USERNAME with your GitHub username:

```sh
git init
git add .
git commit -m "Add Playing in New York"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/playing-in-new-york.git
git push -u origin main
```

Authenticate with GitHub when prompted. GitHub Desktop can also publish the extracted folder. Preserve the included .github directory: it contains the scheduled workflow.

## 2. Enable publishing

In the repository, open Settings → Pages and choose GitHub Actions as the source. Ensure Actions is enabled and repository policies permit the workflow's contents: write and Pages deployment permissions. The default branch must be main. Branch rules that prohibit the workflow from committing directly will need adjustment.

Then open Actions → Refresh screenings and publish → Run workflow on main. This fetches current listings, validates them, saves the snapshot, and publishes the website. The initial push may have failed deployment before Pages was enabled; rerun the workflow after setup.

Open the URL reported by the successful deployment. It will normally be https://YOUR-USERNAME.github.io/playing-in-new-york/ . This is separate from the existing ChatGPT-hosted preview; GitHub updates do not update that preview.

## 3. Daily refresh

The included workflow requests a run at 8:00 a.m. America/New_York every day, adjusting for daylight saving. GitHub may queue scheduled runs, so this is not a guarantee that updated listings will be published at exactly 8:00. Check the Actions tab after the first scheduled run. Public-repository schedules can be disabled after 60 days without repository activity.

Timezone support: https://github.blog/changelog/2026-03-19-github-actions-late-march-2026-updates/
Pages setup: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

## Content maintenance

The daily workflow refreshes listings and downloads available film images. Individually sourced replacement images are already included. Automatic replacement-still sourcing is now implemented through TMDB; enable it using the setup below. AI summaries for newly added films are still maintained separately. Add new summaries to dist/data/film-summaries.json; each sentence must split at a word boundary into two lines of at most 30 characters each. No AI API key is needed for the current site.

Helvetica Neue uses the font installed on the visitor's device, with Helvetica/Arial fallbacks; Courier Prime is included. See README.md for coverage and source details.

## Preview locally

```sh
python3 -m http.server 8000 --directory dist
```

Visit http://localhost:8000 . Opening index.html directly will not load the JSON data reliably; use the local server.

## Enable automatic replacement images

1. Obtain a TMDB API Read Access Token from https://www.themoviedb.org/settings/api .
2. Add it in your GitHub repository under Settings → Secrets and variables → Actions → New repository secret, named TMDB_READ_TOKEN. Do not put the token in any project file.
3. Complete TMDB attribution before enabling its use: add an approved logo and its required notice in a Credits/About section. See README.md and https://developer.themoviedb.org/docs/faq .
4. Run the refresh workflow manually once. Review dist/data/image-issues.json for any titles that could not be matched confidently.

Existing good images are preserved. Missing/corrupt/small images trigger a lookup; candidates must match the film identity and meet minimum dimensions. No arbitrary search-result image is accepted. The process runs during the scheduled refresh, not when visitors hover. No token was bundled, and live API access has not been verified with your account.
