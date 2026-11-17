# JobMatch API

API REST de **recommandation d'offres d'emploi** : Django REST Framework, PostgreSQL + **pgvector**, **Celery/Redis** pour l'analyse asynchrone des CV, moteur de matching **hybride** (embeddings sémantiques + règles métier), tests pytest (couverture ≥ 80 %), CI/CD GitHub Actions et déploiement Docker Compose sur VPS.

## Architecture

```
            ┌──────────┐   JWT    ┌──────────────┐  SQL + <=> (cosinus)  ┌────────────────────┐
 client ───▶│  nginx   │────────▶ │ Django / DRF │──────────────────────▶│ PostgreSQL+pgvector│
            └──────────┘          │  (gunicorn)  │                       └────────────────────┘
                                  └──────┬───────┘                                 ▲
                                         │ .delay()                                │
                                         ▼                                         │
                                  ┌──────────────┐     ┌──────────────────────────┐│
                                  │    Redis     │────▶│ Celery worker            ││
                                  └──────────────┘     │ • analyse de CV          │┘
                                         ▲             │ • embeddings (MiniLM)    │
                                  ┌──────┴───────┐     └──────────────────────────┘
                                  │ Celery beat  │  réindexation nocturne, expiration des offres
                                  └──────────────┘
```

| App | Rôle |
|---|---|
| `apps/accounts` | Utilisateur custom (login par email, rôles `candidate` / `recruiter` / `admin`), JWT, permissions |
| `apps/jobs` | Compétences (taxonomie seedée, ~90 entrées avec alias), entreprises, offres (+ embedding 384 d, index HNSW) |
| `apps/candidates` | Profil candidat, upload de CV, parsing (PDF/DOCX/TXT), tâche `analyze_resume` |
| `apps/matching` | Embedder, règles métier, moteur hybride, historique & feedback des recommandations |
| `apps/core` | Healthcheck, pagination, format d'erreur, choix communs |

## Moteur de matching hybride

1. **Filtres durs (SQL)** : offre active et non expirée, type de contrat souhaité, candidat « full remote » → offres remote/hybride uniquement, offres rejetées (`liked=false`) exclues.
2. **Récupération sémantique** : top‑K (`MATCHING_CANDIDATE_POOL`, 200) par distance cosinus pgvector entre l'embedding du profil (headline, résumé, compétences, extrait du dernier CV) et celui des offres. Sans embedding → repli sur les offres récentes.
3. **Re‑classement par règles** (`apps/matching/services/rules.py`, scores ∈ [0,1]) :

| Critère | Poids | Règle |
|---|---|---|
| `semantic` | 0.50 | similarité cosinus |
| `skills` | 0.25 | couverture des compétences, requises ×2 |
| `experience` | 0.10 | 1 si ≥ minimum, sinon ratio |
| `location` | 0.08 | remote = 1, même ville = 1, hybride ailleurs = 0.3, pénalité si le candidat veut du full remote |
| `salary` | 0.04 | 1 si le haut de fourchette ≥ attente, décroissance sinon |
| `freshness` | 0.03 | décroissance linéaire sur 60 jours |

Chaque recommandation renvoie un **`score_breakdown`** explicable. Les poids sont dans `settings.MATCHING_WEIGHTS`. Le même moteur sert en sens inverse : `GET /jobs/{id}/matching-candidates/` pour le recruteur.

## Analyse asynchrone des CV

`POST /api/v1/resumes/` (multipart, PDF/DOCX/TXT ≤ 5 Mo) → **202 Accepted** + `status: pending`. Le worker :
extraction du texte → compétences (taxonomie + alias + tolérance aux fautes via rapidfuzz) → années d'expérience (mention explicite ou fusion des périodes datées FR/EN, « 2021 – aujourd'hui ») → email/téléphone → enrichissement du profil → recalcul de l'embedding. Statut `done` ou `failed` (+ `error`). Retries exponentiels sur erreurs I/O.

## Endpoints (`/api/v1/`)

Documentation interactive : **`/api/docs/`** (Swagger), schéma : `/api/schema/`.

