import os
import asyncio
import re
import logging
import sys
from telethon import TelegramClient, events
from predictor import CardPredictor
from yaml_manager import init_database, db
from aiohttp import web
import time

# Configuration des logs pour Render.com
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
PORT = int(os.getenv('PORT', '10000'))  # Port 10000 par défaut pour Render.com

# Variables d'état
detected_stat_channel = None
detected_display_channel = None
confirmation_pending = {}

# Gestionnaire de prédictions
predictor = CardPredictor()

# Initialize Telegram client with unique session name
session_name = f'bot_session_{int(time.time())}'
client = TelegramClient(session_name, API_ID, API_HASH)

# Health check server for Render
async def health_check(request):
    return web.Response(text="Bot is running!", status=200)

async def start_web_server():
    """Start web server for Render health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"✅ Serveur web démarré sur 0.0.0.0:{PORT} (Render.com)")
    logger.info(f"🌍 Health check disponible sur: http://0.0.0.0:{PORT}/health")

async def start_bot():
    """Start the bot with proper error handling"""
    try:
        await client.start(bot_token=BOT_TOKEN)
        logger.info("Bot démarré avec succès...")
        
        # Get bot info
        me = await client.get_me()
        username = getattr(me, 'username', 'Unknown') or f"ID:{me.id}"
        logger.info(f"Bot connecté: @{username}")
        
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du bot: {e}")
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
        
        try:
            chat = await client.get_entity(channel_id)
            chat_title = getattr(chat, 'title', f'Canal {channel_id}')
        except:
            chat_title = f'Canal {channel_id}'
            
        await event.respond(f"✅ **Canal de statistiques configuré**\n📋 {chat_title}\n\n✨ Le bot surveillera ce canal pour les prédictions - développé par Sossou Kouamé Appolinaire")
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
        
        try:
            chat = await client.get_entity(channel_id)
            chat_title = getattr(chat, 'title', f'Canal {channel_id}')
        except:
            chat_title = f'Canal {channel_id}'
            
        await event.respond(f"✅ **Canal de diffusion configuré**\n📋 {chat_title}\n\n🚀 Le bot publiera les prédictions dans ce canal - développé par Sossou Kouamé Appolinaire")
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
• Prédictions automatiques anticipées (déclenchées sur 5, 7, 8)
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
• `/reset` - Réinitialiser (admin)

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
            
        status_msg = f"""📊 **Statut du Bot**
        
Canal statistiques: {'✅ Configuré' if detected_stat_channel else '❌ Non configuré'} ({detected_stat_channel})
Canal diffusion: {'✅ Configuré' if detected_display_channel else '❌ Non configuré'} ({detected_display_channel})
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
        
        await event.respond("🔄 Bot réinitialisé avec succès")
        print("Bot réinitialisé par l'administrateur")
    except Exception as e:
        print(f"Erreur dans reset_bot: {e}")

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

