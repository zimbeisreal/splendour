from app import app, db
from extensions import db
from models import User
from werkzeug.security import generate_password_hash, check_password_hash


def update_user_password(user_id: int, new_password: str = None):
    """
    Standalone function to print user info and update password.
    
    Args:
        user_id: The ID of the user to update
        new_password: Optional new password. If None, prompts via input()
    """
    with app.app_context():
        # Fetch the user by ID
        user = db.session.get(User, user_id)
        
        if not user:
            print(f"No user found with ID: {user_id}")
            return False
        
        # Print user info
        print(f"User Name:  {user.username}")
        print(f"User Phone: {user.phone}")
        
        # Get new password (from arg or prompt)
        if new_password is None:
            new_password = input("Enter new password: ")
        
        if not new_password:
            print("Password cannot be empty. Aborting.")
            return False
        
        # Hash and save
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        print(f"Password updated successfully for user ID {user_id}.")
        return True


if __name__ == "__main__":
    # Example usage
    update_user_password(user_id=111)

