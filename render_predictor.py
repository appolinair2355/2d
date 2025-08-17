"""
Version simplifiée du moteur de prédiction pour Render.com
Optimisé pour la performance et la stabilité en production
"""
import re
import random
from typing import Tuple, Optional, List

class CardPredictor:
    """Moteur de prédiction simplifié pour Render.com"""
    
    def __init__(self):
        self.last_predictions = []
        self.prediction_status = {}
        self.processed_messages = set()
        self.status_log = []
        self.prediction_messages = {}
        self.pending_edit_messages = {}
        self.trigger_numbers = {6, 7, 8, 9}  # Déclencheurs étendus
        
    def reset(self):
        """Reset all prediction data"""
        self.last_predictions.clear()
        self.prediction_status.clear()
        self.processed_messages.clear()
        self.status_log.clear()
        self.prediction_messages.clear()
        self.pending_edit_messages.clear()
        print("Données de prédiction réinitialisées")

    def extract_game_number(self, message: str) -> Optional[int]:
        """Extract game number from message"""
        try:
            match = re.search(r"#N\s*(\d+)\.?", message, re.IGNORECASE)
            if match:
                return int(match.group(1))
            match = re.search(r"jeu\s*#?\s*(\d+)", message, re.IGNORECASE)
            if match:
                return int(match.group(1))
            return None
        except (ValueError, AttributeError):
            return None

    def should_trigger_prediction(self, game_number: int) -> bool:
        """Détermine si on doit déclencher une prédiction"""
        last_digit = game_number % 10
        
        # Vérifier si c'est un déclencheur valide
        if last_digit not in self.trigger_numbers:
            return False
            
        # Logique de variabilité - 30% chance d'ignorer un déclencheur répétitif
        if len(self.last_predictions) > 0:
            last_trigger = self.last_predictions[-1][0] % 10 if self.last_predictions[-1] else None
            if last_trigger == last_digit and random.random() < 0.3:
                print(f"🎲 Variabilité: Ignorer déclencheur répétitif {last_digit}")
                return False
        
        return True

    def generate_prediction(self, game_number: int) -> Optional[Tuple[int, str]]:
        """Génère une prédiction pour le jeu donné"""
        try:
            if not self.should_trigger_prediction(game_number):
                return None
                
            # Prédire le prochain numéro (+3 à +5)
            next_number = game_number + random.randint(3, 5)
            
            # Générer combinaison aléatoire
            symbols = ['♠️', '♣️', '♥️', '♦️']
            combination = ''.join(random.choices(symbols, k=random.randint(3, 5)))
            
            prediction = (next_number, combination)
            self.last_predictions.append(prediction)
            self.prediction_status[next_number] = "⏰"
            
            print(f"🔮 Prédiction générée: #{next_number} → {combination}")
            return prediction
            
        except Exception as e:
            print(f"Erreur génération prédiction: {e}")
            return None

    def verify_prediction(self, message: str) -> Optional[str]:
        """Vérifie si un message confirme ou infirme une prédiction"""
        try:
            game_number = self.extract_game_number(message)
            if not game_number:
                return None
                
            # Vérifier si on a une prédiction pour ce numéro
            if game_number in self.prediction_status:
                if "(" in message and ")" in message:
                    # Résultat trouvé
                    self.prediction_status[game_number] = "✅"
                    result = f"✅ #{game_number} CONFIRMÉ"
                    self.status_log.append(result)
                    return result
                    
            # Vérifier si des prédictions sont devenues obsolètes
            for pred_num in list(self.prediction_status.keys()):
                if game_number > pred_num + 2 and self.prediction_status[pred_num] == "⏰":
                    self.prediction_status[pred_num] = "❌❌"
                    result = f"❌❌ #{pred_num} ÉCHEC (jeu dépassé)"
                    self.status_log.append(result)
                    return result
                    
            return None
            
        except Exception as e:
            print(f"Erreur vérification: {e}")
            return None

    def get_statistics(self) -> dict:
        """Retourne les statistiques des prédictions"""
        total = len(self.status_log)
        wins = sum(1 for status in self.prediction_status.values() if status == "✅")
        
        return {
            "total": total,
            "wins": wins,
            "rate": (wins / total * 100) if total > 0 else 0,
            "active": sum(1 for status in self.prediction_status.values() if status == "⏰")
        }