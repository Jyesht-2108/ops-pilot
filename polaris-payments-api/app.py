from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Polaris Payments API")


class PaymentRequest(BaseModel):
    amount: float


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/payments")
def create_payment(payment: PaymentRequest):
    # INTENTIONAL BUG FOR TES-5:
    # Zero amount should return 400, but currently returns 502.
    if payment.amount == 0:
        raise HTTPException(
            status_code=502,
            detail="Payment gateway error"
        )

    if payment.amount < 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    return {
        "status": "success",
        "amount": payment.amount
    }