import re
import random
from typing import Tuple, Optional, List

class CardPredictor:
    """Card game prediction engine with pattern matching and result verification"""
    
    def __init__(self):
        self.last_predictions = []  # Liste [(numéro, combinaison)]
        self.prediction_status = {}  # Statut des prédictions par numéro
        self.processed_messages = set()  # Pour éviter les doublons
        self.status_log = []  # Historique des statuts
        self.prediction_messages = {}  # Stockage des IDs de messages de prédiction
        self.trigger_numbers = [5, 7, 8]  # Numéros déclencheurs
        
    def reset(self):
        """Reset all prediction data"""
        self.last_predictions.clear()
        self.prediction_status.clear()
        self.processed_messages.clear()
        self.status_log.clear()
        self.prediction_messages.clear()
        print("Données de prédiction réinitialisées")

    def extract_game_number(self, message: str) -> Optional[int]:
        """Extract game number from message using pattern #N followed by digits"""
        try:
            # Look for patterns like "#N 123" or "#N123"
            match = re.search(r"#N\s*(\d+)", message, re.IGNORECASE)
            if match:
                return int(match.group(1))
            
            # Alternative pattern matching
            match = re.search(r"jeu\s*#?\s*(\d+)", message, re.IGNORECASE)
            if match:
                return int(match.group(1))
                
            return None
        except (ValueError, AttributeError):
            return None

    def extract_symbols_from_parentheses(self, message: str) -> List[str]:
        """Extract content from parentheses in the message"""
        try:
            return re.findall(r"\(([^)]*)\)", message)
        except Exception:
            return []

    def count_total_cards(self, symbols_str: str) -> int:
        """Count total card symbols in a string"""
        card_symbols = ['♠️', '♥️', '♦️', '♣️', '♠', '♥', '♦', '♣']
        count = 0
        for symbol in card_symbols:
            count += symbols_str.count(symbol)
        return count

    def normalize_suits(self, suits_str: str) -> str:
        """Normalize and sort card suits"""
        # Map emoji versions to simple versions
        suit_map = {
            '♠️': '♠', '♥️': '♥', '♦️': '♦', '♣️': '♣'
        }
        
        normalized = suits_str
        for emoji, simple in suit_map.items():
            normalized = normalized.replace(emoji, simple)
        
        # Extract only card symbols and sort them
        suits = [c for c in normalized if c in '♠♥♦♣']
        return ''.join(sorted(set(suits)))

    def should_predict(self, message: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """Determine if a prediction should be made based on the message"""
        try:
            # Extract game number
            game_number = self.extract_game_number(message)
            if game_number is None:
                return False, None, None

            # Check if already processed
            if game_number in self.prediction_status:
                return False, None, None

            # Only predict for games ending in trigger numbers (5, 7, 8)
            # We predict in advance for the next game ending in 0
            last_digit = game_number % 10
            if last_digit not in self.trigger_numbers:
                return False, None, None

            # Extract symbols from parentheses
            matches = self.extract_symbols_from_parentheses(message)
            if not matches:
                return False, None, None

            # Get first group of symbols
            first_group = matches[0]
            suits = self.normalize_suits(first_group)
            
            if not suits:
                return False, None, None

            # Check for message duplication
            message_hash = hash(message.strip())
            if message_hash in self.processed_messages:
                self.prediction_status[game_number] = 'déjà traité'
                return False, None, None

            # Mark as processed and create prediction
            self.processed_messages.add(message_hash)
            
            # Always predict for the next game ending in 0
            predicted_game = ((game_number // 10) + 1) * 10
            
            self.prediction_status[predicted_game] = '⌛'
            self.last_predictions.append((predicted_game, suits))
            
            print(f"Prédiction créée: Jeu #{predicted_game} -> {suits} (basée sur #{game_number})")
            return True, predicted_game, suits

        except Exception as e:
            print(f"Erreur dans should_predict: {e}")
            return False, None, None
    
    def store_prediction_message(self, game_number: int, message_id: int, chat_id: int):
        """Store prediction message ID for later editing"""
        self.prediction_messages[game_number] = {'message_id': message_id, 'chat_id': chat_id}
        
    def get_prediction_message(self, game_number: int):
        """Get stored prediction message details"""
        return self.prediction_messages.get(game_number)

    def verify_prediction(self, message: str) -> Tuple[Optional[bool], Optional[int]]:
        """Verify prediction results based on verification message"""
        try:
            # Check for verification tags
            if not any(tag in message for tag in ["✅", "🔰", "❌", "⭕"]):
                return None, None

            # Extract game number
            game_number = self.extract_game_number(message)
            if game_number is None:
                return None, None

            # Extract symbol groups
            groups = self.extract_symbols_from_parentheses(message)
            if len(groups) < 2:
                return None, None

            first_group = groups[0]
            second_group = groups[1]

            def is_valid_result():
                """Check if the result has valid card distribution (2+2)"""
                return (self.count_total_cards(first_group) == 2 and 
                        self.count_total_cards(second_group) == 2)

            # Check for pending predictions within offset range
            for offset in range(3):  # Check 0, 1, 2 games back
                target_number = game_number - offset
                
                if (target_number in self.prediction_status and 
                    self.prediction_status[target_number] == '⌛'):
                    
                    if is_valid_result():
                        # Success with offset indicator
                        if offset == 0:
                            statut = '✅0️⃣'  # Perfect timing
                        elif offset == 1:
                            statut = '✅1️⃣'  # 1 game late
                        else:
                            statut = '✅2️⃣'  # 2 games late
                            
                        self.prediction_status[target_number] = statut
                        self.status_log.append((target_number, statut))
                        print(f"Prédiction réussie: Jeu #{target_number} avec offset {offset}")
                        return True, target_number
                    else:
                        # Failed prediction
                        statut = '❌❌'
                        self.prediction_status[target_number] = statut
                        self.status_log.append((target_number, statut))
                        print(f"Prédiction échouée: Jeu #{target_number}")
                        return False, target_number

            return None, None

        except Exception as e:
            print(f"Erreur dans verify_prediction: {e}")
            return None, None

    def get_statistics(self) -> dict:
        """Get prediction statistics"""
        try:
            total_predictions = len(self.status_log)
            if total_predictions == 0:
                return {
                    'total': 0,
                    'wins': 0,
                    'losses': 0,
                    'pending': len([s for s in self.prediction_status.values() if s == '⏳']),
                    'win_rate': 0.0
                }

            wins = sum(1 for _, status in self.status_log if '✅' in status)
            losses = sum(1 for _, status in self.status_log if '❌' in status or '⭕' in status)
            pending = len([s for s in self.prediction_status.values() if s == '⌛'])
            win_rate = (wins / total_predictions * 100) if total_predictions > 0 else 0.0

            return {
                'total': total_predictions,
                'wins': wins,
                'losses': losses,
                'pending': pending,
                'win_rate': win_rate
            }
        except Exception as e:
            print(f"Erreur dans get_statistics: {e}")
            return {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'win_rate': 0.0}

    def get_recent_predictions(self, count: int = 10) -> List[Tuple[int, str]]:
        """Get recent predictions with their status"""
        try:
            recent = []
            for game_num, suits in self.last_predictions[-count:]:
                status = self.prediction_status.get(game_num, '⌛')
                recent.append((game_num, suits, status))
            return recent
        except Exception as e:
            print(f"Erreur dans get_recent_predictions: {e}")
            return []