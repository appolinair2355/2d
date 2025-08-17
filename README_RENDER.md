# 🚀 Guide de Déploiement sur Render.com

## 📋 Fichiers Inclus dans le Pack

- `render_main.py` - Version optimisée pour Render avec serveur web
- `predictor.py` - Moteur de prédiction
- `render_requirements.txt` - Dépendances Python
- `render.yaml` - Configuration Render (optionnel)
- `README_RENDER.md` - Ce guide

## 🔧 Étapes de Déploiement

### 1. Préparation
1. Créez un compte sur [render.com](https://render.com)
2. Uploadez tous les fichiers du pack dans un repository GitHub

### 2. Configuration Render
1. **Créer un nouveau Web Service**
   - Repository: Votre repo GitHub
   - Branch: `main`
   - Root Directory: `/` (racine)

2. **Configuration Build**
   - Build Command: `pip install -r render_requirements.txt`
   - Start Command: `python render_main.py`

3. **Variables d'Environnement**
   ```
   API_ID = 29177661
   API_HASH = a8639172fa8d35dbfd8ea46286d349ab
   BOT_TOKEN = 7989231030:AAGouDi684CxXUy2f5GpQTtNkyu6rQoVVoQ
   ADMIN_ID = 1190237801
   PORT = 10000
   ```

### 3. Plan Gratuit
- **Type**: Web Service
- **Plan**: Free (750h/mois gratuit)
- **Région**: Frankfurt (recommandé pour l'Europe)

### 4. Health Check
Le bot expose automatiquement:
- `https://votre-app.onrender.com/` - Page de statut
- `https://votre-app.onrender.com/health` - Health check

## ⚠️ Limitations du Plan Gratuit

- **Hibernation**: Le service s'endort après 15 min d'inactivité
- **Réveil**: Premier accès peut prendre 30-60 secondes
- **Solution**: Utilisez un service de ping (comme UptimeRobot) pour maintenir éveillé

## 🔍 Monitoring

### Logs en Temps Réel
```bash
# Dans l'interface Render, allez dans "Logs" pour voir:
Bot démarré avec succès...
Bot connecté: @Appma_bot
Web server started on port 10000
✅ Bot en ligne et en attente de messages...
```

### Vérification de Fonctionnement
1. Visitez `https://votre-app.onrender.com/` 
2. Vous devez voir: "Bot is running!"
3. Testez `/start` sur votre bot Telegram

## 🚨 Dépannage

### Bot ne Répond Pas
1. Vérifiez les logs Render
2. Vérifiez les variables d'environnement
3. Testez l'URL de health check

### Service Endormi
1. Configurez un service de ping (UptimeRobot gratuit)
2. Pingez votre URL toutes les 10 minutes
3. Ou passez au plan payant ($7/mois)

### Erreurs Courantes
- **Port Error**: Render assigne automatiquement le port via `$PORT`
- **Session Lock**: Normal au premier démarrage
- **Health Check Failed**: Vérifiez que le serveur web démarre

## 📞 Support

En cas de problème:
1. Consultez les logs Render
2. Vérifiez la configuration des variables
3. Testez en local d'abord avec `python render_main.py`

## 🎯 Fonctionnalités Déployées

Toutes les fonctionnalités avancées du bot sont incluses:
- ✅ Détection automatique des canaux avec invitations privées
- ✅ Prédictions automatiques anticipées (déclenchées sur 5, 7, 8)
- ✅ Prédictions pour les prochains jeux se terminant par 0
- ✅ Vérification des résultats avec statuts détaillés (✅0️⃣, ✅1️⃣, ✅2️⃣, ⭕❌)
- ✅ Rapports automatiques au format personnalisé toutes les 20 mises à jour
- ✅ Commandes administratives complètes
- ✅ Pack de déploiement automatique avec /deploy
- ✅ Health check web pour Render

## 📋 Logique de Prédiction

**Déclenchement** : Jeux se terminant par 5, 7, ou 8
**Cible** : Prochains jeux se terminant par 0

**Exemples** :
- Jeu #1445 détecté → Prédiction pour #1450
- Jeu #1447 détecté → Prédiction pour #1450  
- Jeu #1448 détecté → Prédiction pour #1450

**Format des rapports** :
```
📊 Bilan des 20 dernières prédictions :
🔵120📌 D🔵 statut :✅0️⃣
🔵130📌 D🔵 statut :✅1️⃣
📈 Statistiques: 15/20 (75.0% de réussite)
```

Le bot est maintenant prêt pour la production ! 🚀