# # hash_admin_passwords.py
# from werkzeug.security import generate_password_hash
# from extensions import db
# from models.admin import Admin
# from app import create_app  # replace 'your_app' with your actual app package/folder

# def hash_admin_passwords():
#     app = create_app()  # initialize your Flask app
#     with app.app_context():  # provide application context
#         admins = Admin.query.all()
#         for admin in admins:
#             # Only hash if it looks like plain text
#             if not admin.password.startswith("pbkdf2:sha256"):
#                 print(f"Hashing password for admin: {admin.username}")
#                 admin.password = generate_password_hash(admin.password)
#         db.session.commit()
#         print("All admin passwords hashed successfully!")

# if __name__ == "__main__":
#     hash_admin_passwords()


from werkzeug.security import generate_password_hash

def create_hash(plain_password):
    # Default method is pbkdf2:sha256 with recommended iterations
    return generate_password_hash(plain_password)

if __name__ == "__main__":
    password = input("Enter the plain password to hash: ")
    hashed = create_hash(password)
    print(f"Hashed password:\n{hashed}")