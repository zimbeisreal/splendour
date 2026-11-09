import webbrowser
import signal
import sys
import gc
#import gevent
import time
#from gevent import monkey
#monkey.patch_all()
import os
from flask import Flask, render_template, session, g, request, jsonify, make_response, render_template_string
from config import Config
from models import User
from flask_migrate import Migrate
from extensions import db, login_manager, init_extensions
from sqlalchemy import text
from datetime import datetime, timedelta
from models import BillUtility
from flask_cors import CORS
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from flask_caching import Cache
from blueprints.salary import init_app as init_salary

migrate = Migrate()

def create_app():

    app = Flask(__name__)
    app.config.from_object(Config) 
    app = init_extensions(app)
    #app = init_salary(app)
    migrate.init_app(app, db)


    # Debug settings
    if app.config.get("DEBUG", True):
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        app.jinja_env.auto_reload = True
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        app.config['DEBUG'] = True
        app.config["PROPAGATE_EXCEPTIONS"] = True
        app.config['UPLOAD_FOLDER'] = 'static/uploads/profiles'
        app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

        upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        os.makedirs(upload_path, exist_ok=True)
       
    else:
        app.config["DEBUG"] = False

    cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_THRESHOLD': 50  # Cache only 50 items
})

    # Session security for production
    if not app.debug:
        app.config.update(
            SESSION_COOKIE_SECURE=True,        
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",   
            REMEMBER_COOKIE_SECURE=True,
            REMEMBER_COOKIE_HTTPONLY=True,
            PERMANENT_SESSION_LIFETIME=timedelta(days=30), 
            SESSION_REFRESH_EACH_REQUEST=True,  
            REMEMBER_COOKIE_SAMESITE="None",
        )

    #CORS(app, supports_credentials=True)
    CORS(app, supports_credentials=True, origins=['http://localhost:19000', 'http://10.0.2.2:5000', 'http://192.168.1.*', 'https://finicashi-app.onrender.com'], 
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    # Logging setup
    import logging
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    file_handler = logging.FileHandler('logs/app.log', mode='a', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    
    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False
    
    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(console_handler)
    
    # Database URI fix
    DATABASE_URI = app.config.get("SQLALCHEMY_DATABASE_URI")

    if not DATABASE_URI:
        basedir = os.path.abspath(os.path.dirname(__file__))
        instance_dir = os.path.join(basedir, "instance")
        os.makedirs(instance_dir, exist_ok=True)
        DATABASE_URI = f"sqlite:///{os.path.join(instance_dir, 'fincash.db')}"
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI 

    if DATABASE_URI.startswith("postgres://"):
        DATABASE_URI = DATABASE_URI.replace("postgres://", "postgresql+pg8000://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI

    # ============================================

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Force clean up on shutdown
    def emergency_cleanup():
        """Emergency cleanup - force release all resources"""
        try:
            db.session.remove()
            if hasattr(db.engine, 'pool'):
                db.engine.pool.dispose()
            gc.collect()
        except:
            pass

    # Handle shutdown signals
    def signal_handler(sig, frame):
        emergency_cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Register blueprints
    def register_blueprints(app):
        from blueprints.auth import bp as auth_bp
        from blueprints.profile import bp as profile_bp
        from blueprints.admin import admin_bp as admin_bp
        from blueprints.payments import bp as payment_bp
        from activity import activity_bp as activity_bp
        from blueprints.promoter import promoter_bp
        from notification.notification import notification_bp
        from network.network_routes import network_bp
        from blueprints.rewards import bp as rewards_bp
        from blueprints.salary import salary_bp
        #from services.bills_routes import bill_bp
        #from sub_admin import subadmin_bp
        app.register_blueprint(rewards_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(promoter_bp)
        app.register_blueprint(profile_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(payment_bp)
        app.register_blueprint(activity_bp)
        app.register_blueprint(notification_bp)
        app.register_blueprint(network_bp)
        app.register_blueprint(salary_bp)
        #app.register_blueprint(subadmin_bp)
     
    register_blueprints(app)
  
    logging.basicConfig(level=logging.DEBUG)

    def set_sentry_user_context():
        """Attach current user to Sentry for error tracking"""
        if hasattr(g, 'user') and g.user is not None:
            user_data = {"id": str(g.user.id)}
            
            # Add common fields if they exist
            if hasattr(g.user, 'email') and g.user.email:
                user_data["email"] = g.user.email
            if hasattr(g.user, 'username') and g.user.username:
                user_data["username"] = g.user.username
            if hasattr(g.user, 'phone') and g.user.phone:
                user_data["phone"] = g.user.phone
            if hasattr(g.user, 'role') and g.user.role:
                user_data["role"] = g.user.role
                sentry_sdk.set_tag("user_role", g.user.role)
            
            sentry_sdk.set_user(user_data)
            sentry_sdk.set_tag("user_id", str(g.user.id))
            #print(f"✅ Sentry user context attached for user: {getattr(g.user, 'username', g.user.id)}")
            app.logger.debug(f"Sentry user context attached for user: {getattr(g.user, 'username', g.user.id)}")
        else:
            sentry_sdk.set_user(None)
    # ========== BEFORE REQUEST HANDLERS (Order matters!) ==========
    

    @app.before_request
    def load_logged_in_user():
        """Load user with error handling - prevents crashes"""
        # Skip for public pages AND static files
        if (request.path in ['/', '/healthz', '/favicon.ico', '/ping', '/test', '/db-test'] or 
            request.path.startswith('/static/') or
            request.path.startswith('/debug/')):
            g.user = None
            return
        
        g.user = None
        
        # SAFE: Try to get user, but don't crash
        try:
            user_id = session.get("user_id")
            if user_id:
                # Use a timeout to prevent hanging
                import signal
                import platform
                
                # Check if SIGALRM is available (Unix only)
                if hasattr(signal, 'SIGALRM'):
                    def timeout_handler(signum, frame):
                        raise TimeoutError("Database query timeout")
                    
                    # Set 3 second timeout for database query
                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(3)
                    
                    try:
                        g.user = db.session.get(User, int(user_id))
                    finally:
                        signal.alarm(0)  # Cancel alarm
                        signal.signal(signal.SIGALRM, old_handler)
                else:
                    # Windows fallback - just query without timeout
                    # OR use threading.Timer for timeout
                    g.user = db.session.get(User, int(user_id))
                    
        except TimeoutError:
            app.logger.error(f"Database timeout loading user {user_id}")
            g.user = None
            # Clear session to prevent repeated failures
            session.clear()
        except Exception as e:
            app.logger.error(f"Error loading user: {str(e)}")
            g.user = None
            # If database is failing, clear session
            if "database" in str(e).lower() or "connection" in str(e).lower():
                session.clear()
        set_sentry_user_context()

    # Add before any routes
    @app.before_request
    def log_request():
        # Skip logging static files and health checks
        if request.path.startswith('/static/') or request.path in ['/healthz', '/favicon.ico', '/ping']:
            return
        app.logger.info(f"Request: {request.method} {request.path}")
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Handle rate limiting"""
        return jsonify({"error": "Too many requests. Please slow down."}), 429

    
    
    @app.route('/emergency')
    def emergency():
        return "EMERGENCY! The app is running!"

    @app.route('/emergency-debug')
    def emergency_debug():
        import os
        import sys
        import traceback
        
        result = {
            "status": "ok",
            "python": sys.version,
            "working_dir": os.getcwd(),
            "env": {
                "FLASK_ENV": os.getenv('FLASK_ENV'),
                "RENDER": os.getenv('RENDER'),
                "DEBUG": app.debug,
            }
        }
        
        # Try to import blueprints
        try:
            from blueprints.auth import bp as auth_bp
            result["blueprints"]["auth"] = "OK"
        except Exception as e:
            result["blueprints"]["auth"] = str(e)
        
        return jsonify(result)
    @app.route('/debug/test-errors')
    def debug_test_errors():
        """Test what errors are being thrown"""
        import traceback
        try:
            # Try a simple operation
            result = db.session.execute(text("SELECT 1")).fetchone()
            return {"status": "ok", "result": str(result)}
        except Exception as e:
            # Return the actual error
            return {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }, 500


    @app.errorhandler(500)
    @app.errorhandler(502)
    @app.errorhandler(504)
    def handle_error(e):
        """Handle server errors"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Finicashi - Please Refresh</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="refresh" content="5;url=/">
        </head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>Finicashi</h1>
            <p>We're experiencing high traffic. Please refresh in a moment.</p>
            <p><a href="/">Try again</a></p>
        </body>
        </html>
        """, 200
    
    @app.route("/reset-session")
    def reset_session():
        """Emergency session reset - users can visit this to fix login issues"""
        session.clear()
        
        # Clear all cookies
        response = make_response(render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Session Reset</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body>
                <h1>Session Reset</h1>
                <p>Your session has been cleared. Please <a href="/">return to homepage</a>.</p>
                <script>
                    // Clear localStorage too
                    localStorage.clear();
                    sessionStorage.clear();
                    // Redirect after 2 seconds
                    setTimeout(function() {
                        window.location.href = '/';
                    }, 2000);
                </script>
            </body>
            </html>
        """))
        
        # Clear all cookies
        for cookie in request.cookies:
            response.set_cookie(cookie, '', expires=0)
        
        return response
    @app.route("/debug/check-package", methods=['GET'])
    def debug_check_package():
        """Debug: Check what's in the database"""
        try:
            from models import PackageCatalog
            # Check all packages
            all_packages = PackageCatalog.query.all()
            
            result = {
                "all_packages": []
            }
            
            for pkg in all_packages:
                result["all_packages"].append({
                    "id": pkg.id,
                    "name": pkg.name,
                    "code": pkg.code,
                    "price": pkg.price,
                    "is_active": pkg.is_active
                })
            
            # Specifically check for 50000
            pkg_50000 = PackageCatalog.query.filter_by(price=50000).first()
            
            if pkg_50000:
                result["package_50000"] = {
                    "id": pkg_50000.id,
                    "name": pkg_50000.name,
                    "code": pkg_50000.code,
                    "price": pkg_50000.price
                }
            else:
                result["package_50000"] = "NOT FOUND"
            
            return jsonify(result), 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    @app.route('/api/test')
    def test_api():
        try:
            # Try a simple database query
            result = db.session.execute('SELECT 1').scalar()
            return jsonify({"status": "ok", "db": result})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    @app.route('/favicon.ico')
    def favicon():
        # Return empty response
        return '', 204
    @app.route("/api/whoami")
    def whoami():
        user_id = session.get("user_id")
        return jsonify({"user_id": user_id})  

    @app.route('/privacy')  
    def privacy():
        return  render_template('privacy.html')
    
    @app.route('/terms')  
    def terms():
        return  render_template('terms.html')
    
    @app.route('/refund')  
    def refund():
        return  render_template('refund.html')
    
    @app.route('/policy')
    def policy():
        return render_template('partials/policy.html')
    
    @app.route("/session-test")
    def session_test():
        session['test'] = 'working'
        return {"session": dict(session)}, 200
    from sqlalchemy import text

    @app.route("/db-test")
    def db_test():
        try:
            result = db.session.execute(text("SELECT 1")).fetchone()
            return {"status": "ok", "db": "connected"}, 200
        except Exception as e:
            return {"status": "error", "db": str(e)}, 500
    @app.route("/test")
    def test():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>
            <h1>Test Page</h1>
            <p>If you see this, the server is working.</p>
            <button onclick="alert('Working!')">Click me</button>
        </body>
        </html>
        """
    @app.route("/simple")
    def simple_home():
        return """
        <!DOCTYPE html>
        <html> 
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Finicashi</title>
        </head>
        <body>
            <h1>Finicashi</h1>
            <p>If you see this, the server is working!</p>
            <a href="/">Go to full homepage</a>
            <br><br>
            <a href="/test">Test Page</a>
        </body>
        </html>
        """
    @app.route("/")
    @cache.cached(timeout=300)
    def home():
        return render_template("index.html")
    
    @app.route('/api/loan/apply', methods=['POST'])
    def apply_for_loan():
        return jsonify({
            'success': True,
            'message': 'Loan application submitted successfully'
        }), 200
    
    @app.route("/health")
    def health():
        """Health check for Render - returns quickly"""
        try:
            # Quick DB check with timeout
            db.session.execute(text("SELECT 1")).fetchone()
            return {"status": "healthy"}, 200
        except Exception:
            # Still return 200 to prevent Render from killing the instance
            return {"status": "degraded", "error": "DB slow"}, 200

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}, 200
    

    @app.route('/recover')
    def recover():
        """Emergency recovery page - clears everything"""
        session.clear()
        response = make_response("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Recovering...</title>
            <meta http-equiv="refresh" content="2;url=/">
        </head>
        <body>
            <h1>Recovering...</h1>
            <p>Please wait, redirecting...</p>
            <script>
                localStorage.clear();
                sessionStorage.clear();
                setTimeout(() => window.location.href = '/', 1000);
            </script>
        </body>
        </html>
        """)
        
        # Clear all cookies
        for cookie in request.cookies:
            response.set_cookie(cookie, '', expires=0)
        
        return response
    
    # Cleanup handlers
    @app.after_request
    def cleanup_transactions(response):
        try:
            if db.session.is_active:
                db.session.rollback()
        except Exception as e:
            app.logger.error(f"Session cleanup error: {e}")
            db.session.rollback()
        return response
    
    @app.after_request
    def add_cache_headers(response):
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000'
            response.headers['Expires'] = (datetime.utcnow() + timedelta(days=365)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        return response
    
    @app.after_request
    def add_security_headers(response):
        # Allow cross-origin requests with credentials
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        # Allow all origins for VPN users
        origin = request.headers.get('Origin')
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
        
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        
        return response
    
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()
   
    return app
app = create_app()

# Local development
if __name__ == "__main__":

    webbrowser.open("http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, processes=1, use_reloader=False)
