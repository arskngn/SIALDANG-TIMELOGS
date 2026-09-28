from datetime import datetime
from fastapi import APIRouter, Depends, status, HTTPException, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import os
import shutil
from pathlib import Path
from app.database import get_async_session
from app.api.dependencies import get_current_user, get_current_admin
from app.models.users import User
from app.models.user_201_files import User201File
from app.models.document_types import DocumentType
from app.schemas.user_201_files import CreateUser201File, UpdateUser201File, User201FileResponse
from app.crud.user_201_files import user201_crud
import re
import mimetypes


router = APIRouter(
    prefix="/user-201",
    tags=["User201Files"],
    responses={404: {"description": "User 201 File not found"}},
)


@router.get("/", response_model=List[User201FileResponse], summary="List all User 201 files")
async def list_all(session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_admin)):
    items = await user201_crud.get_many(session)
    res = [User201FileResponse.model_validate(x, from_attributes=True) for x in items]
    for r, x in zip(res, items):
        r.uploaded_at = x.created_at
        r.file_url = get_presigned_url(x.s3_path, x.file_url)
    return res


@router.get("/me", response_model=List[User201FileResponse], summary="List my User 201 files")
async def list_my(
    active_only: bool = False,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    conds = [User201File.user_id == current_user.id]
    if active_only:
        conds.append(User201File.is_active.is_(True))
    items = await user201_crud.get_many(session, *conds)
    res = [User201FileResponse.model_validate(x, from_attributes=True) for x in items]
    for r, x in zip(res, items):
        r.uploaded_at = x.created_at
        r.file_url = get_presigned_url(x.s3_path, x.file_url)
    return res


@router.get("/{item_id}", response_model=User201FileResponse, summary="Get a User 201 file")
async def get_one(item_id: int, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_admin)):
    item = await user201_crud.get_one(session, User201File.id == item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    res = User201FileResponse.model_validate(item, from_attributes=True)
    res.uploaded_at = item.created_at
    res.file_url = get_presigned_url(item.s3_path, item.file_url)
    return res


@router.get("/by-user/{user_id}", response_model=List[User201FileResponse], summary="List User 201 files for user")
async def list_by_user(
    user_id: int,
    active_only: bool = False,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_admin)
):
    conds = [User201File.user_id == user_id]
    if active_only:
        conds.append(User201File.is_active.is_(True))
    items = await user201_crud.get_many(session, *conds)
    res = [User201FileResponse.model_validate(x, from_attributes=True) for x in items]
    for r, x in zip(res, items):
        r.uploaded_at = x.created_at
        r.file_url = get_presigned_url(x.s3_path, x.file_url)
    return res


@router.post("/upload-temp", summary="Upload file to temporary local storage")
async def upload_temp(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Allowed file types
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'img'}
    ALLOWED_MIMETYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/img'}
    
    # Get file extension
    filename_lower = (file.filename or '').lower()
    ext = filename_lower.split('.')[-1] if '.' in filename_lower else ''
    
    # Check file type by extension and MIME type
    mime_type = (file.content_type or '').lower()
    if ext not in ALLOWED_EXTENSIONS or (mime_type and mime_type not in ALLOWED_MIMETYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF, PNG, JPG, JPEG, or IMG files are allowed. Got: {ext or 'unknown'}"
        )
    
    backend_root = Path(__file__).resolve().parents[2]
    temp_dir = backend_root / "static" / "uploads" / "temp" / str(current_user.id)
    temp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_filename = re.sub(r'[^a-zA-Z0-9\-_.]', '', file.filename.replace(' ', '_'))
    file_path = temp_dir / f"{ts}-{safe_filename}"
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    rel_path = f"/static/uploads/temp/{current_user.id}/{ts}-{safe_filename}"
    return {"file_url": rel_path, "temp_path": str(file_path), "file_name": file.filename}


