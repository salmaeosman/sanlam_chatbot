# my-dashboard AI chatbot

Microservice Python pour brancher un chatbot IA a `my-dashboard` tout en reutilisant le contexte applicatif expose par `user-mgmt-api`.

## Ce que fait le service

- authentifie chaque requete via le meme JWT que le frontend
- recupere le contexte live depuis `user-mgmt-api`
- utilise l'API `Gemini` pour generer les reponses
- conserve les sessions dans SQLite
- expose une API REST simple pour le widget frontend

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

## Variables d'environnement

Copier `.env.example` vers `.env` puis renseigner au minimum:

```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
USER_MGMT_API_URL=http://localhost:3000
FRONTEND_ORIGINS=http://localhost:5173
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

## Notes

- les sessions sont stockees dans `data/chatbot.sqlite3`
- le chatbot est volontairement en lecture seule
- le moteur LLM distant est `Gemini`
- si le volume de reclamations devient important, vous pourrez ajouter une pagination cote `user-mgmt-api` plus tard
