import asyncio
import sys
import os
from datetime import datetime, timedelta, date

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_async_session_context, create_db_and_tables, engine
import app.models
from app.models.users import User
from app.models.roles import Role, DEFAULT_ROLES
from app.models.branches import Branch
from app.models.customers import Customer
from app.models.projects import Project
from app.models.user_projects import UserProject
from app.models.task_types import TaskType
from app.models.timelogs import Timelog
from app.models.leave_credits import LeaveCredit
from app.models.document_types import DocumentType
from app.models.user_201_files import User201File
from app.models.notifications import Notification
from app.security import get_password_hash
from sqlalchemy import select, delete


async def seed():
    print("🚀 Initializing Database & Demo Data...")
    await create_db_and_tables()

    async with get_async_session_context() as session:
        # 1. Seed Roles
        print("-> Checking Roles...")
        role_map = {}
        for rname in DEFAULT_ROLES:
            res = await session.execute(select(Role).where(Role.role_name == rname))
            role_obj = res.scalars().first()
            if not role_obj:
                role_obj = Role(role_name=rname)
                session.add(role_obj)
                await session.flush()
            role_map[rname] = role_obj

        # 2. Seed Branches
        print("-> Checking Branches...")
        branch_data = [
            ("Head Office - Ortigas", "217 F. Ortigas Jr. Rd, Ortigas Center, Pasig City"),
            ("Cebu Tech Hub", "Cebu IT Park, Lahug, Cebu City"),
        ]
        branches = []
        for bname, baddr in branch_data:
            res = await session.execute(select(Branch).where(Branch.branch_name == bname))
            b_obj = res.scalars().first()
            if not b_obj:
                b_obj = Branch(branch_name=bname, branch_address=baddr, created_at=datetime.now())
                session.add(b_obj)
                await session.flush()
            branches.append(b_obj)

        # 3. Seed Customers
        print("-> Checking Customers...")
        cust_data = [
            ("Acme Global Solutions", "Enterprise Cloud & FinTech Provider", "Singapore"),
            ("Nexus FinTech Labs", "Digital Banking Solutions", "Philippines"),
        ]
        customers = []
        for cname, cdesc, cloc in cust_data:
            res = await session.execute(select(Customer).where(Customer.customer_name == cname))
            c_obj = res.scalars().first()
            if not c_obj:
                c_obj = Customer(customer_name=cname, description=cdesc, customer_location=cloc, status="Active")
                session.add(c_obj)
                await session.flush()
            customers.append(c_obj)

        # 4. Seed Projects
        print("-> Checking Projects...")
        proj_data = [
            ("Digital Banking Portal", "Omnichannel corporate and retail web banking portal", customers[0].id, branches[0].id, "Ongoing"),
            ("Payment Gateway API", "High-throughput payment orchestration engine", customers[1].id, branches[1].id, "Ongoing"),
            ("Cloud Infrastructure Migration", "Containerized microservices and automated CI/CD pipeline", customers[0].id, branches[0].id, "Completed"),
        ]
        projects = []
        for pname, pdesc, cid, bid, pstat in proj_data:
            res = await session.execute(select(Project).where(Project.project_name == pname))
            p_obj = res.scalars().first()
            if not p_obj:
                p_obj = Project(
                    project_name=pname,
                    description=pdesc,
                    customer_id=cid,
                    branch_id=bid,
                    start_date=date.today() - timedelta(days=90),
                    end_date=date.today() + timedelta(days=270),
                    status=pstat,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(p_obj)
                await session.flush()
            projects.append(p_obj)

        # 5. Seed Users (Admin, Manager, Employee)
        print("-> Checking Demo Users...")
        today = date.today()
        start_date = today - timedelta(days=180)
        end_date = today + timedelta(days=365)
        now = datetime.now().replace(microsecond=0)

        demo_users = [
            {
                "username": "admin",
                "password": "DemoAdmin123!",
                "role": "admin",
                "role_id": role_map["admin"].id,
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@sialdang.com",
                "phone_number": "09171234567",
                "civil_status": "Single",
                "birthdate": date(1992, 5, 15),
                "permanent_address_line": "128 San Antonio St.",
                "current_address_line": "128 San Antonio St.",
                "permanent_address_psgc": "137404000",
                "current_address_psgc": "137404000",
                "salutation": "Mr.",
                "department": "IT",
                "job_level": "Career Level IV",
                "emergency_contact_name": "Maria User",
                "emergency_contact_number": "09181234567",
                "branch_id": branches[0].id,
            },
            {
                "username": "manager",
                "password": "DemoManager123!",
                "role": "manager",
                "role_id": role_map["manager"].id,
                "first_name": "Sarah",
                "last_name": "Jenkins",
                "email": "sjenkins@sialdang.com",
                "phone_number": "09172345678",
                "civil_status": "Married",
                "birthdate": date(1989, 8, 22),
                "permanent_address_line": "45 Emerald Avenue",
                "current_address_line": "45 Emerald Avenue",
                "permanent_address_psgc": "137404000",
                "current_address_psgc": "137404000",
                "salutation": "Ms.",
                "department": "Delivery",
                "job_level": "Career Level III",
                "emergency_contact_name": "David Jenkins",
                "emergency_contact_number": "09182345678",
                "branch_id": branches[0].id,
            },
            {
                "username": "employee",
                "password": "DemoUser123!",
                "role": "user",
                "role_id": role_map["user"].id,
                "first_name": "Alex",
                "last_name": "Rivera",
                "email": "arivera@sialdang.com",
                "phone_number": "09173456789",
                "civil_status": "Single",
                "birthdate": date(1996, 11, 8),
                "permanent_address_line": "88 Pioneer Blvd",
                "current_address_line": "88 Pioneer Blvd",
                "permanent_address_psgc": "137404000",
                "current_address_psgc": "137404000",
                "salutation": "Mr.",
                "department": "Delivery",
                "job_level": "Career Level II",
                "emergency_contact_name": "Elena Rivera",
                "emergency_contact_number": "09183456789",
                "branch_id": branches[0].id,
            }
        ]

        users_dict = {}
        for udata in demo_users:
            uname = udata["username"]
            res = await session.execute(select(User).where(User.username == uname))
            u_obj = res.scalars().first()
            if not u_obj:
                u_obj = User(
                    username=uname,
                    password=get_password_hash(udata["password"]),
                    role=udata["role"],
                    role_id=udata["role_id"],
                    first_name=udata["first_name"],
                    last_name=udata["last_name"],
                    email=udata["email"],
                    phone_number=udata["phone_number"],
                    civil_status=udata["civil_status"],
                    birthdate=udata["birthdate"],
                    permanent_address_line=udata["permanent_address_line"],
                    current_address_line=udata["current_address_line"],
                    permanent_address_psgc=udata["permanent_address_psgc"],
                    current_address_psgc=udata["current_address_psgc"],
                    salutation=udata["salutation"],
                    department=udata["department"],
                    job_level=udata["job_level"],
                    emergency_contact_name=udata["emergency_contact_name"],
                    emergency_contact_number=udata["emergency_contact_number"],
                    emp_start_date=start_date,
                    emp_end_date=end_date,
                    branch_id=udata["branch_id"],
                    blocked=False,
                    date_created=now,
                    date_updated=now,
                )
                session.add(u_obj)
                await session.flush()
            else:
                u_obj.password = get_password_hash(udata["password"])
                u_obj.role = udata["role"]
                u_obj.role_id = udata["role_id"]
                u_obj.emp_start_date = start_date
                u_obj.emp_end_date = end_date
                u_obj.blocked = False
                session.add(u_obj)
                await session.flush()
            users_dict[uname] = u_obj

        # 6. Seed Project Assignments (UserProjects)
        print("-> Assigning Projects to Users...")
        manager_user = users_dict["manager"]
        employee_user = users_dict["employee"]

        assignments = [
            (manager_user.id, projects[0].id, 1, "Project Manager"),
            (manager_user.id, projects[1].id, 1, "Project Manager"),
            (employee_user.id, projects[0].id, 1, "Frontend / Fullstack Developer"),
            (employee_user.id, projects[1].id, 1, "API Developer"),
        ]
        for uid, pid, fte, role_in_proj in assignments:
            res = await session.execute(select(UserProject).where(UserProject.user_id == uid, UserProject.project_id == pid))
            up_obj = res.scalars().first()
            if not up_obj:
                up_obj = UserProject(user_id=uid, project_id=pid, fte=fte, role_in_project=role_in_proj, assigned_at=datetime.now())
                session.add(up_obj)

        # 7. Seed Leave Credits
        print("-> Setting Leave Credits...")
        cur_month = today.strftime("%Y-%m")
        credits_data = [
            (users_dict["admin"].id, 10.0, 15.0),
            (users_dict["manager"].id, 7.0, 12.0),
            (users_dict["employee"].id, 5.0, 8.0),
        ]
        for uid, sick, vac in credits_data:
            res = await session.execute(select(LeaveCredit).where(LeaveCredit.user_id == uid))
            lc = res.scalars().first()
            if not lc:
                lc = LeaveCredit(user_id=uid, sick_leave_balance=sick, vacation_leave_balance=vac, last_allocation_month=cur_month)
                session.add(lc)
            else:
                lc.sick_leave_balance = sick
                lc.vacation_leave_balance = vac
                lc.last_allocation_month = cur_month
                session.add(lc)

        # 8. Seed Task Types
        tt_res = await session.execute(select(TaskType))
        all_tt = {t.name.lower(): t for t in tt_res.scalars().all()}
        training_tt = all_tt.get("training")
        vacation_tt = all_tt.get("vacation leave")

        # 9. Seed Calendar Timelogs for Alex Rivera
        print("-> Seeding Calendar Timelogs...")
        await session.execute(delete(Timelog).where(Timelog.user_id.in_([employee_user.id, manager_user.id])))

        days_since_sunday = (today.weekday() + 1) % 7
        sun_date = today - timedelta(days=days_since_sunday)

        mon_date = sun_date + timedelta(days=1)
        t1 = Timelog(
            user_id=employee_user.id,
            project_id=projects[0].id,
            type="project",
            start_time=datetime(mon_date.year, mon_date.month, mon_date.day, 9, 0),
            end_time=datetime(mon_date.year, mon_date.month, mon_date.day, 13, 0),
            duration_minutes=240,
            description="Sprint 14 User Stories & Core Component Architecture",
            status="Approved",
            approver_id=manager_user.id,
            approved_at=now
        )
        t2 = Timelog(
            user_id=employee_user.id,
            project_id=projects[0].id,
            type="project",
            start_time=datetime(mon_date.year, mon_date.month, mon_date.day, 14, 0),
            end_time=datetime(mon_date.year, mon_date.month, mon_date.day, 18, 0),
            duration_minutes=240,
            description="Interactive dashboard widgets & real-time analytics integration",
            status="Approved",
            approver_id=manager_user.id,
            approved_at=now
        )
        tue_date = sun_date + timedelta(days=2)
        t3 = Timelog(
            user_id=employee_user.id,
            project_id=projects[0].id,
            type="project",
            start_time=datetime(tue_date.year, tue_date.month, tue_date.day, 9, 0),
            end_time=datetime(tue_date.year, tue_date.month, tue_date.day, 13, 0),
            duration_minutes=240,
            description="Database query indexing & caching optimizations",
            status="Approved",
            approver_id=manager_user.id,
            approved_at=now
        )
        t4 = Timelog(
            user_id=employee_user.id,
            project_id=projects[0].id,
            type="project",
            start_time=datetime(tue_date.year, tue_date.month, tue_date.day, 14, 0),
            end_time=datetime(tue_date.year, tue_date.month, tue_date.day, 18, 0),
            duration_minutes=240,
            description="API integration tests and security compliance review",
            status="Approved",
            approver_id=manager_user.id,
            approved_at=now
        )
        wed_date = sun_date + timedelta(days=3)
        t5 = Timelog(
            user_id=employee_user.id,
            project_id=projects[1].id,
            type="project",
            start_time=datetime(wed_date.year, wed_date.month, wed_date.day, 9, 0),
            end_time=datetime(wed_date.year, wed_date.month, wed_date.day, 13, 0),
            duration_minutes=240,
            description="Webhook handler implementation & signature verification",
            status="Pending"
        )
        t6 = Timelog(
            user_id=employee_user.id,
            task_type_id=training_tt.id if training_tt else None,
            type="other",
            start_time=datetime(wed_date.year, wed_date.month, wed_date.day, 14, 0),
            end_time=datetime(wed_date.year, wed_date.month, wed_date.day, 18, 0),
            duration_minutes=240,
            description="Advanced TypeScript & Microservices Architecture Workshop",
            status="Pending"
        )
        thu_date = sun_date + timedelta(days=4)
        t7 = Timelog(
            user_id=employee_user.id,
            project_id=projects[0].id,
            type="project",
            start_time=datetime(thu_date.year, thu_date.month, thu_date.day, 9, 0),
            end_time=datetime(thu_date.year, thu_date.month, thu_date.day, 13, 0),
            duration_minutes=240,
            description="Refactoring frontend state management using Svelte 5 runes",
            status="Pending"
        )
        t8 = Timelog(
            user_id=employee_user.id,
            project_id=projects[1].id,
            type="project",
            start_time=datetime(thu_date.year, thu_date.month, thu_date.day, 14, 0),
            end_time=datetime(thu_date.year, thu_date.month, thu_date.day, 18, 0),
            duration_minutes=240,
            description="Payment settlement scheduler & automated reconciliation tests",
            status="Pending"
        )
        fri_date = sun_date + timedelta(days=5)
        t9 = Timelog(
            user_id=employee_user.id,
            task_type_id=vacation_tt.id if vacation_tt else None,
            type="leave",
            start_time=datetime(fri_date.year, fri_date.month, fri_date.day, 9, 0),
            end_time=datetime(fri_date.year, fri_date.month, fri_date.day, 17, 0),
            duration_minutes=480,
            description="Annual Family Vacation",
            status="Pending"
        )

        session.add_all([t1, t2, t3, t4, t5, t6, t7, t8, t9])

        # 10. Seed Manager Timelogs
        tm1 = Timelog(
            user_id=manager_user.id,
            project_id=projects[0].id,
            type="project",
            start_time=datetime(mon_date.year, mon_date.month, mon_date.day, 9, 0),
            end_time=datetime(mon_date.year, mon_date.month, mon_date.day, 13, 0),
            duration_minutes=240,
            description="Client Stakeholder Sprint Alignment & Roadmap Review",
            status="Approved",
            approver_id=users_dict["admin"].id,
            approved_at=now
        )
        session.add(tm1)

        # 11. Seed 201 Files
        print("-> Seeding 201 Personnel Files...")
        dt_res = await session.execute(select(DocumentType))
        doc_types = {d.code: d for d in dt_res.scalars().all()}

        alex_dir = os.path.join(os.path.dirname(__file__), "static", "uploads", "201-files", "Alex_Rivera", "pre-employment")
        os.makedirs(alex_dir, exist_ok=True)
        sample_file_path = os.path.join(alex_dir, "sample-clearance.pdf")
        if not os.path.exists(sample_file_path):
            with open(sample_file_path, "wb") as f:
                f.write(b"%PDF-1.4 Demo Personnel Document for Portfolio Preview")

        await session.execute(delete(User201File).where(User201File.user_id == employee_user.id))

        f_entries = [
            ("NBI", "NBI Clearance - Alex Rivera.pdf", "/static/uploads/201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "Approved", users_dict["admin"].id, now),
            ("PSA", "PSA Birth Certificate - Alex Rivera.pdf", "/static/uploads/201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "Approved", users_dict["admin"].id, now),
            ("GOTYME_CERT", "GoTyme Bank Certificate - Alex Rivera.pdf", "/static/uploads/201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "Approved", users_dict["admin"].id, now),
            ("TIN", "TIN Document - Alex Rivera.pdf", "/static/uploads/201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "Pending", None, None),
            ("SSS", "SSS Document - Alex Rivera.pdf", "/static/uploads/201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "201-files/Alex_Rivera/pre-employment/sample-clearance.pdf", "Pending", None, None),
        ]

        for code, fname, furl, spath, stat, app_id, app_at in f_entries:
            dtype = doc_types.get(code)
            if dtype:
                u201 = User201File(
                    user_id=employee_user.id,
                    document_type_id=dtype.id,
                    file_name=fname,
                    file_url=furl,
                    s3_path=spath,
                    status=stat,
                    approver_id=app_id,
                    approved_at=app_at,
                    is_active=True,
                    version=1,
                    created_at=now,
                    updated_at=now
                )
                session.add(u201)

        # 12. Seed Notifications
        print("-> Seeding Notifications...")
        notif1 = Notification(
            recipient_id=employee_user.id,
            approver_id=manager_user.id,
            action="approved",
            item_type="timelog",
            item_id=1,
            item_title="Timelog Approved",
            item_description="Sprint 14 User Stories & Core Component Architecture",
            target_route="/tasks",
            is_read=0,
            created_at=now
        )
        session.add(notif1)

        await session.commit()

    print("\n✅ DEMO DATA SEEDED SUCCESSFULLY!")
    print("=======================================================")
    print("DEMO CREDENTIALS FOR PORTFOLIO PREVIEW:")
    print("1) Admin Account:")
    print("   Username: admin")
    print("   Password: DemoAdmin123!")
    print("2) Project Manager Account:")
    print("   Username: manager")
    print("   Password: DemoManager123!")
    print("3) Staff Employee Account:")
    print("   Username: employee")
    print("   Password: DemoUser123!")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(seed())
