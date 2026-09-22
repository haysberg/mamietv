# MamieTV

MamieTV génère une page statique qui affiche **ce qui passe en prime time
(21 h – minuit) sur les chaînes de la TNT française**.

Un seul script Python (lancé via `uv`) télécharge le guide XMLTV, choisit les
programmes, télécharge les logos et écrit un dossier `dist/` prêt à publier —
sur GitHub Pages ou n'importe quel hébergeur statique. Aucun serveur applicatif.

```bash
uv run python build.py      # écrit dist/
python3 -m http.server -d dist 8000   # aperçu local
```

## Fonctionnement

1. **Téléchargement** (`utils/xmltv.py`) : le guide XMLTV de
   [XML TV Fr](https://xmltvfr.fr) (`xmltv_tnt.xml.gz`, régénéré chaque jour).
2. **Sélection** : on ne garde que la fenêtre « ce soir » (21 h → minuit), et
   par chaîne les **deux « vrais » programmes** de la soirée (le prime et sa
   suite), façon Télé-Loisirs. Les interstitiels de moins de 25 min (météo,
   bandes-annonces) sont ignorés au moment de choisir. Un programme commencé
   avant 21 h est gardé s'il lui reste au moins 30 min (un match à 20 h 35),
   pas s'il se termine vers 21 h 25 (Quotidien, émissions d'avant-soirée).
3. **Logos** (`utils/images.py`) : téléchargés en 96×96 (~6 ko au lieu de 130 ko)
   dans `dist/channels/`, servis depuis notre origine (aucun hôte tiers).
4. **Rendu** (`utils/render.py`) : `dist/` est recréé à partir de `static/`
   (assets versionnés), puis `dist/index.html` (Jinja2 + `minify-html`) et
   `dist/data/epg.json` sont écrits de façon atomique, avec
   `dist/data/version.json` (juste `generated_at`) que la page interroge toutes
   les 15 min pour savoir si un guide plus récent est publié.

## Contenu de `dist/`

```
dist/
├── index.html            # page générée (URLs relatives)
├── data/epg.json         # données du soir
├── data/version.json     # generated_at seul, pour le rafraîchissement
├── channels/*.png        # logos téléchargés
├── css/ js/ icons/       # assets copiés depuis static/
├── manifest.webmanifest  # manifeste PWA
├── sw.js                 # service worker (hors ligne)
├── robots.txt
└── 404.html
```

Toutes les URLs sont **relatives**, donc le site fonctionne aussi bien à la
racine qu'en sous-chemin de projet (`https://exemple.github.io/mamietv/`).

## Structure du dépôt

```
mamietv/
├── build.py               # point d'entrée : uv run python build.py
├── mamietv.toml           # configuration (source, fenêtre, chaînes)
├── pyproject.toml         # dépendances (uv), ruff, pytest
├── utils/
│   ├── config.py          # vue typée de mamietv.toml
│   ├── xmltv.py           # téléchargement + parsing + sélection
│   ├── images.py          # téléchargement des logos
│   ├── render.py          # copie des assets + rendu dans dist/
│   ├── build.py           # orchestration
│   └── logs.py            # structlog
├── templates/             # Jinja2 (index, head)
├── static/                # assets sources versionnés (css, js, icons, PWA…)
├── build_tools/
│   └── make_icons.py      # génère les icônes PWA (Pillow, dev uniquement)
└── tests/                 # pytest
```

## Installation

Prérequis : Python 3.14+ et [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run python build.py
```

Avec [go-task](https://taskfile.dev) : `task build`, `task preview`,
`task icons`, `task check`.

## Configuration (`mamietv.toml`)

```toml
[source]
url = "https://xmltvfr.fr/xmltv/xmltv_tnt.xml.gz"

[evening]
start_hour = 21
start_minute = 0
end_hour = 0
end_minute = 0
carry_over_minutes = 30   # un show commencé avant 21 h compte s'il reste ≥ 30 min
max_programs = 2          # nombre de shows retenus par chaîne (le 1er et le 2e)
min_duration_minutes = 25 # en-dessous, considéré comme un interstitiel
channels = []             # liste blanche ; vide = tous les programmes du guide
```

Variables d'environnement : `LOGLEVEL`, et `MAMIETV_STATIC_DIR`,
`MAMIETV_TEMPLATES_DIR`, `MAMIETV_CONFIG`, `MAMIETV_DIST_DIR` pour déplacer les
chemins.

## PWA

`dist/` contient un manifeste et un service worker : le site est installable
(« Ajouter à l'écran d'accueil ») et reste consultable hors ligne (le dernier
programme est mis en cache ; le guide est servi en *network-first*).

Les icônes sont versionnées dans `static/icons/`. Pour les régénérer :

```bash
uv run python build_tools/make_icons.py
```

## Déploiement sur GitHub Pages

Le workflow `.github/workflows/pages.yml` :

1. s'exécute **toutes les 6 h** (cron `17 */6 * * *`), sur `workflow_dispatch`,
   et à chaque push sur `main` touchant les sources ;
2. lance `uv run python build.py` puis publie `dist/` via `actions/deploy-pages`.

Côté dépôt, une seule fois : **Settings → Pages → Source: GitHub Actions**.

> Le cron GitHub peut être retardé (voire désactivé après 60 jours sans commit).
> En cas de besoin, relancer le workflow manuellement depuis l'onglet Actions.

## Tests et lint

```bash
task check
# équivalents directs
uv run ruff check .
uv run pytest -q
```

## Licence

Voir le fichier [LICENSE](LICENSE).
