const axios = require('axios');
const QRCode = require('qrcode');
const FormData = require('form-data');

async function sendQRToTelegram(qr, botToken, chatId) {
    if (!botToken || !chatId) {
        console.error("❌ Erro: Token ou Chat ID do Telegram não informado");
        console.error(`Token: ${botToken ? 'Presente' : 'Ausente'}`);
        console.error(`Chat ID: ${chatId ? 'Presente' : 'Ausente'}`);
        return;
    }

    try {
        console.log("🔄 Gerando QR code como imagem...");
        // Gera o QR code como imagem em memória (buffer)
        const qrBuffer = await QRCode.toBuffer(qr);
        console.log("✅ QR code gerado com sucesso");

        // Cria o form data com a imagem
        const form = new FormData();
        form.append('chat_id', chatId);
        form.append('caption', '🔐 *QR Code para autenticação do WhatsApp*\n\nEscaneie este QR code com seu WhatsApp para autenticar o bot.');
        form.append('photo', qrBuffer, {
            filename: 'qrcode.png',
            contentType: 'image/png',
        });

        console.log("🔄 Enviando QR code para o Telegram...");
        // Envia para o Telegram
        const response = await axios.post(`https://api.telegram.org/bot${botToken}/sendPhoto`, form, {
            headers: form.getHeaders(),
        });

        if (response.data && response.data.ok) {
            console.log("✅ QR Code enviado com sucesso para o Telegram!");
        } else {
            console.error("❌ Erro na resposta do Telegram:", response.data);
        }
    } catch (error) {
        console.error("❌ Erro ao enviar QR para Telegram:");
        if (error.response) {
            console.error(`Status: ${error.response.status}`);
            console.error(`Dados: ${JSON.stringify(error.response.data)}`);
        } else if (error.request) {
            console.error("Sem resposta do servidor");
        } else {
            console.error(`Mensagem: ${error.message}`);
        }
        throw error; // Propaga o erro para ser tratado pelo chamador
    }
}

module.exports = { sendQRToTelegram };