@router.post("/", response_model=User201FileResponse, summary="Create User 201 file (self)")
async def create(payload: CreateUser201File, session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    now = datetime.now()
    payload.created_at = now
    payload.updated_at = now
    # Force ownership to current user
    payload.user_id = current_user.id
    payload.status = payload.status or "Pending"
    payload.is_active = True
    try:
        res = await session.execute(
            select(func.max(User201File.version)).where(
                User201File.user_id == current_user.id,
                User201File.document_type_id == payload.document_type_id
            )
        )
        max_ver = res.scalar_one_or_none()
        payload.version = (int(max_ver or 0) + 1)
        prev_res = await session.execute(
            select(User201File).where(
                User201File.user_id == current_user.id,
                User201File.document_type_id == payload.document_type_id,
                User201File.is_active.is_(True)
            )
        )
        prev_active = prev_res.scalars().all()
        for pa in prev_active:
            pa.is_active = False
            session.add(pa)
    except Exception:
        payload.version = payload.version or 1
    item = await user201_crud.create(session, payload)
    res = User201FileResponse.model_validate(item, from_attributes=True)
    res.uploaded_at = item.created_at
    return res


@router.patch("/{item_id}", response_model=User201FileResponse, summary="Update User 201 file (self)")
async def update(item_id: int, payload: UpdateUser201File, session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    item = await user201_crud.get_one(session, User201File.id == item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your 201 file")
    payload.updated_at = datetime.now()
    item = await user201_crud.update(session, item, payload)
    res = User201FileResponse.model_validate(item, from_attributes=True)
    res.uploaded_at = item.created_at
    return res


@router.delete("/{item_id}", status_code=status.HTTP_200_OK, summary="Delete User 201 file (self)")
async def delete(item_id: int, session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    item = await user201_crud.get_one(session, User201File.id == item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your 201 file")

    # Cleanup file
    backend_root = Path(__file__).resolve().parents[2]
    if item.file_url:
        local_path = backend_root / item.file_url.lstrip("/")
        try:
            if local_path.exists():
                local_path.unlink()
        except Exception:
            pass
    elif item.s3_path:
        local_path = backend_root / "static" / "uploads" / item.s3_path
        try:
            if local_path.exists():
                local_path.unlink()
        except Exception:
            pass

    await user201_crud.delete(session, item)
    return {"message": "Deleted"}


@router.put("/upload-local/{file_path:path}", summary="Upload file locally")
async def upload_local(file_path: str, request: Request):
    # Security check: prevent directory traversal
    if ".." in file_path:
        raise HTTPException(status_code=400, detail="Invalid path")
        
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(backend_root, "static", "uploads")
    full_path = os.path.join(upload_dir, file_path)
    
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    body = await request.body()
    with open(full_path, "wb") as f:
        f.write(body)
        
    return {"status": "uploaded"}


@router.post("/presign", summary="Get presigned URL for S3 upload")
async def presign_upload(
    file_name: str,
    content_type: str,
    category: str = "misc",
    current_user: User = Depends(get_current_user)
):
    # Allowed file types
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'img'}
    ALLOWED_MIMETYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/img'}
    
    # Get file extension
    filename_lower = (file_name or '').lower()
    ext = filename_lower.split('.')[-1] if '.' in filename_lower else ''
    
    # Check file type by extension and MIME type
    mime_type = (content_type or '').lower()
    if ext not in ALLOWED_EXTENSIONS or (mime_type and mime_type not in ALLOWED_MIMETYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF, PNG, JPG, JPEG, or IMG files are allowed. Got: {ext or 'unknown'}"
        )
    
    # Construct folder name from user's full name
    raw_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
    if not raw_name:
        raw_name = current_user.username or str(current_user.id)
    
    # Sanitize: replace spaces with underscores, keep only safe chars
    folder_user = re.sub(r'[^a-zA-Z0-9\-_]', '', raw_name.replace(' ', '_'))

    cat_map = {
        "pre": "pre-employment",
        "payroll": "payroll",
        "gov": "government",
    }
    subfolder = cat_map.get(category, "misc")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    key = f"201-files/{folder_user}/{subfolder}/{ts}-{file_name}"

    upload_url = f"/api/user-201/upload-local/{key}"
    file_url = f"/static/uploads/{key}"
    return {"upload_url": upload_url, "file_url": file_url, "key": key}



def get_presigned_url(s3_path: str, file_url: str) -> str:
    """
    Helper to return the file URL for local static storage.
    """
    if file_url:
        return file_url
    if s3_path:
        return f"/static/uploads/{s3_path}"
    return ""


@router.post("/presign-download", summary="Get URL for file download")
async def presign_download(
    s3_key: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not s3_key:
        raise HTTPException(status_code=400, detail="Missing s3_key")
    
    res = await session.execute(
        select(User201File).where(User201File.s3_path == s3_key).limit(1)
    )
    items = res.scalars().all()
    item = items[0] if items else None
    
    if not item:
        raise HTTPException(status_code=404, detail="File not found")

    is_owner = (item.user_id == current_user.id)
    is_admin = (current_user.role and current_user.role.lower() == "admin")
    
    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to access this file")

    download_url = item.file_url or f"/static/uploads/{s3_key}"
    return {"download_url": download_url}

@router.patch("/{item_id}/approve", response_model=User201FileResponse, summary="Approve 201 file")
async def approve_item(
    item_id: int,
    remarks: str = "",
    session: AsyncSession = Depends(get_async_session),
    admin: User = Depends(get_current_admin)
):
    item = await user201_crud.get_one(session, User201File.id == item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Move temp local file to permanent 201-files storage
    if not item.s3_path and item.file_url and "/temp/" in item.file_url:
        try:
            target_user = await session.get(User, item.user_id)
            doc_type = await session.get(DocumentType, item.document_type_id)
            
            raw_name = f"{target_user.first_name or ''} {target_user.last_name or ''}".strip()
            if not raw_name:
                raw_name = target_user.username or str(target_user.id)
            folder_user = re.sub(r'[^a-zA-Z0-9\-_]', '', raw_name.replace(' ', '_'))
            
            subfolder = "misc"
            if doc_type:
                cat_map = {
                    "pre-employment": "pre-employment",
                    "payroll": "payroll",
                    "government": "government"
                }
                subfolder = cat_map.get(doc_type.category, "misc")
            
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_filename = re.sub(r'[^a-zA-Z0-9\-_.]', '', item.file_name.replace(' ', '_'))
            key = f"201-files/{folder_user}/{subfolder}/{ts}-{safe_filename}"
            
            backend_root = Path(__file__).resolve().parents[2]
            local_path = backend_root / item.file_url.lstrip("/")
            perm_path = backend_root / "static" / "uploads" / key
            perm_path.parent.mkdir(parents=True, exist_ok=True)
            if local_path.exists():
                shutil.move(str(local_path), str(perm_path))
                item.s3_path = key
                item.file_url = f"/static/uploads/{key}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to move file to permanent storage: {str(e)}")

    item.status = "Approved"
    item.approver_id = admin.id
    item.approved_at = datetime.now()
    item.reviewed_by = admin.id
    item.reviewed_at = item.approved_at
    item.remarks = remarks
    try:
        target_user = await session.get(User, item.user_id)
        doc_type = await session.get(DocumentType, item.document_type_id)
        owner_name = f"{(target_user.first_name or '').strip()} {(target_user.last_name or '').strip()}".strip() or (target_user.username or str(target_user.id))
        doc_name = (doc_type.name if doc_type and getattr(doc_type, "name", None) else "").strip() or item.file_name
        base = f"{doc_name} - {owner_name}".strip()
        ext = ""
        if "." in item.file_name:
            dot_idx = item.file_name.rfind(".")
            if dot_idx != -1:
                ext = item.file_name[dot_idx:]
        item.file_name = f"{base}{ext}"
    except Exception:
        pass
    session.add(item)
    await session.commit()
    await session.refresh(item)
    res = User201FileResponse.model_validate(item, from_attributes=True)
    res.uploaded_at = item.created_at
    res.file_url = get_presigned_url(item.s3_path, item.file_url)
    return res


@router.patch("/{item_id}/decline", response_model=User201FileResponse, summary="Decline 201 file")
async def decline_item(
    item_id: int,
    remarks: str = "",
    session: AsyncSession = Depends(get_async_session),
    admin: User = Depends(get_current_admin)
):
    item = await user201_crud.get_one(session, User201File.id == item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    item.status = "Declined"
    item.approver_id = admin.id
    item.approved_at = datetime.now()
    item.reviewed_by = admin.id
    item.reviewed_at = item.approved_at
    item.remarks = remarks
    session.add(item)
    await session.commit()
    await session.refresh(item)
    res = User201FileResponse.model_validate(item, from_attributes=True)
    res.uploaded_at = item.created_at
    res.file_url = get_presigned_url(item.s3_path, item.file_url)
    return res


@router.get("/history", response_model=List[User201FileResponse], summary="Get my file history by document type")
async def get_history(
    document_type: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not document_type:
        raise HTTPException(status_code=400, detail="Missing document_type")
    items = await user201_crud.get_many(
        session,
        User201File.user_id == current_user.id,
        User201File.document_type == document_type,
    )
    res = [User201FileResponse.model_validate(x, from_attributes=True) for x in items]
    for r, x in zip(res, items):
        r.uploaded_at = x.created_at
        r.file_url = get_presigned_url(x.s3_path, x.file_url)
    return res