# --- TRAITEMENT DES MESSAGES DU CANAL DE STATISTIQUES ---
@client.on(events.NewMessage())
async def handle_messages(event):
    """Handle all incoming messages with detailed logging"""
    global detected_stat_channel, detected_display_channel
    
    try:
        message_text = event.message.message
        if not message_text:
            return
            
        # Log tous les messages comme dans main.py
        logger.info(f"📬 TOUS MESSAGES: Canal {event.chat_id} | Texte: {message_text}")
        logger.info(f"🔧 Canal stats configuré: {detected_stat_channel}")
        
        # Si pas de canal stats configuré, ignorer
        if detected_stat_channel is None:
            logger.info("❌ Aucun canal stats configuré, message ignoré")
            return
            
        # Si message ne vient pas du canal stats, ignorer
        if event.chat_id != detected_stat_channel:
            logger.info(f"❌ Message ignoré: Canal {event.chat_id} ≠ Canal stats {detected_stat_channel}")
            return
            
        # Message accepté du canal stats
        logger.info(f"✅ Message accepté du canal stats {event.chat_id}: {message_text}")

        # 1. Vérifier si c'est un message en cours d'édition (⏰ ou 🕐)
        is_pending, game_num = predictor.is_pending_edit_message(message_text)
        if is_pending:
            logger.info(f"⏳ Message #{game_num} mis en attente d'édition finale")
            return  # Ignorer pour le moment, attendre l'édition finale

        # 2. Vérifier si c'est l'édition finale d'un message en attente (🔰 ou ✅)
        predicted, predicted_game, suit = predictor.process_final_edit_message(message_text)
        if predicted:
            logger.info(f"🎯 Message édité finalisé, traitement de la prédiction #{predicted_game}")
            # Message de prédiction selon le nouveau format
            prediction_text = f"🔵{predicted_game} 🔵2D: {suit} :⏳"

            sent_messages = await broadcast(prediction_text)

            # Store message IDs for later editing
            if sent_messages and predicted_game:
                for chat_id, message_id in sent_messages:
                    predictor.store_prediction_message(predicted_game, message_id, chat_id)

            logger.info(f"✅ Prédiction générée après édition finale pour le jeu #{predicted_game}: {suit}")
        else:
            # 3. Vérifier si c'est un nouveau message standard pour prédiction
            predicted, predicted_game, suit = predictor.should_predict(message_text)
            if predicted:
                # Message de prédiction manuelle selon le nouveau format demandé
                prediction_text = f"🔵{predicted_game} 🔵2D: {suit} :⏳"

                sent_messages = await broadcast(prediction_text)

                # Store message IDs for later editing
                if sent_messages and predicted_game:
                    for chat_id, message_id in sent_messages:
                        predictor.store_prediction_message(predicted_game, message_id, chat_id)

                logger.info(f"✅ Prédiction générée pour le jeu #{predicted_game}: {suit}")

        # 4. Vérification des résultats (indépendamment des prédictions)
        verified, number = predictor.verify_prediction(message_text)
        if verified is not None and number is not None:
            status = predictor.prediction_status.get(number, 'Inconnu')
            logger.info(f"🔍 Vérification: Jeu #{number}, Statut: {status}")
            
            # Edit the original prediction message instead of sending new message
            success = await edit_prediction_message(number, status)
            if success:
                logger.info(f"✅ Message de prédiction #{number} mis à jour avec statut: {status}")
            else:
                logger.info(f"⚠️ Impossible de mettre à jour le message #{number}")
                # Pas de nouveau message, juste continuer

        # Generate periodic report every 20 predictions
        # Bilan automatique supprimé sur demande utilisateur

    except Exception as e:
        logger.error(f"Erreur dans handle_messages: {e}")

async def generate_report():
    """Generate and broadcast periodic report with updated format"""
    try:
        bilan = "📊 Bilan des 20 dernières prédictions :\n"
        
        recent_predictions = predictor.status_log[-20:]
        for num, statut in recent_predictions:
            bilan += f"🔵{num}📌 D🔵 statut :{statut}\n"
        
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
            new_text = f"🔵{game_number} 🔵2D: statut :{new_status}"
            
            await client.edit_message(chat_id, message_id, new_text)
            logger.info(f"Message de prédiction #{game_number} mis à jour avec statut: {new_status}")
            return True
    except Exception as e:
        logger.error(f"Erreur lors de la modification du message: {e}")
    return False

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

# --- LANCEMENT ---
async def main():
    """Main function to start the bot"""
    logger.info("Démarrage du bot Telegram sur Render.com...")
    logger.info(f"API_ID: {API_ID}")
    logger.info(f"Bot Token configuré: {'Oui' if BOT_TOKEN else 'Non'}")
    logger.info(f"Port configuré: {PORT}")
    
    # Initialize YAML database
    database = init_database()
    if database:
        logger.info("✅ Gestionnaire YAML initialisé pour Render.com")
    else:
        logger.info("⚠️ Gestionnaire YAML non disponible, utilisation mode basique")
    
    # Validate configuration
    if not API_ID or not API_HASH or not BOT_TOKEN:
        logger.error("❌ Configuration manquante! Vérifiez vos variables d'environnement")
        return
    
    try:
        # Start web server for health checks
        await start_web_server()
        
        # Start the bot
        if await start_bot():
            logger.info("✅ Bot en ligne et en attente de messages...")
            logger.info("🌐 Accès web: http://0.0.0.0:10000")
            await client.run_until_disconnected()
        else:
            logger.error("❌ Échec du démarrage du bot")
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Arrêt du bot demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
        await handle_connection_error()
    finally:
        try:
            await client.disconnect()
            logger.info("Bot déconnecté proprement")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())