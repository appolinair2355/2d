# Package Déploiement 2026 - Migration YAML Complète

## Nouvelles Fonctionnalités 2026:
✅ **Migration PostgreSQL → YAML**: Plus de base de données externe requise
✅ **Stockage fichiers locaux**: Dossier data/ avec fichiers YAML structurés  
✅ **Performance améliorée**: Élimination des connexions base de données
✅ **Commande /intervalle**: Configuration délai 1-60 minutes (actuel: 1min)
✅ **Système As optimisé**: Déclenchement uniquement dans premier groupe
✅ **Multi-plateforme**: Support Replit, Render.com, Docker

## Architecture YAML:
- bot_config.yaml: Configuration persistante
- predictions.yaml: Historique prédictions
- auto_predictions.yaml: Planification automatique  
- message_log.yaml: Logs avec nettoyage automatique

## Déploiement Multi-Plateforme:

### Replit (Port 5000)
- Variables: Configurer dans Replit Secrets
- Start Command: python main.py
- Port automatique: 5000

### Render.com (Port 10000)  
- Variables: Configurer dans Environment
- Start Command: python render_main.py
- Port automatique: 10000

### Docker (Port 8000)
- Variables: Fichier .env ou docker-compose
- Start Command: python render_main.py
- Port configurable: 8000

## Commandes Nouvelles:
/deploy - Package standard
/deploy replit - Package optimisé Replit  
/deploy render - Package optimisé Render.com
/deploy docker - Package avec Dockerfile
/intervalle [minutes] - Configurer délai prédiction
/status - État complet avec intervalle

🚀 Déploiement 100% autonome multi-plateforme!