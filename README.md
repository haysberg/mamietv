# MamieTV

MamieTV affiche **ce qui passe en prime time (20 h 45 – minuit) sur les chaînes
de la TNT française**.
Le backend télécharge le guide XMLTV, le découpe et écrit une poignée de
fichiers statiques ; le front n'est qu'une page qui les lit. Aucun proxy CORS,
aucun parsing XML dans le navigateur, aucun appel réseau côté client.

- **Source des données** : [XML TV Fr](https://xmltvfr.fr) —
  `https://xmltvfr.fr/xmltv/xmltv_tnt.xml.gz` (30 chaînes, régénéré chaque jour).
- **Backend** : FastAPI + APScheduler. Un rafraîchissement toutes les 3 h via
  une requête conditionnelle (`ETag` / `Last-Modified`) : quand le guide n'a pas
  changé, l'origine répond `304` et rien n'est réécrit.
- **Génération** : Jinja2 → `minify-html` → écriture atomique avec des copies
  pré-compressées `.br` / `.gz` (brotli qualité 11, produit une fois par
  régénération, jamais par requête).
- **Service** : FastAPI sert l'arbre statique en négociant `Accept-Encoding`
  et en posant les en-têtes de cache et de sécurité.
- **Sélection façon Télé-Loisirs** : pour chaque chaîne, on garde les deux
  « vrais » programmes de la soirée (le prime et sa suite) ; les interstitiels
  de moins de 25 min (météo, bandes-annonces) sont ignorés au moment de choisir.
- **Logos** : les logos des chaînes sont téléchargés une fois côté backend (petit
  format 96×96, ~6 ko), stockés dans `static/channels/` et servis depuis notre
  origine : plus aucune dépendance à un hôte tiers.
- **Front** : HTML/CSS/JS vanilla, une page, qui lit `data/epg.json`.
- **PWA installable** : manifeste + service worker, donc installable sur un
  téléphone (« Ajouter à l'écran d'accueil ») et consultable hors ligne grâce au
  cache de la dernière soirée.

## Fonctionnement

1. **Démarrage** (`app.py`) : `init_service()` pré-compresse les assets
   versionnés puis lance un premier `update_epg()` ; le planificateur prend le
   relais ensuite.
2. **Mise à jour** (`utils/utils.py`) : téléchargement conditionnel du guide,
   parsing (`utils/xmltv.py`), rendu (`utils/render.py`).
3. **Écriture** : `write_compressed()` écrit d'abord les copies `.br`/`.gz`, puis
   le fichier nu, chaque fois via un fichier temporaire et `os.replace` : une
   requête concurrente ne voit jamais un fichier tronqué.
4. **Service** : `utils/web.py` sert `<fichier>.br`/`.gz` si le client
   l'accepte, ajoute `Vary: Accept-Encoding`, `Cache-Control` et les en-têtes
   de sécurité.

## Structure

```
mamietv/
├── app.py                 # Point d'entrée FastAPI + scheduler
├── mamietv.toml           # Configuration (source, fenêtre « ce soir »)
├── precompress.py         # Écriture atomique + brotli/gzip
├── pyproject.toml         # Dépendances (uv), ruff, pytest
├── utils/
│   ├── config.py          # Vue typée de mamietv.toml
│   ├── xmltv.py           # Téléchargement + parsing XMLTV
│   ├── render.py          # Rendu Jinja + arbre statique
│   ├── web.py             # Middlewares compression / en-têtes
│   ├── utils.py           # Orchestration
│   └── logs.py            # structlog
├── templates/             # Jinja2 (index, head, footer)
├── static/                # Sources versionnées + fichiers générés
│   ├── manifest.webmanifest  # Manifeste PWA
│   ├── sw.js              # Service worker (cache hors ligne)
│   ├── icons/             # Icônes PWA/favicon (générées, versionnées)
│   └── ...
├── build_tools/
│   └── make_icons.py      # Génère les icônes PWA (Pillow, dev uniquement)
└── tests/                 # pytest
```

### PWA

L'app est installable : sur mobile, ouvrir le site puis « Ajouter à l'écran
d'accueil ». Le service worker (`static/sw.js`) met en cache la coquille et
sert le guide en *network-first* (la dernière soirée est dispo hors ligne).

Les icônes sont versionnées. Pour les régénérer après un changement de logo :

```bash
uv run python build_tools/make_icons.py
```

## Installation

Prérequis : Python 3.14+ et [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run python app.py          # http://localhost:8000
```

`task install` et `task` (défaut) font la même chose si [go-task](https://taskfile.dev)
est installé.

Générer les fichiers une seule fois puis quitter :

```bash
task build
# ou : uv run python build.py
```

## Déploiement sur GitHub Pages

Le workflow `.github/workflows/pages.yml` régénère le guide puis publie `static/`
sur GitHub Pages :

1. Il s'exécute **toutes les 6 h** (cron), sur `workflow_dispatch`, et à chaque
   push sur `main` touchant les sources.
2. Il lance `uv run python build.py` (même `init_service()` que le serveur), puis
   publie le dossier `static/` (les `.br`/`.gz` sont retirés : Pages compresse
   lui-même) via `actions/deploy-pages`.
3. Côté dépôt, une seule fois : **Settings → Pages → Source: GitHub Actions**.

Le site est servi à `https://<utilisateur>.github.io/mamietv/`. Toutes les URLs
de la page sont **relatives**, donc le sous-chemin de projet fonctionne sans
configuration (et le serveur FastAPI local sur `/` aussi).

> Les données générées ne sont pas versionnées : elles sont produites à chaque
> exécution du workflow et publiées en artifact, ce qui garde le dépôt léger.

## Configuration (`mamietv.toml`)

```toml
[source]
url = "https://xmltvfr.fr/xmltv/xmltv_tnt.xml.gz"
user_agent = "MamieTV/1.0 (+https://github.com/haysberg/mamietv)"

[server]
update_interval_minutes = 180
host = "0.0.0.0"
port = 8000

[evening]
start_hour = 20
start_minute = 45
end_hour = 0
end_minute = 0
buffer_hours = 0
max_programs = 2          # nombre de shows retenus par chaîne (le 1er et le 2e)
min_duration_minutes = 25 # en-dessous, considéré comme un interstitiel
channels = []             # liste blanche ; vide = toutes les chaînes du guide
```

Variables d'environnement : `LOGLEVEL` (défaut `INFO`), `TZ` (défaut
`Europe/Paris`) et `MAMIETV_STATIC_DIR`, `MAMIETV_TEMPLATES_DIR`,
`MAMIETV_CONFIG` pour déplacer les chemins.

## Déploiement Docker

```bash
docker-compose up -d          # image ghcr.io/haysberg/mamietv:latest
docker-compose -f docker-compose-dev.yml up --build   # build local
```

## Tests et lint

```bash
task check
# équivalents directs
uv run ruff check .
uv run pytest -q
```

## Licence

Voir le fichier [LICENSE](LICENSE).
