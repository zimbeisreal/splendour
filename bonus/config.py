# bonus/config.py
from decimal import Decimal
from typing import Dict, Any, Tuple
from flask import current_app


class BonusConfigHelper:
    """
    Bonus configuration helper with level-based percentages
    Level 1: 10%, Level 2: 5%, Level 3: 3%, Level 4: 2%, Level 5: 1%,
    Levels 6-20: 0.5% each
    """
    
    # Bonus percentages by level
    BONUS_PERCENTAGES = {
        1: Decimal('0.15'),   # 10%
        2: Decimal('0.01'),   # 5%
        3: Decimal('0.01'),   # 3%
        4: Decimal('0.01'),   # 2%
        5: Decimal('0.01'),   # 1%
        # Levels 6-20: 0.5% each
    }
    
    # Default percentage for levels 6-20
    DEFAULT_PERCENTAGE = Decimal('0.000')
    
    MAX_LEVEL = 5
    
    @staticmethod
    def get_bonus_percentage(level: int, package_id: int = None) -> Decimal:
        """
        Get bonus percentage for a given level
        Levels 1-5 have specific percentages, levels 6-20 get 0.5%
        """
        try:
            if not isinstance(level, int) or level < 1 or level > BonusConfigHelper.MAX_LEVEL:
                current_app.logger.warning(f"Invalid level {level}, using default percentage")
                return BonusConfigHelper.DEFAULT_PERCENTAGE
            
            # Return specific percentage for levels 1-5, default for 6-20
            return BonusConfigHelper.BONUS_PERCENTAGES.get(
                level, 
                BonusConfigHelper.DEFAULT_PERCENTAGE
            )
        except Exception as e:
            current_app.logger.error(f"Error getting bonus percentage for level {level}: {e}")
            return BonusConfigHelper.DEFAULT_PERCENTAGE
    
    @staticmethod
    def get_bonus_distribution_summary() -> Dict[str, Any]:
        """Get summary of bonus distribution across all levels"""
        distribution = {}
        total_percentage = Decimal('0')
        
        for level in range(1, BonusConfigHelper.MAX_LEVEL + 1):
            percentage = BonusConfigHelper.get_bonus_percentage(level)
            distribution[level] = {
                'percentage': float(percentage),
                'percentage_display': f"{float(percentage) * 100}%"
            }
            total_percentage += percentage
        
        return {
            'distribution': distribution,
            'total_percentage': float(total_percentage),
            'max_level': BonusConfigHelper.MAX_LEVEL,
            'levels_with_specific_percentages': list(BonusConfigHelper.BONUS_PERCENTAGES.keys())
        }
    
    @staticmethod
    def validate_bonus_configuration() -> Tuple[bool, str]:
        """Validate that bonus configuration is mathematically sound"""
        try:
            total_percentage = Decimal('0')
            
            for level in range(1, BonusConfigHelper.MAX_LEVEL + 1):
                percentage = BonusConfigHelper.get_bonus_percentage(level)
                total_percentage += percentage
            
            # Total should be reasonable (not exceeding 50% for example)
            if total_percentage > Decimal('0.5'):  # 50%
                return False, f"Total bonus percentage too high: {total_percentage*100}%"
            
            if total_percentage <= Decimal('0'):
                return False, "Total bonus percentage must be positive"
            
            return True, f"Bonus configuration valid: {total_percentage*100:.1f}% total across {BonusConfigHelper.MAX_LEVEL} levels"
            
        except Exception as e:
            return False, f"Configuration validation error: {str(e)}"
        
import hashlib
import secrets

def generate_security_hash(user_id: int, payment_id: int, bonus_amount: float) -> str:
    raw = f"{user_id}-{payment_id}-{bonus_amount}-{secrets.token_hex(8)}"
    return hashlib.sha256(raw.encode()).hexdigest()
