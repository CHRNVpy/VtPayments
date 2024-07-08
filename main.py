import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
import aiomysql
import datetime
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv('billing_db_user')
PASS = os.getenv('billing_db_pass')
DB_NAME = os.getenv('billing_db_name')
DB_HOST = os.getenv('billing_db_host')
DB_PORT = int(os.getenv('billing_db_port'))

app = FastAPI()
templates = Jinja2Templates(directory="templates")

db_config = {
    'user': USER,
    'password': PASS,
    'db': DB_NAME,
    'host': DB_HOST,
    'port': DB_PORT,
}


class Record(BaseModel):
    id: str
    name: str
    amount: Decimal
    date: datetime.datetime = None


async def get_locations():
    query = 'SELECT id, title FROM contract_group'
    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                result = await cur.fetchall()
                return result if result else None


async def get_payment_types():
    query = 'SELECT id, title FROM contract_payment_types'
    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                result = await cur.fetchall()
                return result if result else None


async def get_payments(payment_type=None, group_id=None, start_date=None, end_date=None):
    where_clauses = []
    base_query = '''SELECT 
                  c.title,
                  c.comment AS customer,
                  cp.summa,
                  cp.lm 
                FROM 
                  contract_payment cp
                JOIN 
                  contract c ON c.id = cp.cid
                {where}
                ORDER BY 
                  cp.lm DESC;'''

    if payment_type is not None:
        where_clauses.append(f"cp.pt = {payment_type}")
    if group_id is not None:
        where_clauses.append(f"c.gr = {group_id}")
    if start_date is not None:
        where_clauses.append(f"cp.lm >= '{start_date}'")
    if end_date is not None:
        where_clauses.append(f"cp.lm <= '{end_date}'")

    if where_clauses:
        where_block = "WHERE " + " AND ".join(where_clauses)
    else:
        where_block = ''

    query = base_query.format(where=where_block)

    async with aiomysql.create_pool(**db_config) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                result = await cur.fetchall()
                return [Record(id=res[0], name=res[1], amount=res[2], date=res[3]) for res in result]


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    locations = await get_locations()
    payment_types = await get_payment_types()
    return templates.TemplateResponse("index.html",
                                      {"request": request, "locations": locations, "payment_types": payment_types})


@app.get("/records/", response_model=List[Record])
async def read_records(location_id: int, payment_type_id: int, start_date: str = None, end_date: str = None):
    records = await get_payments(payment_type_id, location_id, start_date, end_date)
    return records
