# Package Déploiement 2026 - Migration YAML Complète

## Nouvelles Fonctionnalités 2026:
✅ **Migration PostgreSQL → YAML**: Plus de base de données externe requise
✅ **Stockage fichiers locaux**: Dossier data/ avec fichiers YAML structurés  
✅ **Performance améliorée**: Élimination des connexions base de données
✅ **Commande /intervalle**: Configuration délai 1-60 minutes (actuel: 1min)
✅ **Système As optimisé**: Déclenchement uniquement dans premier groupe

## Architecture YAML:
- bot_config.yaml: Configuration persistante
- predictions.yaml: Historique prédictions
- auto_predictions.yaml: Planification automatique  
- message_log.yaml: Logs avec nettoyage automatique

## Variables Render.com:
- Configurez toutes les variables de .env.example
- Port: 10000
- Start Command: python render_main.py
- PLUS BESOIN de DATABASE_URL PostgreSQL

## Commandes Disponibles:
/intervalle [minutes] - Configurer délai prédiction
/status - État complet avec intervalle
/deploy - Générer ce package

🚀 Déploiement 100% autonome sans dépendances externes!