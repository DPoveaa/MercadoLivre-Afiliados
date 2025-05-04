const axios = require('axios');
const QRCode = require('qrcode');
const FormData = require('form-data');

async function sendQRToTelegram(qr, botToken, chatId) {
    if (!botToken || !chatId) {
        console.log("Erro: Token ou Chat ID do Telegram não informado");
        return;
    }

    try {
        // Gera o QR code como imagem em memória (buffer)
        const qrBuffer = await QRCode.toBuffer(qr);

        // Cria o form data com a imagem
        const form = new FormData();
        form.append('chat_id', chatId);
        form.append('caption', 'QR Code para autenticação do WhatsApp:');
        form.append('photo', qrBuffer, {
            filename: 'qrcode.png',
            contentType: 'image/png',
        });

        // Envia para o Telegram
        await axios.post(`https://api.telegram.org/bot${botToken}/sendPhoto`, form, {
            headers: form.getHeaders(),
        });

        console.log("QR Code enviado com sucesso!");
    } catch (error) {
        console.error("Erro ao enviar QR para Telegram:", error.message);
    }
}

module.exports = { sendQRToTelegram };
