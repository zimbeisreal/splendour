from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta, timezone
from flask import current_app
from sqlalchemy import text, func, and_, or_, case
from models import User, Referral, ReferralBonus, Payment, AuditLog, LoginAttempt, Wallet
from decimal import Decimal
import re
import ipaddress

from extensions import db

class AuditFraudHelper:
    """Enhanced fraud detection and prevention system for referral and bonus operations"""
    
    # Configuration thresholds (could be moved to config)
    FRAUD_THRESHOLDS = {
        'max_accounts_per_ip': 5,
        'max_accounts_per_phone': 3,
        'max_bonuses_per_hour': 10,
        'max_referrals_per_day': 20,
        'suspicious_amount_threshold': 1000,
        'rapid_creation_hours': 24,
        'min_time_between_actions': timedelta(minutes=1)
    }
    
    @staticmethod
    def detect_cycle_in_referrals() -> List[Dict[str, Any]]:
        """
        Detect circular references in referral network using improved cycle detection
        """
        try:
            # Enhanced query to detect cycles of any length
            query = text("""
                WITH RECURSIVE referral_chain AS (
                    -- Base case: direct referrals
                    SELECT 
                        referrer_id as ancestor_id, 
                        referred_id as descendant_id,
                        1 as depth,
                        CAST(referrer_id AS TEXT) || '->' || CAST(referred_id AS TEXT) as path
                    FROM referrals
                    WHERE referrer_id IS NOT NULL
                    
                    UNION ALL
                    
                    -- Recursive case: follow the chain
                    SELECT 
                        rc.ancestor_id,
                        r.referred_id,
                        rc.depth + 1,
                        rc.path || '->' || CAST(r.referred_id AS TEXT)
                    FROM referrals r
                    JOIN referral_chain rc ON r.referrer_id = rc.descendant_id
                    WHERE rc.depth < 10  -- Prevent infinite loops, max depth 10
                    AND rc.ancestor_id != r.referred_id  -- Stop if we find a cycle
                )
                SELECT DISTINCT 
                    ancestor_id as cycle_user_id,
                    path,
                    depth
                FROM referral_chain 
                WHERE ancestor_id = descendant_id
                OR path LIKE '%->' || CAST(ancestor_id AS TEXT) || '->%'
            """)
            
            result = db.session.execute(query)
            cycles = []
            
            for row in result:
                cycle_info = {
                    'user_id': row.cycle_user_id,
                    'path': row.path,
                    'depth': row.depth,
                    'severity': 'HIGH' if row.depth <= 3 else 'MEDIUM'
                }
                cycles.append(cycle_info)
                
                AuditFraudHelper._log_suspicious_activity(
                    f"Referral cycle detected: {row.path}",
                    'referral_cycle',
                    row.cycle_user_id,
                    {'depth': row.depth, 'path': row.path}
                )
            
            current_app.logger.warning(f"Detected {len(cycles)} referral cycles")
            return cycles
            
        except Exception as e:
            current_app.logger.error(f"Error detecting referral cycles: {str(e)}")
            return []
    
    @staticmethod
    def detect_self_referrals() -> List[Dict[str, Any]]:
        """
        Detect and analyze self-referrals with enhanced detection
        """
        try:
            # Direct self-referrals
            direct_self_refs = Referral.query.filter(
                Referral.referrer_id == Referral.referred_id
            ).all()
            
            # Indirect self-referrals (same user with different accounts)
            query = text("""
                SELECT r1.referrer_id, r1.referred_id, u1.email as referrer_email, u2.email as referred_email
                FROM referrals r1
                JOIN users u1 ON r1.referrer_id = u1.id
                JOIN users u2 ON r1.referred_id = u2.id
                WHERE u1.phone = u2.phone AND u1.phone IS NOT NULL AND u1.phone != ''
                AND r1.referrer_id != r1.referred_id
            """)
            
            indirect_result = db.session.execute(query)
            indirect_self_refs = [dict(row) for row in indirect_result]
            
            results = []
            
            # Process direct self-referrals
            for referral in direct_self_refs:
                result = {
                    'type': 'DIRECT',
                    'referral_id': referral.id,
                    'user_id': referral.referrer_id,
                    'created_at': referral.created_at,
                    'severity': 'CRITICAL'
                }
                results.append(result)
                
                AuditFraudHelper._log_suspicious_activity(
                    f"Direct self-referral detected for user {referral.referrer_id}",
                    'self_referral',
                    referral.referrer_id,
                    {'referral_id': referral.id, 'type': 'direct'}
                )
            
            # Process indirect self-referrals
            for ref in indirect_self_refs:
                result = {
                    'type': 'INDIRECT',
                    'referrer_id': ref['referrer_id'],
                    'referred_id': ref['referred_id'],
                    'referrer_email': ref['referrer_email'],
                    'referred_email': ref['referred_email'],
                    'shared_phone': True,
                    'severity': 'HIGH'
                }
                results.append(result)
                
                AuditFraudHelper._log_suspicious_activity(
                    f"Indirect self-referral via shared phone: {ref['referrer_id']} -> {ref['referred_id']}",
                    'self_referral',
                    ref['referrer_id'],
                    {'referred_id': ref['referred_id'], 'type': 'indirect'}
                )
            
            return results
            
        except Exception as e:
            current_app.logger.error(f"Error detecting self-referrals: {str(e)}")
            return []
    
    @staticmethod
    def detect_rapid_multi_account_creation(
        hours: int = None, 
        max_accounts: int = None
    ) -> List[Dict[str, Any]]:
        """
        Detect rapid account creation with multiple detection vectors
        """
        try:
            hours = hours or AuditFraudHelper.FRAUD_THRESHOLDS['rapid_creation_hours']
            max_accounts = max_accounts or AuditFraudHelper.FRAUD_THRESHOLDS['max_accounts_per_ip']
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            # Multi-vector detection: IP, device fingerprint, email pattern, etc.
            queries = {
                'ip_based': text("""
                    SELECT ip_address, COUNT(DISTINCT user_id) as account_count,
                           MIN(created_at) as first_creation,
                           MAX(created_at) as last_creation,
                           GROUP_CONCAT(DISTINCT user_id) as user_ids
                    FROM login_attempts
                    WHERE created_at > :cutoff_time AND success = TRUE
                    GROUP BY ip_address
                    HAVING COUNT(DISTINCT user_id) > :max_accounts
                """),
                
                'device_based': text("""
                    SELECT device_fingerprint, COUNT(DISTINCT user_id) as account_count,
                           MIN(created_at) as first_creation,
                           MAX(created_at) as last_creation
                    FROM login_attempts
                    WHERE created_at > :cutoff_time AND success = TRUE
                    AND device_fingerprint IS NOT NULL AND device_fingerprint != ''
                    GROUP BY device_fingerprint
                    HAVING COUNT(DISTINCT user_id) > :max_accounts
                """),
                
                'email_pattern': text("""
                    SELECT SUBSTRING_INDEX(email, '@', 1) as email_local,
                           COUNT(*) as account_count,
                           GROUP_CONCAT(id) as user_ids
                    FROM users
                    WHERE created_at > :cutoff_time
                    GROUP BY email_local
                    HAVING COUNT(*) > :max_accounts
                    AND email_local REGEXP '.*[0-9]{3,}.*'  -- Contains multiple numbers
                """)
            }
            
            suspicious_activities = []
            params = {'cutoff_time': cutoff_time, 'max_accounts': max_accounts}
            
            for method, query in queries.items():
                try:
                    result = db.session.execute(query, params)
                    for row in result:
                        activity = {
                            'detection_method': method,
                            'account_count': row.account_count,
                            'first_creation': row.first_creation,
                            'last_creation': row.last_creation,
                            'identifier': getattr(row, list(row._mapping.keys())[0]),  # First column
                            'user_ids': getattr(row, 'user_ids', '').split(',') if hasattr(row, 'user_ids') else []
                        }
                        suspicious_activities.append(activity)
                        
                        current_app.logger.warning(
                            f"Rapid account creation detected via {method}: "
                            f"{activity['identifier']} created {activity['account_count']} accounts"
                        )
                except Exception as e:
                    current_app.logger.error(f"Error in {method} detection: {str(e)}")
                    continue
            
            return suspicious_activities
            
        except Exception as e:
            current_app.logger.error(f"Error detecting rapid account creation: {str(e)}")
            return []
    
    @staticmethod
    def detect_same_phone_misuse() -> List[Dict[str, Any]]:
        """
        Enhanced phone misuse detection with pattern analysis
        """
        try:
            max_accounts = AuditFraudHelper.FRAUD_THRESHOLDS['max_accounts_per_phone']
            
            query = text(f"""
                SELECT 
                    phone,
                    COUNT(*) as user_count,
                    GROUP_CONCAT(id) as user_ids,
                    GROUP_CONCAT(username) as usernames,
                    GROUP_CONCAT(created_at) as creation_times,
                    MIN(created_at) as first_creation,
                    MAX(created_at) as last_creation,
                    CASE 
                        WHEN COUNT(*) > {max_accounts} THEN 'CRITICAL'
                        WHEN COUNT(*) > {max_accounts // 2} THEN 'HIGH'
                        ELSE 'MEDIUM'
                    END as severity
                FROM users
                WHERE phone IS NOT NULL AND phone != ''
                GROUP BY phone
                HAVING COUNT(*) > 1
                ORDER BY user_count DESC
            """)
            
            result = db.session.execute(query)
            phone_abuse = []
            
            for row in result:
                abuse_info = {
                    'phone': row.phone,
                    'user_count': row.user_count,
                    'user_ids': row.user_ids.split(','),
                    'usernames': row.usernames.split(','),
                    'creation_times': row.creation_times.split(','),
                    'first_creation': row.first_creation,
                    'last_creation': row.last_creation,
                    'severity': row.severity,
                    'time_span_days': (row.last_creation - row.first_creation).days
                }
                phone_abuse.append(abuse_info)
                
                # Log critical cases
                if abuse_info['severity'] == 'CRITICAL':
                    AuditFraudHelper._log_suspicious_activity(
                        f"Critical phone misuse: {row.phone} used by {row.user_count} accounts",
                        'phone_misuse',
                        None,
                        abuse_info
                    )
            
            return phone_abuse
            
        except Exception as e:
            current_app.logger.error(f"Error detecting phone misuse: {str(e)}")
            return []
    
    @staticmethod
    def detect_geographic_anomalies() -> List[Dict[str, Any]]:
        """
        Detect users logging in from geographically distant locations in short time
        """
        try:
            query = text("""
                SELECT 
                    la1.user_id,
                    la1.ip_address as ip1,
                    la2.ip_address as ip2,
                    la1.country_code as country1,
                    la2.country_code as country2,
                    la1.created_at as time1,
                    la2.created_at as time2,
                    TIMESTAMPDIFF(MINUTE, la1.created_at, la2.created_at) as time_diff_minutes
                FROM login_attempts la1
                JOIN login_attempts la2 ON la1.user_id = la2.user_id
                WHERE la1.success = TRUE AND la2.success = TRUE
                AND la1.country_code != la2.country_code
                AND la1.created_at < la2.created_at
                AND TIMESTAMPDIFF(MINUTE, la1.created_at, la2.created_at) < 120  -- 2 hours
                AND la1.ip_address != la2.ip_address
                ORDER BY time_diff_minutes ASC
            """)
            
            result = db.session.execute(query)
            anomalies = []
            
            for row in result:
                anomaly = {
                    'user_id': row.user_id,
                    'ip_addresses': [row.ip1, row.ip2],
                    'countries': [row.country1, row.country2],
                    'time_period_minutes': row.time_diff_minutes,
                    'severity': 'HIGH' if row.time_diff_minutes < 60 else 'MEDIUM'
                }
                anomalies.append(anomaly)
                
                AuditFraudHelper._log_suspicious_activity(
                    f"Geographic anomaly: user {row.user_id} in {row.country1} and {row.country2} "
                    f"within {row.time_diff_minutes} minutes",
                    'geographic_anomaly',
                    row.user_id,
                    anomaly
                )
            
            return anomalies
            
        except Exception as e:
            current_app.logger.error(f"Error detecting geographic anomalies: {str(e)}")
            return []
    
    @staticmethod
    def detect_bonus_velocity_abuse() -> List[Dict[str, Any]]:
        """
        Detect unusual patterns in bonus acquisition velocity
        """
        try:
            query = text("""
                SELECT 
                    user_id,
                    COUNT(*) as bonus_count,
                    MIN(created_at) as first_bonus,
                    MAX(created_at) as last_bonus,
                    SUM(amount) as total_amount,
                    TIMESTAMPDIFF(HOUR, MIN(created_at), MAX(created_at)) as time_span_hours,
                    CASE 
                        WHEN COUNT(*) / GREATEST(TIMESTAMPDIFF(HOUR, MIN(created_at), MAX(created_at)), 1) > 10 
                        THEN 'CRITICAL'
                        WHEN COUNT(*) / GREATEST(TIMESTAMPDIFF(HOUR, MIN(created_at), MAX(created_at)), 1) > 5 
                        THEN 'HIGH'
                        ELSE 'MEDIUM'
                    END as severity
                FROM referral_bonuses
                WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY user_id
                HAVING bonus_count > 10
                ORDER BY bonus_count DESC
            """)
            
            result = db.session.execute(query)
            velocity_abuse = []
            
            for row in result:
                bonus_rate = row.bonus_count / max(row.time_span_hours, 1)
                
                abuse_info = {
                    'user_id': row.user_id,
                    'bonus_count': row.bonus_count,
                    'total_amount': float(row.total_amount),
                    'time_span_hours': row.time_span_hours,
                    'bonus_per_hour': bonus_rate,
                    'severity': row.severity,
                    'first_bonus': row.first_bonus,
                    'last_bonus': row.last_bonus
                }
                velocity_abuse.append(abuse_info)
                
                if row.severity in ['CRITICAL', 'HIGH']:
                    AuditFraudHelper._log_suspicious_activity(
                        f"Bonus velocity abuse: user {row.user_id} earned {row.bonus_count} "
                        f"bonuses ({bonus_rate:.2f}/hour)",
                        'bonus_velocity',
                        row.user_id,
                        abuse_info
                    )
            
            return velocity_abuse
            
        except Exception as e:
            current_app.logger.error(f"Error detecting bonus velocity abuse: {str(e)}")
            return []
    
    @staticmethod
    def audit_bonus_history(user_id: int) -> Dict[str, Any]:
        """
        Comprehensive audit of user's bonus history with enhanced pattern detection
        """
        try:
            bonuses = ReferralBonus.query.filter_by(user_id=user_id).order_by(
                ReferralBonus.created_at
            ).all()
            
            if not bonuses:
                return {'user_id': user_id, 'status': 'no_bonuses'}
            
            total_bonuses = len(bonuses)
            total_amount = sum(Decimal(str(b.amount)) for b in bonuses)
            
            # Enhanced pattern analysis
            recent_bonuses = [b for b in bonuses if b.created_at > datetime.now(timezone.utc) - timedelta(days=7)]
            high_value_bonuses = [b for b in bonuses if b.amount > AuditFraudHelper.FRAUD_THRESHOLDS['suspicious_amount_threshold']]
            
            # Time-based analysis
            time_patterns = AuditFraudHelper._analyze_bonus_timing(bonuses)
            
            # Amount pattern analysis
            amount_patterns = AuditFraudHelper._analyze_amount_patterns(bonuses)
            
            # Level distribution analysis
            level_distribution = {}
            for bonus in bonuses:
                level = bonus.level
                level_distribution[level] = level_distribution.get(level, 0) + 1
            
            # Referral source analysis
            referral_sources = AuditFraudHelper._analyze_referral_sources(user_id)
            
            audit_result = {
                'user_id': user_id,
                'total_bonuses': total_bonuses,
                'total_amount': float(total_amount),
                'recent_bonuses_7d': len(recent_bonuses),
                'high_value_bonuses': len(high_value_bonuses),
                'time_patterns': time_patterns,
                'amount_patterns': amount_patterns,
                'level_distribution': level_distribution,
                'referral_sources': referral_sources,
                'risk_score': AuditFraudHelper._calculate_enhanced_risk_score(
                    total_bonuses, 
                    len(recent_bonuses),
                    len(high_value_bonuses),
                    time_patterns,
                    amount_patterns
                ),
                'recommendations': AuditFraudHelper._generate_recommendations(
                    total_bonuses, 
                    len(recent_bonuses),
                    len(high_value_bonuses),
                    time_patterns,
                    amount_patterns
                )
            }
            
            # Log high-risk audits
            if audit_result['risk_score'] > 70:
                AuditFraudHelper._log_suspicious_activity(
                    f"High-risk bonus pattern detected for user {user_id}",
                    'high_risk_audit',
                    user_id,
                    {'risk_score': audit_result['risk_score']}
                )
            
            return audit_result
            
        except Exception as e:
            current_app.logger.error(f"Error auditing bonus history for user {user_id}: {str(e)}")
            return {'user_id': user_id, 'error': str(e)}
    
    @staticmethod
    def _analyze_bonus_timing(bonuses: List[ReferralBonus]) -> Dict[str, Any]:
        """Analyze timing patterns in bonus acquisition"""
        if len(bonuses) < 2:
            return {'status': 'insufficient_data'}
        
        bonuses_sorted = sorted(bonuses, key=lambda x: x.created_at)
        time_diffs = []
        
        for i in range(1, len(bonuses_sorted)):
            diff = bonuses_sorted[i].created_at - bonuses_sorted[i-1].created_at
            time_diffs.append(diff.total_seconds() / 60)  # Convert to minutes
        
        avg_time_diff = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        min_time_diff = min(time_diffs) if time_diffs else 0
        
        patterns = {
            'average_time_between_bonuses_minutes': avg_time_diff,
            'minimum_time_between_bonuses_minutes': min_time_diff,
            'total_time_span_days': (bonuses_sorted[-1].created_at - bonuses_sorted[0].created_at).days,
            'bonuses_per_day': len(bonuses) / max((bonuses_sorted[-1].created_at - bonuses_sorted[0].created_at).days, 1)
        }
        
        # Detect patterns
        if min_time_diff < 1:  # Less than 1 minute
            patterns['rapid_succession'] = True
            patterns['rapid_succession_count'] = len([td for td in time_diffs if td < 1])
        else:
            patterns['rapid_succession'] = False
        
        if patterns['bonuses_per_day'] > 20:
            patterns['high_frequency'] = True
        else:
            patterns['high_frequency'] = False
        
        return patterns
    
    @staticmethod
    def _analyze_amount_patterns(bonuses: List[ReferralBonus]) -> Dict[str, Any]:
        """Analyze amount patterns in bonuses"""
        amounts = [float(b.amount) for b in bonuses]
        
        if not amounts:
            return {'status': 'no_data'}
        
        patterns = {
            'average_amount': sum(amounts) / len(amounts),
            'min_amount': min(amounts),
            'max_amount': max(amounts),
            'amount_std_dev': AuditFraudHelper._calculate_std_dev(amounts),
            'unique_amounts': len(set(amounts)),
            'repeated_amounts': len(amounts) - len(set(amounts))
        }
        
        # Detect suspicious patterns
        if patterns['unique_amounts'] == 1 and len(amounts) > 5:
            patterns['suspicious_identical_amounts'] = True
        else:
            patterns['suspicious_identical_amounts'] = False
        
        if patterns['amount_std_dev'] < 0.1 and len(amounts) > 3:
            patterns['suspicious_consistent_amounts'] = True
        else:
            patterns['suspicious_consistent_amounts'] = False
        
        return patterns
    
    @staticmethod
    def _analyze_referral_sources(user_id: int) -> Dict[str, Any]:
        """Analyze where the user's bonuses are coming from"""
        try:
            query = text("""
                SELECT 
                    COUNT(DISTINCT r.referrer_id) as unique_referrers,
                    COUNT(*) as total_referrals,
                    AVG(rb.amount) as avg_bonus_amount,
                    MIN(rb.created_at) as first_bonus_date,
                    MAX(rb.created_at) as last_bonus_date
                FROM referral_bonuses rb
                JOIN referrals r ON rb.referral_id = r.id
                WHERE rb.user_id = :user_id
            """)
            
            result = db.session.execute(query, {'user_id': user_id}).first()
            
            if not result:
                return {'status': 'no_referral_data'}
            
            return {
                'unique_referrers': result.unique_referrers,
                'total_referrals': result.total_referrals,
                'avg_bonus_amount': float(result.avg_bonus_amount) if result.avg_bonus_amount else 0,
                'first_bonus_date': result.first_bonus_date,
                'last_bonus_date': result.last_bonus_date,
                'referrals_per_referrer': result.total_referrals / max(result.unique_referrers, 1)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error analyzing referral sources: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _calculate_std_dev(numbers: List[float]) -> float:
        """Calculate standard deviation of a list of numbers"""
        if len(numbers) < 2:
            return 0.0
        
        mean = sum(numbers) / len(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return variance ** 0.5
    
    @staticmethod
    def _calculate_enhanced_risk_score(
        total_bonuses: int,
        recent_bonuses: int,
        high_value_bonuses: int,
        time_patterns: Dict[str, Any],
        amount_patterns: Dict[str, Any]
    ) -> int:
        """Calculate comprehensive risk score (0-100)"""
        risk_score = 0
        
        # Volume-based risk
        if total_bonuses > 100:
            risk_score += 25
        elif total_bonuses > 50:
            risk_score += 15
        elif total_bonuses > 20:
            risk_score += 10
        
        # Recent activity risk
        if recent_bonuses > 50:
            risk_score += 20
        elif recent_bonuses > 25:
            risk_score += 15
        elif recent_bonuses > 10:
            risk_score += 10
        
        # High-value bonus risk
        if high_value_bonuses > 10:
            risk_score += 20
        elif high_value_bonuses > 5:
            risk_score += 10
        
        # Timing pattern risk
        if time_patterns.get('rapid_succession', False):
            risk_score += 15
            risk_score += min(time_patterns.get('rapid_succession_count', 0) * 2, 10)
        
        if time_patterns.get('high_frequency', False):
            risk_score += 10
        
        # Amount pattern risk
        if amount_patterns.get('suspicious_identical_amounts', False):
            risk_score += 15
        
        if amount_patterns.get('suspicious_consistent_amounts', False):
            risk_score += 10
        
        return min(risk_score, 100)
    
    @staticmethod
    def _generate_recommendations(
        total_bonuses: int,
        recent_bonuses: int,
        high_value_bonuses: int,
        time_patterns: Dict[str, Any],
        amount_patterns: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on risk analysis"""
        recommendations = []
        
        if total_bonuses > 50:
            recommendations.append("Review user's bonus history for unusual patterns")
        
        if recent_bonuses > 25:
            recommendations.append("Consider temporary bonus suspension for review")
        
        if high_value_bonuses > 5:
            recommendations.append("Verify high-value bonus sources")
        
        if time_patterns.get('rapid_succession', False):
            recommendations.append("Investigate rapid bonus succession pattern")
        
        if amount_patterns.get('suspicious_identical_amounts', False):
            recommendations.append("Check for automated or manipulated bonus patterns")
        
        if not recommendations:
            recommendations.append("No immediate action required")
        
        return recommendations
    
    @staticmethod
    def _log_suspicious_activity(
        description: str, 
        activity_type: str, 
        user_id: int = None,
        details: Dict[str, Any] = None
    ) -> None:
        """Enhanced suspicious activity logging"""
        try:
            audit_log = AuditLog(
                actor_id=user_id,
                action=f"fraud_detection_{activity_type}",
                ip_address="system",
                details=description,
                additional_data=details or {}
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error logging suspicious activity: {str(e)}")
            db.session.rollback()
    
    @staticmethod
    def run_comprehensive_audit() -> Dict[str, Any]:
        """
        Run all enhanced fraud detection checks with reporting
        """
        start_time = datetime.now(timezone.utc)
        
        audit_results = {
            'timestamp': start_time.isoformat(),
            'audit_id': f"audit_{start_time.strftime('%Y%m%d_%H%M%S')}",
            'summary': {
                'total_checks': 0,
                'issues_found': 0,
                'critical_issues': 0,
                'high_risk_users': 0
            },
            'cycles_detected': AuditFraudHelper.detect_cycle_in_referrals(),
            'self_referrals': AuditFraudHelper.detect_self_referrals(),
            'rapid_creation': AuditFraudHelper.detect_rapid_multi_account_creation(),
            'phone_misuse': AuditFraudHelper.detect_same_phone_misuse(),
            'geographic_anomalies': AuditFraudHelper.detect_geographic_anomalies(),
            'bonus_velocity_abuse': AuditFraudHelper.detect_bonus_velocity_abuse(),
            'high_risk_users': [],
            'recommendations': []
        }
        
        # Update summary counts
        audit_results['summary']['total_checks'] = 6
        audit_results['summary']['issues_found'] = sum(
            len(audit_results[key]) for key in [
                'cycles_detected', 'self_referrals', 'rapid_creation', 
                'phone_misuse', 'geographic_anomalies', 'bonus_velocity_abuse'
            ]
        )
        
        # Identify high-risk users for detailed audit
        high_risk_candidates = ReferralBonus.query.group_by(
            ReferralBonus.user_id
        ).having(func.count(ReferralBonus.id) > 5).limit(20).all()
        
        for bonus in high_risk_candidates:
            audit = AuditFraudHelper.audit_bonus_history(bonus.user_id)
            if audit.get('risk_score', 0) > 50:
                audit_results['high_risk_users'].append(audit)
                if audit.get('risk_score', 0) > 80:
                    audit_results['summary']['critical_issues'] += 1
        
        audit_results['summary']['high_risk_users'] = len(audit_results['high_risk_users'])
        
        # Generate overall recommendations
        audit_results['recommendations'] = AuditFraudHelper._generate_audit_recommendations(audit_results)
        
        end_time = datetime.now(timezone.utc)
        audit_results['execution_time_seconds'] = (end_time - start_time).total_seconds()
        
        current_app.logger.info(
            f"Comprehensive fraud audit completed: "
            f"{audit_results['summary']['issues_found']} issues found, "
            f"{audit_results['summary']['critical_issues']} critical"
        )
        
        return audit_results
    
    @staticmethod
    def _generate_audit_recommendations(audit_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on audit results"""
        recommendations = []
        summary = audit_results['summary']
        
        if summary['critical_issues'] > 0:
            recommendations.append("Immediate action required for critical issues")
        
        if len(audit_results['self_referrals']) > 0:
            recommendations.append("Review and invalidate self-referrals")
        
        if len(audit_results['rapid_creation']) > 0:
            recommendations.append("Implement IP-based registration limits")
        
        if len(audit_results['phone_misuse']) > 0:
            recommendations.append("Enhance phone verification process")
        
        if len(audit_results['geographic_anomalies']) > 0:
            recommendations.append("Consider geographic-based security checks")
        
        if len(audit_results['bonus_velocity_abuse']) > 0:
            recommendations.append("Implement bonus velocity limits")
        
        if summary['high_risk_users'] > 0:
            recommendations.append(f"Review {summary['high_risk_users']} high-risk user accounts")
        
        if not recommendations:
            recommendations.append("No immediate action required - system appears healthy")
        
        return recommendations
    
    @staticmethod
    def get_user_risk_profile(user_id: int) -> Dict[str, Any]:
        """
        Generate comprehensive risk profile for a specific user
        """
        try:
            # Basic user info
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Run various checks
            bonus_audit = AuditFraudHelper.audit_bonus_history(user_id)
            referral_count = Referral.query.filter_by(referrer_id=user_id).count()
            login_anomalies = AuditFraudHelper._check_login_anomalies(user_id)
            
            # Calculate overall risk score
            risk_factors = []
            
            if bonus_audit.get('risk_score', 0) > 70:
                risk_factors.append('high_bonus_risk')
            
            if referral_count > 50:
                risk_factors.append('high_referral_volume')
            
            if login_anomalies.get('suspicious', False):
                risk_factors.append('login_anomalies')
            
            overall_risk = min(bonus_audit.get('risk_score', 0) + 
                             (10 if 'high_referral_volume' in risk_factors else 0) +
                             (15 if 'login_anomalies' in risk_factors else 0), 100)
            
            return {
                'user_id': user_id,
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'created_at': user.created_at,
                'overall_risk_score': overall_risk,
                'risk_level': 'HIGH' if overall_risk > 70 else 'MEDIUM' if overall_risk > 40 else 'LOW',
                'risk_factors': risk_factors,
                'bonus_audit': bonus_audit,
                'referral_count': referral_count,
                'login_anomalies': login_anomalies,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating risk profile for user {user_id}: {str(e)}")
            return {'user_id': user_id, 'error': str(e)}
    
    @staticmethod
    def _check_login_anomalies(user_id: int) -> Dict[str, Any]:
        """Check for login-related anomalies"""
        try:
            # Get recent successful logins
            recent_logins = LoginAttempt.query.filter_by(
                user_id=user_id, success=True
            ).order_by(LoginAttempt.created_at.desc()).limit(10).all()
            
            if len(recent_logins) < 2:
                return {'suspicious': False, 'reason': 'insufficient_data'}
            
            # Check for multiple locations
            locations = set(login.country_code for login in recent_logins if login.country_code)
            ip_addresses = set(login.ip_address for login in recent_logins if login.ip_address)
            
            anomalies = {
                'suspicious': False,
                'total_logins_checked': len(recent_logins),
                'unique_locations': len(locations),
                'unique_ips': len(ip_addresses)
            }
            
            # Flag if multiple countries in short time
            if len(locations) > 1:
                time_span = recent_logins[0].created_at - recent_logins[-1].created_at
                if time_span.total_seconds() < 3600:  # 1 hour
                    anomalies['suspicious'] = True
                    anomalies['reason'] = 'multiple_locations_short_time'
            
            return anomalies
            
        except Exception as e:
            current_app.logger.error(f"Error checking login anomalies: {str(e)}")
            return {'suspicious': False, 'error': str(e)}