"""
Modèles de base de données pour la persistance du bot Telegram
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

class DatabaseManager:
    """Gestionnaire de base de données PostgreSQL pour le bot"""
    
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL non trouvé dans les variables d'environnement")
        
        self.init_tables()
        print("✅ Base de données initialisée")
    
    def get_connection(self):
        """Retourne une connexion à la base de données"""
        return psycopg2.connect(self.database_url)
    
    def init_tables(self):
        """Initialise les tables de la base de données"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Table pour la configuration du bot
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_config (
                        id SERIAL PRIMARY KEY,
                        key VARCHAR(100) UNIQUE NOT NULL,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table pour les prédictions manuelles
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS predictions (
                        id SERIAL PRIMARY KEY,
                        game_number INTEGER NOT NULL,
                        suit_combination VARCHAR(10),
                        status VARCHAR(20) DEFAULT '⌛',
                        message_id BIGINT,
                        chat_id BIGINT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        verified_at TIMESTAMP,
                        prediction_type VARCHAR(20) DEFAULT 'manual'
                    )
                """)
                
                # Table pour les prédictions automatiques (scheduler)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS auto_predictions (
                        id SERIAL PRIMARY KEY,
                        numero VARCHAR(10) NOT NULL,
                        lanceur VARCHAR(10),
                        heure_lancement TIME,
                        heure_prediction TIME,
                        statut VARCHAR(20) DEFAULT '⌛',
                        message_id BIGINT,
                        chat_id BIGINT,
                        launched BOOLEAN DEFAULT FALSE,
                        verified BOOLEAN DEFAULT FALSE,
                        prediction_format VARCHAR(20),
                        created_at DATE DEFAULT CURRENT_DATE,
                        UNIQUE(numero, created_at)
                    )
                """)
                
                # Table pour l'historique des messages
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS message_log (
                        id SERIAL PRIMARY KEY,
                        message_hash VARCHAR(64) UNIQUE,
                        channel_id BIGINT,
                        content TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
    
    def set_config(self, key: str, value: Any):
        """Sauvegarde une valeur de configuration"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bot_config (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) 
                    DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """, (key, json.dumps(value) if isinstance(value, (dict, list)) else str(value)))
                conn.commit()
    
    def get_config(self, key: str, default=None):
        """Récupère une valeur de configuration"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
                result = cur.fetchone()
                if result:
                    try:
                        return json.loads(result['value'])
                    except (json.JSONDecodeError, ValueError):
                        return result['value']
                return default
    
    def save_prediction(self, game_number: int, suit_combination: str, 
                       message_id: Optional[int] = None, chat_id: Optional[int] = None, 
                       prediction_type: str = 'manual'):
        """Sauvegarde une prédiction manuelle"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO predictions 
                    (game_number, suit_combination, message_id, chat_id, prediction_type)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (game_number, suit_combination, message_id, chat_id, prediction_type))
                conn.commit()
    
    def update_prediction_status(self, game_number: int, status: str):
        """Met à jour le statut d'une prédiction"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE predictions 
                    SET status = %s, verified_at = CURRENT_TIMESTAMP
                    WHERE game_number = %s
                """, (status, game_number))
                conn.commit()
    
    def get_pending_predictions(self) -> List[Dict]:
        """Récupère les prédictions en attente"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM predictions 
                    WHERE status = '⌛' 
                    ORDER BY created_at ASC
                """)
                return [dict(row) for row in cur.fetchall()]
    
    def save_auto_prediction_schedule(self, schedule_data: Dict[str, Any]):
        """Sauvegarde la planification automatique complète"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Supprime l'ancienne planification du jour
                cur.execute("DELETE FROM auto_predictions WHERE created_at = CURRENT_DATE")
                
                # Insère la nouvelle planification
                for numero, data in schedule_data.items():
                    cur.execute("""
                        INSERT INTO auto_predictions 
                        (numero, lanceur, heure_lancement, heure_prediction, statut, 
                         message_id, chat_id, launched, verified, prediction_format)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        numero, data.get('lanceur'), data.get('heure_lancement'),
                        data.get('heure_prediction'), data.get('statut', '⌛'),
                        data.get('message_id'), data.get('chat_id'),
                        data.get('launched', False), data.get('verified', False),
                        data.get('prediction_format')
                    ))
                conn.commit()
    
    def load_auto_prediction_schedule(self) -> Dict[str, Any]:
        """Charge la planification automatique du jour"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM auto_predictions 
                    WHERE created_at = CURRENT_DATE
                    ORDER BY heure_lancement
                """)
                
                schedule = {}
                for row in cur.fetchall():
                    schedule[row['numero']] = {
                        'lanceur': row['lanceur'],
                        'heure_lancement': str(row['heure_lancement'])[:5] if row['heure_lancement'] else None,
                        'heure_prediction': str(row['heure_prediction'])[:5] if row['heure_prediction'] else None,
                        'statut': row['statut'],
                        'message_id': row['message_id'],
                        'chat_id': row['chat_id'],
                        'launched': row['launched'],
                        'verified': row['verified'],
                        'prediction_format': row['prediction_format']
                    }
                return schedule
    
    def update_auto_prediction(self, numero: str, updates: Dict[str, Any]):
        """Met à jour une prédiction automatique"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
                values = list(updates.values()) + [numero]
                
                cur.execute(f"""
                    UPDATE auto_predictions 
                    SET {set_clause}
                    WHERE numero = %s AND created_at = CURRENT_DATE
                """, values)
                conn.commit()
    
    def is_message_processed(self, message_content: str, channel_id: int) -> bool:
        """Vérifie si un message a déjà été traité"""
        import hashlib
        message_hash = hashlib.sha256(f"{channel_id}:{message_content}".encode()).hexdigest()
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM message_log WHERE message_hash = %s", (message_hash,))
                return cur.fetchone() is not None
    
    def mark_message_processed(self, message_content: str, channel_id: int):
        """Marque un message comme traité"""
        import hashlib
        message_hash = hashlib.sha256(f"{channel_id}:{message_content}".encode()).hexdigest()
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO message_log (message_hash, channel_id, content)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (message_hash) DO NOTHING
                """, (message_hash, channel_id, message_content))
                conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du bot"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Statistiques des prédictions manuelles
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN status LIKE '✅%' THEN 1 END) as success,
                        COUNT(CASE WHEN status = '⌛' THEN 1 END) as pending
                    FROM predictions
                """)
                manual_stats = cur.fetchone()
                
                # Statistiques des prédictions automatiques
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN launched THEN 1 END) as launched,
                        COUNT(CASE WHEN verified THEN 1 END) as verified
                    FROM auto_predictions 
                    WHERE created_at = CURRENT_DATE
                """)
                auto_stats = cur.fetchone()
                
                return {
                    'manual': dict(manual_stats) if manual_stats else {},
                    'auto': dict(auto_stats) if auto_stats else {}
                }

# Instance globale
db = None

def init_database():
    """Initialise la base de données"""
    global db
    try:
        db = DatabaseManager()
        return db
    except Exception as e:
        print(f"❌ Erreur initialisation base de données: {e}")
        return None