| Méthode | Route | Accès |
|---|---|---|
| POST | `auth/register/` · `auth/token/` · `auth/token/refresh/` | public |
| GET/PATCH | `auth/me/` | connecté |
| GET | `jobs/` (filtres `contract_type`, `remote`, `location`, `skill`, `company`, `search`, `ordering`) · `jobs/{id}/` · `companies/` · `skills/` | public |
| POST/PATCH/DELETE | `jobs/` · `companies/` | recruteur propriétaire |
| GET/PATCH | `candidates/me/` | candidat |
| POST/GET/DELETE | `resumes/` · `resumes/{id}/` | candidat |
| GET | `recommendations/?limit=&contract_type=&remote=&location=` | candidat |
| POST/PATCH | `recommendations/{id}/feedback/` (`liked`, `applied`) | candidat |
| GET | `jobs/{id}/matching-candidates/` | recruteur propriétaire |
| GET | `health/` | public (DB + Redis) |

### Exemple

```bash
curl -s -X POST localhost:8000/api/v1/auth/register/ -H 'Content-Type: application/json' \
  -d '{"email":"awa@example.com","username":"awa","password":"Tr3s-solide!"}'
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/token/ -d email=awa@example.com -d password='Tr3s-solide!' | jq -r .access)
curl -s -H "Authorization: Bearer $TOKEN" -F file=@cv.pdf localhost:8000/api/v1/resumes/
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/recommendations/?limit=5
```

## Démarrage

### Avec Docker (recommandé)

```bash
cp .env.example .env
docker compose up --build
```

API sur http://localhost:8000. Pour un build rapide sans torch (≈ 1 Go de moins), mettez `INSTALL_ML=0` et `EMBEDDER_BACKEND=fake` dans `.env`. Le modèle `paraphrase-multilingual-MiniLM-L12-v2` est téléchargé au premier embedding puis mis en cache dans le volume `hf-cache`.

### En local

Prérequis : Python 3.12+, PostgreSQL 16 avec l'extension `vector`, Redis.

```bash
make install                       # venv + dépendances de dev
.venv/bin/pip install -r requirements/ml.txt   # modèle d'embeddings (torch CPU)
cp .env.example .env               # adapter DATABASE_URL / REDIS_URL
python manage.py migrate           # crée l'extension vector et seed les compétences
python manage.py runserver
celery -A config worker -l info    # dans un autre terminal
```

Sans `ml.txt`, mettez `EMBEDDER_BACKEND=fake` (embeddings par hachage, utile pour le dev rapide).

## Tests & qualité

```bash
make test      # pytest + couverture (échoue sous 80 %)
make lint      # ruff check + ruff format --check
```

Les tests utilisent une vraie base PostgreSQL/pgvector, Celery en mode eager et un `FakeEmbedder` déterministe (pas de modèle à télécharger). Couverture actuelle : **~97 %**.

## CI/CD

- **`ci.yml`** (push / PR) : ruff → vérification des migrations → pytest avec services `pgvector/pgvector:pg16` et `redis:7` (seuil 80 %, rapport `coverage.xml` en artefact) → build de l'image Docker sur les PR.
- **`cd.yml`** (CI verte sur `main`, tag `v*` ou manuel) : build & push sur GHCR (`sha-<commit>` + `latest`) → si `DEPLOY_ENABLED=true`, copie des fichiers de déploiement sur le VPS → `scripts/deploy.sh` : pull, migrations, `up -d`, healthcheck, **rollback automatique** vers l'image précédente en cas d'échec.

### Mise en place du VPS

1. Installer Docker + le plugin Compose, créer `/opt/jobmatch` et y placer un `.env` de production (voir `.env.example` ; `DJANGO_ALLOWED_HOSTS` doit inclure `localhost` pour le healthcheck).
2. Dans GitHub → *Settings → Environments → production*, ajouter les secrets :
   `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (clé privée), optionnellement `VPS_APP_DIR` et `GHCR_READ_TOKEN` (PAT `read:packages`, nécessaire si le package GHCR est privé, car le `GITHUB_TOKEN` expire après le job).
3. Dans *Settings → Secrets and variables → Actions → Variables*, créer la variable de dépôt `DEPLOY_ENABLED` = `true`. Sans elle, le CD publie l'image sur GHCR mais saute l'étape de déploiement.
4. HTTPS : placer un certificat devant nginx (Certbot, ou Caddy/Traefik) puis mettre `DJANGO_SECURE_SSL_REDIRECT=1`.

> Le rollback restaure l'image précédente mais ne revient pas sur les migrations : gardez des migrations rétro‑compatibles (expand/contract).
