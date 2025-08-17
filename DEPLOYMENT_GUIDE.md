# Guide de Déploiement Render.com

## 📦 Package Inclus

Le package `render_deployment_complete.zip` contient tous les fichiers nécessaires :

### Fichiers Principaux
- `render_main.py` - Point d'entrée principal avec serveur web
- `render_predictor.py` - Version allégée du moteur de prédiction  
- `predictor.py` - Moteur de prédiction complet avec déclenchement variable
- `scheduler.py` - Système de planification automatique
- `models.py` - Modèles de base de données

### Configuration
- `render.yaml` - Configuration Render.com avec health check
- `render_requirements.txt` - Dépendances Python complètes
- `prediction.yaml` - Données de planification
- `README_RENDER.md` - Documentation spécifique

## 🚀 Instructions de Déploiement

### 1. Préparer le Repository
```bash
# Extraire le package
unzip render_deployment_complete.zip -d telegram-bot-render/
cd telegram-bot-render/
```

### 2. Configuration Render.com

**Variables d'Environnement Requises :**
```
API_ID=29177661
API_HASH=votre_api_hash
BOT_TOKEN=votre_bot_token
ADMIN_ID=1190237801
PORT=10000
```

**Paramètres de Service :**
- **Type:** Web Service
- **Environnement:** Python 3
- **Build Command:** `pip install -r render_requirements.txt`
- **Start Command:** `python render_main.py`
- **Plan:** Free (recommandé pour test)
- **Région:** Frankfurt (ou proche de vos utilisateurs)

### 3. Fonctionnalités Déployées

#### Système de Déclenchement Variable ✅
- Déclencheurs : 6, 7, 8, 9 (au lieu de seulement 7, 8)
- Évite la répétition du même déclencheur
- 30% de chance d'ignorer un déclencheur répétitif

#### Exemples de Variabilité
```
#137 (finit par 7) → prédit #140
#146 (finit par 6) → prédit #150  
#158 (finit par 8) → prédit #160
#169 (finit par 9) → prédit #170
#177 (finit par 7) → peut être ignoré pour variabilité
```

#### Logique ⏰ Corrigée ✅
- ⏰ ne marque plus immédiatement comme échec
- Continue la vérification jusqu'à jeu > prédiction+2
- Marque alors ❌❌ automatiquement

#### Port et Health Check ✅
- Port dynamique Render.com : `0.0.0.0:$PORT`
- Health check endpoint : `/health`
- Monitoring automatique de l'état du service

## 🔧 Vérification Post-Déploiement

### 1. Health Check
```bash
curl https://votre-app.onrender.com/health
# Réponse attendue: "Bot is running!"
```

### 2. Logs à Surveiller
```
✅ Serveur web démarré sur 0.0.0.0:10000 (Render.com)
✅ Configuration chargée: API_ID=29177661, ADMIN_ID=1190237801
Bot connecté: @Appma_bot
✅ Bot en ligne et en attente de messages...
```

### 3. Test des Fonctionnalités
- Ajout du bot dans un canal → Invitation automatique
- Messages avec déclencheurs variables → Prédictions générées
- Messages ⏰ → Logique d'attente correcte
- Vérification 2+2 → Statuts appropriés (✅0️⃣, ✅1️⃣, ✅2️⃣, ❌❌)

## 📊 Monitoring

Le service Render.com surveille automatiquement :
- Réponse du health check endpoint
- Consommation CPU/mémoire
- Logs d'erreur et redémarrages

## 🔄 Mises à Jour

Pour mettre à jour le déploiement :
1. Modifier les fichiers localement
2. Recréer le package avec `python render_complete_package.py`
3. Extraire et push vers le repository Render.com
4. Redéploiement automatique

## 🆘 Support

En cas de problème :
1. Vérifier les logs Render.com
2. Tester le health check endpoint
3. Vérifier les variables d'environnement
4. Consulter la documentation Render.com

---
**Développé par Sossou Kouamé Appolinaire**
**Package créé le 6 Août 2025**