import os
import asyncio
import re
import json
import zipfile
import tempfile
import shutil
from datetime import datetime
from telethon import TelegramClient, events
from telethon.events import ChatAction
from dotenv import load_dotenv
from predictor import CardPredictor
from scheduler import PredictionScheduler
from models import init_database, db
from aiohttp import web
import threading

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
try:
    API_ID = int(os.getenv('API_ID') or '0')
    API_HASH = os.getenv('API_HASH') or ''
    BOT_TOKEN = os.getenv('BOT_TOKEN') or ''
    ADMIN_ID = int(os.getenv('ADMIN_ID') or '0')
    PORT = int(os.getenv('PORT') or '10000')
    
    # Validation des variables requises
    if not API_ID or API_ID == 0:
        raise ValueError("API_ID manquant ou invalide")
    if not API_HASH:
        raise ValueError("API_HASH manquant")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN manquant")
        
    print(f"✅ Configuration chargée: API_ID={API_ID}, ADMIN_ID={ADMIN_ID}, PORT={PORT}")
except Exception as e:
    print(f"❌ Erreur configuration: {e}")
    print("Vérifiez vos variables d'environnement")
    exit(1)

# Fichier de configuration persistante
CONFIG_FILE = 'bot_config.json'

# Variables d'état
detected_stat_channel = None
detected_display_channel = None
confirmation_pending = {}
prediction_interval = 5  # Intervalle en minutes avant de chercher "A" (défaut: 5 min)

def load_config():
    """Load configuration from database"""
    global detected_stat_channel, detected_display_channel, prediction_interval
    try:
        if db:
            detected_stat_channel = db.get_config('stat_channel')
            detected_display_channel = db.get_config('display_channel')
            interval_config = db.get_config('prediction_interval')
            if detected_stat_channel:
                detected_stat_channel = int(detected_stat_channel)
            if detected_display_channel:
                detected_display_channel = int(detected_display_channel)
            if interval_config:
                prediction_interval = int(interval_config)
            print(f"✅ Configuration chargée depuis la DB: Stats={detected_stat_channel}, Display={detected_display_channel}, Intervalle={prediction_interval}min")
        else:
            # Fallback vers l'ancien système JSON si DB non disponible
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    detected_stat_channel = config.get('stat_channel')
                    detected_display_channel = config.get('display_channel')
                    prediction_interval = config.get('prediction_interval', 5)
                    print(f"✅ Configuration chargée depuis JSON: Stats={detected_stat_channel}, Display={detected_display_channel}, Intervalle={prediction_interval}min")
            else:
                print("ℹ️ Aucune configuration trouvée, nouvelle configuration")
    except Exception as e:
        print(f"⚠️ Erreur chargement configuration: {e}")

def save_config():
    """Save configuration to database and JSON backup"""
    try:
        if db:
            # Sauvegarde en base de données
            db.set_config('stat_channel', detected_stat_channel)
            db.set_config('display_channel', detected_display_channel)
            db.set_config('prediction_interval', prediction_interval)
            print("💾 Configuration sauvegardée en base de données")

        # Sauvegarde JSON de secours
        config = {
            'stat_channel': detected_stat_channel,
            'display_channel': detected_display_channel,
            'prediction_interval': prediction_interval
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"💾 Configuration sauvegardée: Stats={detected_stat_channel}, Display={detected_display_channel}, Intervalle={prediction_interval}min")
    except Exception as e:
        print(f"❌ Erreur sauvegarde configuration: {e}")

def update_channel_config(source_id: int, target_id: int):
    """Update channel configuration"""
    global detected_stat_channel, detected_display_channel
    detected_stat_channel = source_id
    detected_display_channel = target_id
    save_config()

# Initialize database
database = init_database()

# Gestionnaire de prédictions
predictor = CardPredictor()

# Planificateur automatique
scheduler = None

# Initialize Telegram client with unique session name
import time
session_name = f'bot_session_{int(time.time())}'
client = TelegramClient(session_name, API_ID, API_HASH)

async def start_bot():
    """Start the bot with proper error handling"""
    try:
        # Load saved configuration first
        load_config()

        await client.start(bot_token=BOT_TOKEN)
        print("Bot démarré avec succès...")

        # Get bot info
        me = await client.get_me()
        username = getattr(me, 'username', 'Unknown') or f"ID:{getattr(me, 'id', 'Unknown')}"
        print(f"Bot connecté: @{username}")

    except Exception as e:
        print(f"Erreur lors du démarrage du bot: {e}")
        return False

    return True

