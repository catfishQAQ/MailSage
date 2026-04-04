import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import Account
from schemas import AccountCreate, AccountUpdate, AccountOut
from crypto import encrypt

router = APIRouter()


@router.get("/", response_model=list[AccountOut])
async def list_accounts(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Account))
    return result.scalars().all()


@router.post("/", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(data: AccountCreate, session: AsyncSession = Depends(get_session)):
    # 检查邮箱是否已添加
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

    await session.commit()
    await session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: str, session: AsyncSession = Depends(get_session)):
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await session.delete(account)
    await session.commit()


@router.post("/{account_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(account_id: str, session: AsyncSession = Depends(get_session)):
    """手动触发指定账号的 IMAP 增量同步"""
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    from services.imap_service import sync_account
    import asyncio
    asyncio.create_task(sync_account(account_id))
    return {"message": f"已触发 {account.email} 同步任务"}
