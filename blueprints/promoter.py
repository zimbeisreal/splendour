"""
Promoter Registration Blueprint
Handles promoter registration page rendering and API endpoints
"""

from flask import Blueprint, render_template, request, jsonify, session, current_app
from extensions import db
from models import Promoter, User
from datetime import datetime
import re
import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

promoter_bp = Blueprint('promoter', __name__, url_prefix='/promoter')


# ============================================================
# ROUTE: Render Promoter Registration Page
# ============================================================

@promoter_bp.route('/register')
def promoter_register_page():
    """
    Render the promoter registration page
    URL: /promoter/register
    """
    return render_template('partials/promoter.html')

@promoter_bp.route('/login')
def promoter_login_page():
    """
    Render the promoter registration page
    URL: /promoter/register
    """
    return render_template('/promoter_login.html')


# ============================================================
# API: Promoter Signup
# ============================================================

@promoter_bp.route('/signup', methods=['POST'])
def promoter_signup():
    """
    API endpoint for promoter registration
    URL: /promoter/promoter/signup
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # ============================================================
        # VALIDATE REQUIRED FIELDS
        # ============================================================
        
        required_fields = [
            'full_name', 'nin', 'phone_direct', 'location',
            'promoted_products', 'experience_months', 'promoter_type',
            'expected_daily', 'expected_weekly', 'available_hours'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # ============================================================
        # VALIDATE PHONE NUMBERS
        # ============================================================
        
        phone_direct = data.get('phone_direct', '').strip()
        phone_whatsapp = data.get('phone_whatsapp', '').strip() if data.get('phone_whatsapp') else None
        
        # Validate phone number format (Uganda: 256XXXXXXXXX)
        phone_pattern = re.compile(r'^256[0-9]{9}$')
        
        if not phone_pattern.match(phone_direct):
            return jsonify({
                'success': False,
                'error': 'Invalid phone number format. Use format: 256700000000'
            }), 400
        
        if phone_whatsapp and not phone_pattern.match(phone_whatsapp):
            return jsonify({
                'success': False,
                'error': 'Invalid WhatsApp number format. Use format: 256700000000'
            }), 400
        
        # ============================================================
        # VALIDATE NIN (National ID Number)
        # ============================================================
        
        nin = data.get('nin', '').strip().upper()
        # Basic NIN validation - adjust pattern as needed
        nin_pattern = re.compile(r'^[A-Z0-9]{10,14}$')
        if not nin_pattern.match(nin):
            return jsonify({
                'success': False,
                'error': 'Invalid NIN format. Please enter a valid National ID Number'
            }), 400
        
        # ============================================================
        # VALIDATE EXPECTED EARNINGS
        # ============================================================
        
        try:
            expected_daily = float(data.get('expected_daily', 0))
            expected_weekly = float(data.get('expected_weekly', 0))
            
            if expected_daily < 10000:
                return jsonify({
                    'success': False,
                    'error': 'Expected daily earnings must be at least UGX 10,000'
                }), 400
            
            if expected_weekly < 50000:
                return jsonify({
                    'success': False,
                    'error': 'Expected weekly earnings must be at least UGX 50,000'
                }), 400
                
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid expected earnings amount'
            }), 400
        
        # ============================================================
        # CHECK FOR EXISTING PROMOTER
        # ============================================================
        
        existing = Promoter.query.filter(
            (Promoter.phone_direct == phone_direct) | 
            (Promoter.nin == nin)
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': 'A promoter with this phone number or NIN already exists'
            }), 400
        
        # ============================================================
        # CREATE PROMOTER
        # ============================================================
        
        # Parse skills from JSON
        skills = data.get('skills', [])
        if isinstance(skills, str):
            try:
                import json
                skills = json.loads(skills)
            except:
                skills = []
        
        promoter = Promoter(
            full_name=data.get('full_name', '').strip(),
            nin=nin,
            phone_direct=phone_direct,
            phone_whatsapp=phone_whatsapp,
            email=data.get('email', '').strip() or None,
            location=data.get('location', '').strip(),
            previous_companies=data.get('previous_companies', '').strip() or None,
            promoted_products=data.get('promoted_products', '').strip(),
            experience_months=data.get('experience_months', ''),
            promoter_type=data.get('promoter_type', ''),
            team_size=int(data.get('team_size', 0)) if data.get('team_size') else 0,
            expected_daily=expected_daily,
            expected_weekly=expected_weekly,
            available_hours=data.get('available_hours', ''),
            preferred_areas=data.get('preferred_areas', '').strip() or None,
            skills=skills,
            status='pending',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(promoter)
        db.session.commit()
        
        logger.info(f"✅ New promoter registered: {promoter.full_name} - {promoter.phone_direct}")
        
        # ============================================================
        # OPTIONAL: CREATE USER ACCOUNT
        # ============================================================
        # Uncomment if you want to create a user account for the promoter
        """
        user = User(
            username=f"promoter_{promoter.id}",
            phone=phone_direct,
            role='promoter',
            is_active=True,
            is_verified=False,
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
        """
        
        # ============================================================
        # RETURN SUCCESS RESPONSE
        # ============================================================
        
        return jsonify({
            'success': True,
            'message': 'Registration submitted successfully!',
            'data': {
                'id': promoter.id,
                'full_name': promoter.full_name,
                'phone_direct': promoter.phone_direct,
                'status': promoter.status,
                'created_at': promoter.created_at.isoformat() if promoter.created_at else None
            }
        }), 201
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in promoter signup: {e}")
        return jsonify({
            'success': False,
            'error': 'Database error. Please try again later.'
        }), 500
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error in promoter signup: {e}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500


# ============================================================
# API: Get Promoter Status
# ============================================================

@promoter_bp.route('/api/promoter/status/<int:promoter_id>', methods=['GET'])
def get_promoter_status(promoter_id):
    """
    Get promoter status by ID
    """
    try:
        promoter = Promoter.query.get(promoter_id)
        
        if not promoter:
            return jsonify({
                'success': False,
                'error': 'Promoter not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'id': promoter.id,
                'full_name': promoter.full_name,
                'status': promoter.status,
                'created_at': promoter.created_at.isoformat() if promoter.created_at else None,
                'verified_at': promoter.verified_at.isoformat() if promoter.verified_at else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting promoter status: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get promoter status'
        }), 500


# ============================================================
# API: Verify Promoter (Admin Only)
# ============================================================

@promoter_bp.route('/api/promoter/verify/<int:promoter_id>', methods=['POST'])
def verify_promoter(promoter_id):
    """
    Admin endpoint to verify a promoter
    """
    # Check if user is admin
    if not session.get('role') == 'admin':
        return jsonify({
            'success': False,
            'error': 'Unauthorized. Admin access required.'
        }), 403
    
    try:
        promoter = Promoter.query.get(promoter_id)
        
        if not promoter:
            return jsonify({
                'success': False,
                'error': 'Promoter not found'
            }), 404
        
        if promoter.status == 'verified':
            return jsonify({
                'success': False,
                'error': 'Promoter already verified'
            }), 400
        
        promoter.status = 'verified'
        promoter.verified_at = datetime.utcnow()
        promoter.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ Promoter verified: {promoter.full_name} - {promoter.phone_direct}")
        
        # Trigger bonus payment (UGX 20,000)
        # You can implement this based on your bonus system
        
        return jsonify({
            'success': True,
            'message': 'Promoter verified successfully! UGX 20,000 bonus will be sent.',
            'data': {
                'id': promoter.id,
                'full_name': promoter.full_name,
                'status': promoter.status,
                'verified_at': promoter.verified_at.isoformat() if promoter.verified_at else None
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error verifying promoter: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to verify promoter'
        }), 500

# blueprints/promoter.py

@promoter_bp.route('/login', methods=['POST'])
def promoter_login():
    """
    Authenticate promoter and return promoter data
    POST /promoter/login
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request data'
            }), 400
        
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        
        # ============================================================
        # VALIDATION
        # ============================================================
        if not phone:
            return jsonify({
                'success': False,
                'message': 'Phone number required'
            }), 400
        
        if not password:
            return jsonify({
                'success': False,
                'message': 'Password required'
            }), 400
        
        # ============================================================
        # FORMAT PHONE
        # ============================================================
        formatted_phone = phone.replace(' ', '')
        if formatted_phone.startswith('+'):
            formatted_phone = formatted_phone[1:]
        if formatted_phone.startswith('0'):
            formatted_phone = '256' + formatted_phone[1:]
        if formatted_phone.startswith('256') and len(formatted_phone) > 12:
            formatted_phone = formatted_phone[:12]
        
        # ============================================================
        # FIND PROMOTER
        # ============================================================
        promoter = Promoter.find_by_phone(formatted_phone)
        
        if not promoter:
            # Try with original format
            promoter = Promoter.find_by_phone(phone)
            
        if not promoter:
            logger.warning(f"Promoter not found: {formatted_phone}")
            return jsonify({
                'success': False,
                'message': 'Promoter not found. Please contact admin.'
            }), 404
        
        # ============================================================
        # CHECK PASSWORD
        # ============================================================
        if not promoter.check_password(password):
            logger.warning(f"Invalid password for promoter: {formatted_phone}")
            return jsonify({
                'success': False,
                'message': 'Invalid password. Please try again.'
            }), 401
        
        # ============================================================
        # CHECK STATUS
        # ============================================================
        if not promoter.is_active:
            return jsonify({
                'success': False,
                'message': 'Account is inactive. Please contact admin.'
            }), 403
        
        if promoter.status == 'suspended':
            return jsonify({
                'success': False,
                'message': 'Account suspended. Please contact admin.'
            }), 403
        
        # ============================================================
        # UPDATE LAST LOGIN
        # ============================================================
        promoter.update_last_login()
        db.session.commit()
        
        # ============================================================
        # SET SESSION
        # ============================================================
        session['promoter_id'] = promoter.id
        session['promoter_role'] = promoter.promoter_type
        session['is_promoter'] = True
        session['promoter_name'] = promoter.full_name
        
        # ============================================================
        # RESPONSE
        # ============================================================
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'promoter': promoter.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Promoter login error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Login failed. Please try again.'
        }), 500


