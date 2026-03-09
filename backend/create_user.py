"""
Utility to create or update users in users.json.

Usage examples:
  # Admin — access to all collections
  python create_user.py admin secret123 admin

  # Regular user — access to all collections
  python create_user.py mathew pass123 user

  # Restricted user — HR Team only
  python create_user.py priya pass456 user --collections "HR Team"

  # Restricted user — multiple collections
  python create_user.py ravi pass789 user --collections "HR Team,Sales Team"
"""

import json
import sys
import argparse
import bcrypt
from pathlib import Path

USERS_FILE = Path("./users.json")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def load_users() -> list:
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_users(users: list) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Create or update a user in users.json")
    parser.add_argument("username", help="Username")
    parser.add_argument("password", help="Plain-text password (will be hashed)")
    parser.add_argument("role", choices=["admin", "user"], help="Role")
    parser.add_argument(
        "--collections",
        default=None,
        help=(
            "Comma-separated list of collections this user can access. "
            "Leave blank to allow all collections. "
            'Example: --collections "HR Team,Sales Team"'
        ),
    )
    args = parser.parse_args()

    # Parse allowed_collections
    if args.collections:
        allowed = [c.strip() for c in args.collections.split(",") if c.strip()]
    else:
        allowed = None  # None = unrestricted

    users = load_users()
    hashed = hash_password(args.password)

    # Update existing user or append new one
    existing = next((u for u in users if u["username"].lower() == args.username.lower()), None)
    if existing:
        existing["password_hash"]      = hashed
        existing["role"]               = args.role
        existing["allowed_collections"] = allowed
        print(f"Updated user: {args.username}")
    else:
        users.append({
            "username":           args.username,
            "password_hash":      hashed,
            "role":               args.role,
            "allowed_collections": allowed,
        })
        print(f"Created user: {args.username}")

    save_users(users)

    # Print summary
    if allowed is None:
        print(f"  Role: {args.role} | Collections: ALL")
    else:
        print(f"  Role: {args.role} | Collections: {', '.join(allowed)}")


if __name__ == "__main__":
    main()
