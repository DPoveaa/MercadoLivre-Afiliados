const { Client, LocalAuth } = require('whatsapp-web.js');
const { sendQRToTelegram} = require('../Telegram/tl_auth');
const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });
const { sendTelegramMessage } = require('../Telegram/tl_enviar');

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

console.log(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './auth_data' }),
    puppeteer: {
        headless: false,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('qr', async (qr) => {
    console.log('[QR EVENT] Novo QR recebido');
    await sendQRToTelegram(qr, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    // Agendar lembrete após 1 minuto
    setTimeout(() => {
        sendTelegramMessage('⚠️ Lembrete: O QR Code ainda não foi escaneado.', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    }, 60000); // 60 segundos
});

client.on('authenticated', async () => {
    console.log('[AUTHENTICATED] Autenticado com sucesso!');
    await sendTelegramMessage('✅ WhatsApp autenticado com sucesso!', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    process.exit(0); // Fecha o script após autenticar
});

client.on('auth_failure', async (msg) => {
    console.error('[AUTH FAILURE]', msg);
    await sendTelegramMessage(`❌ Falha na autenticação do WhatsApp:\n\n${msg}`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    process.exit(1);
});

client.on('disconnected', async (reason) => {
    console.log('[DISCONNECTED]', reason);
    await sendTelegramMessage(`🔴 Bot do WhatsApp foi desconectado. Motivo: *${reason}*`, null,TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    console.log('Tentando reinicializar...');
    client.destroy().then(() => client.initialize());
});

client.initialize();
