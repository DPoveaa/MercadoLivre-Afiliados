// tl_enviar.js

const axios = require('axios');
const fs = require('fs');
const path = require('path');

/**
 * Função de log com timestamp.
 */
function log(message) {
    const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19);
    console.log(`[${timestamp}] ${message}`);
}

/**
 * Envia uma mensagem para o Telegram com ou sem imagem (via URL).
 * @param {string} message - Texto da mensagem.
 * @param {string|null} imageUrl - URL da imagem (opcional).
 * @param {string} botToken - Token do bot do Telegram.
 * @param {string} chatId - ID do chat do Telegram.
 */
async function sendTelegramMessage(message, imageUrl = null, botToken, chatId) {
    if (!botToken || !chatId) {
        log("Erro: Token ou Chat ID do Telegram não informado");
        return false;
    }

    try {
        if (imageUrl) {
            // Busca a imagem da URL como buffer
            const imageResponse = await axios.get(imageUrl, { responseType: 'arraybuffer' });

            const formData = new FormData();
            formData.append('chat_id', chatId);
            formData.append('caption', message);
            formData.append('parse_mode', 'Markdown');
            formData.append('photo', Buffer.from(imageResponse.data), {
                filename: 'image.jpg',
                contentType: 'image/jpeg',
            });

            const photoRes = await axios.post(`https://api.telegram.org/bot${botToken}/sendPhoto`, formData, {
                headers: formData.getHeaders()
            });

            return photoRes.status === 200;
        }

        // Apenas mensagem de texto
        const textRes = await axios.post(`https://api.telegram.org/bot${botToken}/sendMessage`, {
            chat_id: chatId,
            text: message,
            parse_mode: 'Markdown'
        });

        return textRes.status === 200;
    } catch (err) {
        log(`Erro ao enviar para Telegram: ${err.message}`);
        return false;
    }
}

module.exports = {
    sendTelegramMessage,
    log
};
