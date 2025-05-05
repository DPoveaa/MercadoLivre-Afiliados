const { Client, LocalAuth } = require('whatsapp-web.js');
const { sendQRToTelegram } = require('../Telegram/tl_auth');
const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });
const { sendTelegramMessage } = require('../Telegram/tl_enviar');

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

let qrFoiEscaneadoRecentemente = false;

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './auth_data' }),
    puppeteer: {
        headless: false,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
          ],
    }
});

client.on('ready', async () => {
    console.log('[READY] Cliente WhatsApp está pronto.');

    // Se não teve QR recente, significa que já estava autenticado
    if (!qrFoiEscaneadoRecentemente) {
        await sendTelegramMessage('✅ WhatsApp já estava autenticado e está pronto.', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    }

    process.exit(0);
});


client.on('qr', async (qr) => {
    console.log('[QR EVENT] Novo QR recebido');
    qrFoiEscaneadoRecentemente = true;
    await sendQRToTelegram(qr, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);

    // Lembrete se não escanear
    setTimeout(() => {
        if (qrFoiEscaneadoRecentemente) {
            sendTelegramMessage('⚠️ Lembrete: O QR Code ainda não foi escaneado.', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        }
    }, 60000);
});

client.on('authenticated', async () => {
    console.log('[AUTHENTICATED] Autenticado com sucesso!');
    if (qrFoiEscaneadoRecentemente) {
        await sendTelegramMessage('✅ WhatsApp autenticado com sucesso!', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        qrFoiEscaneadoRecentemente = false; // reseta a flag
    }
    process.exit(0);
});

client.on('auth_failure', async (msg) => {
    console.error('[AUTH FAILURE]', msg);
    await sendTelegramMessage(`❌ Falha na autenticação do WhatsApp:\n\n${msg}`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    process.exit(1);
});

client.on('disconnected', async (reason) => {
    console.log('[DISCONNECTED]', reason);
    await sendTelegramMessage(`🔴 Bot do WhatsApp foi desconectado. Motivo: *${reason}*`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    console.log('Tentando reinicializar...');
    client.destroy().then(() => client.initialize());
});

client.initialize();
