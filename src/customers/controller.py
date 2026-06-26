import uuid
from datetime import timedelta, datetime, timezone
from os import access

from click import DateTime
from fastapi import HTTPException, Request
from src.utils.helper import Helper
from src.customers.dtos import CustomerSchema, CustomerRegisterSchema, CustomerLoginSchema
from src.customers.models import CustomerModel, CustomerRegistrationModel, RefreshTokenModel
from sqlalchemy.orm import Session
import jwt
from src.utils.settings import settings

class CustomerController:

    def create_customer(self, body: CustomerSchema, db: Session):
        customer = CustomerModel(
            name=body.name, email=body.email, gender=body.gender,
            address=body.address, mobile=body.mobile, pincode=body.pincode,
            is_active=body.is_active
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        print(body.model_dump())
        return customer


    def get_all_customers(self, db: Session):
        all_customers = db.query(CustomerModel).all()
        return all_customers


    def get_customer_by_id(self, customer_id: str, db: Session):
        a_customer = db.query(CustomerModel).get(customer_id).first()
        if not a_customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return a_customer


    def register_customer(self,body: CustomerRegisterSchema, db: Session):
        is_customer_exist = (db.query(CustomerModel)
        .filter(CustomerModel.mobile == body.mobile)
        .first())
        if not is_customer_exist:
            raise HTTPException(status_code=404, detail="Customer not found")
        is_number_exist =   (db.query(CustomerRegistrationModel)
        .filter(CustomerRegistrationModel.mobile == body.mobile)
        .first())
        if is_number_exist:
            raise HTTPException(status_code=400, detail="number already exist")
        hashed_password = Helper.generate_hashed_password(body.password)
        body.password = hashed_password
        customer_registration_data = CustomerRegistrationModel(mobile=body.mobile, password=hashed_password)
        db.add(customer_registration_data)
        db.commit()
        db.refresh(customer_registration_data)
        return customer_registration_data

    async def customer_login_internal(
            self,
            body: CustomerLoginSchema,
            db: Session
    ):

        is_customer_exist = (
            db.query(CustomerModel)
            .filter(CustomerModel.mobile == body.mobile)
            .first()
        )

        if not is_customer_exist:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        is_number_exist = (
            db.query(CustomerRegistrationModel)
            .filter(CustomerRegistrationModel.mobile == body.mobile)
            .first()
        )

        if not is_number_exist:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized"
            )

        if not Helper.verify_password(
                body.password,
                is_number_exist.password
        ):
            raise HTTPException(
                status_code=401,
                detail="Wrong password"
            )

        exp_time = datetime.now(
            timezone.utc
        ) + timedelta(
            minutes=settings.EXP_TIME
        )

        access_token = jwt.encode(
            {
                "customer_id": is_customer_exist.id,
                "mobile": is_number_exist.mobile,
                "exp": exp_time
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        refresh_token = str(uuid.uuid4())

        return {
            "customer_id": is_customer_exist.id,
            "mobile": is_number_exist.mobile,
            "access_token": access_token,
            "refresh_token": refresh_token
        }


    async def customer_login(self, body: CustomerLoginSchema, db: Session, request: Request):

        await Helper.check_rate_limit(
            request=request,
            mobile=body.mobile
        )

        try:

            response = await self.customer_login_internal(
                body=body,
                db=db
            )

            await Helper.clear_login_attempt(
                request=request,
                mobile=body.mobile
            )

            return response

        except Exception:

            await Helper.increment_login_attempt(
                request=request,
                mobile=body.mobile
            )

            raise

    @staticmethod
    def is_authenticated(request: Request):
        auth_header = request.headers.get("Authorization")
        customer_id = request.headers.get("customer_id")

        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing token")

        if not customer_id:
            raise HTTPException(
                status_code=401,
                detail="Missing customer_id header"
            )

        try:
            token = auth_header.split(" ")[1]

            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            token_customer_id = str(payload.get("customer_id"))

            if token_customer_id != str(customer_id):
                raise HTTPException(
                    status_code=403,
                    detail="Customer ID and token mismatch"
                )

            return {
                "message": "Authenticated",
                "customer_id": token_customer_id,
                "mobile": payload.get("mobile")
            }

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")

        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