# --- INVITATION / CONFIRMATION ---
@client.on(events.ChatAction())
async def handler_join(event):
    """Handle bot joining channels/groups"""
    global confirmation_pending

    try:
        print(f"ChatAction event: {event}")
        print(f"user_joined: {event.user_joined}, user_added: {event.user_added}")
        print(f"user_id: {event.user_id}, chat_id: {event.chat_id}")

        if event.user_joined or event.user_added:
            me = await client.get_me()
            me_id = getattr(me, 'id', None)
            print(f"Mon ID: {me_id}, Event user_id: {event.user_id}")

            if event.user_id == me_id:
                confirmation_pending[event.chat_id] = 'waiting_confirmation'

                # Get channel info
                try:
                    chat = await client.get_entity(event.chat_id)
                    chat_title = getattr(chat, 'title', f'Canal {event.chat_id}')
                except:
                    chat_title = f'Canal {event.chat_id}'

                # Send private invitation to admin
                invitation_msg = f"""🔔 **Nouveau canal détecté**

📋 **Canal** : {chat_title}
🆔 **ID** : {event.chat_id}

**Choisissez le type de canal** :
• `/set_stat {event.chat_id}` - Canal de statistiques
• `/set_display {event.chat_id}` - Canal de diffusion

Envoyez votre choix en réponse à ce message."""

                try:
                    await client.send_message(ADMIN_ID, invitation_msg)
                    print(f"Invitation envoyée à l'admin pour le canal: {chat_title} ({event.chat_id})")
                except Exception as e:
                    print(f"Erreur envoi invitation privée: {e}")
                    # Fallback: send to the channel temporarily for testing
                    await client.send_message(event.chat_id, f"⚠️ Impossible d'envoyer l'invitation privée. Canal ID: {event.chat_id}")
                    print(f"Message fallback envoyé dans le canal {event.chat_id}")
    except Exception as e:
        print(f"Erreur dans handler_join: {e}")

@client.on(events.NewMessage(pattern=r'/set_stat (-?\d+)'))
async def set_stat_channel(event):
    """Set statistics channel (only admin in private)"""
    global detected_stat_channel, confirmation_pending

    try:
        # Only allow in private chat with admin
        if event.is_group or event.is_channel:
            return

        if event.sender_id != ADMIN_ID:
            await event.respond("❌ Seul l'administrateur peut configurer les canaux")
            return

        # Extract channel ID from command
        match = event.pattern_match
        channel_id = int(match.group(1))

        # Check if channel is waiting for confirmation
        if channel_id not in confirmation_pending:
            await event.respond("❌ Ce canal n'est pas en attente de configuration")
            return

        detected_stat_channel = channel_id
        confirmation_pending[channel_id] = 'configured_stat'

        # Save configuration
        save_config()

        try:
            chat = await client.get_entity(channel_id)
            chat_title = getattr(chat, 'title', f'Canal {channel_id}')
        except:
            chat_title = f'Canal {channel_id}'

        await event.respond(f"✅ **Canal de statistiques configuré**\n📋 {chat_title}\n\n✨ Le bot surveillera ce canal pour les prédictions - développé par Sossou Kouamé Appolinaire\n💾 Configuration sauvegardée automatiquement")
        print(f"Canal de statistiques configuré: {channel_id}")

    except Exception as e:
        print(f"Erreur dans set_stat_channel: {e}")

@client.on(events.NewMessage(pattern=r'/set_display (-?\d+)'))
async def set_display_channel(event):
    """Set display channel (only admin in private)"""
    global detected_display_channel, confirmation_pending

    try:
        # Only allow in private chat with admin
        if event.is_group or event.is_channel:
            return

        if event.sender_id != ADMIN_ID:
            await event.respond("❌ Seul l'administrateur peut configurer les canaux")
            return

        # Extract channel ID from command
        match = event.pattern_match
        channel_id = int(match.group(1))

        # Check if channel is waiting for confirmation
        if channel_id not in confirmation_pending:
            await event.respond("❌ Ce canal n'est pas en attente de configuration")
            return

        detected_display_channel = channel_id
        confirmation_pending[channel_id] = 'configured_display'

        # Save configuration
        save_config()

        try:
            chat = await client.get_entity(channel_id)
            chat_title = getattr(chat, 'title', f'Canal {channel_id}')
        except:
            chat_title = f'Canal {channel_id}'

        await event.respond(f"✅ **Canal de diffusion configuré**\n📋 {chat_title}\n\n🚀 Le bot publiera les prédictions dans ce canal - développé par Sossou Kouamé Appolinaire\n💾 Configuration sauvegardée automatiquement")
        print(f"Canal de diffusion configuré: {channel_id}")

    except Exception as e:
        print(f"Erreur dans set_display_channel: {e}")

