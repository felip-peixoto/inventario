require('dotenv').config();
const crypto = require('node:crypto');
const express = require('express');

// Step 1: Import the parts of the module you want to use
//import { MercadoPagoConfig, Order } from "mercadopago";
const { MercadoPagoConfig, Payment} = require('mercadopago');

const app = express();
app.use(express.json());

const client = new MercadoPagoConfig({
	accessToken: process.env.ACCESS_TOKEN,
	options: { timeout: 5000 },
});


const payment = new Payment(client);

app.post('/criar-pix', async (req, res) => {
  try {
    const { valor, descricao } = req.body;
 
    const resposta = await payment.create({
      body: {
        transaction_amount: Number(valor),
        description: descricao || 'Cobrança PIX',
        payment_method_id: 'pix',
        payer: { email: 'pagador@email.com' },
      },
      requestOptions: { idempotencyKey: crypto.randomUUID() },
    });

    const dados = resposta.point_of_interaction.transaction_data;
 
    res.json({
      id: resposta.id,
      status: resposta.status,
      copiaECola: dados.qr_code,
      qrCodeBase64: dados.qr_code_base64,
    });
    
  } catch (erro) {
    console.error(erro);
    res.status(400).json({ erro: erro.message });
  }
});

app.listen(3000, () => {
  console.log('Servidor rodando na porta 3000');
});