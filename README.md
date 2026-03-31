# my-dashboard AI chatbot + PV backend

Backend Python autonome pour `my-dashboard` qui regroupe:

- le microservice chatbot IA existant
- le backend PV qui remplace `incident-intel-bot`

Tu peux donc reutiliser ce dossier `back-python` comme backend separe et supprimer ensuite `incident-intel-bot`.

## Ce que fait le service

- authentifie chaque requete via le meme JWT que le frontend
- recupere le contexte live depuis `user-mgmt-api`
- utilise l'API `Gemini` pour generer les reponses
- conserve les sessions dans SQLite
- expose une API REST simple pour le widget frontend
- expose aussi les routes PV compatibles avec `my-dashboard`

## Architecture

- frontend: `my-dashboard`
- backend metier: `user-mgmt-api`
- base de donnees metier: PostgreSQL / `user_mgmt`
- microservice IA: `back-python`

Le microservice ne lit pas directement PostgreSQL. Il passe par `user-mgmt-api`, qui reste l'unique point d'acces a votre base `user_mgmt`.

## Endpoints

- `GET /health`
- `POST /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{session_id}`
- `POST /api/v1/chat/sessions/{session_id}/messages`
- `POST /pv-extractions/ingest`
- `GET /pv-extractions`
- `GET /pv-extractions/stats`
- `GET /pv-extractions/{id}`
- `PATCH /pv-extractions/{id}`
- `DELETE /pv-extractions/{id}`
- `GET /pv-extractions/{id}/source-document`

Des alias existent aussi sous `/api/v1/pv-extractions/...`.

## Variables d'environnement

Copier `.env.example` vers `.env` puis renseigner au minimum:

```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
USER_MGMT_API_URL=http://localhost:3000
FRONTEND_ORIGINS=http://localhost:5173
CHATBOT_DB_PATH=data/chatbot.sqlite3
USER_MGMT_PV_UPLOAD_TIMEOUT_SECONDS=180
PV_UPLOAD_MAX_BYTES=15728640
```

## Installation

```bash
venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Lancement

```bash
venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

## Integration frontend

Dans `my-dashboard/.env`:

```env
VITE_API_URL=http://localhost:3000
VITE_CHATBOT_API_URL=http://localhost:8001
VITE_PV_AGENT_API_URL=http://localhost:8001
```

Le widget frontend envoie automatiquement le JWT courant au microservice. Le microservice reutilise ensuite ce JWT pour appeler `user-mgmt-api`, qui lui-meme parle deja a PostgreSQL.

## Notes

- les sessions sont stockees dans `data/chatbot.sqlite3`
- les PV restent stockes dans `user-mgmt-api` / PostgreSQL
- le chatbot est volontairement en lecture seule
- le moteur LLM distant est `Gemini`
- si le volume de reclamations devient important, vous pourrez ajouter une pagination cote `user-mgmt-api` plus tard

## Migration depuis `incident-intel-bot`

Une fois `back-python` lance et `my-dashboard` pointe vers `http://localhost:8001` pour `VITE_PV_AGENT_API_URL`, le repo `incident-intel-bot` n est plus necessaire pour l extraction PV.