@promoter_bp.route('/profile', methods=['GET'])
def promoter_profile():
    """Get promoter profile"""
    try:
        promoter_id = session.get('promoter_id')
        
        if not promoter_id:
            return jsonify({
                'success': False,
                'message': 'Not authenticated'
            }), 401
        
        promoter = Promoter.query.get(promoter_id)
        
        if not promoter:
            return jsonify({
                'success': False,
                'message': 'Promoter not found'
            }), 404
        
        return jsonify({
            'success': True,
            'promoter': promoter.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Promoter profile error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Failed to load profile'
        }), 500


@promoter_bp.route('/register/', methods=['POST'])
def promoter_register_():
    """
    Register a new promoter
    POST /promoter/register
    """
    try:
        data = request.get_json()
        
        # ============================================================
        # VALIDATE REQUIRED FIELDS
        # ============================================================
        required_fields = ['full_name', 'nin', 'phone_direct', 'promoted_products', 
                          'experience_months', 'promoter_type', 'expected_daily', 
                          'available_hours']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'{field} is required'
                }), 400
        
        # ============================================================
        # CHECK DUPLICATES
        # ============================================================
        if Promoter.find_by_nin(data['nin']):
            return jsonify({
                'success': False,
                'message': 'NIN already registered'
            }), 409
        
        if Promoter.find_by_phone(data['phone_direct']):
            return jsonify({
                'success': False,
                'message': 'Phone number already registered'
            }), 409
        
        # ============================================================
        # CREATE PROMOTER
        # ============================================================
        promoter = Promoter(
            full_name=data['full_name'],
            nin=data['nin'],
            phone_direct=data['phone_direct'],
            phone_whatsapp=data.get('phone_whatsapp'),
            email=data.get('email'),
            location=data.get('location', ''),
            previous_companies=data.get('previous_companies'),
            promoted_products=data['promoted_products'],
            experience_months=data['experience_months'],
            promoter_type=data['promoter_type'],
            team_size=data.get('team_size', 0),
            expected_daily=data['expected_daily'],
            expected_weekly=data.get('expected_weekly', data['expected_daily'] * 7),
            available_hours=data['available_hours'],
            preferred_areas=data.get('preferred_areas'),
            skills=data.get('skills', []),
            status='pending',
            is_active=True
        )
        
        # Set password if provided
        if data.get('password'):
            promoter.set_password(data['password'])
        
        db.session.add(promoter)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Promoter registered successfully',
            'promoter': promoter.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Promoter registration error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Registration failed. Please try again.'
        }), 500


