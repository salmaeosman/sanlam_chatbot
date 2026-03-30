# my-dashboard AI chatbot + PV backend

Backend Python autonome pour `my-dashboard` qui regroupe:

- le microservice chatbot IA existant
- un backend PV compatible avec la logique de `incident-intel-bot`

Tu peux donc reutiliser ce dossier `back-python` comme backend separe, sans dependre du repo `incident-intel-bot`.

## Ce que fait le service

- authentifie chaque requete via le meme JWT que le frontend
- recupere le contexte live depuis `user-mgmt-api`
- utilise l'API `Gemini` pour generer les reponses
- conserve les sessions dans SQLite
- expose une API REST simple pour le widget frontend
- gere aussi les extractions de PV en local avec stockage SQLite
- conserve les documents source uploades
- peut deleguer l'extraction OCR/IA a un autre service Python si `PV_REMOTE_INGEST_URL` est configure

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
- `GET /pv-extractions`
- `GET /pv-extractions/{id}`
- `POST /pv-extractions/ingest`
- `PATCH /pv-extractions/{id}`
- `DELETE /pv-extractions/{id}`
- `GET /pv-extractions/{id}/source-document`
- alias disponibles aussi sous `/api/v1/pv-extractions/...`

## Variables d'environnement

Copier `.env.example` vers `.env` puis renseigner au minimum:

```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
USER_MGMT_API_URL=http://localhost:3000
FRONTEND_ORIGINS=http://localhost:5173
PV_DB_PATH=data/pv_records.sqlite3
PV_UPLOAD_DIR=data/pv_uploads
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
```

Le widget frontend envoie automatiquement le JWT courant au microservice. Le microservice reutilise ensuite ce JWT pour appeler `user-mgmt-api`, qui lui-meme parle deja a PostgreSQL.

Pour reutiliser l'ancien frontend `incident-intel-bot`, il suffit de pointer:

```env
VITE_API_URL=http://localhost:8001
```

Le frontend n'est alors plus requis pour faire tourner le backend.

## Notes

- les sessions sont stockees dans `data/chatbot.sqlite3`
- les PV sont stockes dans `data/pv_records.sqlite3`
- les fichiers uploades PV sont stockes dans `data/pv_uploads/`
- le chatbot est volontairement en lecture seule
- le moteur LLM distant est `Gemini`
- si le volume de reclamations devient important, vous pourrez ajouter une pagination cote `user-mgmt-api` plus tard

## Peut-on supprimer `incident-intel-bot` ?

Oui, une fois que tu as:

- garde ce dossier `back-python`
- configure le frontend cible (`my-dashboard` ou un autre) pour appeler ce backend
- verifie que tes appels PV passent bien par `http://localhost:8001`

Le backend PV n'est plus heberge dans `incident-intel-bot`.