# --- COMMANDES DE BASE ---
@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    """Send welcome message when user starts the bot"""
    try:
        welcome_msg = """🎯 **Bot de Prédiction de Cartes - Bienvenue !**

🔹 **Développé par Sossou Kouamé Appolinaire**

**Fonctionnalités** :
• Prédictions automatiques anticipées (déclenchées sur 7, 8)
• Prédictions pour les prochains jeux se terminant par 0
• Vérification des résultats avec statuts détaillés
• Rapports automatiques toutes les 20 prédictions mises à jour

**Configuration** :
1. Ajoutez-moi dans vos canaux
2. Je vous enverrai automatiquement une invitation privée
3. Répondez avec `/set_stat [ID]` ou `/set_display [ID]`

**Commandes** :
• `/start` - Ce message
• `/status` - État du bot (admin)
• `/intervalle` - Configure le délai de prédiction (admin)
• `/report` - Compteur de bilan détaillé (admin)
• `/sta` - Statut des déclencheurs (admin)
• `/reset` - Réinitialiser (admin)
• `/deploy` - Pack de déploiement 2D (admin)

Le bot est prêt à analyser vos jeux ! 🚀"""

        await event.respond(welcome_msg)
        print(f"Message de bienvenue envoyé à l'utilisateur {event.sender_id}")

        # Test message private pour vérifier la connectivité
        if event.sender_id == ADMIN_ID:
            await asyncio.sleep(2)
            test_msg = "🔧 Test de connectivité : Je peux vous envoyer des messages privés !"
            await event.respond(test_msg)

    except Exception as e:
        print(f"Erreur dans start_command: {e}")

# --- COMMANDES ADMINISTRATIVES ---
@client.on(events.NewMessage(pattern='/status'))
async def show_status(event):
    """Show bot status (admin only)"""
    try:
        if event.sender_id != ADMIN_ID:
            return

        config_status = "✅ Sauvegardée" if os.path.exists(CONFIG_FILE) else "❌ Non sauvegardée"
        status_msg = f"""📊 **Statut du Bot**

Canal statistiques: {'✅ Configuré' if detected_stat_channel else '❌ Non configuré'} ({detected_stat_channel})
Canal diffusion: {'✅ Configuré' if detected_display_channel else '❌ Non configuré'} ({detected_display_channel})
⏱️ Intervalle de prédiction: {prediction_interval} minutes
Configuration persistante: {config_status}
Prédictions actives: {len(predictor.prediction_status)}
Dernières prédictions: {len(predictor.last_predictions)}
Messages traités: {len(predictor.processed_messages)}
"""
        await event.respond(status_msg)
    except Exception as e:
        print(f"Erreur dans show_status: {e}")

@client.on(events.NewMessage(pattern='/reset'))
async def reset_bot(event):
    """Reset bot configuration (admin only)"""
    global detected_stat_channel, detected_display_channel, confirmation_pending

    try:
        if event.sender_id != ADMIN_ID:
            return

        detected_stat_channel = None
        detected_display_channel = None
        confirmation_pending.clear()
        predictor.reset()

        # Save the reset configuration
        save_config()

        await event.respond("🔄 Bot réinitialisé avec succès\n💾 Configuration effacée et sauvegardée")
        print("Bot réinitialisé par l'administrateur")
    except Exception as e:
        print(f"Erreur dans reset_bot: {e}")

# Handler /deploy supprimé - remplacé par le handler 2D plus bas

@client.on(events.NewMessage(pattern='/test_invite'))
async def test_invite(event):
    """Test sending invitation (admin only)"""
    try:
        if event.sender_id != ADMIN_ID:
            return

        # Test invitation message
        test_msg = f"""🔔 **Test d'invitation**

📋 **Canal test** : Canal de test
🆔 **ID** : -1001234567890

**Choisissez le type de canal** :
• `/set_stat -1001234567890` - Canal de statistiques
• `/set_display -1001234567890` - Canal de diffusion

Ceci est un message de test pour vérifier les invitations."""

        await event.respond(test_msg)
        print(f"Message de test envoyé à l'admin")

    except Exception as e:
        print(f"Erreur dans test_invite: {e}")

