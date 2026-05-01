import os
import mercadopago


class PixPayment:
    def __init__(self):
        self.sdk = mercadopago.SDK(os.environ["MERCADOPAGO_ACCESS_TOKEN"])

    def create(self, amount: float, description: str) -> dict:
        payment_data = {
            "transaction_amount": amount,
            "description": description,
            "payment_method_id": "pix",
            "payer": {"email": ""},
        }
        return self.sdk.payment().create(payment_data)
