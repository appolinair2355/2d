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
        self.pending_edit_messages = {}  # Messages en attente d'édition {game_number: message_content}
        # Système de déclenchement basé sur les As (A) dans le premier groupe uniquement
        self.trigger_numbers = {7, 8}  # Numéros de fin qui déclenchent les prédictions
        
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
        """Extract game number from message using pattern #N followed by digits"""
        try:
            # Look for patterns like "#N 123", "#N123", "#N60.", etc.
            match = re.search(r"#N\s*(\d+)\.?", message, re.IGNORECASE)
            if match:
                number = int(match.group(1))
                print(f"Numéro de jeu extrait: {number}")
                return number
            
            # Alternative pattern matching
            match = re.search(r"jeu\s*#?\s*(\d+)", message, re.IGNORECASE)
            if match:
                number = int(match.group(1))
                print(f"Numéro de jeu alternatif extrait: {number}")
                return number
                
            print(f"Aucun numéro de jeu trouvé dans: {message}")
            return None
        except (ValueError, AttributeError) as e:
            print(f"Erreur extraction numéro: {e}")
            return None

    def extract_symbols_from_parentheses(self, message: str) -> List[str]:
        """Extract content from parentheses in the message"""
        try:
            return re.findall(r"\(([^)]*)\)", message)
        except Exception:
            return []

    def count_total_cards(self, symbols_str: str) -> int:
        """Count total card symbols in a string"""
        # Compter d'abord les versions emoji, puis les versions simples
        # pour éviter le double comptage
        emoji_symbols = ['♠️', '♥️', '♦️', '♣️']
        simple_symbols = ['♠', '♥', '♦', '♣']
        
        # Remplacer les emojis par des marqueurs temporaires pour éviter le double comptage
        temp_str = symbols_str
        emoji_count = 0
        
        for emoji in emoji_symbols:
            count = temp_str.count(emoji)
            emoji_count += count
            # Remplacer par des marqueurs pour éviter le recomptage
            temp_str = temp_str.replace(emoji, 'X')
        
        # Compter les symboles simples restants
        simple_count = 0
        for symbol in simple_symbols:
            simple_count += temp_str.count(symbol)
            
        total = emoji_count + simple_count
        print(f"Comptage cartes détaillé: emoji={emoji_count}, simple={simple_count}, total={total} dans '{symbols_str}'")
        return total

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

            # Extract symbols from parentheses first to check for Ace trigger
            matches = self.extract_symbols_from_parentheses(message)
            if len(matches) < 2:
                print(f"❌ Pas assez de groupes de parenthèses (besoin de 2): {matches}")
                return False, None, None

            first_group = matches[0]
            second_group = matches[1]
            
            # NOUVELLE LOGIQUE: Vérifier la présence d'As (A) dans les groupes
            has_ace_first = 'A' in first_group
            has_ace_second = 'A' in second_group
            
            print(f"🎯 Analyse As: Premier groupe='{first_group}' (As: {has_ace_first}), Deuxième groupe='{second_group}' (As: {has_ace_second})")
            
            # RÈGLES DE DÉCLENCHEMENT:
            # 1. Prédire SEULEMENT si As dans le PREMIER groupe
            # 2. NE PAS prédire si As dans le DEUXIÈME groupe  
            # 3. NE PAS prédire si As dans les DEUX groupes
            if not has_ace_first:
                print(f"❌ Pas d'As dans le premier groupe, pas de prédiction")
                return False, None, None
                
            if has_ace_second:
                print(f"❌ As détecté dans le deuxième groupe, prédiction bloquée")
                return False, None, None
            
            print(f"✅ Condition As validée: As dans premier groupe uniquement")

            # Calculate predicted game number (jeu suivant)
            predicted_game = game_number + 1
            
            # ANTI-DOUBLON: Check if predicted game already has a prediction (any status)
            if predicted_game in self.prediction_status:
                print(f"❌ Prédiction déjà existante pour le jeu #{predicted_game} (statut: {self.prediction_status[predicted_game]}), ignoré")
                return False, None, None
            
            # ANTI-DOUBLON: Double check from processed messages to avoid scheduler conflicts
            if f"auto_prediction_{predicted_game}" in self.processed_messages:
                print(f"❌ Prédiction automatique déjà planifiée pour #{predicted_game}, ignoré")
                return False, None, None
            
            # Check if current game already processed
            if game_number in self.processed_messages:
                print(f"Jeu #{game_number} déjà traité, ignoré")
                return False, None, None

            # Get suits from first group
            suits = self.normalize_suits(first_group)
            
            if not suits:
                return False, None, None

            # Mark current game as processed
            self.processed_messages.add(game_number)
            
            # Create prediction for target game
            self.prediction_status[predicted_game] = '⌛'
            self.last_predictions.append((predicted_game, suits))
            
            print(f"✅ Prédiction créée: Jeu #{predicted_game} -> {suits} (déclenchée par #{game_number} avec As dans premier groupe)")
            print(f"📊 Prédictions actives: {[k for k, v in self.prediction_status.items() if v == '⌛']}")
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
        
    def check_expired_predictions(self, current_game_number: int) -> List[int]:
        """Check for expired predictions (offset > 2) and mark them as failed"""
        expired_predictions = []
        
        for pred_num, status in list(self.prediction_status.items()):
            if status == '⌛' and current_game_number > pred_num + 2:
                # Marquer comme échouée
                self.prediction_status[pred_num] = '❌❌'
                self.status_log.append((pred_num, '❌❌'))
                expired_predictions.append(pred_num)
                print(f"❌ Prédiction expirée: #{pred_num} marquée comme échouée (jeu actuel: #{current_game_number})")
        
        return expired_predictions
        
    def is_pending_edit_message(self, message: str) -> Tuple[bool, Optional[int]]:
        """Check if message has ⏰ or 🕐 indicating it's being edited"""
        try:
            if "⏰" in message or "🕐" in message:
                game_number = self.extract_game_number(message)
                if game_number:
                    print(f"🔄 Message #{game_number} en cours d'édition détecté: ⏰ ou 🕐")
                    # Stocker le message en attente
                    self.pending_edit_messages[game_number] = message
                    return True, game_number
            return False, None
        except Exception as e:
            print(f"Erreur dans is_pending_edit_message: {e}")
            return False, None
    
    def process_final_edit_message(self, message: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """Process message when it's finally edited with 🔰 or ✅"""
        try:
            if "🔰" in message or "✅" in message:
                game_number = self.extract_game_number(message)
                if game_number and game_number in self.pending_edit_messages:
                    print(f"✅ Message #{game_number} finalisé avec 🔰 ou ✅")
                    
                    # Supprimer de la liste d'attente
                    del self.pending_edit_messages[game_number]
                    
                    # Traiter maintenant le message pour déclenchement As
                    return self.should_predict(message)
                    
            return False, None, None
        except Exception as e:
            print(f"Erreur dans process_final_edit_message: {e}")
            return False, None, None

    def verify_prediction(self, message: str) -> Tuple[Optional[bool], Optional[int]]:
        """Verify prediction results based on verification message"""
        try:
            # NOUVELLE LOGIQUE: Ignorer complètement les messages ⏰ et 🕐 pour la vérification
            if "⏰" in message or "🕐" in message:
                print(f"⏰/🕐 détecté dans le message - ignoré pour la vérification")
                return None, None

            # Check for verification tags (uniquement messages normaux)
            if not any(tag in message for tag in ["✅", "🔰", "❌", "⭕"]):
                return None, None

            # Extract game number
            game_number = self.extract_game_number(message)
            if game_number is None:
                print(f"Aucun numéro de jeu trouvé dans: {message}")
                return None, None

            print(f"Numéro de jeu du résultat: {game_number}")

            # Extract symbol groups
            groups = self.extract_symbols_from_parentheses(message)
            if len(groups) < 2:
                print(f"Groupes de symboles insuffisants: {groups}")
                return None, None

            first_group = groups[0]
            second_group = groups[1]
            print(f"Groupes extraits: '{first_group}' et '{second_group}'")

            def is_valid_result():
                """Check if the result has valid card distribution (2+2)"""
                count1 = self.count_total_cards(first_group)
                count2 = self.count_total_cards(second_group)
                print(f"Comptage cartes: groupe1={count1}, groupe2={count2}")
                is_valid = count1 == 2 and count2 == 2
                print(f"Résultat valide (2+2): {is_valid}")
                return is_valid

            # Vérifier les prédictions en attente dans le bon ordre
            # 1. Chercher d'abord si ce jeu correspond exactement à une prédiction (offset 0)
            # 2. Puis vérifier si c'est le jeu suivant d'une prédiction (offset +1)
            # 3. Puis vérifier si c'est 2 jeux après une prédiction (offset +2)
            
            # Vérifier d'abord si c'est un résultat valide (2+2 cartes)
            if not is_valid_result():
                print(f"❌ Résultat invalide: pas exactement 2+2 cartes, ignoré pour vérification")
                return None, None
            
            for offset in range(4):  # Check 0, 1, 2 , 3offsets
                predicted_number = game_number - offset
                print(f"Vérification si le jeu #{game_number} correspond à la prédiction #{predicted_number} (offset {offset})")
                
                if (predicted_number in self.prediction_status and 
                    self.prediction_status[predicted_number] == '⌛'):
                    print(f"Prédiction en attente trouvée: #{predicted_number}")
                    
                    # Success with offset indicator - résultat déjà validé comme 2+2
                    if offset == 0:
                        statut = '✅0️⃣'  # Perfect timing
                        elif offset == 1:
                            statut = '✅1️⃣'  # 1 game late
                        elif offset == 2:
                            statut = '✅2️⃣'  # 2 games late
                        elif offset == 3:
                            statut = '✅3️⃣'  # 3 games late
                        else:
                            statut = '❌❌'   # plus de 3 -> échec
                        
                    self.prediction_status[predicted_number] = statut
                    self.status_log.append((predicted_number, statut))
                    print(f"✅ Prédiction réussie: #{predicted_number} validée par le jeu #{game_number} (offset {offset})")
                    return True, predicted_number

            # Si aucune prédiction trouvée dans les 3 offsets, ne pas marquer comme expirées ici
            # Les prédictions expirées seront traitées séparément
            print(f"Aucune prédiction correspondante trouvée pour le jeu #{game_number}")
            print(f"Prédictions actuelles en attente: {[k for k, v in self.prediction_status.items() if v == '⌛']}")
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
                    'pending': len([s for s in self.prediction_status.values() if s == '⌛']),
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