@client.on(events.NewMessage(pattern='/sta'))
async def show_trigger_numbers(event):
    """Show current trigger numbers for automatic predictions"""
    try:
        if event.sender_id != ADMIN_ID:
            return

        trigger_nums = list(predictor.trigger_numbers)
        trigger_nums.sort()

        msg = f"""📊 **Statut des Déclencheurs Automatiques**

🎯 **Numéros de fin activant les prédictions**: {', '.join(map(str, trigger_nums))}

📋 **Fonctionnement**:
• Le bot surveille les jeux se terminant par {', '.join(map(str, trigger_nums))}
• Il prédit automatiquement le prochain jeu se terminant par 0
• Format: "🔵 {{numéro}} 📌 D🔵 statut :''⌛''"

📈 **Statistiques actuelles**:
• Prédictions actives: {len([s for s in predictor.prediction_status.values() if s == '⌛'])}
• Canal stats configuré: {'✅' if detected_stat_channel else '❌'}
• Canal affichage configuré: {'✅' if detected_display_channel else '❌'}

💡 **Canal détecté**: {detected_stat_channel if detected_stat_channel else 'Aucun'}"""

        await event.respond(msg)
        print(f"Statut des déclencheurs envoyé à l'admin")

    except Exception as e:
        print(f"Erreur dans show_trigger_numbers: {e}")
        await event.respond(f"❌ Erreur: {e}")