@promoter_bp.route('/logout', methods=['POST'])
def promoter_logout():
    """Logout promoter"""
    try:
        session.pop('promoter_id', None)
        session.pop('promoter_role', None)
        session.pop('is_promoter', None)
        session.pop('promoter_name', None)
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Promoter logout error: {e}")
        return jsonify({
            'success': False,
            'message': 'Logout failed'
        }), 500

# blueprints/promoter.py - Add this route
from flask import redirect, url_for

@promoter_bp.route('/dashboard', methods=['GET'])
def promoter_profile_page():
    """
    Render the promoter profile dashboard page
    URL: /profile/promoter
    """
    # Check if promoter is logged in
    promoter_id = session.get('promoter_id')
    
    if not promoter_id:
        # Redirect to promoter login if not authenticated
        return redirect(url_for('promoter_login_page'))
    
    # Get promoter data
    promoter = Promoter.query.get(promoter_id)
    
    if not promoter:
        session.clear()
        return redirect(url_for('promoter_login_page'))
    
    # Render the promoter profile template
    return render_template('partials/promoter_profile.html', promoter=promoter)


@promoter_bp.route('/login', methods=['GET'])
def promoter_login_page_():
    """
    Render the promoter login page
    URL: /promoter/login (GET)
    """
    # If already logged in, redirect to profile
    if session.get('promoter_id'):
        return redirect(url_for('promoter.promoter_profile'))
    
    return render_template('index.html')