import asyncio
import sys
import os
import getpass
from datetime import datetime, timedelta, date

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_async_session_context, Base, engine, create_db_and_tables
import app.models  # Ensure all models are registered
from app.crud.users import user_crud
from app.models.users import User
from app.models.roles import Role, DEFAULT_ROLES
from app.security import get_password_hash
from sqlalchemy import select, func

MIN_PASSWORD_LENGTH = 8


def prompt_password() -> str:
    """Prompt for the admin password (hidden input) with confirmation."""
    while True:
        password = getpass.getpass("Enter admin password: ")

        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"❌ Password must be at least {MIN_PASSWORD_LENGTH} characters. Try again.")
            continue

        confirm = getpass.getpass("Confirm admin password: ")

        if password != confirm:
            print("❌ Passwords do not match. Try again.")
            continue

        return password


async def init_db():
    """Initialize the database."""
    try:
        await create_db_and_tables()
    except Exception as e:
        print(f"Database initialization error: {e}")


async def create_admin_user(admin_password: str):
    """Create the default admin user."""
    print("Initializing database...")
    await init_db()

    try:
        async with get_async_session_context() as session:
            # Seed roles first
            print("Seeding roles...")
            try:
                r_count_result = await session.execute(select(func.count(Role.id)))
                r_count = r_count_result.scalar_one()

                if r_count == 0:
                    for name in DEFAULT_ROLES:
                        session.add(Role(role_name=name))

                    await session.commit()
                    print(f"✅ Roles seeded: {', '.join(DEFAULT_ROLES)}")
                else:
                    print("✅ Roles already exist")

            except Exception as e:
                print(f"❌ Error seeding roles: {e}")
                raise

            print("Creating admin user...")

            start_date = date.today()
            end_date = start_date + timedelta(days=365)
            now = datetime.now().replace(microsecond=0)

            admin_data = {
                "username": "admin",
                "password": admin_password,
                "role": "admin",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@example.com",
                "phone_number": "09123456789",
                "civil_status": "Single",
                "birthdate": date(2000, 1, 1),
                "permanent_address_line": "217 NIA Road",
                "current_address_line": "217 NIA Road",
                "permanent_address_psgc": "1705205037",
                "current_address_psgc": "1705205037",
                "salutation": "Mr.",
                "department": "IT",
                "job_level": "Career Level IV",
                "emergency_contact_name": "Emergency Admin",
                "emergency_contact_number": "09123456789",
                "emp_start_date": start_date,
                "emp_end_date": end_date,
            }

            role_value = admin_data["role"].strip().lower()

            role_result = await session.execute(
                select(Role).where(func.lower(Role.role_name) == role_value)
            )
            role_obj = role_result.scalars().first()

            if not role_obj:
                print(f"❌ Role '{admin_data['role']}' not found!")
                return

            # Check if admin exists
            existing_user_result = await session.execute(
                select(User).where(User.username == admin_data["username"])
            )
            existing_user = existing_user_result.scalars().first()

            if existing_user:
                existing_user.password = get_password_hash(admin_data["password"])
                existing_user.role = admin_data["role"]
                existing_user.role_id = role_obj.id
                existing_user.first_name = admin_data["first_name"]
                existing_user.last_name = admin_data["last_name"]
                existing_user.email = admin_data["email"]

                existing_user.phone_number = admin_data["phone_number"]
                existing_user.civil_status = admin_data["civil_status"]
                existing_user.birthdate = admin_data["birthdate"]
                existing_user.permanent_address_line = admin_data["permanent_address_line"]
                existing_user.current_address_line = admin_data["current_address_line"]
                existing_user.permanent_address_psgc = admin_data["permanent_address_psgc"]
                existing_user.current_address_psgc = admin_data["current_address_psgc"]

                existing_user.salutation = admin_data["salutation"]
                existing_user.department = admin_data["department"]
                existing_user.job_level = admin_data["job_level"]
                existing_user.emergency_contact_name = admin_data["emergency_contact_name"]
                existing_user.emergency_contact_number = admin_data["emergency_contact_number"]
                existing_user.emp_start_date = admin_data["emp_start_date"]
                existing_user.emp_end_date = admin_data["emp_end_date"]

                existing_user.gotyme_account_name = None
                existing_user.gotyme_account_number = None
                existing_user.tin_number = None
                existing_user.sss_number = None
                existing_user.philhealth_number = None
                existing_user.pagibig_number = None
                existing_user.blocked = False
                existing_user.date_updated = now

                session.add(existing_user)
                await session.commit()
                print("✅ Updated user: admin")
                return

            new_user = User(
                username=admin_data["username"],
                password=get_password_hash(admin_data["password"]),
                role=admin_data["role"],
                role_id=role_obj.id,
                first_name=admin_data["first_name"],
                last_name=admin_data["last_name"],
                email=admin_data["email"],

                phone_number=admin_data["phone_number"],
                civil_status=admin_data["civil_status"],
                birthdate=admin_data["birthdate"],
                permanent_address_line=admin_data["permanent_address_line"],
                current_address_line=admin_data["current_address_line"],
                permanent_address_psgc=admin_data["permanent_address_psgc"],
                current_address_psgc=admin_data["current_address_psgc"],

                salutation=admin_data["salutation"],
                department=admin_data["department"],
                job_level=admin_data["job_level"],
                emergency_contact_name=admin_data["emergency_contact_name"],
                emergency_contact_number=admin_data["emergency_contact_number"],
                emp_start_date=admin_data["emp_start_date"],
                emp_end_date=admin_data["emp_end_date"],

                gotyme_account_name=None,
                gotyme_account_number=None,
                tin_number=None,
                sss_number=None,
                philhealth_number=None,
                pagibig_number=None,
                blocked=False,
                date_created=now,
                date_updated=now,
            )

            session.add(new_user)
            await session.commit()
            print("✅ Created user: admin")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        password = prompt_password()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)

    asyncio.run(create_admin_user(password))