@client.on(events.NewMessage(pattern='/report'))
async def show_report_status(event):
    """Show report counter and remaining messages until next automatic report"""
    try:
        if event.sender_id != ADMIN_ID:
            return

        total_predictions = len(predictor.status_log)
        processed_messages = len(predictor.processed_messages)
        pending_predictions = len([s for s in predictor.prediction_status.values() if s == '⌛'])

        # Calculate remaining until next report (every 20 predictions)
        if total_predictions == 0:
            remaining_for_report = 20
            last_report_at = 0
        else:
            last_report_at = (total_predictions // 20) * 20
            remaining_for_report = 20 - (total_predictions % 20)
            if remaining_for_report == 20:
                remaining_for_report = 0

        # Calculate statistics for completed predictions
        wins = sum(1 for _, status in predictor.status_log if '✅' in status)
        losses = sum(1 for _, status in predictor.status_log if '❌' in status or '⭕' in status)
        win_rate = (wins / total_predictions * 100) if total_predictions > 0 else 0.0

        msg = f"""📊 **Compteur de Bilan et Statut des Prédictions**

🎯 **Messages Traités**:
• Total de jeux traités: {processed_messages}
• Total de prédictions générées: {total_predictions}
• Prédictions en attente: {pending_predictions}

📈 **Résultats des Prédictions**:
• Prédictions réussies: {wins} ✅
• Prédictions échouées: {losses} ❌
• Taux de réussite: {win_rate:.1f}%

📋 **Compteur de Rapport Automatique**:
• Dernier rapport généré après: {last_report_at} prédictions
• Prédictions depuis dernier rapport: {total_predictions - last_report_at}
• Restant avant prochain rapport: {remaining_for_report}

⏰ **Prochaine Génération**:
{'🔄 Le prochain rapport sera généré automatiquement' if remaining_for_report > 0 else '✅ Prêt pour la génération du prochain rapport'}

💡 **Note**: Les rapports automatiques sont générés toutes les 20 prédictions mises à jour avec un statut final."""

        await event.respond(msg)
        print(f"Rapport de compteur envoyé à l'admin")

    except Exception as e:
        print(f"Erreur dans show_report_status: {e}")
        await event.respond(f"❌ Erreur: {e}")

# Handler /deploy supprimé - remplacé par le handler 2D unique

@client.on(events.NewMessage(pattern='/scheduler'))
async def manage_scheduler(event):
    """Gestion du planificateur automatique (admin uniquement)"""
    global scheduler
    try:
        if event.sender_id != ADMIN_ID:
            return

        # Parse command arguments
        message_parts = event.message.message.split()
        if len(message_parts) < 2:
            await event.respond("""🤖 **Commandes du Planificateur Automatique**

**Usage**: `/scheduler [commande]`

**Commandes disponibles**:
• `start` - Démarre le planificateur automatique
• `stop` - Arrête le planificateur
• `status` - Affiche le statut actuel
• `generate` - Génère une nouvelle planification
• `config [source_id] [target_id]` - Configure les canaux

**Exemple**: `/scheduler config -1001234567890 -1001987654321`""")
            return

        command = message_parts[1].lower()

        if command == "start":
            if not scheduler:
                if detected_stat_channel and detected_display_channel:
                    scheduler = PredictionScheduler(
                        client, predictor,
                        detected_stat_channel, detected_display_channel
                    )
                    # Démarre le planificateur en arrière-plan
                    asyncio.create_task(scheduler.run_scheduler())
                    await event.respond("✅ **Planificateur démarré**\n\nLe système de prédictions automatiques est maintenant actif.")
                else:
                    await event.respond("❌ **Configuration manquante**\n\nVeuillez d'abord configurer les canaux source et cible avec `/set_stat` et `/set_display`.")
            else:
                await event.respond("⚠️ **Planificateur déjà actif**\n\nUtilisez `/scheduler stop` pour l'arrêter.")

        elif command == "stop":
            if scheduler:
                scheduler.stop_scheduler()
                scheduler = None
                await event.respond("🛑 **Planificateur arrêté**\n\nLes prédictions automatiques sont désactivées.")
            else:
                await event.respond("ℹ️ **Planificateur non actif**\n\nUtilisez `/scheduler start` pour le démarrer.")

        elif command == "status":
            if scheduler:
                status = scheduler.get_schedule_status()
                status_msg = f"""📊 **Statut du Planificateur**

🔄 **État**: {'🟢 Actif' if status['is_running'] else '🔴 Inactif'}
📋 **Planification**:
• Total de prédictions: {status['total']}
• Prédictions lancées: {status['launched']}
• Prédictions vérifiées: {status['verified']}
• En attente: {status['pending']}

⏰ **Prochaine prédiction**: {status['next_launch'] or 'Aucune'}

🔧 **Configuration**:
• Canal source: {detected_stat_channel}
• Canal cible: {detected_display_channel}"""
                await event.respond(status_msg)
            else:
                await event.respond("ℹ️ **Planificateur non configuré**\n\nUtilisez `/scheduler start` pour l'activer.")

        elif command == "generate":
            if scheduler:
                scheduler.regenerate_schedule()
                await event.respond("🔄 **Nouvelle planification générée**\n\nLa planification quotidienne a été régénérée avec succès.")
            else:
                # Crée un planificateur temporaire pour générer
                temp_scheduler = PredictionScheduler(client, predictor, 0, 0)
                temp_scheduler.regenerate_schedule()
                await event.respond("✅ **Planification générée**\n\nFichier `prediction.yaml` créé. Utilisez `/scheduler start` pour activer.")

        elif command == "config" and len(message_parts) >= 4:
            source_id = int(message_parts[2])
            target_id = int(message_parts[3])

            # Met à jour la configuration globale
            update_channel_config(source_id, target_id)

            await event.respond(f"""✅ **Configuration mise à jour**

📥 **Canal source**: {source_id}
📤 **Canal cible**: {target_id}

Utilisez `/scheduler start` pour activer le planificateur.""")

        else:
            await event.respond("❌ **Commande inconnue**\n\nUtilisez `/scheduler` sans paramètre pour voir l'aide.")

    except Exception as e:
        print(f"Erreur dans manage_scheduler: {e}")
        await event.respond(f"❌ Erreur: {e}")

@client.on(events.NewMessage(pattern='/schedule_info'))
async def schedule_info(event):
    """Affiche les informations détaillées de la planification (admin uniquement)"""
    try:
        if event.sender_id != ADMIN_ID:
            return

        if scheduler and scheduler.schedule_data:
            # Affiche les 10 prochaines prédictions
            current_time = scheduler.get_current_time_slot()
            upcoming = []

            for numero, data in scheduler.schedule_data.items():
                if (not data["launched"] and
                    data["heure_lancement"] >= current_time):
                    upcoming.append((numero, data["heure_lancement"]))

            upcoming.sort(key=lambda x: x[1])
            upcoming = upcoming[:10]  # Limite à 10

            msg = "📅 **Prochaines Prédictions Automatiques**\n\n"
            for numero, heure in upcoming:
                msg += f"🔵 {numero} → {heure}\n"

            if not upcoming:
                msg += "ℹ️ Aucune prédiction en attente pour aujourd'hui."

            await event.respond(msg)
        else:
            await event.respond("❌ **Aucune planification active**\n\nUtilisez `/scheduler generate` pour créer une planification.")

    except Exception as e:
        print(f"Erreur dans schedule_info: {e}")
        await event.respond(f"❌ Erreur: {e}")

@client.on(events.NewMessage(pattern='/intervalle'))
async def set_prediction_interval(event):
    """Configure l'intervalle avant que le système cherche 'A' (admin uniquement)"""
    global prediction_interval
    try:
        if event.sender_id != ADMIN_ID:
            return

        # Parse command arguments
        message_parts = event.message.message.split()
        
        if len(message_parts) < 2:
            await event.respond(f"""⏱️ **Configuration de l'Intervalle de Prédiction**

**Usage**: `/intervalle [minutes]`

**Intervalle actuel**: {prediction_interval} minutes

**Description**: 
Définit le temps d'attente en minutes avant que le système commence à analyser les messages pour chercher la lettre 'A' dans les parenthèses et déclencher les prédictions.

**Exemples**:
• `/intervalle 3` - Attendre 3 minutes
• `/intervalle 10` - Attendre 10 minutes
• `/intervalle 1` - Attendre 1 minute

**Recommandé**: Entre 1 et 15 minutes""")
            return

        try:
            new_interval = int(message_parts[1])
            if new_interval < 1 or new_interval > 60:
                await event.respond("❌ **Erreur**: L'intervalle doit être entre 1 et 60 minutes")
                return
            
            old_interval = prediction_interval
            prediction_interval = new_interval
            
            # Sauvegarder la configuration
            save_config()
            
            await event.respond(f"""✅ **Intervalle mis à jour**

⏱️ **Ancien intervalle**: {old_interval} minutes
⏱️ **Nouvel intervalle**: {prediction_interval} minutes

Le système attendra maintenant {prediction_interval} minute(s) avant de commencer l'analyse des messages pour la détection des 'A' dans les parenthèses.

Configuration sauvegardée automatiquement.""")
            
            print(f"✅ Intervalle de prédiction mis à jour: {old_interval} → {prediction_interval} minutes")
            
        except ValueError:
            await event.respond("❌ **Erreur**: Veuillez entrer un nombre valide de minutes")
            
    except Exception as e:
        print(f"Erreur dans set_prediction_interval: {e}")
        await event.respond(f"❌ Erreur: {e}")

@client.on(events.NewMessage(pattern='/deploy'))
async def generate_deploy_package(event):
    """Génère le package de déploiement 2D pour Render.com (admin uniquement)"""
    try:
        if event.sender_id != ADMIN_ID:
            return

        await event.respond("🚀 **Génération Package deployment_2d.zip...**")
        
        try:
            # Créer le package ZIP avec nom correct
            package_name = 'deployment_2d.zip'
            
            with zipfile.ZipFile(package_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Fichiers principaux
                files_to_include = [
                    'main.py', 'render_main.py', 'render_predictor.py', 
                    'render_requirements.txt', 'render.yaml', 'models.py',
                    'predictor.py', 'scheduler.py', 'README_RENDER.md', 'DEPLOYMENT_GUIDE.md'
                ]
                
                for file_path in files_to_include:
                    if os.path.exists(file_path):
                        zipf.write(file_path)
                
                # Configuration .env.example avec PREDICTION_INTERVAL
                env_content = f"""API_ID=29177661
API_HASH=a8639172fa8d35dbfd8ea46286d349ab
BOT_TOKEN=7815360317:AAGsrFzeUZrHOjujf5aY2UjlBj4GOblHSig
ADMIN_ID=1190237801
PORT=10000
PREDICTION_INTERVAL={prediction_interval}"""
                zipf.writestr('.env.example', env_content)
                
                # requirements.txt pour Render.com (obligatoire - versions compatibles)
                requirements_content = """telethon==1.35.0
aiohttp==3.9.5
python-dotenv==1.0.1
pyyaml==6.0.1
psycopg2-binary==2.9.7"""
                zipf.writestr('requirements.txt', requirements_content)
                
                # runtime.txt pour spécifier la version Python
                runtime_content = "python-3.11.4"
                zipf.writestr('runtime.txt', runtime_content)
                
                # Documentation 2D
                readme_2d = f"""# Package Déploiement 2D - Août 2025

## Nouvelles Fonctionnalités:
• Commande /intervalle (1-60 minutes) - Actuel: {prediction_interval}min
• Configuration persistante base de données
• Système déclenchement par As uniquement dans premier groupe

## Variables Render.com:
- Configurez toutes les variables de .env.example
- Port: 10000
- Start Command: python render_main.py

## Commandes Disponibles:
/intervalle [minutes] - Configurer délai prédiction
/status - État complet avec intervalle
/deploy - Générer ce package

Prêt pour déploiement Render.com!"""
                zipf.writestr('README_2D.md', readme_2d)
            
            file_size = os.path.getsize(package_name) / 1024
            
            # Envoyer le message de confirmation
            await event.respond(f"""✅ **PACKAGE 2D CRÉÉ AVEC SUCCÈS!**

📦 **Fichier**: deployment_2d.zip ({file_size:.1f} KB)
🆕 **Commande /intervalle** incluse (actuel: {prediction_interval}min)
🔧 **Port 10000** configuré pour Render.com
📚 **Documentation 2D** complète""")
            
            # Envoyer le fichier ZIP en pièce jointe
            await client.send_file(
                event.chat_id,
                package_name,
                caption="📦 **Package de Déploiement 2D** - Prêt pour Render.com port 10000"
            )
            
            print(f"✅ Package deployment_2d.zip créé: {file_size:.1f} KB")
            
        except Exception as e:
            await event.respond(f"❌ Erreur création: {str(e)}")

    except Exception as e:
        print(f"Erreur deploy: {e}")

# --- TRAITEMENT DES MESSAGES DU CANAL DE STATISTIQUES ---
@client.on(events.NewMessage())
@client.on(events.MessageEdited())
async def handle_messages(event):
    """Handle messages from statistics channel"""
    try:
        # Debug: Log ALL incoming messages first
        message_text = event.message.message if event.message else "Pas de texte"
        print(f"📬 TOUS MESSAGES: Canal {event.chat_id} | Texte: {message_text[:100]}")
        print(f"🔧 Canal stats configuré: {detected_stat_channel}")

        # Check if stat channel is configured
        if detected_stat_channel is None:
            print("⚠️ PROBLÈME: Canal de statistiques non configuré!")
            return

        # Check if message is from the configured channel
        if event.chat_id != detected_stat_channel:
            print(f"❌ Message ignoré: Canal {event.chat_id} ≠ Canal stats {detected_stat_channel}")
            return

        if not message_text:
            print("❌ Message vide ignoré")
            return

        print(f"✅ Message accepté du canal stats {event.chat_id}: {message_text}")

        # 1. Vérifier si c'est un message en cours d'édition (⏰ ou 🕐)
        is_pending, game_num = predictor.is_pending_edit_message(message_text)
        if is_pending:
            print(f"⏳ Message #{game_num} mis en attente d'édition finale")
            return  # Ignorer pour le moment, attendre l'édition finale

        # 2. Vérifier si c'est l'édition finale d'un message en attente (🔰 ou ✅)
        predicted, predicted_game, suit = predictor.process_final_edit_message(message_text)
        if predicted:
            print(f"🎯 Message édité finalisé, traitement de la prédiction #{predicted_game}")
            # Message de prédiction selon le nouveau format
            prediction_text = f"🔵{predicted_game}— JOKER 2D| ⏳"

            sent_messages = await broadcast(prediction_text)

            # Store message IDs for later editing
            if sent_messages and predicted_game:
                for chat_id, message_id in sent_messages:
                    predictor.store_prediction_message(predicted_game, message_id, chat_id)

            print(f"✅ Prédiction générée après édition finale pour le jeu #{predicted_game}: {suit}")
        else:
            # 3. Traitement normal des messages (pas d'édition en cours)
            predicted, predicted_game, suit = predictor.should_predict(message_text)
            if predicted:
                # Message de prédiction manuelle selon le nouveau format demandé
                prediction_text = f"🔵{predicted_game}— JOKER 2D| ⏳"

                sent_messages = await broadcast(prediction_text)

                # Store message IDs for later editing
                if sent_messages and predicted_game:
                    for chat_id, message_id in sent_messages:
                        predictor.store_prediction_message(predicted_game, message_id, chat_id)

                print(f"✅ Prédiction manuelle générée pour le jeu #{predicted_game}: {suit}")

        # Check for prediction verification (manuel + automatique)
        verified, number = predictor.verify_prediction(message_text)
        if verified is not None and number is not None:
            statut = predictor.prediction_status.get(number, 'Inconnu')
            # Edit the original prediction message instead of sending new message
            success = await edit_prediction_message(number, statut)
            if success:
                print(f"✅ Message de prédiction #{number} mis à jour avec statut: {statut}")
            else:
                print(f"⚠️ Impossible de mettre à jour le message #{number}, envoi d'un nouveau message")
                status_text = f"🔵{number}— JOKER 2D| {statut}"
                await broadcast(status_text)
        
        # Check for expired predictions on every valid result message
        game_number = predictor.extract_game_number(message_text)
        if game_number and not ("⏰" in message_text or "🕐" in message_text):
            expired = predictor.check_expired_predictions(game_number)
            for expired_num in expired:
                # Edit expired prediction messages
                success = await edit_prediction_message(expired_num, '❌❌')
                if success:
                    print(f"✅ Message de prédiction expirée #{expired_num} mis à jour avec ❌❌")
                else:
                    print(f"⚠️ Impossible de mettre à jour le message expiré #{expired_num}")
                    status_text = f"🔵{expired_num}— JOKER 2D| ❌❌"
                    await broadcast(status_text)

        # Vérification des prédictions automatiques du scheduler
        if scheduler and scheduler.schedule_data:
            # Récupère les numéros des prédictions automatiques en attente
            pending_auto_predictions = []
            for numero_str, data in scheduler.schedule_data.items():
                if data["launched"] and not data["verified"]:
                    numero_int = int(numero_str.replace('N', ''))
                    pending_auto_predictions.append(numero_int)

            if pending_auto_predictions:
                # Vérifie si ce message correspond à une prédiction automatique
                predicted_num, status = scheduler.verify_prediction_from_message(message_text, pending_auto_predictions)

                if predicted_num and status:
                    # Met à jour la prédiction automatique
                    numero_str = f"N{predicted_num:03d}"
                    if numero_str in scheduler.schedule_data:
                        data = scheduler.schedule_data[numero_str]
                        data["verified"] = True
                        data["statut"] = status

                        # Met à jour le message
                        await scheduler.update_prediction_message(numero_str, data, status)

                        # Ajouter une nouvelle prédiction pour maintenir la continuité
                        scheduler.add_next_prediction()

                        # Sauvegarde
                        scheduler.save_schedule(scheduler.schedule_data)
                        print(f"📝 Prédiction automatique {numero_str} vérifiée: {status}")
                        print(f"🔄 Nouvelle prédiction générée pour maintenir la continuité")

        # Generate periodic report every 20 predictions
        if len(predictor.status_log) > 0 and len(predictor.status_log) % 20 == 0:
            await generate_report()

    except Exception as e:
        print(f"Erreur dans handle_messages: {e}")

async def broadcast(message):
    """Broadcast message to display channel"""
    global detected_display_channel

    sent_messages = []
    if detected_display_channel:
        try:
            sent_message = await client.send_message(detected_display_channel, message)
            sent_messages.append((detected_display_channel, sent_message.id))
            print(f"Message diffusé: {message}")
        except Exception as e:
            print(f"Erreur lors de l'envoi: {e}")
    else:
        print("⚠️ Canal d'affichage non configuré")

    return sent_messages

async def edit_prediction_message(game_number: int, new_status: str):
    """Edit prediction message with new status"""
    try:
        message_info = predictor.get_prediction_message(game_number)
        if message_info:
            chat_id = message_info['chat_id']
            message_id = message_info['message_id']
            new_text = f"🔵{game_number}— JOKER 2D| {new_status}"

            await client.edit_message(chat_id, message_id, new_text)
            print(f"Message de prédiction #{game_number} mis à jour avec statut: {new_status}")
            return True
    except Exception as e:
        print(f"Erreur lors de la modification du message: {e}")
    return False

async def generate_report():
    """Generate and broadcast periodic report with updated format"""
    try:
        bilan = "📊 Bilan des 20 dernières prédictions :\n"

        recent_predictions = predictor.status_log[-20:]
        for num, statut in recent_predictions:
            bilan += f"🔵{num}— JOKER 2D| {statut}\n"

        # Calculate statistics
        total = len(recent_predictions)
        wins = sum(1 for _, status in recent_predictions if '✅' in status)
        win_rate = (wins / total * 100) if total > 0 else 0

        bilan += f"\n📈 Statistiques: {wins}/{total} ({win_rate:.1f}% de réussite)"

        await broadcast(bilan)
        print(f"Rapport généré: {wins}/{total} prédictions réussies")

    except Exception as e:
        print(f"Erreur dans generate_report: {e}")

# --- ENVOI VERS LES CANAUX ---
# (Function moved above to handle message editing)

# --- GESTION D'ERREURS ET RECONNEXION ---
async def handle_connection_error():
    """Handle connection errors and attempt reconnection"""
    print("Tentative de reconnexion...")
    await asyncio.sleep(5)
    try:
        await client.connect()
        print("Reconnexion réussie")
    except Exception as e:
        print(f"Échec de la reconnexion: {e}")

# --- SERVEUR WEB POUR MONITORING ---
async def health_check(request):
    """Health check endpoint"""
    return web.Response(text="Bot is running!", status=200)

async def bot_status(request):
    """Bot status endpoint"""
    status = {
        "bot_online": True,
        "stat_channel": detected_stat_channel,
        "display_channel": detected_display_channel,
        "predictions_active": len(predictor.prediction_status),
        "total_predictions": len(predictor.status_log)
    }
    return web.json_response(status)

async def create_web_server():
    """Create and start web server"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/status', bot_status)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ Serveur web démarré sur 0.0.0.0:{PORT}")
    return runner

# --- LANCEMENT ---
async def main():
    """Main function to start the bot"""
    print("Démarrage du bot Telegram...")
    print(f"API_ID: {API_ID}")
    print(f"Bot Token configuré: {'Oui' if BOT_TOKEN else 'Non'}")
    print(f"Port web: {PORT}")

    # Validate configuration
    if not API_ID or not API_HASH or not BOT_TOKEN:
        print("❌ Configuration manquante! Vérifiez votre fichier .env")
        return

    try:
        # Start web server first
        web_runner = await create_web_server()
        
        # Start the bot
        if await start_bot():
            print("✅ Bot en ligne et en attente de messages...")
            print(f"🌐 Accès web: http://0.0.0.0:{PORT}")
            await client.run_until_disconnected()
        else:
            print("❌ Échec du démarrage du bot")

    except KeyboardInterrupt:
        print("\n🛑 Arrêt du bot demandé par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur critique: {e}")
        await handle_connection_error()
    finally:
        try:
            await client.disconnect()
            print("Bot déconnecté proprement")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())