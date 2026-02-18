# Deployment Notes

## Environment variables
- **SECRET_KEY** (required): Set a secure random key in production. E.g. `openssl rand -hex 32`
- **FLASK_DEBUG**: Set to `false` or unset in production

## Run with Gunicorn
```bash
gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5000 app:app
```
(Eventlet required for Socket.IO)

## Or run directly
```bash
python app.py
```

## Folders created at runtime
- `static/uploads/profiles/` – profile pictures
- `static/uploads/memories/` – bingo/memory photos
- `exports/` – account export CSVs
