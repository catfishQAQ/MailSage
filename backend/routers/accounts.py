import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from crypto import encrypt
from database import get_session
from models import Account, Email
from schemas import AccountCreate, AccountOut, AccountUpdate
from services.imap_service import sync_account

router = APIRouter()


@router.get("/", response_model=list[AccountOut])
async def list_accounts(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Account))
    return result.scalars().all()


@router.post("/", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(data: AccountCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(Account).where(Account.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该邮箱已添加")

    account = Account(
        id=str(uuid.uuid4()),
        email=data.email,
        display_name=data.display_name or data.email,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        imap_use_ssl=data.imap_use_ssl,
        smtp_host=data.smtp_host,
        smtp_port=data.smtp_port,
        smtp_use_ssl=data.smtp_use_ssl,
        encrypted_password=encrypt(data.password),
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: str, session: AsyncSession = Depends(get_session)):
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    return account


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: str,
    data: AccountUpdate,
    session: AsyncSession = Depends(get_session),
):
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    if data.display_name is not None:
        account.display_name = data.display_name
    if data.password is not None:
        account.encrypted_password = encrypt(data.password)
    if data.is_active is not None:
        account.is_active = data.is_active
    if data.prompt_context is not None:
        account.prompt_context = data.prompt_context or None

    await session.commit()
    await session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: str, session: AsyncSession = Depends(get_session)):
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    # Explicitly delete child emails so current SQLite deployments behave the same
    # even before foreign-key cascade settings are fully enforced.
    await session.execute(delete(Email).where(Email.account_id == account_id))
    await session.delete(account)
    await session.commit()


@router.post("/{account_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(account_id: str, session: AsyncSession = Depends(get_session)):
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    asyncio.create_task(sync_account(account_id))
    return {"message": f"已触发 {account.email} 同步任务"}
